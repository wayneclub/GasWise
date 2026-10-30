/// <reference types="node" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { IDBFactory } from 'fake-indexeddb'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { FavoriteButton } from './FavoriteButton'
import { isFavorite, loadFavorites } from '../lib/favorites'

describe('FavoriteButton', () => {
  const station = {
    id: 'test_station_1',
    name: 'Shell Downtown',
    source: 'google',
    address: '100 Main St, Los Angeles, CA',
    location: { lat: 34.05, lng: -118.25 },
    price_per_gallon: '4.89',
    fuel_type: 'regular' as const,
  }

  beforeEach(() => {
    vi.stubGlobal('indexedDB', new IDBFactory())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders unpressed state and toggles to favorited on click', async () => {
    render(<FavoriteButton station={station} />)

    const btn = screen.getByRole('button', { name: 'Save station' })
    expect(btn).toHaveAttribute('aria-pressed', 'false')

    fireEvent.click(btn)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Remove from favorites' })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
    })

    expect(await isFavorite('google:test_station_1')).toBe(true)
    const stored = await loadFavorites()
    expect(stored).toHaveLength(1)
    expect(stored[0].name).toBe('Shell Downtown')

    // Click again to unfavorite
    fireEvent.click(screen.getByRole('button', { name: 'Remove from favorites' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Save station' })).toHaveAttribute(
        'aria-pressed',
        'false',
      )
    })
    expect(await isFavorite('google:test_station_1')).toBe(false)
  })

  it('renders button with label when iconOnly is false', async () => {
    render(<FavoriteButton station={station} iconOnly={false} />)
    expect(screen.getByText('Save station')).toBeInTheDocument()
  })
})
