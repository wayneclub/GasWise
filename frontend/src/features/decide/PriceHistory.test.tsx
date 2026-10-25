import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import { I18nProvider } from '../../i18n/I18nProvider'
import { PriceHistory } from './PriceHistory'
const station = { id: 'one', source: 'waze', name: 'Test', location: { lat: 34, lng: -118 }, fuel_type: 'regular' as const }
const observation = { observation_kind: 'report' as const, source: 'waze', station_id: 'one', payment_type: 'cash', condition: 'normal', price: '4.199', reported_at: '2026-10-12T12:00:00Z', observed_at: '2026-10-12T12:01:00Z', membership: null, octane: null }
afterEach(() => vi.restoreAllMocks())
const show = () => render(<I18nProvider locale="en"><PriceHistory station={station} /></I18nProvider>)
it('loads only on expansion and keeps payment and membership series separate', async () => {
  const fetch = vi.spyOn(api, 'priceHistory').mockResolvedValue({ truncated: false, observations: [observation, { ...observation, price: '4.099', reported_at: '2026-10-10T12:00:00Z' }, { ...observation, payment_type: 'credit', price: '4.999' }, { ...observation, condition: 'member', membership: 'Club', price: '3.999' }] })
  show()
  expect(fetch).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: /Price history/ }))
  fireEvent.click(await screen.findByRole('button', { name: 'Source / payment / conditions' }))
  expect(screen.getAllByRole('option')).toHaveLength(3)
  expect(screen.getByText('+$0.10')).toBeInTheDocument()
  expect(screen.queryByText('$4.999')).not.toBeInTheDocument()
  fireEvent.click(screen.getAllByRole('option')[1])
  expect(screen.getByText(/One observation only/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '7 days' }))
  await waitFor(() => expect(fetch).toHaveBeenLastCalledWith(expect.objectContaining({ days: 7 }), expect.any(AbortSignal)))
})
it('distinguishes missing history from a failed request and allows retry', async () => {
  vi.spyOn(api, 'priceHistory').mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ observations: [], truncated: false })
  show(); fireEvent.click(screen.getByRole('button', { name: /Price history/ }))
  await screen.findByText('History is temporarily unavailable.')
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByText(/No observations in this period yet/)).toBeInTheDocument()
})
it('plots real daily checks separately while retaining the original source report time', async () => {
  vi.spyOn(api, 'priceHistory').mockResolvedValue({ truncated: false, observations: [
    { ...observation, observation_kind: 'daily_check', observed_at: '2026-10-13T12:00:00Z' },
    { ...observation, observation_kind: 'daily_check', observed_at: '2026-10-15T12:00:00Z' },
  ] })
  show(); fireEvent.click(screen.getByRole('button', { name: /Price history/ }))
  const chart = await screen.findByRole('img', { name: 'Recorded price observations over time' })
  const circles = chart.querySelectorAll('circle')
  expect(circles).toHaveLength(2)
  expect(circles[0].getAttribute('cx')).not.toBe(circles[1].getAttribute('cx'))
  expect(screen.getByText('View 2 observations')).toBeInTheDocument()
  expect(screen.getAllByText(/Source reported:/)).toHaveLength(2)
  expect(screen.getByText('$0.00')).toBeInTheDocument()
})
