import {fireEvent, render, screen, within} from '@testing-library/react'
import {expect, it} from 'vitest'
import {I18nProvider} from '../../i18n/I18nProvider'
import type {SmartResult} from '../../api/types'
import fixture from '../../test/fixtures/demo-search.json'
import {Leaderboards} from './Leaderboards'

it('shows three ranked choices for each category, with dated AAA regional context', () => {
  const result = structuredClone(fixture) as unknown as SmartResult
  const rows = result.ranking!.results.slice(0,3)
  rows[0].regional_benchmark = {state:'CA',region:'Los Angeles-Long Beach',scope:'metro',fuel_type:'premium',price_per_gallon:'6.74',price_as_of:'2026-10-12',retrieved_at:'2026-10-12T15:00:00Z',source_url:'https://gasprices.aaa.com/?state=CA'}
  result.ranking!.leaderboards = {best_value:rows,cheapest_overall:[...rows].reverse(),fastest_stop:[rows[1],rows[0],rows[2]]}
  render(<I18nProvider locale="en"><Leaderboards result={result} primary="best_value" navApp="google" tripMode="round_trip"/></I18nProvider>)
  const board = screen.getByRole('region',{name:'Top 3 stations'})
  expect(within(board).getAllByRole('listitem')).toHaveLength(3)
  expect(within(board).getByText(/Metro average · 2026-10-12/)).toBeInTheDocument()
  const names = () => within(board).getAllByRole('listitem').map(li=>within(li).getAllByRole('link')[0].textContent)
  expect(names()[0]).toBe(rows[0].station.name)
  expect(within(board).getAllByText('Including time cost')).toHaveLength(3)
  expect(within(board).getByText(/It is not the amount you pay/)).toBeInTheDocument()
  fireEvent.click(within(board).getByRole('radio',{name:'Cost'}))
  expect(names()).toEqual([...rows].reverse().map(r=>r.station.name))
  expect(within(board).queryByText('Including time cost')).not.toBeInTheDocument()
  expect(within(board).getAllByText('Fuel + driving fuel')).toHaveLength(3)
  fireEvent.click(within(board).getByRole('radio',{name:'Speed'}))
  expect(names()[0]).toBe(rows[1].station.name)
  expect(within(board).getAllByRole('listitem')).toHaveLength(3)
})

it('opens station details and provides navigation button for ranked stations', () => {
  HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) { this.open = true }
  HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) { this.open = false }
  const result = structuredClone(fixture) as unknown as SmartResult
  const rows = result.ranking!.results.slice(0, 3)
  result.ranking!.leaderboards = { best_value: rows, cheapest_overall: rows, fastest_stop: rows }
  render(<I18nProvider locale="en"><Leaderboards result={result} primary="best_value" navApp="google" tripMode="round_trip"/></I18nProvider>)
  const board = screen.getByRole('region', { name: 'Top 3 stations' })
  const firstItem = within(board).getAllByRole('listitem')[0]

  // Verify prominent "View details" button
  const viewButton = within(firstItem).getByRole('button', { name: new RegExp(`View details ${rows[0].station.name}`) })
  expect(viewButton).toBeInTheDocument()

  // Verify navigation link
  const navLink = within(firstItem).getByRole('link', { name: new RegExp(`Navigate ${rows[0].station.name}`) })
  expect(navLink).toHaveAttribute('href', expect.stringContaining('google.com/maps/dir'))

  // Verify favorite button
  const favButton = within(firstItem).getByRole('button', { name: /save/i })
  expect(favButton).toBeInTheDocument()

  // Click view details
  fireEvent.click(viewButton)
  expect(screen.getByRole('dialog', { name: 'Station details' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: rows[0].station.name })).toBeInTheDocument()
})
