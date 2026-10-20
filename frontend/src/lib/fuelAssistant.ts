import { api } from '../api/client'
import { alertCredential } from './smartAlerts'

const DATABASE = 'gaswise-fuel-assistant-v1'
const EVENTS = 'refuels'
const SETTINGS = 'settings'
const SETTINGS_SLOT = 'current'

export interface FuelAssistantSettings { weeklyMiles: number; typicalGallons: number }
export interface RefuelEvent { id: string; at: string }
export interface NeedEstimate {
  state: 'not_due' | 'approaching' | 'due' | 'unknown'
  confidence: 'high' | 'medium' | 'low'
  earliestDays: number | null
  latestDays: number | null
}

export const DEFAULT_FUEL_ASSISTANT_SETTINGS: FuelAssistantSettings = { weeklyMiles: 200, typicalGallons: 10 }

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1)
    request.onupgradeneeded = () => {
      request.result.createObjectStore(EVENTS, { keyPath: 'id' })
      request.result.createObjectStore(SETTINGS)
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = request.onblocked = () => reject(new Error('fuel_assistant_storage_unavailable'))
  })
}

async function transact<T>(stores: string | string[], mode: IDBTransactionMode,
                            run: (tx: IDBTransaction) => IDBRequest<T>): Promise<T> {
  const db = await open()
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(stores, mode)
      const request = run(tx)
      request.onsuccess = () => resolve(request.result)
      request.onerror = tx.onerror = tx.onabort = () => reject(new Error('fuel_assistant_storage_unavailable'))
    })
  } finally { db.close() }
}

export async function loadFuelAssistant(): Promise<{ settings: FuelAssistantSettings; events: RefuelEvent[] }> {
  const settings = await transact<FuelAssistantSettings | undefined>(SETTINGS, 'readonly', tx => tx.objectStore(SETTINGS).get(SETTINGS_SLOT))
  const events = await transact<RefuelEvent[]>(EVENTS, 'readonly', tx => tx.objectStore(EVENTS).getAll())
  return { settings: settings ?? DEFAULT_FUEL_ASSISTANT_SETTINGS,
    events: events.filter(event => Number.isFinite(Date.parse(event.at))).sort((a, b) => Date.parse(b.at) - Date.parse(a.at)).slice(0, 20) }
}

export async function saveFuelAssistantSettings(settings: FuelAssistantSettings): Promise<void> {
  const value = { weeklyMiles: Math.min(2000, Math.max(10, Math.round(settings.weeklyMiles))),
    typicalGallons: Math.min(30, Math.max(1, Math.round(settings.typicalGallons))) }
  await transact(SETTINGS, 'readwrite', tx => tx.objectStore(SETTINGS).put(value, SETTINGS_SLOT))
}

export async function recordRefuel(at = new Date()): Promise<RefuelEvent> {
  const event = { id: crypto.randomUUID(), at: at.toISOString() }
  await transact(EVENTS, 'readwrite', tx => tx.objectStore(EVENTS).put(event))
  return event
}

export async function deleteRefuel(id: string): Promise<void> {
  await transact(EVENTS, 'readwrite', tx => tx.objectStore(EVENTS).delete(id))
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2
}

export function estimateNeed(events: RefuelEvent[], settings: FuelAssistantSettings, mpg: number,
                             now = new Date()): NeedEstimate {
  const valid = events.map(event => Date.parse(event.at)).filter(Number.isFinite).sort((a, b) => b - a)
  if (!valid.length || !Number.isFinite(mpg) || mpg <= 0) return { state: 'unknown', confidence: 'low', earliestDays: null, latestDays: null }
  const intervals = valid.slice(0, 6).flatMap((time, index, list) => {
    if (index === list.length - 1) return []
    const days = (time - list[index + 1]) / 86_400_000
    return days >= 2 && days <= 60 ? [days] : []
  })
  const derived = settings.typicalGallons * mpg / settings.weeklyMiles * 7
  const cycle = intervals.length ? median(intervals) : derived
  const confidence = intervals.length >= 3 ? 'high' : intervals.length >= 1 ? 'medium' : 'low'
  const elapsed = Math.max(0, (now.getTime() - valid[0]) / 86_400_000)
  const remaining = cycle - elapsed
  const uncertainty = cycle * (confidence === 'high' ? 0.15 : confidence === 'medium' ? 0.25 : 0.4)
  const progress = elapsed / Math.max(cycle, 1)
  return {
    state: progress >= 0.9 ? 'due' : progress >= 0.65 ? 'approaching' : 'not_due',
    confidence,
    earliestDays: Math.max(0, Math.round(remaining - uncertainty)),
    latestDays: Math.max(0, Math.round(remaining + uncertainty)),
  }
}

export async function syncNeedEstimate(estimate: NeedEstimate): Promise<void> {
  const credential = await alertCredential()
  if (!credential) return
  await api.updateAlertNeed({ ...credential, state: estimate.state, confidence: estimate.confidence, ttl_hours: 48 })
}

export async function clearFuelAssistant(): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const request = indexedDB.deleteDatabase(DATABASE)
    request.onsuccess = () => resolve()
    request.onerror = request.onblocked = () => reject(new Error('fuel_assistant_storage_unavailable'))
  })
}

export async function replaceFuelAssistant(value: { settings?: FuelAssistantSettings; events?: RefuelEvent[] } | null): Promise<void> {
  await clearFuelAssistant()
  if (!value) return
  const settings = value.settings ?? DEFAULT_FUEL_ASSISTANT_SETTINGS
  await saveFuelAssistantSettings(settings)
  const events = (value.events ?? []).filter(event => typeof event.id === 'string' && event.id.length <= 100 &&
    typeof event.at === 'string' && Number.isFinite(Date.parse(event.at))).slice(0, 20)
  for (const event of events) {
    await transact(EVENTS, 'readwrite', tx => tx.objectStore(EVENTS).put(event))
  }
}
