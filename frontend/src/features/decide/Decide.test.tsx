import { StrictMode } from 'react'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { IDBFactory } from 'fake-indexeddb'
import type { SmartResult } from '../../api/types'
import { loadFuelAssistant } from '../../lib/fuelAssistant'
import App from '../../App'
import fixture from '../../test/fixtures/demo-search.json'

const demo = fixture as unknown as SmartResult

function respond(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers }))
}

beforeEach(() => {
  sessionStorage.clear()
  vi.stubGlobal('indexedDB', new IDBFactory())
  localStorage.setItem('gaswise.prefs.v1', JSON.stringify({ onboarded: true, fuelType: 'premium', mpg: '22', locale: 'en' }))
  Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true })
  Object.defineProperty(navigator, 'geolocation', {
    configurable: true,
    value: {
      getCurrentPosition: (ok: PositionCallback) =>
        ok({ coords: { latitude: 34.0522, longitude: -118.2437 } } as GeolocationPosition),
    },
  })
  HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) {
    this.open = true
  }
  HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) {
    this.open = false
  }
})

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
  sessionStorage.clear()
})

describe('Decide', () => {
  it('opens straight to a recommendation with directions and reasons', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(demo))
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Chevron', level: 2 })).toBeInTheDocument()
    expect(screen.queryByText(/\$2.05 more · vs Arco/)).not.toBeInTheDocument()
    expect(screen.getByText('$2.05 more')).toBeInTheDocument()
    expect(screen.getByText('vs Arco (cheapest)')).toBeInTheDocument()
    expect(screen.getByText('Saves 19 min')).toBeInTheDocument()
    expect(screen.queryByText('Trade-off: about $6.32 per hour of driving.')).not.toBeInTheDocument()
    // Fuel burned driving to the station is part of the compared total.
    expect(screen.queryByText('Fuel to get there')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:'Cost breakdown'}))
    expect(screen.getByText('Fuel to get there')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Navigate' })).toHaveAttribute(
      'href',
      expect.stringContaining('destination=34.0602,-118.2437'),
    )
    const hero = within(screen.getByRole('region', { name: 'Chevron' }))
    expect(hero.getByText(/Estimated pump payment for 10 gal/)).toHaveTextContent('≈ $63.90')
    expect(hero.getAllByText('Comparison cost')[0]).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/smart/search-jobs/start')
    expect(JSON.parse(String(init?.body))).toMatchObject({ origin: { lat: 34.0522, lng: -118.2437 }, fuel_type: 'premium' })
  })

  it('keeps a Google quote unverified and labels a marked-up payment estimate as an assumption', async () => {
    const result = structuredClone(demo)
    const row = result.ranking!.results.find((r) => r.station.name === 'Chevron')!
    Object.assign(row.station, { source: 'google_maps_web', payment_type: 'unknown', comparison_price_per_gallon: '6.59', payment_price_adjustment: '0.20', payment_inference: { classification: 'cash', confidence: 'medium' } })
    Object.assign(row, { purchase_cost: '65.90', actual_fuel_cost: '66.30' })
    for (const rec of Object.values(result.ranking!.recommendations!)) {
      if (rec.station?.name === 'Chevron') rec.station = row.station
    }
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(result))
    render(<App />)
    await screen.findByRole('heading', { name: 'Chevron', level: 2 })
    const hero = within(screen.getByRole('region', { name: 'Chevron' }))
    expect(hero.getByText(/Estimated with payment assumption for 10 gal/)).toHaveTextContent('≈ $65.90')
    expect(hero.getByText(/This Google Maps quote has no payment terms/)).toBeInTheDocument()
    expect(hero.getByText(/This is an inference; payment terms remain unverified/)).toBeInTheDocument()
    expect(hero.getByText('Unconfirmed; check at the pump')).toBeInTheDocument()
  })

  it('changes the headline station when the priority changes', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(demo))
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Chevron', level: 2 })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('radio', { name: 'Cost' }))
    expect(await screen.findByRole('heading', { name: 'Arco', level: 2 })).toBeInTheDocument()
    expect(screen.getByText('Save $2.05')).toBeInTheDocument()
    expect(screen.getByText('vs Chevron (quickest)')).toBeInTheDocument()
    expect(screen.getByText('Adds 19 min')).toBeInTheDocument()
  })

  it('marks TOP TIER brands and sends the preference with a zero-call rerank', async () => {
    const tagged = structuredClone(demo)
    for (const station of [
      ...tagged.ranking!.results.map((row) => row.station),
      ...Object.values(tagged.ranking!.recommendations!).map((rec) => rec.station),
    ]) {
      if (station?.name === 'Chevron') station.top_tier_brand = 'Chevron'
    }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(tagged))
    render(<App />)
    await screen.findByRole('heading', { name: 'Chevron', level: 2 })
    expect(screen.getAllByLabelText('Chevron is a TOP TIER licensed brand').length).toBeGreaterThan(0)
    expect(screen.queryByLabelText('Arco is a TOP TIER licensed brand')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toMatchObject({ prefer_top_tier: true })
    fireEvent.click(await screen.findByLabelText(/Prefer TOP TIER/))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    const [url, init] = fetchMock.mock.calls[1]
    expect(url).toBe('/api/v1/smart/rerank')
    expect(JSON.parse(String(init?.body)).options).toMatchObject({ prefer_top_tier: false })
  })

  it('explains when TOP TIER was preferred over a slightly cheaper station', async () => {
    const preferred = structuredClone(demo)
    const best = preferred.ranking!.recommendations!.best_value
    best.station!.top_tier_brand = 'Chevron'
    best.top_tier_preferred_over = { station_name: 'Shell', extra_cost: '0.30', margin: '0.50' }
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(preferred))
    render(<App />)
    expect(await screen.findByText('TOP TIER preferred: $0.30 more than Shell (limit $0.50)')).toBeInTheDocument()
  })

  it('reranks the held snapshot when gallons change, without a new search', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(demo))
    render(<App />)
    await screen.findByRole('heading', { name: 'Chevron', level: 2 })

    expect(screen.getByRole('button', { name: /Edit this fill/ })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('button', { name: 'Increase gallons' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Edit this fill/ }))
    expect(screen.getByRole('button', { name: /Edit this fill/ })).toHaveAttribute('aria-expanded', 'true')
    fireEvent.click(screen.getByRole('button', { name: 'Increase gallons' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    const [url, init] = fetchMock.mock.calls[1]
    expect(url).toBe('/api/v1/smart/rerank')
    expect(JSON.parse(String(init?.body))).toMatchObject({ signature: demo.signature, options: { gallons: '11' } })
  })

  it('searches once under StrictMode without aborting the active request', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(demo))
    render(<StrictMode><App /></StrictMode>)
    await screen.findByRole('heading', { name: 'Chevron', level: 2 })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][1]?.signal?.aborted).toBe(false)
  })

  it('cancels the older rerank when preferences change again', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => respond(demo))
      .mockImplementationOnce(() => new Promise<Response>(() => {}))
      .mockImplementation(() => respond(demo))
    render(<App />)
    await screen.findByRole('heading', { name: 'Chevron', level: 2 })
    fireEvent.click(screen.getByRole('button', { name: /Edit this fill/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Increase gallons' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    fireEvent.click(screen.getByRole('button', { name: 'Increase gallons' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
    expect(fetchMock.mock.calls[1][1]?.signal?.aborted).toBe(true)
  })

  it('starts a new wider geographic search when no station fits', async () => {
    localStorage.setItem('gaswise.prefs.v1', JSON.stringify({ ...JSON.parse(localStorage.getItem('gaswise.prefs.v1') ?? '{}'), allowUnknownPayment: false, paymentPolicyVersion: 2 }))
    const empty = structuredClone(demo)
    empty.ranking!.results = []
    for (const key of Object.keys(empty.ranking!.recommendations!)) {
      empty.ranking!.recommendations![key] = {
        ...empty.ranking!.recommendations![key],
        station: null,
        decision: { recommended_station_id: null, status: 'no_eligible_stations', reason: 'none' },
      }
    }
    const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(empty))
    render(<App />)
    expect(await screen.findByText('No eligible live fuel prices nearby')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Expand to 20 miles' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Expand to 10 miles' }))
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    expect(fetch.mock.calls[1][0]).toBe('/api/v1/smart/search-jobs/start')
    expect(JSON.parse(String(fetch.mock.calls[1][1]?.body))).toMatchObject({ radius_meters: 16093.44, allow_unknown_payment: false })
  })

  it('renders the same decision in Traditional Chinese', async () => {
    localStorage.setItem('gaswise.prefs.v1', JSON.stringify({ onboarded: true, fuelType: 'premium', mpg: '22', locale: 'zh-TW' }))
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(demo))
    render(<App />)
    expect(await screen.findByRole('heading', {name:'Chevron',level:2})).toBeInTheDocument()
    expect(screen.getByText('多 $2.05')).toBeInTheDocument()
    expect(screen.getByText('比 Arco（最便宜）')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:'費用明細'}))
    expect(screen.getByText('來回油耗')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '導航' })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('zh-TW')
  })

  it('asks before requesting location the first time', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(demo))
    Object.defineProperty(navigator, 'permissions', {
      configurable: true,
      value: { query: () => Promise.resolve({ state: 'prompt' }) },
    })
    render(<App />)
    const button = await screen.findByRole('button', { name: /Use current location/ })
    expect(fetchMock).not.toHaveBeenCalled()
    fireEvent.click(button)
    expect(await screen.findByRole('heading', { name: 'Chevron', level: 2 })).toBeInTheDocument()
    Object.defineProperty(navigator, 'permissions', { configurable: true, value: undefined })
  })

  it('waits out Retry-After before allowing another search', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      respond({ detail: 'search_capacity_exceeded' }, 429, { 'Retry-After': '5' }),
    )
    render(<App />)
    expect(await screen.findByText('GasWise is busy')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Try again in 5s/ })).toBeDisabled()
  })
})

