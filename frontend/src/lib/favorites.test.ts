/// <reference types="node" />
import { IDBFactory } from 'fake-indexeddb'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  clearFavorites,
  deleteFavorite,
  favoriteKey,
  isFavorite,
  loadFavorites,
  replaceFavorites,
  saveFavorite,
  toggleFavorite,
  updateFavoriteNotes,
} from './favorites'

describe('favorites', () => {
  beforeEach(() => {
    vi.stubGlobal('indexedDB', new IDBFactory())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('computes canonical or fallback favorite keys', () => {
    expect(favoriteKey({ id: '123', source: 'gasbuddy' })).toBe('gasbuddy:123')
    expect(favoriteKey({ id: '123', source: 'gasbuddy', canonical_id: 'google_places:abc' })).toBe('google_places:abc')
  })

  it('saves, queries, toggles and deletes favorites', async () => {
    const station = {
      id: 'st_1',
      name: 'Shell Test',
      source: 'google',
      address: '100 Main St',
      location: { lat: 34.05, lng: -118.25 },
      price_per_gallon: '4.59',
      fuel_type: 'regular' as const,
    }

    expect(await isFavorite('google:st_1')).toBe(false)
    const added = await toggleFavorite(station)
    expect(added).toBe(true)
    expect(await isFavorite('google:st_1')).toBe(true)

    const list = await loadFavorites()
    expect(list).toHaveLength(1)
    expect(list[0].name).toBe('Shell Test')
    expect(list[0].lastObservedPrice).toBe('4.59')

    await updateFavoriteNotes('google:st_1', 'Great car wash')
    const updated = await loadFavorites()
    expect(updated[0].notes).toBe('Great car wash')

    // Test explicit saveFavorite with direct update
    await saveFavorite({ ...updated[0], notes: 'Updated note' })
    expect((await loadFavorites())[0].notes).toBe('Updated note')

    const toggledOff = await toggleFavorite(station)
    expect(toggledOff).toBe(false)
    expect(await isFavorite('google:st_1')).toBe(false)
    expect(await loadFavorites()).toHaveLength(0)

    // Test deleteFavorite explicitly
    await toggleFavorite(station)
    expect(await isFavorite('google:st_1')).toBe(true)
    await deleteFavorite('google:st_1')
    expect(await isFavorite('google:st_1')).toBe(false)
  })

  it('supports replace and clear operations', async () => {
    const fav1 = {
      id: 'fav_1',
      stationId: 's1',
      name: 'Station 1',
      location: { lat: 34, lng: -118 },
      addedAt: '2026-10-01T12:00:00Z',
    }
    const fav2 = {
      id: 'fav_2',
      stationId: 's2',
      name: 'Station 2',
      location: { lat: 34.1, lng: -118.1 },
      addedAt: '2026-10-02T12:00:00Z',
    }
    await replaceFavorites([fav1, fav2])
    const list = await loadFavorites()
    expect(list).toHaveLength(2)
    // Sorted by addedAt desc
    expect(list[0].id).toBe('fav_2')

    await clearFavorites()
    expect(await loadFavorites()).toHaveLength(0)
  })
})
