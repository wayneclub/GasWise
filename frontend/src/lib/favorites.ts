import { useCallback, useEffect, useRef, useState } from 'react'
import type { Station } from '../api/types'

const DATABASE = 'gaswise-favorites-v1'
const STORE = 'favorites'
const CHANGE_EVENT = 'gaswise:favorites-changed'

export interface FavoriteStation {
  id: string
  stationId: string
  source?: string | null
  canonicalId?: string | null
  name: string
  address?: string | null
  brand?: string | null
  topTierBrand?: string | null
  location: { lat: number; lng: number }
  addedAt: string
  notes?: string | null
  lastObservedPrice?: number | string | null
  fuelType?: string | null
  priceUpdatedAt?: string | null
}

export function favoriteKey(station: {
  id?: string | null
  source?: string | null
  canonical_id?: string | null
}): string {
  if (station.canonical_id) return station.canonical_id
  return `${station.source ?? 'custom'}:${station.id ?? ''}`
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1)
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE)) {
        request.result.createObjectStore(STORE, { keyPath: 'id' })
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = request.onblocked = () => reject(new Error('favorites_storage_unavailable'))
  })
}

async function transact<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDB()
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode)
      const store = tx.objectStore(STORE)
      const req = run(store)
      req.onsuccess = () => resolve(req.result)
      req.onerror = tx.onerror = tx.onabort = () => reject(new Error('favorites_storage_unavailable'))
    })
  } finally {
    db.close()
  }
}

function notifyFavoritesChanged() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(CHANGE_EVENT))
  }
}

export async function loadFavorites(): Promise<FavoriteStation[]> {
  try {
    const list = await transact<FavoriteStation[]>('readonly', store => store.getAll())
    return (list ?? []).sort((a, b) => Date.parse(b.addedAt) - Date.parse(a.addedAt))
  } catch {
    return []
  }
}

export async function saveFavorite(fav: FavoriteStation): Promise<void> {
  await transact('readwrite', store => store.put(fav))
  notifyFavoritesChanged()
}

export async function deleteFavorite(id: string): Promise<void> {
  await transact('readwrite', store => store.delete(id))
  notifyFavoritesChanged()
}

export async function isFavorite(id: string): Promise<boolean> {
  try {
    const result = await transact<FavoriteStation | undefined>('readonly', store => store.get(id))
    return Boolean(result)
  } catch {
    return false
  }
}

export async function toggleFavorite(station: Partial<Station> & { id: string }): Promise<boolean> {
  const key = favoriteKey(station)
  const exists = await isFavorite(key)
  if (exists) {
    await deleteFavorite(key)
    return false
  }
  const fav: FavoriteStation = {
    id: key,
    stationId: station.id,
    source: station.source ?? null,
    canonicalId: station.canonical_id ?? null,
    name: station.name ?? station.id,
    address: station.address ?? null,
    brand: (station as any).brand ?? null,
    topTierBrand: station.top_tier_brand ?? null,
    location: station.location ?? { lat: 0, lng: 0 },
    addedAt: new Date().toISOString(),
    lastObservedPrice: station.price_per_gallon ?? null,
    fuelType: station.fuel_type ?? null,
    priceUpdatedAt: station.price_updated_at ?? null,
    notes: null,
  }
  await saveFavorite(fav)
  return true
}

export async function updateFavoriteNotes(id: string, notes: string | null): Promise<void> {
  const list = await loadFavorites()
  const found = list.find(item => item.id === id)
  if (found) {
    await saveFavorite({ ...found, notes: notes?.trim() || null })
  }
}

export async function clearFavorites(): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const req = indexedDB.deleteDatabase(DATABASE)
    req.onsuccess = () => {
      notifyFavoritesChanged()
      resolve()
    }
    req.onerror = req.onblocked = () => reject(new Error('favorites_storage_unavailable'))
  })
}

export async function replaceFavorites(favorites: FavoriteStation[]): Promise<void> {
  await clearFavorites()
  for (const item of favorites) {
    await saveFavorite(item)
  }
}

export function useFavorites() {
  const [favorites, setFavorites] = useState<FavoriteStation[]>([])
  const [loading, setLoading] = useState(true)
  const mountedRef = useRef(true)

  const reload = useCallback(() => {
    loadFavorites()
      .then(items => {
        if (mountedRef.current) {
          setFavorites(items)
          setLoading(false)
        }
      })
      .catch(() => {
        if (mountedRef.current) {
          setLoading(false)
        }
      })
  }, [])

  useEffect(() => {
    mountedRef.current = true
    reload()
    const handle = () => reload()
    window.addEventListener(CHANGE_EVENT, handle)
    return () => {
      mountedRef.current = false
      window.removeEventListener(CHANGE_EVENT, handle)
    }
  }, [reload])

  const favoriteIds = new Set(favorites.map(f => f.id))

  const isFav = (keyOrStation: string | Partial<Station>) => {
    const key = typeof keyOrStation === 'string' ? keyOrStation : favoriteKey(keyOrStation)
    return favoriteIds.has(key)
  }

  const toggle = async (station: Partial<Station> & { id: string }) => {
    return await toggleFavorite(station)
  }

  const remove = async (id: string) => {
    await deleteFavorite(id)
  }

  const updateNotes = async (id: string, notes: string | null) => {
    await updateFavoriteNotes(id, notes)
  }

  return {
    favorites,
    loading,
    isFav,
    toggle,
    remove,
    updateNotes,
    reload,
  }
}
