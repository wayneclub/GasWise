import { api } from '../api/client'
import { alertCredential } from './smartAlerts'

const DATABASE = 'gaswise-fuel-assistant-v1'
const EVENTS = 'refuels'
const SETTINGS = 'settings'
const SETTINGS_SLOT = 'current'

export interface FuelAssistantSettings { weeklyMiles: number; typicalGallons: number }
export interface RefuelEvent {
  id: string
  at: string
  stationId?: string
  stationName?: string
  stationAddress?: string
  pricePerGallon?: number
  fuelType?: string
  gallons?: number
  cost?: number
  notes?: string
}
export interface NeedEstimate {
  state: 'not_due' | 'approaching' | 'due' | 'unknown'
  confidence: 'high' | 'medium' | 'low'
  earliestDays: number | null
  latestDays: number | null
  basis: 'insufficient_data' | 'epa_vehicle' | 'manual_mpg' | 'refuel_cadence'
  observations: number
}

export interface RefuelToastEvent { stationName: string }
const REFUEL_TOAST_EVENT = 'gaswise:refuel-recorded'

export function notifyRefuelRecorded(stationName: string): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(REFUEL_TOAST_EVENT, { detail: { stationName } }))
  }
}

export function onRefuelRecorded(callback: (detail: RefuelToastEvent) => void): () => void {
  if (typeof window === 'undefined') return () => {}
  const handler = (event: Event) => {
    const custom = event as CustomEvent<RefuelToastEvent>
    if (custom.detail) callback(custom.detail)
  }
  window.addEventListener(REFUEL_TOAST_EVENT, handler)
  return () => window.removeEventListener(REFUEL_TOAST_EVENT, handler)
}

export const DEFAULT_FUEL_ASSISTANT_SETTINGS: FuelAssistantSettings = { weeklyMiles: 200, typicalGallons: 10 }

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      return reject(new Error('fuel_assistant_storage_unavailable'))
    }
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
    events: events.filter(event => Number.isFinite(Date.parse(event.at))).sort((a, b) => Date.parse(b.at) - Date.parse(a.at)).slice(0, 100) }
}

export async function saveFuelAssistantSettings(settings: FuelAssistantSettings): Promise<void> {
  const value = { weeklyMiles: Math.min(2000, Math.max(10, Math.round(settings.weeklyMiles))),
    typicalGallons: Math.min(30, Math.max(1, Math.round(settings.typicalGallons))) }
  await transact(SETTINGS, 'readwrite', tx => tx.objectStore(SETTINGS).put(value, SETTINGS_SLOT))
}

export async function recordRefuel(
  at: Date | string = new Date(),
  details?: Partial<Omit<RefuelEvent, 'id' | 'at'>>
): Promise<RefuelEvent> {
  const atIso = typeof at === 'string' ? at : at.toISOString()
  const event: RefuelEvent = {
    id: crypto.randomUUID(),
    at: atIso,
    ...details,
  }
  await transact(EVENTS, 'readwrite', tx => tx.objectStore(EVENTS).put(event))
  return event
}

export async function updateRefuel(
  id: string,
  updates: Partial<Omit<RefuelEvent, 'id'>>
): Promise<RefuelEvent | null> {
  const existing = await transact<RefuelEvent | undefined>(EVENTS, 'readonly', tx => tx.objectStore(EVENTS).get(id))
  if (!existing) return null
  const updated: RefuelEvent = {
    ...existing,
    ...updates,
    id,
    at: updates.at ? (typeof updates.at === 'string' ? updates.at : (updates.at as any).toISOString()) : existing.at,
  }
  await transact(EVENTS, 'readwrite', tx => tx.objectStore(EVENTS).put(updated))
  return updated
}

export async function deleteRefuel(id: string): Promise<void> {
  await transact(EVENTS, 'readwrite', tx => tx.objectStore(EVENTS).delete(id))
}

