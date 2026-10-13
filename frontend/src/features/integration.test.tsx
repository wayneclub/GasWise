import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { I18nProvider } from '../i18n/I18nProvider'
import { VehicleIdentityContext } from '../lib/vehicleIdentity'
import { Parts } from './parts/Parts'
import { ExcludedStations } from './decide/ExcludedStations'
import { StationList } from './decide/StationList'
import type { RankedStation } from '../api/types'
import { VehiclePicker } from './setup/VehiclePicker'
import fixture from '../test/fixtures/demo-search.json'

const response = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body)))
const car = { id: 12345, year: 2003, make: 'Honda', model: 'Accord', fuel_type: 'Regular Gasoline', combined_mpg: '25' }
const decoded = { vin_masked: '*************4352', year: 2003, make: 'Honda', model: 'Accord', engine_liters: '2.4' }
const vin = '1HGCM82633A004352' // Public sample used only in mocked requests.

beforeEach(() => {
  localStorage.setItem('gaswise.prefs.v1', JSON.stringify({ onboarded: true, locale: 'en', navApp: 'waze' }))
  Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true })
  Object.defineProperty(navigator, 'permissions', { configurable: true, value: undefined })
  Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition: (ok: PositionCallback) => ok({ coords: { latitude: 34, longitude: -118 } } as GeolocationPosition) } })
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
})
afterEach(() => { vi.restoreAllMocks(); localStorage.clear() })
const english = (component: React.ReactNode) => <I18nProvider locale="en">{component}</I18nProvider>

it('saves cashback and reranks held prices without a new search', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(() => response(fixture))
  render(<App />)
  await screen.findByRole('heading', { name: 'Chevron', level: 2 })
  fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
  fireEvent.change(screen.getByRole('spinbutton', { name: 'Card cashback' }), { target: { value: '4.5' } })
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
  expect(fetch.mock.calls[1][0]).toBe('/api/v1/smart/rerank')
  expect(JSON.parse(String(fetch.mock.calls[1][1]?.body)).options.credit_cashback_percent).toBe('4.5')
  expect(JSON.parse(localStorage.getItem('gaswise.prefs.v1')!).creditCashbackPercent).toBe('4.5')
  fireEvent.click(screen.getByRole('radio', { name: /^Cash$/ }))
  expect(screen.getByRole('spinbutton', { name: 'Card cashback' })).toBeDisabled()
})

it('follows browser language until a manual choice, persists it, and can return to automatic', () => {
  localStorage.setItem('gaswise.prefs.v1', JSON.stringify({ onboarded: false }))
  let languages = ['zh-CN', 'en-US']
  vi.spyOn(navigator, 'languages', 'get').mockImplementation(() => languages)
  const app = render(<App />)
  expect(document.documentElement.lang).toBe('zh-CN')
  expect(screen.getByRole('combobox', { name: '语言' })).toHaveValue('auto')
  languages = ['es-MX']
  fireEvent(window, new Event('languagechange'))
  expect(document.documentElement.lang).toBe('es')
  fireEvent.change(screen.getByRole('combobox', { name: 'Idioma' }), { target: { value: 'zh-CN' } })
  languages = ['en-US']
  fireEvent(window, new Event('languagechange'))
  expect(document.documentElement.lang).toBe('zh-CN')
  app.unmount()
  render(<App />)
  expect(document.documentElement.lang).toBe('zh-CN')
  expect(screen.getByRole('combobox', { name: '语言' })).toHaveValue('zh-CN')
  fireEvent.change(screen.getByRole('combobox', { name: '语言' }), { target: { value: 'auto' } })
  expect(document.documentElement.lang).toBe('en')
  expect(JSON.parse(localStorage.getItem('gaswise.prefs.v1')!).locale).toBeNull()
})

