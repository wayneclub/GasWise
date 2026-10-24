import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { SmartResult } from '../../api/types'
import fixture from '../../test/fixtures/demo-search.json'
import { SearchFallback } from './SearchFallback'

function emptyResult() {
  const result = structuredClone(fixture) as unknown as SmartResult
  result.snapshot.stations = []
  result.snapshot.inventory = []
  result.ranking!.results = []
  result.snapshot.source_statuses = [{ source: 'google_maps_web', status: 'ok', quote_count: 0 }]
  return result
}

it('distinguishes a completed empty search and offers explicit radius choices', () => {
  const onRadius = vi.fn()
  render(<SearchFallback result={emptyResult()} completing={false} radius={5} navApp="google" onRadius={onRadius} onRetry={vi.fn()} />)
  expect(screen.getByText('No eligible live fuel prices nearby')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Expand to 10 miles' }))
  fireEvent.click(screen.getByRole('button', { name: 'Expand to 20 miles' }))
  expect(onRadius.mock.calls).toEqual([[10], [20]])
  expect(screen.queryByRole('link', { name: 'Navigate' })).not.toBeInTheDocument()
})

it('shows real unpriced inventory with navigation without inventing a price', () => {
  const result = emptyResult()
  result.snapshot.inventory = [{ place_id: 'rural-1', name: 'Small Town Fuel', address: '1 Main St', location: { lat: 34, lng: -118 }, available_fuel_types: [], distance_meters: 0 }]
  render(<SearchFallback result={result} completing={false} radius={10} navApp="google" onRadius={vi.fn()} onRetry={vi.fn()} />)
  expect(screen.getByText('Small Town Fuel')).toBeInTheDocument()
  expect(screen.getByText('Price not reported')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Navigate' })).toHaveAttribute('href', expect.stringContaining('destination=34,-118'))
  expect(screen.queryByRole('button', { name: 'Expand to 10 miles' })).not.toBeInTheDocument()
})

it('labels old source prices and source failures independently', () => {
  const result = emptyResult()
  const station = structuredClone((fixture as unknown as SmartResult).snapshot.stations[0])
  station.price_updated_at = '2020-01-01T00:00:00Z'
  result.snapshot.stations = [station]
  result.snapshot.source_statuses = [{ source: 'waze', status: 'unavailable', detail: 'timeout', quote_count: 0 }]
  render(<SearchFallback result={result} completing={false} radius={20} navApp="google" onRadius={vi.fn()} onRetry={vi.fn()} />)
  expect(screen.getByText(/Expired report/)).toBeInTheDocument()
  expect(screen.getByText('Some price sources could not be reached')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
})

it('keeps partial empty data in a completing state until all sources settle', () => {
  render(<SearchFallback result={emptyResult()} completing radius={5} navApp="google" onRadius={vi.fn()} onRetry={vi.fn()} />)
  expect(screen.getByText('Filling in live fuel prices')).toBeInTheDocument()
  expect(screen.queryByText('No eligible live fuel prices nearby')).not.toBeInTheDocument()
})
