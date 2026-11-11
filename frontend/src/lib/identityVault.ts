/** Browser-only authenticated encryption. No network, localStorage, or plaintext fallback. */
import { validIdentity } from './identity'
import type { VehicleIdentity } from './vehicleIdentity'

const DATABASE = 'gaswise-private-v1'
const STORE = 'vault'
const SLOT = 'vehicle'
const MAX_AGE = 30 * 24 * 60 * 60 * 1000
const aad = (expires: number) => new TextEncoder().encode(`GasWise:vehicle-identity:v1:${expires}`)
type VaultRecord = { key: CryptoKey; iv: Uint8Array<ArrayBuffer>; ciphertext: ArrayBuffer; expires: number }
let queue: Promise<unknown> = Promise.resolve()

interface VaultPayload {
  version: 2
  active: VehicleIdentity | null
  vehicles: Record<number, VehicleIdentity>
}

let cachedDb: IDBDatabase | null = null
let cachedFactory: IDBFactory | null = null

function open(): Promise<IDBDatabase> {
  if (cachedDb && cachedFactory === indexedDB) {
    return Promise.resolve(cachedDb)
  }
  return new Promise((resolve, reject) => {
    const factory = indexedDB
    const request = factory.open(DATABASE, 1)
    request.onupgradeneeded = () => request.result.createObjectStore(STORE)
    request.onsuccess = () => {
      const db = request.result
      cachedDb = db
      cachedFactory = factory
      db.onversionchange = () => {
        db.close()
        if (cachedDb === db) cachedDb = null
      }
      db.onclose = () => {
        if (cachedDb === db) cachedDb = null
      }
      resolve(db)
    }
    request.onerror = () => reject(new Error('private_storage_unavailable'))
    request.onblocked = () => reject(new Error('private_storage_unavailable'))
  })
}

async function read(): Promise<VaultRecord | undefined> {
  const db = await open()
  return await new Promise((resolve, reject) => {
    try {
      const tx = db.transaction(STORE, 'readonly')
      const request = tx.objectStore(STORE).get(SLOT)
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => {
        cachedDb = null
        reject(new Error('private_storage_unavailable'))
      }
    } catch {
      cachedDb = null
      reject(new Error('private_storage_unavailable'))
    }
  })
}

async function write(record: VaultRecord | null) {
  const db = await open()
  await new Promise<void>((resolve, reject) => {
    try {
      const tx = db.transaction(STORE, 'readwrite')
      const store = tx.objectStore(STORE)
      if (record) store.put(record, SLOT)
      else store.delete(SLOT)
      tx.oncomplete = () => resolve()
      tx.onerror = tx.onabort = () => {
        cachedDb = null
        reject(new Error('private_storage_unavailable'))
      }
    } catch {
      cachedDb = null
      reject(new Error('private_storage_unavailable'))
    }
  })
}

export function supportsIdentityVault() {
  return typeof indexedDB !== 'undefined' && !!globalThis.crypto?.subtle
}

async function decryptVaultPayload(record: VaultRecord): Promise<VaultPayload | null> {
  if (!Number.isFinite(record.expires) || record.key.extractable || record.key.algorithm.name !== 'AES-GCM') {
    throw new Error('invalid_record')
  }
  const plaintext = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: record.iv, additionalData: aad(record.expires) },
    record.key,
    record.ciphertext,
  )
  const parsed = JSON.parse(new TextDecoder().decode(plaintext))
  if (!parsed || typeof parsed !== 'object') throw new Error('invalid_identity')

  // Backward compatibility: If the decrypted payload is a single legacy VehicleIdentity
  if ('kind' in parsed && (parsed.kind === 'vin' || parsed.kind === 'plate')) {
    const legacy = parsed as VehicleIdentity
    if (!validIdentity(legacy)) throw new Error('invalid_identity')
    const vehicleId = (legacy.value as { vehicle_id?: number }).vehicle_id
    const vehicles: Record<number, VehicleIdentity> = {}
    if (typeof vehicleId === 'number') {
      vehicles[vehicleId] = legacy
    }
    return { version: 2, active: legacy, vehicles }
  }

  // Modern VaultPayload format
  const active = parsed.active && validIdentity(parsed.active) ? (parsed.active as VehicleIdentity) : null
  const rawVehicles = parsed.vehicles && typeof parsed.vehicles === 'object' ? parsed.vehicles : {}
  const vehicles: Record<number, VehicleIdentity> = {}
  for (const [key, val] of Object.entries(rawVehicles)) {
    const numKey = Number(key)
    if (Number.isFinite(numKey) && val && validIdentity(val as VehicleIdentity)) {
      vehicles[numKey] = val as VehicleIdentity
    }
  }

  return { version: 2, active, vehicles }
}

