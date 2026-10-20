import { expect, it } from 'vitest'
import { estimateNeed } from './fuelAssistant'

const settings = { weeklyMiles: 200, typicalGallons: 10 }
const event = (daysAgo: number) => ({ id: String(daysAgo), at: new Date(Date.UTC(2026, 9, 20 - daysAgo)).toISOString() })
const now = new Date(Date.UTC(2026, 9, 20))

it('uses a broad low-confidence range from explicit driving assumptions', () => {
  const estimate = estimateNeed([event(0)], settings, 25, now)
  expect(estimate).toEqual({ state: 'not_due', confidence: 'low', earliestDays: 5, latestDays: 12 })
})

it('learns cadence from refuel events and becomes due without claiming exact fuel', () => {
  const estimate = estimateNeed([event(9), event(19), event(29), event(39)], settings, 25, now)
  expect(estimate.state).toBe('due')
  expect(estimate.confidence).toBe('high')
  expect(estimate.earliestDays).toBe(0)
})

it('stays unknown without an explicit refuel event', () => {
  expect(estimateNeed([], settings, 25, now).state).toBe('unknown')
})
