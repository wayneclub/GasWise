import type { SmartResult } from '../api/types'
import type { Origin } from './session'

const KEY = 'gaswise.fuel-session.v1'
const MAX_AGE = 30 * 60 * 1000

export interface SavedFuelSession {
  result: SmartResult
  origin: Origin
  originKind: 'device' | 'manual'
  originLabel: string | null
  searchKey: string
  rankKey: string
  checkedAt: number
}

export function clearFuelSession() {
  try { sessionStorage.removeItem(KEY) } catch { /* Storage may be blocked. */ }
}

/** Per-tab recovery only. Never copy locations or signed snapshots to localStorage. */
export function loadFuelSession(searchKey?: string, rankKey?: string): SavedFuelSession | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return null
    const saved = JSON.parse(raw) as SavedFuelSession
    const elapsed = Date.now() - saved.checkedAt
    if ((searchKey !== undefined && saved.searchKey !== searchKey) ||
        (rankKey !== undefined && saved.rankKey !== rankKey) ||
        !Number.isFinite(saved.checkedAt) || elapsed < 0 || elapsed > MAX_AGE ||
        !Number.isFinite(saved.origin?.lat) || Math.abs(saved.origin.lat) > 90 ||
        !Number.isFinite(saved.origin?.lng) || Math.abs(saved.origin.lng) > 180 ||
        !['device', 'manual'].includes(saved.originKind) ||
        !(saved.originLabel === null || typeof saved.originLabel === 'string') ||
        typeof saved.result?.signature !== 'string' ||
        !Number.isFinite(Date.parse(saved.result?.snapshot?.expires_at)) ||
        !saved.result.snapshot.query || !Array.isArray(saved.result.snapshot.stations) ||
        !Array.isArray(saved.result.snapshot.source_statuses) ||
        (saved.result.ranking != null && !Array.isArray(saved.result.ranking.results))) {
      clearFuelSession()
      return null
    }
    return saved
  } catch {
    clearFuelSession()
    return null
  }
}

export function saveFuelSession(saved: SavedFuelSession) {
  try { sessionStorage.setItem(KEY, JSON.stringify(saved)) } catch { /* Continue in memory if storage is full or blocked. */ }
}