describe('service integration', () => {
  it('supports all payment conditions and defaults legacy preferences to Google Maps', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(() => response(fixture))
    render(<App />)
    await screen.findByRole('heading', { name: 'Chevron', level: 2 })
    expect(screen.getByRole('link', { name: 'Navigate' })).toHaveAttribute('href', expect.stringContaining('google.com/maps/dir/'))
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
    fireEvent.click(screen.getByRole('radio', { name: 'All' }))
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    expect(fetch.mock.calls[1][0]).toBe('/api/v1/smart/rerank')
    expect(JSON.parse(String(fetch.mock.calls[1][1]?.body)).options.payment_type).toBe('cash_or_credit')
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body)).route_limit).toBe(20)
  })

  it('keeps the fuel snapshot while switching to parts and back', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(() => response(fixture))
    render(<App />)
    await screen.findByRole('heading', { name: 'Chevron', level: 2 })
    fireEvent.click(screen.getByRole('tab', { name: 'Car parts' }))
    expect(screen.getByRole('heading', { name: 'Find the right fit for your car' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: 'Save on fuel' }))
    expect(screen.getByRole('heading', { name: 'Chevron', level: 2 })).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('shows real rating fields and opens a station drawer', async () => {
    const data = structuredClone(fixture)
    const station = data.ranking.recommendations.best_value.station
    Object.assign(station, { rating: 4.2, review_count: 315, rating_source: 'Google Maps' })
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => response(data))
    render(<App />)
    await screen.findByRole('heading', { name: 'Chevron', level: 2 })
    fireEvent.click(screen.getByRole('button', { name: 'View details' }))
    const drawer = screen.getByRole('dialog', { name: 'Station details' })
    expect(within(drawer).getByText('4.2 · 315 reviews')).toBeInTheDocument()
    expect(within(drawer).getByText(/Customer rating from Google Maps/)).toBeInTheDocument()
    expect(within(drawer).getByText(/Price payment terms/)).toBeInTheDocument()
    fireEvent.click(within(drawer).getByRole('button', { name: 'Close' }))
    expect(drawer).not.toBeVisible()
  })

  it('applies a validated destination to a fresh on-route search', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(() => response(fixture))
    render(<App />)
    await screen.findByRole('heading', { name: 'Chevron', level: 2 })
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
    fireEvent.click(screen.getByRole('radio', { name: 'On my route' }))
    fireEvent.click(screen.getByRole('button', { name: 'Apply trip' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a valid latitude')
    expect(fetch).toHaveBeenCalledTimes(1)
    fireEvent.change(screen.getByRole('textbox', { name: 'Destination latitude' }), { target: { value: '34.1' } })
    fireEvent.change(screen.getByRole('textbox', { name: 'Destination longitude' }), { target: { value: '-118.3' } })
    fireEvent.click(screen.getByRole('button', { name: 'Apply trip' }))
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    expect(JSON.parse(String(fetch.mock.calls[1][1]?.body))).toMatchObject({ trip_mode: 'on_route', destination: { lat: 34.1, lng: -118.3 } })
    expect(JSON.parse(localStorage.getItem('gaswise.prefs.v1')!).destination).toBeNull()
  })

  it('resolves VIN configuration choices without persisting VIN', async () => {
    const changed = vi.fn()
    const fetch = vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => response({ status: 'needs_input', decoded, choices: [{ value: '12345', label: 'Accord Coupe · 2.4 L · Automatic 5-spd · Front-Wheel Drive' }] }))
      .mockImplementationOnce(() => response({ status: 'resolved', decoded, choices: [], vehicle: car }))
    render(english(<VehiclePicker vehicle={null} onChange={changed} />))
    fireEvent.click(screen.getByRole('radio', { name: 'VIN' }))
    fireEvent.change(screen.getByRole('textbox', { name: '17-character VIN' }), { target: { value: vin } })
    fireEvent.click(screen.getByRole('button', { name: 'Find' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Accord Coupe · 2.4 L · Automatic 5-spd · Front-Wheel Drive' }))
    await waitFor(() => expect(changed).toHaveBeenCalledWith(expect.objectContaining({ id: 12345, fuelType: 'regular' })))
    expect(fetch.mock.calls[1][0]).toBe('/api/v1/vehicles/vin')
    expect(JSON.parse(String(fetch.mock.calls[1][1]?.body))).toMatchObject({ vin, vehicle_id: 12345 })
    expect(localStorage.getItem('gaswise.prefs.v1')).not.toContain(vin)
  })

  it('sends normalized state and plate to the plate service', async () => {
    const changed = vi.fn()
    const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(() => response({ resolution: { status: 'resolved', decoded, choices: [], vehicle: car } }))
    render(english(<VehiclePicker vehicle={null} onChange={changed} />))
    fireEvent.click(screen.getByRole('radio', { name: 'Plate' }))
    fireEvent.change(screen.getByRole('textbox', { name: 'License plate' }), { target: { value: 'abc 123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Find' }))
    await waitFor(() => expect(changed).toHaveBeenCalled())
    expect(fetch.mock.calls[0][0]).toBe('/api/v1/vehicles/plate')
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({ state: 'CA', plate: 'ABC123' })
  })

  it.each([
    ['compatible', 'Verified fit'],
    ['incompatible', 'Does not fit; do not use'],
    ['needs_confirmation', 'More verification needed'],
    ['conflict', 'Sources disagree; do not install yet'],
  ])('renders a parts %s decision without promoting uncertainty', async (status, label) => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(() => response({ status, fitment_confirmed: status === 'compatible', vehicle: decoded, amazon_url: 'https://www.amazon.com/dp/B019IPTB0W', title: 'Sample filter', evidence: [], warnings: [], reasons: [] }))
    render(english(<VehicleIdentityContext.Provider value={{ identity: { kind: 'vin', value: { vin } }, setIdentity: () => {} }}><Parts vehicle={null} onChooseCar={() => {}} /></VehicleIdentityContext.Provider>))
    fireEvent.click(screen.getByRole('radio', { name: 'Check a product link' }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Amazon US product URL' }), { target: { value: 'https://www.amazon.com/dp/B019IPTB0W' } })
    expect(fetch).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Check fitment' }))
    expect(await screen.findByRole('heading', { name: label })).toBeInTheDocument()
    expect(fetch.mock.calls[0][0]).toBe('/api/v1/parts/fitment')
    expect(localStorage.getItem('gaswise.prefs.v1')).not.toContain(vin)
  })
})

it('searches the car catalogue and shows only verified native fits as compatible', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(() => response({ keyword: 'oil filter', vehicle: decoded, source_status: 'ok', items: [
    { name: 'Sample verified filter', brand: 'Test', part_number: '123', product_url: 'https://www.autozone.com/p/test-filter/111', status: 'compatible', evidence: { status: 'matched', detail: 'Exact vehicle match' } },
    { name: 'Unresolved filter', brand: 'Test', part_number: '456', product_url: 'https://www.autozone.com/p/test-filter/222', status: 'needs_confirmation', evidence: { status: 'conditional', detail: 'Confirmation needed' } },
  ] }))
  render(english(<VehicleIdentityContext.Provider value={{ identity: { kind: 'vin', value: { vin } }, setIdentity: () => {} }}><Parts vehicle={null} onChooseCar={() => {}} /></VehicleIdentityContext.Provider>))
  fireEvent.click(screen.getByRole('button', { name: 'Find suitable parts' }))
  expect(await screen.findByRole('heading', { name: '1 verified fits among 2 checked candidates' })).toBeInTheDocument()
  expect(screen.getByText('Verified fit')).toBeInTheDocument()
  expect(screen.getByText('More verification needed')).toBeInTheDocument()
  expect(fetch.mock.calls[0][0]).toBe('/api/v1/parts/search')
  expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toMatchObject({ keyword: 'oil filter', max_results: 6, vin: { vin } })
})


it('keeps stale costs labeled with their actual gallons when a snapshot expires', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => response(fixture))
    .mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ detail: 'snapshot_expired' }), { status: 409 })))
  render(<App />)
  await screen.findByRole('heading', { name: 'Chevron', level: 2 })
  fireEvent.click(screen.getByRole('button', { name: 'Increase gallons' }))
  await screen.findByText(/These prices expired/)
  expect(within(screen.getByRole('region', { name: 'Chevron' })).getByText(/Total for 10 gal/)).toBeInTheDocument()
})

