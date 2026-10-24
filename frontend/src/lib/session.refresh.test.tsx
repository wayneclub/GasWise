import { act, renderHook } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { DEFAULT_PREFS, loadPrefs } from './prefs'
import { haversineDistanceMeters, useFuelSession } from './session'
import fixture from '../test/fixtures/demo-search.json'

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks() })

it('refreshes visible prices on the interval, pauses hidden tabs, and bypasses prices on manual refresh', async () => {
  vi.useFakeTimers()
  const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true)
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify(fixture)))
  const session = renderHook(() => useFuelSession(DEFAULT_PREFS))
  await act(async () => session.result.current.start({ override: {lat:34,lng:-118} }))
  expect(fetch).toHaveBeenCalledTimes(1)
  await act(async () => vi.advanceTimersByTimeAsync(120000))
  expect(fetch).toHaveBeenCalledTimes(2)
  expect(JSON.parse(String(fetch.mock.calls[1][1]?.body)).force_refresh).toBe(false)
  visibility.mockReturnValue('hidden')
  await act(async () => vi.advanceTimersByTimeAsync(240000))
  expect(fetch).toHaveBeenCalledTimes(2)
  visibility.mockReturnValue('visible')
  await act(async () => document.dispatchEvent(new Event('visibilitychange')))
  expect(fetch).toHaveBeenCalledTimes(3)
  await act(async () => session.result.current.refresh())
  expect(JSON.parse(String(fetch.mock.calls[3][1]?.body)).force_refresh).toBe(true)
  session.unmount()
  await act(async () => vi.advanceTimersByTimeAsync(600000))
  expect(fetch).toHaveBeenCalledTimes(4)
})

it('keeps the displayed snapshot on update failure and backs off instead of looping', async () => {
  vi.useFakeTimers()
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify(fixture))).mockImplementation(async () => new Response(JSON.stringify({detail:'temporarily_unavailable'}),{status:503}))
  const session = renderHook(() => useFuelSession(DEFAULT_PREFS))
  await act(async () => session.result.current.start({ override: {lat:34,lng:-118} }))
  await act(async () => vi.advanceTimersByTimeAsync(120000))
  expect(fetch).toHaveBeenCalledTimes(2)
  expect(session.result.current.phase).toBe('ready')
  expect(session.result.current.result?.signature).toBe(fixture.signature)
  expect(session.result.current.error?.code).toBe('temporarily_unavailable')
  await act(async () => vi.advanceTimersByTimeAsync(120000))
  expect(fetch).toHaveBeenCalledTimes(2)
  await act(async () => vi.advanceTimersByTimeAsync(120000))
  expect(fetch).toHaveBeenCalledTimes(3)
})

it('pauses price polling when the fuel page is not the active service', async () => {
  vi.useFakeTimers()
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify(fixture)))
  const session = renderHook(({active}) => useFuelSession(DEFAULT_PREFS,active), {initialProps:{active:true}})
  await act(async () => session.result.current.start({override:{lat:34,lng:-118}}))
  session.rerender({active:false})
  await act(async () => vi.advanceTimersByTimeAsync(360000))
  expect(fetch).toHaveBeenCalledTimes(1)
  await act(async () => session.rerender({active:true}))
  expect(fetch).toHaveBeenCalledTimes(2)
})

it('restores a reloaded tab without another search and keeps the manual location label', async () => {
  const current = structuredClone(fixture)
  current.snapshot.expires_at = new Date(Date.now() + 600000).toISOString()
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify(current)))
  const first = renderHook(() => useFuelSession(DEFAULT_PREFS))
  await act(async () => first.result.current.start({ override: { lat: 34, lng: -118 }, label: 'Pasadena, CA' }))
  first.unmount()
  const restored = renderHook(() => useFuelSession(DEFAULT_PREFS))
  expect(restored.result.current.phase).toBe('ready')
  expect(restored.result.current.origin).toEqual({ lat: 34, lng: -118 })
  expect(restored.result.current.originKind).toBe('manual')
  expect(restored.result.current.originLabel).toBe('Pasadena, CA')
  expect(restored.result.current.result).toEqual(current)
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(localStorage.getItem('gaswise.fuel-session.v1')).toBeNull()
})

it('restores expired results while refreshing in the background and preserves them if offline', async () => {
  vi.useFakeTimers()
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true)
  const current = structuredClone(fixture)
  current.snapshot.expires_at = new Date(Date.now() + 600000).toISOString()
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify(current)))
    .mockRejectedValue(new Error('offline'))
  const first = renderHook(() => useFuelSession(DEFAULT_PREFS))
  await act(async () => first.result.current.start({ override: { lat: 34, lng: -118 } }))
  first.unmount()
  await act(async () => vi.advanceTimersByTimeAsync(660000))
  const restored = renderHook(() => useFuelSession(DEFAULT_PREFS))
  await act(async () => {})
  expect(fetch).toHaveBeenCalledTimes(2)
  expect(restored.result.current.phase).toBe('ready')
  expect(restored.result.current.expired).toBe(true)
  expect(restored.result.current.result).toEqual(current)
  expect(restored.result.current.error?.code).toBe('network_unavailable')
})

