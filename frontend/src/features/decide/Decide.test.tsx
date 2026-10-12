import { StrictMode } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { SmartResult } from '../../api/types'
import App from '../../App'
import fixture from '../../test/fixtures/demo-search.json'

const demo = fixture as unknown as SmartResult

function respond(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers }))
}

beforeEach(() => {
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
})

describe('Decide', () => {
  it('opens straight to a recommendation with directions and reasons', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(demo))
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Chevron', level: 2 })).toBeInTheDocument()
    expect(screen.getByText('Best among comparable prices')).toBeInTheDocument()
    expect(screen.getByText('$2.05 more')).toBeInTheDocument()
    expect(screen.getByText('vs Arco (cheapest)')).toBeInTheDocument()
    expect(screen.getByText('Saves 19 min')).toBeInTheDocument()
    expect(screen.getByText('Trade-off: about $6.32 per hour of driving.')).toBeInTheDocument()
    // Fuel burned driving to the station is part of the compared total.
    expect(screen.getByText('Fuel to get there')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Navigate' })).toHaveAttribute(
      'href',
      expect.stringContaining('destination=34.0602,-118.2437'),
    )
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/smart/search')
    expect(JSON.parse(String(init?.body))).toMatchObject({ origin: { lat: 34.0522, lng: -118.2437 }, fuel_type: 'premium' })
  })

  it('changes the headline station when the priority changes', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(demo))
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Chevron', level: 2 })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('radio', { name: 'Money' }))
    expect(await screen.findByRole('heading', { name: 'Arco', level: 2 })).toBeInTheDocument()
    expect(screen.getAllByText('Lowest cost').length).toBeGreaterThan(0)
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
    fireEvent.click(screen.getByRole('button', { name: 'Increase gallons' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    fireEvent.click(screen.getByRole('button', { name: 'Increase gallons' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
    expect(fetchMock.mock.calls[1][1]?.signal?.aborted).toBe(true)
  })

  it('offers to widen eligibility when no station fits', async () => {
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
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(empty))
    render(<App />)
    expect(await screen.findByText('No station fits right now')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Include unconfirmed prices' })).toBeInTheDocument()
  })

  it('renders the same decision in Traditional Chinese', async () => {
    localStorage.setItem('gaswise.prefs.v1', JSON.stringify({ onboarded: true, fuelType: 'premium', mpg: '22', locale: 'zh-TW' }))
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => respond(demo))
    render(<App />)
    expect(await screen.findByText('可比較站中最值得')).toBeInTheDocument()
    expect(screen.getByText('多 $2.05')).toBeInTheDocument()
    expect(screen.getByText('比 Arco（最便宜）')).toBeInTheDocument()
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
