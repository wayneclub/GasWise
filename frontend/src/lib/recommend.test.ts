import { describe, expect, it } from 'vitest'
import type { SmartResult } from '../api/types'
import fixture from '../test/fixtures/demo-search.json'
import { assess, breakdown, freshnessKey, openingLabel, picks, tradeoff } from './recommend'

const demo = fixture as unknown as SmartResult

function clone(): SmartResult {
  return structuredClone(demo)
}

describe('picks', () => {
  it('merges strategies that agree on one station', () => {
    const cards = picks(demo)
    expect(cards.map((pick) => [pick.station.name, pick.keys])).toEqual([
      ['Chevron', ['best_value', 'fastest_stop']],
      ['Arco', ['cheapest_overall']],
    ])
    expect(cards[0].row?.station.name).toBe('Chevron')
  })

  it('states the trade-off against the cheapest station', () => {
    const [hero, ...rest] = picks(demo)
    const trade = tradeoff(hero, [hero, ...rest])!
    expect(trade).toMatchObject({ name: 'Arco', minutes: 19, heroIsCheaper: false })
    expect(trade.saved).toBeCloseTo(2.05)
    expect(trade.perHour).toBeCloseTo(2.05 / (19.46 / 60), 0)
    // From the cheap side, the same trade is priced against the quickest stop.
    const fromCheap = tradeoff(rest[0], [hero, ...rest])!
    expect(fromCheap).toMatchObject({ name: 'Chevron', heroIsCheaper: true, minutes: 19 })
  })

  it('leads with the strategy that matches the priority', () => {
    expect(picks(demo, 'cheapest_overall')[0]).toMatchObject({ station: { name: 'Arco' }, keys: ['cheapest_overall'] })
    expect(picks(demo, 'fastest_stop')[0]).toMatchObject({ station: { name: 'Chevron' }, keys: ['fastest_stop', 'best_value'] })
    expect(picks(demo, 'best_value')[0].keys[0]).toBe('best_value')
  })
})

describe('assess', () => {
  it('treats a single source as neutral and only flags real gaps such as unconfirmed hours', () => {
    const result = assess(demo)
    expect(result.level).toBe('medium')
    expect(result.reasons).toEqual([{ key: 'reason.hours' }])
    expect(result.positives).toEqual([])
    expect(result).toMatchObject({ usable: 3, total: 3 })
  })

  it('is high only when the top pick is fresh, corroborated and open', () => {
    const result = clone()
    const best = result.ranking!.recommendations!.best_value
    best.decision!.status = 'robust'
    best.station!.open_now = true
    result.ranking!.results[0].station.open_now = true
    expect(assess(result).level).toBe('high')
  })

  it('drops to low when the price is stale or coverage is thin', () => {
    const sameDay = clone()
    sameDay.ranking!.results[0].price_age_minutes = 6 * 60
    expect(assess(sameDay).reasons).not.toContainEqual({ key: 'reason.stale' })
    const stale = clone()
    stale.ranking!.results[0].price_age_minutes = 25 * 60
    expect(assess(stale).level).toBe('low')
    expect(assess(stale).reasons).toContainEqual({ key: 'reason.stale' })
    const thin = clone()
    thin.ranking!.results = thin.ranking!.results.slice(0, 2)
    expect(assess(thin).level).toBe('medium')
    expect(assess(thin).reasons).toContainEqual({ key: 'reason.thin', vars: { usable: 2, total: 3 } })
  })

  it('reports no match when nothing was eligible', () => {
    const empty = clone()
    empty.ranking!.recommendations!.best_value = {
      ...empty.ranking!.recommendations!.best_value,
      station: null,
      decision: { recommended_station_id: null, status: 'no_eligible_stations', reason: 'none' },
    }
    expect(assess(empty).level).toBe('none')
  })
})

describe('positive signals', () => {
  it('counts agreeing sources and open hours as evidence', () => {
    const result = clone()
    const best = result.ranking!.recommendations!.best_value
    best.station!.open_now = true
    result.ranking!.results[0].price_comparison!.eligible_source_count = 3
    result.ranking!.results[0].price_comparison!.quality = 'corroborated'
    const assessment = assess(result)
    expect(assessment.level).toBe('high')
    expect(assessment.positives).toEqual([{ key: 'good.corroborated', vars: { count: 3 } }, { key: 'hours.open' }])
  })

  it('labels freshness by age with a one-day stale threshold', () => {
    expect(freshnessKey(30)).toBe('freshness.fresh')
    expect(freshnessKey(23 * 60)).toBe('freshness.today')
    expect(freshnessKey(25 * 60)).toBe('freshness.stale')
    expect(freshnessKey(null)).toBe('freshness.unknown')
  })
})

describe('breakdown', () => {
  const rows = demo.ranking!.results
  const arco = rows.find((row) => row.station.name === 'Arco')!

  it('adds purchase and driving fuel and compares with the quickest stop', () => {
    const b = breakdown(arco, rows, 10)
    expect([b.purchase, b.detourFuel, b.total]).toEqual(['59.90', '2.35', '62.25'])
    expect(b.reference).toEqual({ name: 'Chevron', total: '64.30', savings: '2.05' })
    expect(b.breakEven).toEqual({ key: 'breakdown.above', gallons: 4.9 })
  })

  it('warns when the planned fill is below the break-even amount', () => {
    expect(breakdown(arco, rows, 4).breakEven).toEqual({ key: 'breakdown.onlyAbove', gallons: 4.9 })
  })

  it('has no comparison for the quickest stop itself', () => {
    const chevron = rows.find((row) => row.station.name === 'Chevron')!
    const b = breakdown(chevron, rows, 10)
    expect(b.isReference).toBe(true)
    expect(b.reference).toBeNull()
    expect(b.breakEven).toBeNull()
  })
})

describe('openingLabel', () => {
  const station = demo.ranking!.results[0].station
  it('prefers the source label and never claims unknown hours are open', () => {
    expect(openingLabel({ ...station, open_now: true, details: { opening_status: 'Open 24 hours' } })).toEqual({
      key: 'hours.open',
      label: 'Open 24 hours',
      tone: 'ok',
    })
    expect(openingLabel({ ...station, open_now: false }).tone).toBe('warn')
    expect(openingLabel({ ...station, open_now: null, details: { opening_status: 'Open' } })).toEqual({
      key: 'hours.unknown',
      label: null,
      tone: 'muted',
    })
  })
})
