import { act, renderHook } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { DEFAULT_PREFS } from './prefs'
import { useFuelSession } from './session'
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
