import type { Origin } from './session'
import type { Station } from '../api/types'
import { alertCredential, alertWatchKey, isAlertWatched, updateAlertWatch } from './smartAlerts'

const DATABASE = 'gaswise-lifezones-v1'
const STORE = 'zones'

export interface LifeZone {
  id: string
  kind: 'home' | 'work' | 'custom'
  name: string
  query: string
  origin: Origin
  radiusMiles: number
  lastObservedPrice?: number
  updatedAt: string
}

export interface ArbitrageOpportunity {
  fromZone: LifeZone
  toZone: LifeZone
  priceDiff: number // $/gal (e.g. 0.45)
  detourMiles: number
  grossSavings: number
  detourCost: number
  netSavings: number
  isBeneficial: boolean
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1)
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE)) {
        request.result.createObjectStore(STORE, { keyPath: 'id' })
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = request.onblocked = () => reject(new Error('lifezones_storage_unavailable'))
  })
}

async function transact<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDB()
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode)
      const store = tx.objectStore(STORE)
      const req = run(store)
      req.onsuccess = () => resolve(req.result)
      req.onerror = tx.onerror = tx.onabort = () => reject(new Error('lifezones_storage_unavailable'))
    })
  } finally {
    db.close()
  }
}

export async function loadLifeZones(): Promise<LifeZone[]> {
  try {
    const list = await transact<LifeZone[]>('readonly', store => store.getAll())
    return (list ?? []).sort((a, b) => {
      const order = { home: 0, work: 1, custom: 2 }
      return (order[a.kind] ?? 2) - (order[b.kind] ?? 2)
    })
  } catch {
    return []
  }
}

export async function saveLifeZone(zone: LifeZone): Promise<void> {
  await transact('readwrite', store => store.put({ ...zone, updatedAt: new Date().toISOString() }))
}

export async function deleteLifeZone(id: string): Promise<void> {
  await transact('readwrite', store => store.delete(id))
}

export async function clearLifeZones(): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const req = indexedDB.deleteDatabase(DATABASE)
    req.onsuccess = () => resolve()
    req.onerror = req.onblocked = () => reject(new Error('lifezones_storage_unavailable'))
  })
}

export async function replaceLifeZones(zones: LifeZone[]): Promise<void> {
  await clearLifeZones()
  for (const zone of zones.slice(0, 3)) {
    await saveLifeZone(zone)
  }
}

/**
 * Approximate distance between two coordinates in miles using Haversine formula.
 */
export function estimateDistanceMiles(a: Origin, b: Origin): number {
  const R = 3958.8 // Earth radius in miles
  const dLat = (b.lat - a.lat) * (Math.PI / 180)
  const dLng = (b.lng - a.lng) * (Math.PI / 180)
  const sinDLat = Math.sin(dLat / 2)
  const sinDLng = Math.sin(dLng / 2)
  const sq = sinDLat * sinDLat +
    Math.cos(a.lat * (Math.PI / 180)) * Math.cos(b.lat * (Math.PI / 180)) * sinDLng * sinDLng
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(sq)))
}

/**
 * Calculates whether refueling at a neighboring Life Zone (e.g. Work 90007 vs Home 90015)
 * provides a positive net savings after factoring in the detour driving cost.
 */
export function calculateArbitrage(
  fromZone: LifeZone,
  toZone: LifeZone,
  gallons: number,
  mpg: number,
  overrideDetourMiles?: number
): ArbitrageOpportunity | null {
  if (!fromZone.lastObservedPrice || !toZone.lastObservedPrice) return null
  const priceDiff = fromZone.lastObservedPrice - toZone.lastObservedPrice
  if (priceDiff <= 0) return null

  const detourMiles = overrideDetourMiles ?? Math.round(estimateDistanceMiles(fromZone.origin, toZone.origin) * 10) / 10
  const effectiveMpg = mpg > 0 ? mpg : 25
  const grossSavings = Math.round(priceDiff * gallons * 100) / 100
  const detourCost = Math.round(((detourMiles / effectiveMpg) * toZone.lastObservedPrice) * 100) / 100
  const netSavings = Math.round((grossSavings - detourCost) * 100) / 100

  return {
    fromZone,
    toZone,
    priceDiff: Math.round(priceDiff * 100) / 100,
    detourMiles,
    grossSavings,
    detourCost,
    netSavings,
    isBeneficial: netSavings >= 1.0,
  }
}

/**
 * Synchronizes aggregated watches for the life zones without transmitting any personal labels.
 * Only anonymous station IDs and fuel conditions are monitored on the server.
 */
export async function syncAggregatedLifeZoneWatches(
  stations: Station[],
  fuelType: Station['fuel_type'] = 'regular'
): Promise<number> {
  const creds = await alertCredential()
  if (!creds) return 0

  let watchedCount = 0
  const candidates = stations.slice(0, 5)
  for (const station of candidates) {
    if (!station.id || !station.source) continue
    const watch = {
      enabled: true,
      canonical_id: station.canonical_id ?? null,
      source: station.source,
      station_id: station.id,
      station_name: station.name ?? station.id,
      fuel_type: station.fuel_type ?? fuelType,
      payment_type: station.payment_type ?? ('unknown' as const),
      membership_required: station.membership_required ?? null,
      octane: station.octane ?? null,
      currency: 'USD' as const,
      unit: 'US_gallon' as const,
      expected_gallons: 10,
      threshold_cents: 10,
    }
    const key = alertWatchKey(watch)
    const already = await isAlertWatched(key)
    if (!already) {
      try {
        await updateAlertWatch(watch)
        watchedCount++
      } catch {}
    }
  }
  return watchedCount
}