it('labels estimated card prices and keeps TOP TIER as a compact text badge', async () => {
  const data = structuredClone(demo)
  const station = data.ranking!.recommendations!.best_value.station!
  Object.assign(station, { payment_type: 'unknown', price_per_gallon: '6.39', comparison_price_per_gallon: '6.59', payment_price_adjustment: '0.20', top_tier_brand: 'Chevron' })
  vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(data))
  render(<App />)
  await screen.findByRole('heading', { name: 'Chevron', level: 2 })
  expect(screen.getByText('Card estimate +$0.20/gal · source $6.39')).toBeInTheDocument()
  const badge = screen.getByRole('img', { name: 'Chevron is a TOP TIER licensed brand' })
  expect(badge).toHaveTextContent('TOP TIER')
  expect(badge.querySelector('img')).toBeNull()
})


it('makes an unavailable AAA benchmark explicit without inventing an average', async () => {
  const unavailable = structuredClone(demo)
  unavailable.snapshot.warnings = [...(unavailable.snapshot.warnings ?? []), 'AAA regional average unavailable for CA']
  vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(unavailable))
  render(<App />)
  expect(await screen.findByText('AAA: temporarily unavailable')).toBeInTheDocument()
  expect(screen.queryByText(/Metro average/)).not.toBeInTheDocument()
})

