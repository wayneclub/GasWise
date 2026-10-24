import { describe, expect, it } from 'vitest'
import { navigationUrl } from './navigation'
import { DEFAULT_PREFS } from './prefs'
import { searchBody } from './session'

const origin = { lat: 34.05, lng: -118.24 }

describe('searchBody', () => {
  it('sends the vehicle instead of fuel and MPG when one is saved', () => {
    const body = searchBody(
      { ...DEFAULT_PREFS, vehicle: { id: 40000, label: 'E400', fuelType: 'premium', combinedMpg: '22' } },
      origin,
    )
    expect(body).toMatchObject({ vehicle_id: 40000, calculate_routes: true, strategy: 'best_value' })
    expect(body).not.toHaveProperty('fuel_type')
    expect(body).not.toHaveProperty('mpg')
  })

  it('maps priority and membership to ranking options', () => {
    const body = searchBody({ ...DEFAULT_PREFS, preference: 'time', costco: true, payment: 'cash', gallons: 12 }, origin)
    expect(body).toMatchObject({
      time_value_per_hour: '15',
      strategy: 'fastest_stop',
      memberships: ['costco'],
      payment_type: 'cash',
      gallons: '12',
      fuel_type: 'regular',
      mpg: '25',
    })
  })

  it('requests extra GasBuddy pages only for grades Maps summaries omit', () => {
    expect(searchBody({ ...DEFAULT_PREFS }, origin).gasbuddy_page_limit).toBe(3)
    expect(searchBody({ ...DEFAULT_PREFS, fuelType: 'premium' }, origin).gasbuddy_page_limit).toBe(5)
    const vehicle = searchBody(
      { ...DEFAULT_PREFS, vehicle: { id: 40000, label: 'E400', fuelType: 'premium', combinedMpg: '22' } },
      origin,
    )
    expect(vehicle.gasbuddy_page_limit).toBe(5)
  })

  it('routes a bounded shortlist first and leaves expansion explicit', () => {
    const body = searchBody({ ...DEFAULT_PREFS }, origin)
    expect(body.route_limit).toBe(10)
    expect(body.estimate_unrouted_routes).toBe(true)
  })
})

describe('navigationUrl', () => {
  it('puts only the destination in the link', () => {
    expect(navigationUrl('google', 34.1, -118.2)).toBe(
      'https://www.google.com/maps/dir/?api=1&destination=34.1,-118.2&travelmode=driving',
    )
    expect(navigationUrl('waze', 34.1, -118.2)).toContain('ll=34.1,-118.2')
    expect(navigationUrl('apple', 34.1, -118.2)).toContain('daddr=34.1,-118.2')
  })
})