it('uses a chosen ZIP location after a device location timeout', async () => {
  Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition: (_ok: PositionCallback, fail: PositionErrorCallback) => fail({ code: 3 } as GeolocationPositionError) } })
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => response(String(url).includes('locations/resolve') ? { candidates: [{ id: 'zip', label: 'Los Angeles, CA 90015, USA', location: { lat: 34.04, lng: -118.27 } }] } : fixture))
  render(<App />)
  await screen.findByRole('heading', { name: 'Location request timed out' })
  fireEvent.change(screen.getByRole('textbox', { name: 'Address, city or US ZIP code' }), { target: { value: '90015' } })
  fireEvent.click(screen.getByRole('button', { name: 'Find' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Los Angeles, CA 90015, USA' }))
  await screen.findByRole('heading', { name: 'Chevron', level: 2 })
  expect(JSON.parse(String(fetch.mock.calls[1][1]?.body)).origin).toEqual({ lat: 34.04, lng: -118.27 })
  expect(localStorage.getItem('gaswise.prefs.v1')).not.toContain('90015')
})

it('sets one shared vehicle in settings and uses it in the parts tab', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => response(String(url).includes('vehicles/vin') ? { status: 'resolved', decoded, choices: [], vehicle: car } : String(url).includes('parts/search') ? { keyword: 'oil filter', vehicle: decoded, source_status: 'ok', items: [] } : fixture))
  render(<App />)
  await screen.findByRole('heading', { name: 'Chevron', level: 2 })
  fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
  fireEvent.click(screen.getByRole('radio', { name: 'VIN' }))
  fireEvent.change(screen.getByRole('textbox', { name: '17-character VIN' }), { target: { value: vin } })
  fireEvent.click(screen.getByRole('button', { name: 'Find' }))
  await within(screen.getByRole('main', { name: 'Settings' })).findByText('2003 Honda Accord')
  fireEvent.click(screen.getByRole('button', { name: 'Back' }))
  fireEvent.click(screen.getByRole('tab', { name: 'Car parts' }))
  expect(screen.queryByRole('textbox', { name: '17-character VIN' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Find suitable parts' }))
  await screen.findByRole('heading', { name: '0 verified fits among 0 checked candidates' })
  const call = fetch.mock.calls.find(([url]) => String(url).includes('/parts/search'))!
  expect(JSON.parse(String(call[1]?.body)).vin).toEqual({ vin, vehicle_id: 12345 })
})

it('does not let a late GPS response replace the manually chosen location', async () => {
  let finishGPS: PositionCallback | undefined
  Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition: (ok: PositionCallback) => { finishGPS = ok } } })
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => response(String(url).includes('locations/resolve') ? { candidates: [{ id: 'zip', label: 'Chosen ZIP', location: { lat: 34.04, lng: -118.27 } }] } : fixture))
  render(<App />)
  await waitFor(() => expect(finishGPS).toBeDefined())
  fireEvent.click(screen.getByRole('button', { name: 'Search location' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Address, city or US ZIP code' }), { target: { value: '90015' } })
  fireEvent.click(screen.getByRole('button', { name: 'Find' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Chosen ZIP' }))
  await screen.findByRole('heading', { name: 'Chevron', level: 2 })
  finishGPS!({ coords: { latitude: 10, longitude: 20 } } as GeolocationPosition)
  await waitFor(() => expect(screen.getByText('Chosen ZIP')).toBeInTheDocument())
  expect(fetch.mock.calls.filter(([url]) => String(url).includes('smart/search'))).toHaveLength(1)
})

it('requests GPS on a tap without waiting for the permissions query', async () => {
  const locate = vi.fn((ok: PositionCallback) => ok({ coords: { latitude: 34, longitude: -118 } } as GeolocationPosition))
  Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition: locate } })
  const query = vi.fn().mockResolvedValueOnce({ state: 'prompt' }).mockImplementation(() => new Promise(() => {}))
  Object.defineProperty(navigator, 'permissions', { configurable: true, value: { query } })
  vi.spyOn(globalThis, 'fetch').mockImplementation(() => response(fixture))
  render(<App />)
  await screen.findByText('Waiting for browser location permission')
  expect(locate).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Use current location' }))
  expect(locate).toHaveBeenCalledTimes(1)
  await screen.findByRole('heading', { name: 'Chevron', level: 2 })
})

it('keeps the selected address and fuel result when GPS fails', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation((url) => response(String(url).includes('locations/resolve') ? { candidates: [{ id: 'zip', label: 'Chosen ZIP', location: { lat: 34.04, lng: -118.27 } }] } : fixture))
  render(<App />)
  await screen.findByRole('heading', { name: 'Chevron', level: 2 })
  fireEvent.click(screen.getByRole('button', { name: 'Search location' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Address, city or US ZIP code' }), { target: { value: '90015' } })
  fireEvent.click(screen.getByRole('button', { name: 'Find' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Chosen ZIP' }))
  await screen.findByRole('heading', { name: 'Chevron', level: 2 })
  Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition: (_ok: PositionCallback, fail: PositionErrorCallback) => fail({ code: 3 } as GeolocationPositionError) } })
  fireEvent.click(screen.getByRole('button', { name: 'Use current location' }))
  await screen.findByText(/Keeping your previous search location/)
  expect(screen.getByRole('heading', { name: 'Chevron', level: 2 })).toBeInTheDocument()
  expect(screen.getByText('Chosen ZIP')).toBeInTheDocument()
})


it('opens settings as a page and preserves the fuel session on return', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(() => response(fixture))
  render(<App />)
  await screen.findByRole('heading', { name: 'Chevron', level: 2 })
  const summary = screen.getByRole('button', { name: /Manual fuel and mileage settings.*Details/ })
  expect(summary).toHaveAttribute('aria-expanded', 'false')
  fireEvent.click(summary)
  expect(screen.getByRole('button', { name: 'Edit vehicle' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
  expect(screen.getByRole('main', { name: 'Settings' })).toBeInTheDocument()
  expect(screen.queryByRole('dialog', { name: 'Settings' })).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Chevron', level: 2 })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Back' }))
  expect(screen.getByRole('heading', { name: 'Chevron', level: 2 })).toBeInTheDocument()
  expect(fetch).toHaveBeenCalledTimes(1)
  const body = JSON.parse(String(fetch.mock.calls[0][1]?.body))
  expect(body).toMatchObject({ opening_policy: 'require_open', discovery_tiles: 20, maps_detail_limit: 5, route_limit: 20, estimate_unrouted_routes: true, max_results: 100, allow_unknown_payment: true, unknown_payment_credit_markup: '0.20' })
})

 it('places compact TOP TIER next to the name and reports quote age rather than collection freshness', () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-12T16:30:00Z'))
  try {
    const rows = structuredClone(fixture.ranking.results) as unknown as RankedStation[]
    rows[0].station.source = 'google_maps_web'
    rows[0].station.top_tier_brand = 'Chevron'
    rows[0].station.price_updated_at = '2026-10-11T21:30:00Z'
    rows[0].station.fetched_at = '2026-10-12T16:30:00Z'
    render(english(<StationList rows={rows} />))
    fireEvent.click(screen.getByRole('button', { name: /Compare/ }))
    const name = screen.getByRole('button', { name: `View details ${rows[0].station.name}` })
    expect(within(name.parentElement!).getByText('TOP TIER')).toBeInTheDocument()
    expect(within(name.closest('td')!).getByLabelText('Price source: Google Maps')).toBeInTheDocument()
    expect(screen.getByText(/19 h ago/)).toBeInTheDocument()
    expect(screen.queryByText(/updated today/i)).not.toBeInTheDocument()
  } finally { vi.useRealTimers() }
 })

it('switches cash/card on the main screen through rerank, without acquiring prices again', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(() => response(fixture))
  render(<App />)
  await screen.findByRole('heading', {name:'Chevron',level:2})
  fireEvent.click(screen.getByRole('radio',{name:'Cash'}))
  await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(2))
  expect(fetch.mock.calls[1][0]).toBe('/api/v1/smart/rerank')
  expect(JSON.parse(String(fetch.mock.calls[1][1]?.body)).options.payment_type).toBe('cash')
  fireEvent.click(screen.getByRole('radio',{name:'Card'}))
  await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(3))
  expect(fetch.mock.calls[2][0]).toBe('/api/v1/smart/rerank')
  expect(JSON.parse(String(fetch.mock.calls[2][1]?.body)).options.payment_type).toBe('credit')
})

