import { fireEvent, render, screen, within } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { RankedStation } from '../../api/types'
import fixture from '../../test/fixtures/demo-search.json'
import { StationList } from './StationList'

function rows(): RankedStation[] {
  return structuredClone(fixture.ranking.results).slice(0, 3).map((row, index) => {
    row.station.name = ['Low total', 'Quick stop', 'Low pump'][index]
    row.station.price_per_gallon = ['4.20', '4.30', '4.00'][index]
    delete (row.station as { comparison_price_per_gallon?: string }).comparison_price_per_gallon
    row.actual_fuel_cost = ['40.00', '42.05', '41.20'][index]
    row.extra_travel_minutes = ['8.00', '3.00', '10.00'][index]
    return row as unknown as RankedStation
  })
}
function bodyRows() {
  return [...screen.getByRole('table').querySelectorAll('tbody tr')]
}

it('opens with distinct money, time and pump-price winners and explicit comparison differences', () => {
  render(<StationList rows={rows()} />)
  expect(screen.getByRole('button', { name: 'Compare 3 stations' })).toHaveAttribute('aria-expanded', 'true')
  const [cheapest, pump, quick] = bodyRows()
  expect(within(cheapest as HTMLElement).getByText('Lowest total')).toBeInTheDocument()
  expect(within(quick as HTMLElement).getByText('Quickest')).toBeInTheDocument()
  expect(within(pump as HTMLElement).getByText('Lowest price')).toBeInTheDocument()
  expect(within(quick as HTMLElement).getByText('+$2.05 vs lowest')).toBeInTheDocument()
  expect(within(cheapest as HTMLElement).getByText('+5 min vs quickest')).toBeInTheDocument()
  expect(screen.getByText(/after cashback; time excluded/)).toBeInTheDocument()
})

it('sorts locally using the reusable custom selector without fetching or mutating input', () => {
  const data = rows()
  const before = structuredClone(data)
  const fetch = vi.spyOn(globalThis, 'fetch')
  render(<StationList rows={data} />)
  fireEvent.click(screen.getByRole('button', { name: 'Sort stations' }))
  fireEvent.click(screen.getByRole('option', { name: 'Quickest first' }))
  expect(bodyRows()[0]).toHaveTextContent('Quick stop')
  fireEvent.click(screen.getByRole('button', { name: 'Sort stations' }))
  fireEvent.click(screen.getByRole('option', { name: 'Lowest price first' }))
  expect(bodyRows()[0]).toHaveTextContent('Low pump')
  expect(fetch).not.toHaveBeenCalled()
  expect(data).toEqual(before)
  fetch.mockRestore()
})

it('keeps cost differences consistent with displayed cents and handles ties without inventing a winner', () => {
  const data = rows()
  data[0].actual_fuel_cost = '10.001'
  data[1].actual_fuel_cost = '10.004'
  data[2].actual_fuel_cost = '10.105'
  render(<StationList rows={data} />)
  expect(screen.getAllByText('Lowest total')).toHaveLength(2)
  expect(screen.getByText('+$0.11 vs lowest')).toBeInTheDocument()
  expect(screen.queryByText(/\+\$0.00/)).not.toBeInTheDocument()
})

it('compares actual travel times rather than declaring rounded minute values tied', () => {
  const data = rows()
  data[0].extra_travel_minutes = '3.10'
  data[1].extra_travel_minutes = '3.49'
  render(<StationList rows={data} />)
  expect(screen.getAllByText('Quickest')).toHaveLength(1)
  expect(screen.getByText('+<1 min vs quickest')).toBeInTheDocument()
})

it('does not turn missing or invalid values into free fuel, instant travel or winning labels', () => {
  const data = rows()
  Object.assign(data[0], { actual_fuel_cost: null, extra_travel_minutes: null })
  Object.assign(data[0].station, { price_per_gallon: 'NaN' })
  render(<StationList rows={data} />)
  const missing = bodyRows().find(row => row.textContent?.includes('Low total'))!
  expect(missing).not.toHaveTextContent('Lowest total')
  expect(missing).not.toHaveTextContent('Quickest')
  expect(missing).not.toHaveTextContent('$0.00')
  expect(missing).not.toHaveTextContent('NaN')
  expect(bodyRows().at(-1)).toBe(missing)
})

it('shows real zero costs instead of treating them as missing', () => {
  const data = rows()
  data[0].actual_fuel_cost = '0.00'
  render(<StationList rows={data} />)
  expect(within(bodyRows()[0] as HTMLElement).getByText('$0.00')).toBeInTheDocument()
  expect(within(bodyRows()[0] as HTMLElement).getByText('Lowest total')).toBeInTheDocument()
})

it('keeps payment estimates, unknown conditions, membership and estimated routing visible', () => {
  const data = rows()
  Object.assign(data[0].station, { payment_type: 'unknown', comparison_price_per_gallon: '4.40', membership_required: 'Costco' })
  data[0].route.source = 'straight_line_estimate'
  render(<StationList rows={data} tripMode="on_route" />)
  expect(screen.getAllByText('Extra driving time').length).toBeGreaterThan(0)
  expect(screen.queryByText('Round-trip time')).not.toBeInTheDocument()
  const station = within(bodyRows()[0] as HTMLElement)
  expect(station.getByText('$4.40')).toBeInTheDocument()
  expect(station.getByText('Estimated')).toBeInTheDocument()
  expect(station.getByText('Unconfirmed; check at the pump')).toBeInTheDocument()
  expect(station.getByText('Costco membership required')).toBeInTheDocument()
  expect(station.getByText('Estimated drive and cost')).toBeInTheDocument()
})

it('caps the initial comparison, retains hidden-row baselines, supports more and collapse', () => {
  const data = Array.from({ length: 8 }, (_, index) => {
    const row = structuredClone(rows()[0])
    row.station.name = `Station ${index}`
    row.actual_fuel_cost = String(index + 10)
    row.extra_travel_minutes = String(index === 7 ? 1 : index + 4)
    return row
  })
  render(<StationList rows={data} />)
  expect(bodyRows()).toHaveLength(5)
  expect(screen.queryByText('Quickest')).not.toBeInTheDocument()
  expect(screen.getByText('+3 min vs quickest')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Show more stations (3 remaining)' }))
  expect(bodyRows()).toHaveLength(8)
  expect(screen.getByText('Quickest')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Compare 8 stations' }))
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})

it('does not show a comparison with fewer than two candidates', () => {
  render(<StationList rows={rows().slice(0, 1)} />)
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
