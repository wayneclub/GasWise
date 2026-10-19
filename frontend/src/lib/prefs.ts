import { useCallback, useState } from 'react'
import type { FuelType } from '../api/types'
import { LOCALES, type Locale } from '../i18n'
import { loadFuelSession } from './fuelSessionStorage'

export type Preference = 'money' | 'balanced' | 'time'
export type NavApp = 'google' | 'apple' | 'waze'

export interface SavedVehicle {
  id: number
  label: string
  fuelType: FuelType
  combinedMpg: string
}

export interface Prefs {
  onboarded: boolean
  vehicle: SavedVehicle | null
  /** Used only without a vehicle; a vehicle supplies its EPA grade. */
  fuelType: FuelType
  /** Manual MPG without a vehicle. Null lets the backend use EPA combined MPG. */
  mpg: string | null
  gallons: number
  payment: 'credit' | 'cash' | 'cash_or_credit'
  timeValuePerHour?: number
  searchRadiusMiles?: number
  creditCashbackPercent: string
  costco: boolean
  preference: Preference
  paymentPolicyVersion: number
  allowUnknownPayment: boolean
  /** Best overall may pick a TOP TIER station that costs at most 5 cents per gallon more. */
  preferTopTier: boolean
  tripMode: 'round_trip' | 'on_route'
  destination: { lat: number; lng: number } | null
  navDefaultVersion: number
  navApp: NavApp
  /** Null follows the browser language. */
  locale: Locale | null
}

export const DEFAULT_PREFS: Prefs = {
  onboarded: false,
  vehicle: null,
  fuelType: 'regular',
  mpg: '25',
  gallons: 10,
  payment: 'credit',
  creditCashbackPercent: '0',
  timeValuePerHour: 15,
  searchRadiusMiles: 5,
  costco: false,
  preference: 'balanced',
  allowUnknownPayment: true,
  paymentPolicyVersion: 2,
  preferTopTier: true,
  navApp: 'google',
  navDefaultVersion: 2,
  tripMode: 'round_trip',
  destination: null,
  locale: null,
}

const KEY = 'gaswise.prefs.v1'

// Only user choices live here. Fuel search recovery uses short-lived sessionStorage separately.
export function normalizePrefs(value: unknown, restoreFuelSession = false): Prefs {
  const parsed = value && typeof value === 'object' ? value as Partial<Prefs> : {}
  const saved = Object.fromEntries(Object.keys(DEFAULT_PREFS).filter(key=>key in parsed).map(key=>[key,parsed[key as keyof Prefs]])) as Partial<Prefs>
  const reward = Number(saved.creditCashbackPercent ?? 0)
  saved.creditCashbackPercent = Number.isFinite(reward) ? String(Math.min(100, Math.max(0, reward))) : '0'
  saved.timeValuePerHour = Math.min(500, Math.max(0, Number(saved.timeValuePerHour ?? 15) || 0))
  saved.searchRadiusMiles = [2, 5, 10, 20].includes(saved.searchRadiusMiles ?? 5) ? saved.searchRadiusMiles ?? 5 : 5
  const trip = restoreFuelSession ? loadFuelSession()?.result.snapshot.query : null
  const destination = trip?.destination
  const restoreTrip = trip?.trip_mode === 'on_route' && destination &&
    Number.isFinite(destination.lat) && Math.abs(destination.lat) <= 90 &&
    Number.isFinite(destination.lng) && Math.abs(destination.lng) <= 180
  return { ...DEFAULT_PREFS, ...saved, locale: LOCALES.some((item) => item.value === saved.locale) ? saved.locale! : null, allowUnknownPayment: saved.paymentPolicyVersion === 2 ? saved.allowUnknownPayment ?? true : true, paymentPolicyVersion: 2, navApp: saved.navDefaultVersion === 2 ? saved.navApp ?? 'google' : 'google', navDefaultVersion: 2, tripMode: restoreTrip ? 'on_route' : 'round_trip', destination: restoreTrip ? destination : null }
}

export function loadPrefs(): Prefs {
  try {
    const raw = localStorage.getItem(KEY)
    return normalizePrefs(raw ? JSON.parse(raw) : {}, true)
  } catch {
    return DEFAULT_PREFS
  }
}

export function savePrefs(prefs: Prefs) {
  try {
    const publicPrefs=Object.fromEntries(Object.keys(DEFAULT_PREFS).map(key=>[key,prefs[key as keyof Prefs]]))
    localStorage.setItem(KEY, JSON.stringify({ ...publicPrefs, paymentPolicyVersion: 2, tripMode: 'round_trip', destination: null }))
  } catch {
    // Private mode or blocked storage: the session still works without persistence.
  }
}

export function usePrefs() {
  const [prefs, setPrefs] = useState<Prefs>(loadPrefs)
  const update = useCallback((change: Partial<Prefs>) => {
    setPrefs((current) => {
      const next = { ...current, ...change }
      savePrefs(next)
      return next
    })
  }, [])
  const replace = useCallback((value: Prefs) => {
    const next = normalizePrefs(value)
    setPrefs(next)
    savePrefs(next)
  }, [])
  return [prefs, update, replace] as const
}

export function effectiveFuel(prefs: Prefs): FuelType {
  return prefs.vehicle?.fuelType ?? prefs.fuelType
}
