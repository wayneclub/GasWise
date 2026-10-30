import { validIdentity } from './identity'
import type { Prefs } from './prefs'
import { normalizePrefs } from './prefs'
import type { VehicleIdentity } from './vehicleIdentity'
import { loadFuelAssistant, type FuelAssistantSettings, type RefuelEvent } from './fuelAssistant'
import { loadLifeZones, type LifeZone } from './lifeZones'

const DATABASE = 'gaswise-profile-v1'
const STORE = 'profile'
const SLOT = 'current'
const ITERATIONS = 310_000
const encoder = new TextEncoder()
const decoder = new TextDecoder()

export interface LocalProfile {
  id: string
  createdAt: string
}

interface BackupEnvelope {
  format: 'gaswise-private-backup'
  version: 1
  kdf: { name: 'PBKDF2'; hash: 'SHA-256'; iterations: number; salt: string }
  cipher: { name: 'AES-GCM'; iv: string }
  ciphertext: string
}

interface BackupPayload {
  profile: LocalProfile
  prefs: Prefs
  identity: VehicleIdentity | null
  exportedAt: string
  assistant?: { settings: FuelAssistantSettings; events: RefuelEvent[] }
  lifeZones?: LifeZone[]
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1)
    request.onupgradeneeded = () => request.result.createObjectStore(STORE)
    request.onsuccess = () => resolve(request.result)
    request.onerror = request.onblocked = () => reject(new Error('profile_storage_unavailable'))
  })
}

async function record(value?: LocalProfile | null): Promise<LocalProfile | undefined> {
  const db = await open()
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, value === undefined ? 'readonly' : 'readwrite')
      const store = tx.objectStore(STORE)
      if (value === undefined) {
        const request = store.get(SLOT)
        request.onsuccess = () => resolve(request.result)
        request.onerror = () => reject(new Error('profile_storage_unavailable'))
      } else {
        if (value) store.put(value, SLOT); else store.delete(SLOT)
        tx.oncomplete = () => resolve(value ?? undefined)
        tx.onerror = tx.onabort = () => reject(new Error('profile_storage_unavailable'))
      }
    })
  } finally { db.close() }
}

export async function getLocalProfile(): Promise<LocalProfile> {
  const existing = await record()
  if (existing?.id && existing.createdAt) return existing
  const profile = { id: crypto.randomUUID(), createdAt: new Date().toISOString() }
  await record(profile)
  return profile
}

export async function replaceLocalProfile(profile: LocalProfile): Promise<void> {
  if (!/^[0-9a-f-]{36}$/i.test(profile.id) || !Number.isFinite(Date.parse(profile.createdAt))) throw new Error('invalid_backup')
  await record(profile)
}

export async function resetLocalProfile(): Promise<LocalProfile> {
  await record(null)
  return getLocalProfile()
}

export async function requestPersistentStorage(): Promise<boolean> {
  if (!navigator.storage?.persist) return false
  return navigator.storage.persist()
}

function base64(bytes: Uint8Array): string {
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary)
}

function bytes(value: string): Uint8Array<ArrayBuffer> {
  const binary = atob(value)
  return Uint8Array.from(binary, char => char.charCodeAt(0))
}

async function key(passphrase: string, salt: Uint8Array<ArrayBuffer>, usages: KeyUsage[]) {
  if (passphrase.length < 8) throw new Error('weak_passphrase')
  const material = await crypto.subtle.importKey('raw', encoder.encode(passphrase), 'PBKDF2', false, ['deriveKey'])
  return crypto.subtle.deriveKey({ name: 'PBKDF2', hash: 'SHA-256', salt, iterations: ITERATIONS }, material, { name: 'AES-GCM', length: 256 }, false, usages)
}

export async function exportPrivateBackup(prefs: Prefs, identity: VehicleIdentity | null, passphrase: string): Promise<string> {
  const profile = await getLocalProfile()
  const salt = crypto.getRandomValues(new Uint8Array(16))
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const assistant = await loadFuelAssistant()
  const lifeZones = await loadLifeZones()
  const payload: BackupPayload = { profile, prefs: normalizePrefs(prefs), identity, assistant, lifeZones, exportedAt: new Date().toISOString() }
  const ciphertext = await crypto.subtle.encrypt({ name: 'AES-GCM', iv, additionalData: encoder.encode('GasWise private backup v1') }, await key(passphrase, salt, ['encrypt']), encoder.encode(JSON.stringify(payload)))
  const envelope: BackupEnvelope = { format: 'gaswise-private-backup', version: 1, kdf: { name: 'PBKDF2', hash: 'SHA-256', iterations: ITERATIONS, salt: base64(salt) }, cipher: { name: 'AES-GCM', iv: base64(iv) }, ciphertext: base64(new Uint8Array(ciphertext)) }
  return JSON.stringify(envelope)
}

export async function importPrivateBackup(source: string, passphrase: string): Promise<BackupPayload> {
  let envelope: BackupEnvelope
  try { envelope = JSON.parse(source) as BackupEnvelope } catch { throw new Error('invalid_backup') }
  if (envelope.format !== 'gaswise-private-backup' || envelope.version !== 1 || envelope.kdf?.iterations !== ITERATIONS) throw new Error('invalid_backup')
  try {
    const plaintext = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: bytes(envelope.cipher.iv), additionalData: encoder.encode('GasWise private backup v1') }, await key(passphrase, bytes(envelope.kdf.salt), ['decrypt']), bytes(envelope.ciphertext))
    const payload = JSON.parse(decoder.decode(plaintext)) as BackupPayload
    if (!payload.profile || (payload.identity && !validIdentity(payload.identity))) throw new Error('invalid_backup')
    await replaceLocalProfile(payload.profile)
    return { ...payload, prefs: normalizePrefs(payload.prefs) }
  } catch (error) {
    if (error instanceof Error && error.message === 'weak_passphrase') throw error
    throw new Error('invalid_backup')
  }
}

export function shortProfileId(profile: LocalProfile): string {
  return profile.id.replaceAll('-', '').slice(0, 8).toUpperCase()
}
