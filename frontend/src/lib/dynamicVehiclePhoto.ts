import { useEffect, useState } from 'react'
import { resolveVehiclePhoto } from './vehicleStyle'

const CACHE_PREFIX = 'gw_veh_photo_v2_'
const CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000 // 7 days cache

const memoryCache = new Map<string, { url: string | null; timestamp: number }>()

function getCachedPhoto(cleanKey: string): string | null | undefined {
  const inMem = memoryCache.get(cleanKey)
  if (inMem && Date.now() - inMem.timestamp < CACHE_TTL_MS) {
    return inMem.url
  }
  try {
    const raw = typeof window !== 'undefined' ? localStorage.getItem(CACHE_PREFIX + cleanKey) : null
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Date.now() - parsed.timestamp < CACHE_TTL_MS) {
        memoryCache.set(cleanKey, parsed)
        return parsed.url
      }
    }
  } catch {
    // Ignore storage errors in test or restricted environments
  }
  return undefined
}

function setCachedPhoto(cleanKey: string, url: string | null): void {
  const item = { url, timestamp: Date.now() }
  memoryCache.set(cleanKey, item)
  try {
    if (typeof window !== 'undefined') {
      localStorage.setItem(CACHE_PREFIX + cleanKey, JSON.stringify(item))
    }
  } catch {
    // Ignore storage quota errors
  }
}

/**
 * Clean vehicle string to search Wikipedia / automotive image archives effectively.
 */
export function cleanVehicleQuery(label?: string | null): string {
  if (!label) return ''
  let cleaned = label
    .replace(/\b(vin|plate|automatic|manual)\b/gi, '')
    .replace(/\b(awd|4wd|fwd|rwd|4x4|hybrid|turbo|phev|ev)\b/gi, '')
    .replace(/\b(premium|limited|sport|touring|select|preferred|base|plus)\b/gi, '')
    .replace(/\b(2dr|4dr|5dr)\b/gi, '')
    .replace(/\s+/g, ' ')
    .trim()
  return cleaned
}

/**
 * Asynchronously fetch authentic vehicle exterior photograph from open automotive/encyclopedic archives.
 */
export async function fetchDynamicVehiclePhoto(label?: string | null): Promise<string | null> {
  if (!label) return null
  const query = cleanVehicleQuery(label)
  if (!query) return null
  const cacheKey = query.toLowerCase().replace(/[^a-z0-9]/g, '_')

  const cached = getCachedPhoto(cacheKey)
  if (cached !== undefined) {
    return cached
  }

  // Helper to query Wikimedia PageImages
  async function queryApi(searchTerms: string): Promise<string | null> {
    try {
      const apiUrl = `https://en.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch=${encodeURIComponent(
        searchTerms,
      )}&gsrlimit=1&prop=pageimages&pithumbsize=800&format=json&origin=*`

      const res = await fetch(apiUrl, {
        method: 'GET',
        headers: { Accept: 'application/json' },
      })
      if (!res.ok) return null
      const data = await res.json()
      const pages = data?.query?.pages
      if (!pages) return null

      const firstPage = Object.values(pages)[0] as {
        thumbnail?: { source?: string }
        title?: string
      }
      const source = firstPage?.thumbnail?.source
      if (source && typeof source === 'string' && /^https?:\/\//i.test(source)) {
        return source
      }
      return null
    } catch {
      return null
    }
  }

  // 1. Try full cleaned query (e.g., "2024 Mazda CX-30")
  let photo = await queryApi(query)

  // 2. Fallback without year if not found (e.g., "Mazda CX-30")
  if (!photo) {
    const withoutYear = query.replace(/\b(?:19[89]\d|20\d{2})\b/g, '').trim()
    if (withoutYear && withoutYear !== query) {
      photo = await queryApi(withoutYear)
    }
  }

  setCachedPhoto(cacheKey, photo)
  return photo
}

export interface DynamicPhotoResult {
  photoUrl: string | null
  isStudio: boolean
  isLoading: boolean
}

/**
 * Hook to resolve authentic exterior photograph:
 * 1. Checks pre-bundled studio cutout (E400, Tesla 3/Y, BMW M4, Toyota RAV4)
 * 2. Checks custom user imageUrl
 * 3. Dynamically queries Wikimedia/encyclopedic archives for any unlisted vehicle
 */
export function useDynamicVehiclePhoto(
  label?: string | null,
  customImageUrl?: string | null,
  color?: string | null,
): DynamicPhotoResult {
  // Pre-bundled or custom photo check
  const studioOrCustom = resolveVehiclePhoto(label, customImageUrl, color)

  // If studio cutout or custom image is resolved, return immediately
  const isStudio = Boolean(
    studioOrCustom &&
      (studioOrCustom.includes('/vehicles/2018_mercedes_benz_e400') ||
        studioOrCustom.includes('/vehicles/tesla_model_') ||
        studioOrCustom.includes('/vehicles/bmw_m4_coupe_') ||
        studioOrCustom.includes('/vehicles/toyota_') ||
        studioOrCustom.includes('/vehicles/ford_') ||
        studioOrCustom.includes('/vehicles/nissan_') ||
        studioOrCustom.includes('/vehicles/kia_') ||
        studioOrCustom.includes('/vehicles/honda_')),
  )

  const [dynamicUrl, setDynamicUrl] = useState<string | null>(() => {
    if (studioOrCustom) return studioOrCustom
    if (!label) return null
    const key = cleanVehicleQuery(label).toLowerCase().replace(/[^a-z0-9]/g, '_')
    return getCachedPhoto(key) ?? null
  })

  const [isLoading, setIsLoading] = useState<boolean>(() => {
    if (studioOrCustom) return false
    if (!label) return false
    const key = cleanVehicleQuery(label).toLowerCase().replace(/[^a-z0-9]/g, '_')
    return getCachedPhoto(key) === undefined
  })

  useEffect(() => {
    if (studioOrCustom) {
      setDynamicUrl(studioOrCustom)
      setIsLoading(false)
      return
    }

    if (!label) {
      setDynamicUrl(null)
      setIsLoading(false)
      return
    }

    const key = cleanVehicleQuery(label).toLowerCase().replace(/[^a-z0-9]/g, '_')
    const cached = getCachedPhoto(key)
    if (cached !== undefined) {
      setDynamicUrl(cached)
      setIsLoading(false)
      return
    }

    let active = true
    setIsLoading(true)

    fetchDynamicVehiclePhoto(label).then((url) => {
      if (!active) return
      setDynamicUrl(url)
      setIsLoading(false)
    })

    return () => {
      active = false
    }
  }, [label, studioOrCustom])

  return {
    photoUrl: studioOrCustom || dynamicUrl,
    isStudio,
    isLoading,
  }
}