it('does not restore results for a different fuel search', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify(fixture)))
  const first = renderHook(() => useFuelSession(DEFAULT_PREFS))
  await act(async () => first.result.current.start({ override: { lat: 34, lng: -118 } }))
  first.unmount()
  const restored = renderHook(() => useFuelSession({ ...DEFAULT_PREFS, fuelType: 'diesel' }))
  expect(restored.result.current.phase).toBe('idle')
  expect(restored.result.current.result).toBeNull()
  expect(fetch).toHaveBeenCalledTimes(1)
})

it('discards recovery data after 30 minutes', async () => {
  vi.useFakeTimers()
  vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify(fixture)))
  const first = renderHook(() => useFuelSession(DEFAULT_PREFS))
  await act(async () => first.result.current.start({ override: { lat: 34, lng: -118 } }))
  first.unmount()
  await act(async () => vi.advanceTimersByTimeAsync(1800001))
  const restored = renderHook(() => useFuelSession(DEFAULT_PREFS))
  expect(restored.result.current.result).toBeNull()
  expect(sessionStorage.getItem('gaswise.fuel-session.v1')).toBeNull()
})

it('continues searching when browser storage is blocked', async () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => { throw new Error('blocked') })
  vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify(fixture)))
  const session = renderHook(() => useFuelSession(DEFAULT_PREFS))
  await act(async () => session.result.current.start({ override: { lat: 34, lng: -118 } }))
  expect(session.result.current.phase).toBe('ready')
})

it('ignores corrupt recovery data', () => {
  sessionStorage.setItem('gaswise.fuel-session.v1', '{broken')
  const session = renderHook(() => useFuelSession(DEFAULT_PREFS))
  expect(session.result.current.phase).toBe('idle')
  expect(sessionStorage.getItem('gaswise.fuel-session.v1')).toBeNull()
})

it('restores the route destination from tab recovery without long-lived location storage', async () => {
  const destination = { lat: 34.1, lng: -118.1 }
  const prefs = { ...DEFAULT_PREFS, tripMode: 'on_route' as const, destination }
  const current = structuredClone(fixture)
  Object.assign(current.snapshot.query, { trip_mode: 'on_route', destination })
  current.snapshot.expires_at = new Date(Date.now() + 600000).toISOString()
  vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify(current)))
  const first = renderHook(() => useFuelSession(prefs))
  await act(async () => first.result.current.start({ override: { lat: 34, lng: -118 } }))
  first.unmount()
  expect(loadPrefs().tripMode).toBe('on_route')
  expect(loadPrefs().destination).toEqual(destination)
  expect(localStorage.getItem('gaswise.fuel-session.v1')).toBeNull()
})

it('accurately computes Haversine distance between two coordinates', () => {
  // ~111km per latitude degree
  const p1 = { lat: 34.0, lng: -118.0 }
  const p2 = { lat: 34.005, lng: -118.0 } // ~556 meters north
  const dist = haversineDistanceMeters(p1, p2)
  expect(dist).toBeGreaterThan(550)
  expect(dist).toBeLessThan(560)
})

it('updates dynamic routes and rankings in background when device location moves past threshold', async () => {
  let watchCallback: ((pos: GeolocationPosition) => void) | null = null
  let clearWatchCalled = false

  Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true })
  Object.defineProperty(navigator, 'geolocation', {
    configurable: true,
    value: {
      getCurrentPosition: (ok: PositionCallback) =>
        ok({ coords: { latitude: 34.0522, longitude: -118.2437 } } as GeolocationPosition),
      watchPosition: vi.fn((ok: PositionCallback) => {
        watchCallback = ok
        return 99
      }),
      clearWatch: vi.fn((id: number) => {
        if (id === 99) clearWatchCalled = true
      }),
    },
  })
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')

  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify(fixture)))
  const session = renderHook(() => useFuelSession(DEFAULT_PREFS))

  await act(async () => session.result.current.start({ userInitiated: true }))
  expect(session.result.current.phase).toBe('ready')
  expect(fetchMock).toHaveBeenCalledTimes(1)
  expect(watchCallback).not.toBeNull()

  // Small drift (< 400m): ~10 meters east -> should NOT trigger background fetch
  await act(async () => {
    watchCallback?.({ coords: { latitude: 34.0522, longitude: -118.2436 } } as GeolocationPosition)
  })
  expect(fetchMock).toHaveBeenCalledTimes(1)

  // Significant movement (> 400m): ~600 meters north -> triggers background fetch
  await act(async () => {
    watchCallback?.({ coords: { latitude: 34.0576, longitude: -118.2437 } } as GeolocationPosition)
  })
  expect(fetchMock).toHaveBeenCalledTimes(2)
  // Background fetch does not force refresh provider cache, uses background mode
  expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body)).origin).toEqual({ lat: 34.0576, lng: -118.2437 })

  session.unmount()
  expect(clearWatchCalled).toBe(true)
})
