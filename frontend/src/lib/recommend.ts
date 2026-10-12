import { comparisonPrice } from './format'
import type { RankedStation, SmartResult, Station, StrategyKey, StrategyRecommendation } from '../api/types'
import type { MessageKey, Vars } from '../i18n'

/** Copy is returned as message keys so every locale renders the same decision. */
export interface Message {
  key: MessageKey
  vars?: Vars
}

export type Confidence = 'high' | 'medium' | 'low' | 'none'

export interface Assessment {
  level: Confidence
  reasons: Message[]
  positives: Message[]
  usable: number
  total: number
}

export interface Pick {
  keys: StrategyKey[]
  recommendation: StrategyRecommendation
  station: Station
  row: RankedStation | null
}

const ORDER: StrategyKey[] = ['best_value', 'cheapest_overall', 'fastest_stop', 'on_my_route']

/**
 * Priority picks the headline card. Time value alone rarely flips the winner (a detour that saves
 * $10 in 10 minutes beats any time value under $60/h), so each priority leads with its own strategy.
 */
export const PRIORITY_STRATEGY = { money: 'cheapest_overall', balanced: 'best_value', time: 'fastest_stop' } as const satisfies Record<
  'money' | 'balanced' | 'time',
  StrategyKey
>

export function sameStation(a: Station, b: Station): boolean {
  return a.source === b.source && a.id === b.id
}

export function findRow(rows: RankedStation[], station: Station): RankedStation | null {
  return rows.find((row) => sameStation(row.station, station)) ?? null
}

/** Strategy cards, merged when several strategies agree on one station. */
export function picks(result: SmartResult, primary: StrategyKey = 'best_value'): Pick[] {
  const ranking = result.ranking
  if (!ranking) return []
  const merged: Pick[] = []
  for (const key of [primary, ...ORDER.filter((k) => k !== primary)]) {
    if (key === 'on_my_route' && result.snapshot.query.trip_mode !== 'on_route') continue
    const recommendation = ranking.recommendations?.[key]
    const station = recommendation?.station
    if (!recommendation || !station) continue
    const existing = merged.find((pick) => sameStation(pick.station, station))
    if (existing) existing.keys.push(key)
    else merged.push({ keys: [key], recommendation, station, row: findRow(ranking.results, station) })
  }
  return merged
}

function stationCount(result: SmartResult): number {
  if (result.coverage) return result.coverage.discovered
  const keys = new Set(result.snapshot.stations.map((s) => s.canonical_id ?? `${s.source}:${s.id}`))
  return Math.max(keys.size, result.snapshot.inventory?.length ?? 0)
}

/** Deterministic, explainable confidence for the top pick (frontend-plan.md section 4). */
/** A price only counts as old after a full day; same-day updates are normal for pump prices. */
export const STALE_PRICE_MINUTES = 24 * 60

export function freshnessKey(ageMinutes: number | null | undefined): MessageKey {
  if (ageMinutes == null) return 'freshness.unknown'
  if (ageMinutes <= 60) return 'freshness.fresh'
  return ageMinutes <= STALE_PRICE_MINUTES ? 'freshness.today' : 'freshness.stale'
}

/**
 * Deterministic, explainable confidence for the headline pick. Cautions are real problems
 * (old, disputed or unverified data); positives are evidence the user can trust. A single
 * source is not a defect: extra sources exist to cross-check, so agreement is a positive.
 */
export function assess(result: SmartResult, primary: StrategyKey = 'best_value'): Assessment {
  const ranking = result.ranking
  const usable = ranking?.results.length ?? 0
  const total = Math.max(stationCount(result), usable)
  const best = ranking?.recommendations?.[primary]
  if (!ranking || !best?.station || best.decision?.status === 'no_eligible_stations') {
    return { level: 'none', reasons: [{ key: 'reason.noEligible' }], positives: [], usable, total }
  }
  const row = findRow(ranking.results, best.station)
  const reasons: Message[] = []
  const positives: Message[] = []
  let level: Confidence = 'high'
  const lower = (to: Confidence) => {
    const rank: Confidence[] = ['high', 'medium', 'low']
    if (rank.indexOf(to) > rank.indexOf(level)) level = to
  }

  const ageMinutes = row?.price_age_minutes
  if (row && ageMinutes == null) {
    lower('medium')
    reasons.push({ key: 'reason.unknownTime' })
  } else if (ageMinutes != null && ageMinutes > STALE_PRICE_MINUTES) {
    lower('low')
    reasons.push({ key: 'reason.stale' })
  }
  const comparison = row?.price_comparison
  if (comparison?.quality === 'disputed') {
    lower('low')
    reasons.push({ key: 'reason.disputed' })
  } else if (comparison && comparison.eligible_source_count >= 2) {
    positives.push({ key: 'good.corroborated', vars: { count: comparison.eligible_source_count } })
  }
  if (usable < 3) {
    lower('medium')
    reasons.push({ key: 'reason.thin', vars: { usable, total } })
  }
  if (best.station.payment_type === 'unknown') {
    lower('medium')
    reasons.push({ key: 'reason.payment' })
  }
  if (best.station.open_now == null) {
    lower('medium')
    reasons.push({ key: 'reason.hours' })
  } else if (best.station.open_now) {
    positives.push({ key: 'hours.open' })
  }
  return { level, reasons, positives, usable, total }
}

