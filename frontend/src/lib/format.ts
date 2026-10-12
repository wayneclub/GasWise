import type { Station } from '../api/types'
import type { MessageKey, Translate } from '../i18n'

export function fuelKey(fuel: 'regular' | 'midgrade' | 'premium' | 'diesel'): MessageKey {
  return `fuel.${fuel}`
}

/** Money arrives as exact decimal strings; formatting is display-only, never arithmetic. Always USD. */
export function usd(value: string | number | null | undefined): string {
  if (value == null) return '-'
  const amount = Number(value)
  const sign = amount < 0 ? '-' : ''
  return `${sign}$${Math.abs(amount).toFixed(2)}`
}

/** US pump prices are often quoted to a tenth of a cent ($5.799). */
export function perGallon(value: string): string {
  const amount = Number(value)
  const thousandths = Math.round(amount * 1000) % 10
  return `$${amount.toFixed(thousandths === 0 ? 2 : 3)}`
}

export function minutes(value: string | number | null | undefined, t: Translate): string {
  if (value == null) return '-'
  const total = Math.round(Number(value))
  if (total < 1) return t('time.lessThanMinute')
  if (total < 60) return t('time.minutes', { n: total })
  return t('time.hoursMinutes', { h: Math.floor(total / 60), m: total % 60 })
}

export function gallons(value: string | number, t: Translate): string {
  const amount = Number(value)
  return t('unit.gallons', { n: Number.isInteger(amount) ? amount : amount.toFixed(1) })
}

export function miles(value: string | number, t: Translate): string {
  const amount = Number(value)
  return t('unit.miles', { n: amount < 10 ? amount.toFixed(1) : Math.round(amount) })
}

/** Relative age phrase ("12 min ago"), embedded by callers in "Updated ..." or "Collected ...". */
export function age(iso: string | null | undefined, t: Translate, now: Date = new Date()): string {
  if (!iso) return t('age.unknown')
  const diff = Math.max(0, (now.getTime() - new Date(iso).getTime()) / 60000)
  if (diff < 1) return t('age.now')
  if (diff < 60) return t('age.minutes', { n: Math.round(diff) })
  if (diff < 48 * 60) return t('age.hours', { n: Math.round(diff / 60) })
  return t('age.days', { n: Math.round(diff / 1440) })
}

const SOURCE_LABEL: Record<string, string> = {
  gasbuddy_web: 'GasBuddy',
  gasbuddy: 'GasBuddy',
  google_maps_web: 'Google Maps',
  google_places: 'Google',
  waze: 'Waze',
  synthetic: 'Demo',
  gasbuddy_demo: 'Demo',
}

export function sourceLabel(source: string): string {
  return SOURCE_LABEL[source] ?? source
}

/** Comparison estimate never replaces the source quote in the snapshot. */
export function comparisonPrice(station: Pick<Station, 'price_per_gallon'> & Partial<Station>): string {
  return station.comparison_price_per_gallon ?? station.price_per_gallon
}
