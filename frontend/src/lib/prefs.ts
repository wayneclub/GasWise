import { useCallback, useState } from 'react'
import type { FuelType } from '../api/types'
import { LOCALES, type Locale } from '../i18n'

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

/** Recommendation preference, not cash: the value of one hour of driving time in USD. */
export const TIME_VALUE: Record<Preference, number> = { money: 0, balanced: 15, time: 30 }

const KEY = 'gaswise.prefs.v1'

// Only user choices live here. The signed price snapshot is never persisted.
export function loadPrefs(): Prefs {
  try {
    const raw = localStorage.getItem(KEY)
    const saved = raw ? JSON.parse(raw) as Partial<Prefs> : {}
    const reward = Number(saved.creditCashbackPercent ?? 0)
    saved.creditCashbackPercent = Number.isFinite(reward) ? String(Math.min(100, Math.max(0, reward))) : '0'
    return { ...DEFAULT_PREFS, ...saved, locale: LOCALES.some((item) => item.value === saved.locale) ? saved.locale! : null, allowUnknownPayment: saved.paymentPolicyVersion === 2 ? saved.allowUnknownPayment ?? true : true, paymentPolicyVersion: 2, navApp: saved.navDefaultVersion === 2 ? saved.navApp ?? 'google' : 'google', navDefaultVersion: 2, tripMode: 'round_trip', destination: null }
  } catch {
    return DEFAULT_PREFS
  }
}

function savePrefs(prefs: Prefs) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...prefs, paymentPolicyVersion: 2, tripMode: 'round_trip', destination: null }))
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
  return [prefs, update] as const
}

export function effectiveFuel(prefs: Prefs): FuelType {
  return prefs.vehicle?.fuelType ?? prefs.fuelType
}