it('labels geometric driving estimates in recommendations and station details', async () => {
  const data = structuredClone(demo)
  for (const row of [...data.ranking!.results, ...Object.values(data.ranking!.leaderboards ?? {}).flat()]) {
    row.route.source = 'straight_line_estimate'
    row.route.duration_basis = 'geometric_estimate'
  }
  vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(data))
  render(<App />)
  await screen.findByRole('heading', { name: 'Chevron', level: 2 })
  expect(screen.getAllByText('Estimated drive and cost').length).toBeGreaterThan(0)
  fireEvent.click(screen.getByRole('button', { name: 'View details' }))
  expect(screen.getByRole('dialog', { name: 'Station details' }).textContent).toContain('Estimated drive and cost')
})

it('refreshes held prices without restarting the full station and route search', async () => {
  const data = structuredClone(demo)
  data.snapshot.expires_at = new Date(Date.now() + 600000).toISOString()
  data.snapshot.query.radius_meters = 5 * 1609.344
  data.snapshot.source_cache = { maps: { checked_at: new Date(Date.now() - 120000).toISOString(), state: 'stale' } }
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(data))
  render(<App />)
  await screen.findByRole('heading', { name: 'Chevron', level: 2 })
  fireEvent.click(screen.getByRole('button', { name: 'Refresh prices' }))
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
  expect(fetch.mock.calls[1][0]).toBe('/api/v1/smart/refresh-prices')
  const body = JSON.parse(String(fetch.mock.calls[1][1]?.body))
  expect(body.signature).toBe(data.signature)
  expect(body.snapshot.routes).toEqual(data.snapshot.routes)
  expect(body.options).toBeDefined()
})

