/// <reference types="node" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { IDBFactory } from 'fake-indexeddb'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { FavoritesDrawer } from './FavoritesDrawer'
import { saveFavorite, loadFavorites } from '../../lib/favorites'

describe('FavoritesDrawer', () => {
  beforeEach(() => {
    vi.stubGlobal('indexedDB', new IDBFactory())
    HTMLDialogElement.prototype.showModal = function () { this.open = true }
    HTMLDialogElement.prototype.close = function () { this.open = false }
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders empty state when there are no favorites', () => {
    render(<FavoritesDrawer open={true} onClose={() => {}} />)
    expect(screen.getByText('No favorite stations yet')).toBeInTheDocument()
    expect(
      screen.getByText(/Tap the heart icon on any gas station to save it here/),
    ).toBeInTheDocument()
  })

  it('renders favorite stations, allows updating notes and removing station', async () => {
    await saveFavorite({
      id: 'google:st_1',
      stationId: 'st_1',
      name: 'Costco Wholesale Gas',
      address: '2207 E Olympic Blvd, Los Angeles, CA',
      location: { lat: 34.02, lng: -118.22 },
      addedAt: '2026-10-30T00:00:00Z',
      lastObservedPrice: '3.99',
      fuelType: 'regular',
      notes: 'Requires active membership card',
    })

    render(<FavoritesDrawer open={true} onClose={() => {}} navApp="google" />)

    await waitFor(() => {
      expect(screen.getByText('Costco Wholesale Gas')).toBeInTheDocument()
    })
    expect(screen.getByText('Requires active membership card')).toBeInTheDocument()
    expect(screen.getByText('$3.99')).toBeInTheDocument()

    // Edit notes
    fireEvent.click(screen.getByText('Edit'))
    const input = screen.getByDisplayValue('Requires active membership card')
    fireEvent.change(input, { target: { value: 'Best price on Saturdays' } })
    fireEvent.click(screen.getByText('Save notes'))

    await waitFor(async () => {
      const stored = await loadFavorites()
      expect(stored[0].notes).toBe('Best price on Saturdays')
    })

    // Remove favorite
    const removeBtn = screen.getByRole('button', {
      name: 'Remove from favorites Costco Wholesale Gas',
    })
    fireEvent.click(removeBtn)

    await waitFor(() => {
      expect(screen.getByText('No favorite stations yet')).toBeInTheDocument()
    })
  })
})
