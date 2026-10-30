/// <reference types="node" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { IDBFactory } from 'fake-indexeddb'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MyPage } from './MyPage'
import { saveFavorite, loadFavorites } from '../../lib/favorites'
import { DEFAULT_PREFS } from '../../lib/prefs'

describe('MyPage', () => {
  beforeEach(() => {
    vi.stubGlobal('indexedDB', new IDBFactory())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders empty state when there are no favorite stations', () => {
    const onNavigate = vi.fn()
    render(<MyPage prefs={DEFAULT_PREFS} onNavigateToFuel={onNavigate} />)

    expect(screen.getByText('No favorite stations yet')).toBeInTheDocument()
    const searchBtn = screen.getByRole('button', { name: 'Find Gas Stations' })
    fireEvent.click(searchBtn)
    expect(onNavigate).toHaveBeenCalled()
  })

  it('renders favorite stations and price analytics with stats, bars, notes and deletion', async () => {
    await saveFavorite({
      id: 'google:shell_downtown',
      stationId: 'shell_downtown',
      name: 'Shell Downtown',
      source: 'google',
      address: '100 Main St, Los Angeles, CA',
      location: { lat: 34.05, lng: -118.25 },
      lastObservedPrice: '4.89',
      fuelType: 'regular',
      topTierBrand: 'Shell',
      addedAt: '2026-10-30T00:00:00Z',
    })

    await saveFavorite({
      id: 'google:costco_la',
      stationId: 'costco_la',
      name: 'Costco Wholesale',
      source: 'google',
      address: '2207 E Olympic Blvd, Los Angeles, CA',
      location: { lat: 34.02, lng: -118.22 },
      lastObservedPrice: '4.29',
      fuelType: 'regular',
      addedAt: '2026-10-30T01:00:00Z',
      notes: 'Best prices on weekends',
    })

    await saveFavorite({
      id: 'google:chevron_express',
      stationId: 'chevron_express',
      name: 'Chevron Express',
      source: 'google',
      address: '800 Figueroa St, Los Angeles, CA',
      location: { lat: 34.04, lng: -118.26 },
      lastObservedPrice: '5.19',
      fuelType: 'regular',
      topTierBrand: 'Chevron',
      addedAt: '2026-10-30T02:00:00Z',
    })

    render(
      <MyPage
        prefs={{ ...DEFAULT_PREFS, gallons: 10 }}
        onNavigateToFuel={() => {}}
      />,
    )

    // Wait for favorites to load
    await waitFor(() => {
      expect(screen.getByText('Favorite Stations Price Analysis')).toBeInTheDocument()
    })

    // Stat cards assertions
    // Lowest price is 4.29 (Costco)
    expect(screen.getAllByText('$4.29').length).toBeGreaterThan(0)
    // Spread is 5.19 - 4.29 = 0.90
    expect(screen.getByText('$0.90')).toBeInTheDocument()
    // Max savings = 0.90 * 10 = $9.00
    expect(screen.getByText('$9.00')).toBeInTheDocument()

    // Price visualization sections
    expect(screen.getByText('Price Distribution Spectrum')).toBeInTheDocument()
    expect(screen.getByText(/Full Tank Cost Comparison/)).toBeInTheDocument()
    expect(screen.getByText('Baseline')).toBeInTheDocument()

    // Station list items
    expect(screen.getAllByText('Costco Wholesale').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Shell Downtown').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Chevron Express').length).toBeGreaterThan(0)
    expect(screen.getByText('Best prices on weekends')).toBeInTheDocument()

    // Edit notes
    const editBtns = screen.getAllByText('Edit')
    fireEvent.click(editBtns[0])
    const noteInput = screen.getByDisplayValue('Best prices on weekends')
    fireEvent.change(noteInput, { target: { value: 'Free tire air available' } })
    fireEvent.click(screen.getByText('Save notes'))

    await waitFor(async () => {
      const stored = await loadFavorites()
      const costco = stored.find((s) => s.id === 'google:costco_la')
      expect(costco?.notes).toBe('Free tire air available')
    })

    // Delete one station
    const deleteBtn = screen.getByRole('button', {
      name: 'Remove from favorites Chevron Express',
    })
    fireEvent.click(deleteBtn)

    await waitFor(() => {
      expect(screen.queryByText('Chevron Express')).not.toBeInTheDocument()
    })
  })
})