it('starts one new transaction when a server restart invalidates the held snapshot', async () => {
  const data = structuredClone(demo)
  data.snapshot.expires_at = new Date(Date.now() + 600000).toISOString()
  data.snapshot.query.radius_meters = 5 * 1609.344
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => respond(data))
    .mockImplementationOnce(() => respond({ detail: 'invalid_snapshot_signature' }, 409))
    .mockImplementation(() => respond(data))
  render(<App />)
  await screen.findByRole('heading', { name: 'Chevron', level: 2 })
  fireEvent.click(screen.getByRole('button', { name: 'Refresh prices' }))
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3))
  expect(fetch.mock.calls.map(([url]) => url)).toEqual(['/api/v1/smart/search-jobs/start', '/api/v1/smart/refresh-prices', '/api/v1/smart/search'])
  expect(JSON.parse(String(fetch.mock.calls[2][1]?.body)).force_refresh).toBe(false)
})

it('shows payment inference separately from raw unknown payment in station details', async () => {
  const data = structuredClone(demo)
  const station = data.ranking!.recommendations!.best_value!.station!
  station.payment_type = 'unknown'
  station.payment_inference = { classification: 'cash', confidence: 'medium', basis: 'contemporaneous_price_match' }
  vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(data))
  render(<App />)
  await screen.findByRole('heading', { name: station.name, level: 2 })
  fireEvent.click(screen.getByRole('button', { name: 'View details' }))
  expect(screen.getByRole('dialog', { name: 'Station details' }).textContent).toContain('Possible cash price')
})

it('recovers a remounted page without locating or searching again', async () => {
  const current = structuredClone(demo)
  current.snapshot.expires_at = new Date(Date.now() + 600000).toISOString()
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(current))
  const locate = vi.spyOn(navigator.geolocation, 'getCurrentPosition')
  const first = render(<App />)
  await screen.findByRole('heading', { name: 'Chevron', level: 2 })
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(locate).toHaveBeenCalledTimes(1)
  first.unmount()
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'Chevron', level: 2 })).toBeInTheDocument()
  await waitFor(() => expect(screen.queryByText('Finding your location')).not.toBeInTheDocument())
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(locate).toHaveBeenCalledTimes(1)
})

it('clicking navigate or record button records refuel and shows toast notification', async () => {
  const data = structuredClone(demo)
  vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(data))
  render(<App />)
  await screen.findByRole('heading', { name: 'Chevron', level: 2 })

  // Click explicit record refuel button on HeroPick
  const recordBtn = screen.getByRole('button', { name: 'Record refuel here' })
  fireEvent.click(recordBtn)

  // Shows toast notification
  expect(await screen.findByRole('status')).toHaveTextContent('Recorded fueling at Chevron')

  // Check storage has this refuel event
  const assistant = await loadFuelAssistant()
  expect(assistant.events.some((e) => e.stationName === 'Chevron')).toBe(true)

  // Clicking "View in My Profile" switches to My tab
  const viewBtn = screen.getByRole('button', { name: 'View in My Profile' })
  fireEvent.click(viewBtn)

  expect(await screen.findByText('Refueling Records (1)')).toBeInTheDocument()
  expect(screen.getAllByText('Chevron').length).toBeGreaterThanOrEqual(1)
})