export interface Breakdown {
  gallons: string
  pricePerGallon: string
  purchase: string
  detourFuel: string
  total: string
  reference: { name: string; total: string | null; savings: string } | null
  isReference: boolean
  breakEven: { key: 'breakdown.any' | 'breakdown.above' | 'breakdown.onlyAbove'; gallons: number } | null
}

export function breakdown(row: RankedStation, rows: RankedStation[], gallons: number): Breakdown {
  const be = row.break_even
  const isReference = !be || be.reference_station_id === row.station.id
  const referenceRow = be ? rows.find((r) => r.station.id === be.reference_station_id) : undefined
  let breakEven: Breakdown['breakEven'] = null
  if (be && !isReference && Number(be.price_savings_per_gallon) > 0 && be.fuel_only_gallons != null) {
    const threshold = Math.round(Number(be.fuel_only_gallons) * 10) / 10
    const key = threshold === 0 ? 'breakdown.any' : threshold > gallons ? 'breakdown.onlyAbove' : 'breakdown.above'
    breakEven = { key, gallons: threshold }
  }
  return {
    gallons: String(gallons),
    pricePerGallon: comparisonPrice(row.station),
    purchase: row.purchase_cost,
    detourFuel: row.detour_fuel_cost,
    total: row.actual_fuel_cost,
    reference:
      be && !isReference
        ? {
            name: be.reference_station_name,
            total: referenceRow?.actual_fuel_cost ?? null,
            savings: be.fuel_savings_at_requested_gallons,
          }
        : null,
    isReference,
    breakEven,
  }
}

/**
 * Opening status. The source label (e.g. "Closes 10 PM") is English-only upstream text,
 * so it is shown only for English; other locales get the translated state.
 */
export function openingLabel(station: Station): { key: MessageKey; label: string | null; tone: 'ok' | 'muted' | 'warn' } {
  const label = typeof station.details?.opening_status === 'string' ? station.details.opening_status : null
  if (station.open_now === true) return { key: 'hours.open', label, tone: 'ok' }
  if (station.open_now === false) return { key: 'hours.closed', label, tone: 'warn' }
  return { key: 'hours.unknown', label: null, tone: 'muted' }
}

export interface Tradeoff {
  /** The opposite extreme: the cheapest station when the headline is faster, otherwise the quickest. */
  name: string
  saved: number
  minutes: number
  perHour: number
  heroIsCheaper: boolean
}

/**
 * The decision in one line, priced as an hourly rate so the user can judge it against their own time.
 * Display-only arithmetic on already-rounded money; the ranking itself never uses it.
 */
export function tradeoff(hero: Pick, all: Pick[]): Tradeoff | null {
  const cheapest = all.find((pick) => pick.keys.includes('cheapest_overall'))
  const quickest = all.find((pick) => pick.keys.includes('fastest_stop'))
  const other = hero === cheapest ? quickest : cheapest
  if (!other || other === hero) return null
  const costDiff = Number(other.recommendation.actual_fuel_cost) - Number(hero.recommendation.actual_fuel_cost)
  const timeDiff = Number(other.recommendation.extra_travel_minutes) - Number(hero.recommendation.extra_travel_minutes)
  // Only a real trade: one is cheaper and the other is faster.
  const heroIsCheaper = costDiff > 0 && timeDiff < 0
  const heroIsFaster = costDiff < 0 && timeDiff > 0
  const minutes = Math.round(Math.abs(timeDiff))
  if ((!heroIsCheaper && !heroIsFaster) || minutes < 1) return null
  const saved = Math.abs(costDiff)
  return { name: other.station.name, saved, minutes, perHour: saved / (Math.abs(timeDiff) / 60), heroIsCheaper }
}
