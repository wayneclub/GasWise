/// <reference types="node" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { IDBFactory } from 'fake-indexeddb'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { FavoriteStationsSection } from './FavoriteStationsSection'
import { saveFavorite, loadFavorites } from '../../lib/favorites'

describe('FavoriteStationsSection', () => {
  beforeEach(() => {
    vi.stubGlobal('indexedDB', new IDBFactory())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders empty state when there are no favorites', () => {
    render(<FavoriteStationsSection />)
    expect(screen.getByText('No favorite stations yet')).toBeInTheDocument()
    expect(screen.getByText('Favorites (0)')).toBeInTheDocument()
  })

  it('renders favorite stations and supports editing note and deletion', async () => {
    await saveFavorite({
      id: 'google:st_chevron',
      stationId: 'st_chevron',
      name: 'Chevron Valley',
      address: '500 Valley Blvd',
      location: { lat: 34.08, lng: -118.1 },
      addedAt: '2026-10-30T00:00:00Z',
      lastObservedPrice: '4.85',
      fuelType: 'premium',
      topTierBrand: 'Chevron',
    })

    render(<FavoriteStationsSection navApp="apple" />)

    await waitFor(() => {
      expect(screen.getByText('Chevron Valley')).toBeInTheDocument()
    })
    expect(screen.getByText('TOP TIER')).toBeInTheDocument()
    expect(screen.getByText('Favorites (1)')).toBeInTheDocument()

    // Add notes
    fireEvent.click(screen.getByText('Notes'))
    const input = screen.getByPlaceholderText(
      'Add private notes (e.g. member perks, car wash)',
    )
    fireEvent.change(input, { target: { value: 'Free air pump' } })
    fireEvent.click(screen.getByText('Save notes'))

    await waitFor(async () => {
      const stored = await loadFavorites()
      expect(stored[0].notes).toBe('Free air pump')
    })

    // Delete
    const deleteBtn = screen.getByRole('button', {
      name: 'Remove from favorites Chevron Valley',
    })
    fireEvent.click(deleteBtn)

    await waitFor(() => {
      expect(screen.getByText('No favorite stations yet')).toBeInTheDocument()
    })
  })
})
