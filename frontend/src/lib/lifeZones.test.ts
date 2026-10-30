import { describe, expect, it } from 'vitest'
import {
  calculateArbitrage,
  estimateDistanceMiles,
  type LifeZone,
} from './lifeZones'

describe('LifeZones arbitrage calculation', () => {
  const homeZone: LifeZone = {
    id: 'home',
    kind: 'home',
    name: 'Home (90015)',
    query: '90015',
    origin: { lat: 34.039, lng: -118.267 },
    radiusMiles: 5,
    lastObservedPrice: 4.89,
    updatedAt: new Date().toISOString(),
  }

  const workZone: LifeZone = {
    id: 'work',
    kind: 'work',
    name: 'Work (90007)',
    query: '90007',
    origin: { lat: 34.024, lng: -118.288 },
    radiusMiles: 5,
    lastObservedPrice: 4.45,
    updatedAt: new Date().toISOString(),
  }

  it('estimates distance accurately between 90015 and 90007', () => {
    const dist = estimateDistanceMiles(homeZone.origin, workZone.origin)
    expect(dist).toBeGreaterThan(1.0)
    expect(dist).toBeLessThan(3.0)
  })

  it('identifies beneficial arbitrage when 90007 is substantially cheaper than 90015', () => {
    // 90015 is $4.89, 90007 is $4.45 (diff: $0.44/gal)
    // 10 gallons = $4.40 gross savings
    // ~1.6 miles detour at 25 MPG = ~0.064 gallons * $4.45 = ~$0.28 detour cost
    // Net savings = ~$4.12
    const arbitrage = calculateArbitrage(homeZone, workZone, 10, 25)
    expect(arbitrage).not.toBeNull()
    expect(arbitrage?.priceDiff).toBe(0.44)
    expect(arbitrage?.netSavings).toBeGreaterThan(3.5)
    expect(arbitrage?.isBeneficial).toBe(true)
  })

  it('returns null if toZone is not cheaper than fromZone', () => {
    const arbitrage = calculateArbitrage(workZone, homeZone, 10, 25)
    expect(arbitrage).toBeNull()
  })

  it('handles custom detour miles override', () => {
    const arbitrage = calculateArbitrage(homeZone, workZone, 10, 25, 2.0)
    expect(arbitrage?.detourMiles).toBe(2.0)
    expect(arbitrage?.grossSavings).toBe(4.4)
    expect(arbitrage?.isBeneficial).toBe(true)
  })
})