async function encryptAndSave(payload: VaultPayload | null): Promise<void> {
  const hasVehicles = payload && Object.keys(payload.vehicles).length > 0
  const hasActive = payload && payload.active !== null

  if (!payload || (!hasVehicles && !hasActive)) {
    await write(null)
    return
  }

  const previous = await read()
  const oldKey = previous?.key
  const key =
    oldKey?.type === 'secret' && !oldKey.extractable && oldKey.algorithm.name === 'AES-GCM'
      ? oldKey
      : await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt'])
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const expires = Date.now() + MAX_AGE

  // If there's only an active identity and no vehicles map, save in legacy format for maximum backward compatibility
  const toSerialize =
    !hasVehicles && hasActive
      ? payload.active
      : payload

  const ciphertext = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv, additionalData: aad(expires) },
    key,
    new TextEncoder().encode(JSON.stringify(toSerialize)),
  )
  await write({ key, iv, ciphertext, expires })
}

/**
 * Loads the active vehicle identity, or the identity for a specific vehicleId.
 */
export async function loadIdentity(vehicleId?: number | null): Promise<VehicleIdentity | null> {
  if (!supportsIdentityVault()) return null
  const record = await read()
  if (!record) return null
  if (record.expires <= Date.now()) {
    await write(null)
    return null
  }
  try {
    const vault = await decryptVaultPayload(record)
    if (!vault) return null
    if (typeof vehicleId === 'number') {
      const match = vault.vehicles[vehicleId]
      if (match) return match
      const activeVehicleId = (vault.active?.value as { vehicle_id?: number })?.vehicle_id
      if (activeVehicleId === vehicleId) return vault.active
      return null
    }
    return vault.active
  } catch {
    await write(null)
    return null
  }
}

/**
 * Loads all stored vehicle identities mapped by vehicleId.
 */
export async function loadAllIdentities(): Promise<Record<number, VehicleIdentity>> {
  if (!supportsIdentityVault()) return {}
  const record = await read()
  if (!record) return {}
  if (record.expires <= Date.now()) {
    await write(null)
    return {}
  }
  try {
    const vault = await decryptVaultPayload(record)
    return vault?.vehicles ?? {}
  } catch {
    await write(null)
    return {}
  }
}

/**
 * Saves or clears the identity for a specific vehicle or default/active.
 */
export function saveIdentity(identity: VehicleIdentity | null, vehicleId?: number | null): Promise<void> {
  const operation = queue.catch(() => {}).then(async () => {
    if (!supportsIdentityVault()) throw new Error('private_storage_unavailable')
    if (identity && !validIdentity(identity)) throw new Error('invalid_identity')

    const previous = await read()
    let currentVault: VaultPayload = { version: 2, active: null, vehicles: {} }
    if (previous && previous.expires > Date.now()) {
      try {
        const decrypted = await decryptVaultPayload(previous)
        if (decrypted) currentVault = decrypted
      } catch {
        // Start fresh if corrupted
      }
    }

    if (typeof vehicleId === 'number') {
      if (identity) {
        currentVault.vehicles[vehicleId] = identity
      } else {
        delete currentVault.vehicles[vehicleId]
      }
      // If the active identity was this vehicle, update active as well
      const activeVehicleId = (currentVault.active?.value as { vehicle_id?: number })?.vehicle_id
      if (activeVehicleId === vehicleId || currentVault.active === null) {
        currentVault.active = identity
      }
    } else {
      currentVault.active = identity
      const vId = (identity?.value as { vehicle_id?: number })?.vehicle_id
      if (typeof vId === 'number') {
        if (identity) currentVault.vehicles[vId] = identity
        else delete currentVault.vehicles[vId]
      }
    }

    await encryptAndSave(currentVault)
  })
  queue = operation
  return operation
}

/**
 * Explicit helper to save or delete identity for a specific vehicleId.
 */
export function saveVehicleIdentity(vehicleId: number, identity: VehicleIdentity | null): Promise<void> {
  return saveIdentity(identity, vehicleId)
}

/**
 * Saves all vehicle identities in a single encrypted batch.
 */
export function saveAllIdentities(
  vehicles: Record<number, VehicleIdentity>,
  activeIdentity?: VehicleIdentity | null,
): Promise<void> {
  const operation = queue.catch(() => {}).then(async () => {
    if (!supportsIdentityVault()) throw new Error('private_storage_unavailable')
    for (const id of Object.values(vehicles) as VehicleIdentity[]) {
      if (!validIdentity(id)) throw new Error('invalid_identity')
    }
    if (activeIdentity && !validIdentity(activeIdentity)) throw new Error('invalid_identity')

    const firstVehicle = (Object.values(vehicles)[0] as VehicleIdentity | undefined) ?? null
    const payload: VaultPayload = {
      version: 2,
      active: activeIdentity ?? firstVehicle,
      vehicles,
    }
    await encryptAndSave(payload)
  })
  queue = operation
  return operation
}
