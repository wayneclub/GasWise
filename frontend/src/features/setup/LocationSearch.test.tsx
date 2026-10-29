import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import { I18nProvider } from '../../i18n/I18nProvider'
import { LocationSearch } from './LocationSearch'
import type { Origin } from '../../lib/session'

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
})

function search(onChoose: (location: Origin, label: string) => void, query = '90015') {
  render(<I18nProvider locale="en"><LocationSearch onChoose={onChoose} /></I18nProvider>)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: query } })
  fireEvent.click(screen.getByRole('button', { name: 'Find' }))
}

it('applies the only resolved US location with one search submission', async () => {
  const candidate = { id: 'ny', label: 'New York, NY 10001, USA', location: { lat: 40.75, lng: -73.99 } }
  vi.spyOn(api, 'resolveLocation').mockResolvedValue({ candidates: [candidate], source: 'google_maps_web' })
  const choose = vi.fn()
  search(choose, '10001')
  await waitFor(() => expect(choose).toHaveBeenCalledExactlyOnceWith(candidate.location, candidate.label))
})

it('requires an explicit choice when the provider returns multiple locations', async () => {
  const candidates = [
    { id: 'il', label: 'Springfield, IL, USA', location: { lat: 39.8, lng: -89.65 } },
    { id: 'ma', label: 'Springfield, MA, USA', location: { lat: 42.1, lng: -72.59 } },
  ]
  vi.spyOn(api, 'resolveLocation').mockResolvedValue({ candidates, source: 'google_maps_web' })
  const choose = vi.fn()
  search(choose, 'Springfield')
  const option = await screen.findByRole('button', { name: candidates[1].label })
  expect(choose).not.toHaveBeenCalled()
  fireEvent.click(option)
  expect(choose).toHaveBeenCalledExactlyOnceWith(candidates[1].location, candidates[1].label)
})

it('says the area is unsupported when only places outside the US match', async () => {
  vi.spyOn(api, 'resolveLocation').mockResolvedValue({ candidates: [], reason: 'unsupported_area', source: 'google_maps_web' })
  search(vi.fn(), 'Taipei')
  expect(await screen.findByRole('status')).toHaveTextContent('Only US locations are supported')
})

it('accepts two-letter city and state abbreviations', async () => {
  const candidate = { id: 'ny', label: 'New York', location: { lat: 40.71, lng: -74.01 } }
  const resolve = vi.spyOn(api, 'resolveLocation').mockResolvedValue({ candidates: [candidate], source: 'google_maps_web' })
  const choose = vi.fn()
  search(choose, 'NY')
  await waitFor(() => expect(choose).toHaveBeenCalledExactlyOnceWith(candidate.location, candidate.label))
  expect(resolve).toHaveBeenCalledWith('NY', 'en', expect.any(AbortSignal))
})

it('passes current locale for native language resolution', async () => {
  const candidate = { id: 'la_dt', label: '洛杉磯市中心', location: { lat: 34.05, lng: -118.25 } }
  const resolve = vi.spyOn(api, 'resolveLocation').mockResolvedValue({ candidates: [candidate], source: 'google_maps_web' })
  const choose = vi.fn()
  render(<I18nProvider locale="zh-TW"><LocationSearch onChoose={choose} /></I18nProvider>)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'downtown la' } })
  fireEvent.click(screen.getByRole('button', { name: '搜尋' }))
  await waitFor(() => expect(choose).toHaveBeenCalledExactlyOnceWith(candidate.location, candidate.label))
  expect(resolve).toHaveBeenCalledWith('downtown la', 'zh-TW', expect.any(AbortSignal))
})

it('saves chosen location to recent searches and allows one-click re-selection', async () => {
  const candidate = { id: 'irvine', label: 'Irvine, CA, USA', location: { lat: 33.68, lng: -117.82 } }
  vi.spyOn(api, 'resolveLocation').mockResolvedValue({ candidates: [candidate], source: 'google_maps_web' })
  const choose = vi.fn()
  const { unmount } = render(<I18nProvider locale="en"><LocationSearch onChoose={choose} /></I18nProvider>)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Irvine' } })
  fireEvent.click(screen.getByRole('button', { name: 'Find' }))
  await waitFor(() => expect(choose).toHaveBeenCalledWith(candidate.location, candidate.label))
  unmount()

  // Render again: recent item should appear as a quick shortcut button
  const chooseSecond = vi.fn()
  render(<I18nProvider locale="en"><LocationSearch onChoose={chooseSecond} /></I18nProvider>)
  const recentBtn = await screen.findByRole('button', { name: /Irvine, CA, USA/ })
  fireEvent.click(recentBtn)
  expect(chooseSecond).toHaveBeenCalledWith(candidate.location, candidate.label)
})