it('shows both recovered payment quotes and closure evidence without a navigation recommendation', () => {
  const result = structuredClone(fixture) as unknown as import('../api/types').SmartResult
  const station = {...result.snapshot.stations[0],name:'C.T. Truck Stop',source:'gasbuddy_web',canonical_id:'google_places:closed',payment_type:'credit' as const,price_per_gallon:'6.37',open_now:false,business_status:'permanently_closed' as const,details:{location_source_name:'Shell'}}
  result.snapshot.stations = [station,{...station,payment_type:'cash',price_per_gallon:'6.17'}]
  result.snapshot.unlocated_gasbuddy = []
  render(english(<ExcludedStations records={[[station.canonical_id,station]]} result={result} />))
  expect(screen.getByText('C.T. Truck Stop')).toBeInTheDocument()
  expect(screen.getByText('Google Maps · Shell')).toBeInTheDocument()
  expect(screen.getByText('Cash $6.17')).toBeInTheDocument()
  expect(screen.getByText('Card $6.37')).toBeInTheDocument()
  expect(screen.queryByRole('link',{name:/Navigate/})).not.toBeInTheDocument()
})


it('does not restore a cleared identity from an outstanding vehicle lookup', async () => {
  let finish!: (value: Response) => void
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise<Response>(resolve => { finish = resolve }))
  const save = vi.fn()
  const update = vi.fn()
  const picker = render(english(<VehicleIdentityContext.Provider value={{identity:null,setIdentity:save}}><VehiclePicker vehicle={null} onChange={update} /></VehicleIdentityContext.Provider>))
  fireEvent.click(screen.getByRole('radio', { name: 'VIN' }))
  fireEvent.change(screen.getByRole('textbox', { name: '17-character VIN' }), { target: { value: vin } })
  fireEvent.click(screen.getByRole('button', { name: 'Find' }))
  expect(fetch).toHaveBeenCalledTimes(1)
  picker.unmount() // Clearing private data remounts the picker and discards its draft.
  await act(async () => { finish(new Response(JSON.stringify({status:'resolved',vehicle:car}))) })
  expect(save).not.toHaveBeenCalled()
  expect(update).not.toHaveBeenCalled()
})