export async function recordStationRefuel(station: {
  id?: string | null
  name: string
  address?: string | null
  price_per_gallon?: string | number | null
  comparison_price_per_gallon?: string | number | null
  lastObservedPrice?: string | number | null
}, options?: {
  fuelType?: string | null
  gallons?: number | null
  note?: string | null
}): Promise<RefuelEvent> {
  const rawPrice = station.lastObservedPrice ?? station.comparison_price_per_gallon ?? station.price_per_gallon
  const numericPrice = rawPrice != null && !isNaN(Number(rawPrice)) ? Number(rawPrice) : undefined
  const gallons = options?.gallons != null ? Number(options.gallons) : undefined
  const cost = numericPrice != null && gallons != null ? Number((numericPrice * gallons).toFixed(2)) : undefined

  try {
    const now = new Date()
    const { events } = await loadFuelAssistant()
    const recent = events.find(e => {
      const diffMs = now.getTime() - Date.parse(e.at)
      return diffMs >= 0 && diffMs < 3 * 60 * 1000 && (e.stationName === station.name || (station.id && e.stationId === station.id))
    })

    if (recent) {
      const updated = await updateRefuel(recent.id, {
        at: now.toISOString(),
        stationId: (station.id ?? recent.stationId) ?? undefined,
        stationName: station.name ?? recent.stationName,
        stationAddress: (station.address ?? recent.stationAddress) ?? undefined,
        pricePerGallon: numericPrice ?? recent.pricePerGallon,
        fuelType: (options?.fuelType ?? recent.fuelType) ?? undefined,
        gallons: gallons ?? recent.gallons,
        cost: cost ?? recent.cost,
      })
      if (updated) {
        notifyRefuelRecorded(station.name)
        return updated
      }
    }

    const event = await recordRefuel(now, {
      stationId: station.id ?? undefined,
      stationName: station.name,
      stationAddress: station.address ?? undefined,
      pricePerGallon: numericPrice,
      fuelType: options?.fuelType ?? undefined,
      gallons,
      cost,
      notes: options?.note ?? undefined,
    })
    notifyRefuelRecorded(station.name)
    return event
  } catch {
    notifyRefuelRecorded(station.name)
    return {
      id: crypto.randomUUID(),
      at: new Date().toISOString(),
      stationName: station.name,
      stationAddress: station.address ?? undefined,
      pricePerGallon: numericPrice,
      fuelType: options?.fuelType ?? undefined,
      gallons,
      cost,
    }
  }
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2
}

export function estimateNeed(events: RefuelEvent[], settings: FuelAssistantSettings, mpg: number,
                             now = new Date(),
                             mpgBasis: 'epa_vehicle' | 'manual_mpg' = 'manual_mpg'): NeedEstimate {
  const valid = events.map(event => Date.parse(event.at)).filter(Number.isFinite).sort((a, b) => b - a)
  const canDerive = Number.isFinite(mpg) && mpg > 0 && settings.weeklyMiles > 0 && settings.typicalGallons > 0
  const unknown = (): NeedEstimate => ({ state: 'unknown', confidence: 'low', earliestDays: null, latestDays: null,
    basis: canDerive ? mpgBasis : 'insufficient_data', observations: valid.length })
  if (!valid.length) return unknown()
  const intervals = valid.slice(0, 6).flatMap((time, index, list) => {
    if (index === list.length - 1) return []
    const days = (time - list[index + 1]) / 86_400_000
    return days >= 2 && days <= 60 ? [days] : []
  })
  if (!intervals.length && !canDerive) return unknown()
  const cycle = intervals.length ? median(intervals) : settings.typicalGallons * mpg / settings.weeklyMiles * 7
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
    basis: intervals.length ? 'refuel_cadence' : mpgBasis,
    observations: valid.length,
  }
}

export async function syncNeedEstimate(estimate: NeedEstimate): Promise<void> {
  const credential = await alertCredential()
  if (!credential) return
  await api.updateAlertNeed({ ...credential, state: estimate.state, confidence: estimate.confidence, ttl_hours: 48 })
}

export async function clearFuelAssistant(): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    if (typeof indexedDB === 'undefined') return resolve()
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
    typeof event.at === 'string' && Number.isFinite(Date.parse(event.at))).slice(0, 100)
  for (const event of events) {
    await transact(EVENTS, 'readwrite', tx => tx.objectStore(EVENTS).put(event))
  }
}
