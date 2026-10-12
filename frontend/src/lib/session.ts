import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../api/client'
import type { RankOptions, SmartResult, SmartSearchBody } from '../api/types'
import { type Prefs, TIME_VALUE } from './prefs'

export interface Origin {
  lat: number
  lng: number
}

export type Phase = 'idle' | 'locating' | 'searching' | 'ready' | 'error'

export interface SessionError {
  kind: 'location' | 'api'
  code: string
  retryAfterSeconds?: number | null
  at: number
}

const SEARCH_RADIUS_METERS = 8000

function rankOptions(prefs: Prefs): Partial<RankOptions> {
  return {
    gallons: String(prefs.gallons),
    payment_type: prefs.payment,
    credit_cashback_percent: prefs.creditCashbackPercent || '0',
    memberships: prefs.costco ? ['costco'] : [],
    time_value_per_hour: String(TIME_VALUE[prefs.preference]),
    allow_unknown_payment: prefs.allowUnknownPayment,
    unknown_payment_credit_markup: '0.20',
    prefer_top_tier: prefs.preferTopTier,
    opening_policy: 'require_open',
    max_results: 100,
  }
}

export function searchBody(prefs: Prefs, origin: Origin): SmartSearchBody {
  return {
    ...rankOptions(prefs),
    origin,
    radius_meters: SEARCH_RADIUS_METERS,
    strategy: 'best_value',
    max_results: 100,
    calculate_routes: true,
    route_limit: 100,
    discovery_tiles: 5,
    trip_mode: prefs.tripMode,
    ...(prefs.tripMode === 'on_route' && prefs.destination ? { destination: prefs.destination } : {}),
    ...(prefs.vehicle
      ? { vehicle_id: prefs.vehicle.id }
      : { fuel_type: prefs.fuelType, mpg: prefs.mpg }),
  } as SmartSearchBody
}

/** Ask the browser only after a tap when permission was never granted, so the prompt has context. */
async function permissionState(): Promise<PermissionState | 'unknown'> {
  try {
    return (await navigator.permissions?.query({ name: 'geolocation' }))?.state ?? 'unknown'
  } catch {
    return 'unknown'
  }
}

export function locate(): Promise<Origin> {
  return new Promise((resolve, reject) => {
    if (!window.isSecureContext || !('geolocation' in navigator)) {
      reject(new Error('unsupported'))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({ lat: position.coords.latitude, lng: position.coords.longitude }),
      (error) => reject(new Error(error.code === 1 ? 'denied' : error.code === 3 ? 'location_timeout' : 'unavailable')),
      { enableHighAccuracy: true, timeout: 60000, maximumAge: 120000 },
    )
  })
}

/**
 * One fuel decision transaction: locate once, acquire prices once, then rerank
 * locally-held snapshots with zero upstream calls. No polling, no auto-refresh.
 */
export function useFuelSession(prefs: Prefs) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState<SessionError | null>(null)
  const [result, setResult] = useState<SmartResult | null>(null)
  const [locationPermission, setLocationPermission] = useState<PermissionState | 'unknown'>('unknown')
  const [originKind, setOriginKind] = useState<'device' | 'manual' | null>(null)
  const resultRef = useRef<SmartResult | null>(null)
  resultRef.current = result
  const [origin, setOrigin] = useState<Origin | null>(null)
  const [reranking, setReranking] = useState(false)
  const [expired, setExpired] = useState(false)
  const locationRequest = useRef(0)
  const controller = useRef<AbortController | null>(null)
  const rerankController = useRef<AbortController | null>(null)
  const prefsRef = useRef(prefs)
  prefsRef.current = prefs

  const search = useCallback(async (at: Origin) => {
    controller.current?.abort()
    rerankController.current?.abort()
    setReranking(false)
    const abort = new AbortController()
    controller.current = abort
    setPhase('searching')
    setError(null)
    setExpired(false)
    try {
      const next = await api.search(searchBody(prefsRef.current, at), abort.signal)
      if (abort.signal.aborted) return
      setResult(next)
      setPhase('ready')
    } catch (caught) {
      if (abort.signal.aborted) return
      const apiError = caught instanceof ApiError ? caught : new ApiError(0, 'unexpected_error')
      setError({ kind: 'api', code: apiError.code, retryAfterSeconds: apiError.retryAfterSeconds, at: Date.now() })
      setPhase('error')
    }
  }, [])

  const start = useCallback(
    async (options: { override?: Origin; userInitiated?: boolean } = {}) => {
      const request = ++locationRequest.current
      const { override, userInitiated = false } = options
      if (override) {
        setOriginKind('manual')
        setOrigin(override)
        await search(override)
        return
      }
      setPhase('locating')
      setError(null)
      // Preserve the tap's user activation when opening the browser prompt.
      const requested = userInitiated ? locate().then((at) => ({ at }), (caught: unknown) => ({ caught })) : null
      const permission = userInitiated ? 'unknown' : await permissionState()
      if (request !== locationRequest.current) return
      setLocationPermission(permission)
      if (!userInitiated && (permission === 'prompt' || permission === 'denied')) {
        setError({ kind: 'location', code: permission === 'denied' ? 'denied' : 'prompt', at: Date.now() })
        setPhase(resultRef.current ? 'ready' : 'error')
        return
      }
      try {
        const response = requested ? await requested : { at: await locate() }
        if ('caught' in response) throw response.caught
        const at = response.at
        if (request !== locationRequest.current) return
        setLocationPermission('granted')
        setOriginKind('device')
        setOrigin(at)
        await search(at)
      } catch (caught) {
        if (request !== locationRequest.current) return
        setError({ kind: 'location', code: caught instanceof Error ? caught.message : 'unavailable', at: Date.now() })
        setPhase(resultRef.current ? 'ready' : 'error')
        void permissionState().then((state) => {
          if (request !== locationRequest.current) return
          setLocationPermission(state)
          if (state === 'prompt') setError({ kind: 'location', code: 'permission_pending', at: Date.now() })
        })
      }
    },
    [search],
  )

  const refresh = useCallback(() => (origin ? search(origin) : start({ userInitiated: true })), [origin, search, start])

  const expandRoutes = useCallback(async () => {
    if (!result) return
    controller.current?.abort()
    rerankController.current?.abort()
    setReranking(false)
    const abort = new AbortController()
    controller.current = abort
    setPhase('searching'); setError(null)
    try {
      const next = await api.routes(result.snapshot, result.signature, abort.signal)
      if (abort.signal.aborted) return
      setResult(next); setPhase('ready')
    } catch (caught) {
      if (abort.signal.aborted) return
      if (caught instanceof ApiError && caught.status === 409) setExpired(true)
      else setError({ kind: 'api', code: caught instanceof ApiError ? caught.code : 'unexpected_error', at: Date.now() })
      setPhase('ready')
    }
  }, [result])

  // Ranking choices rerank the held snapshot. Vehicle or fuel changes need new prices.
  const rankKey = JSON.stringify(rankOptions(prefs))
  const searchKey = JSON.stringify([prefs.vehicle?.id ?? null, prefs.fuelType, prefs.mpg, prefs.tripMode, prefs.destination])
  const lastRankKey = useRef(rankKey)
  const lastSearchKey = useRef(searchKey)

  useEffect(() => {
    if (searchKey !== lastSearchKey.current) {
      lastSearchKey.current = searchKey
      lastRankKey.current = rankKey
      if (origin && phase !== 'idle') void search(origin)
      return
    }
    if (rankKey === lastRankKey.current || !result || phase !== 'ready') return
    const abort = new AbortController()
    rerankController.current?.abort()
    rerankController.current = abort
    const timer = window.setTimeout(async () => {
      lastRankKey.current = rankKey
      setReranking(true)
      try {
        const next = await api.rerank(result.snapshot, result.signature, rankOptions(prefsRef.current), abort.signal)
        if (abort.signal.aborted) return
        setResult(next)
        setError(null)
      } catch (caught) {
        if (abort.signal.aborted) return
        if (caught instanceof ApiError && caught.status === 409) setExpired(true)
        else if (caught instanceof ApiError)
          setError({ kind: 'api', code: caught.code, retryAfterSeconds: caught.retryAfterSeconds, at: Date.now() })
      } finally {
        if (!abort.signal.aborted) setReranking(false)
      }
    }, 250)
    return () => {
      window.clearTimeout(timer)
      abort.abort()
    }
  }, [rankKey, searchKey, result, origin, phase, search])

  useEffect(() => () => {
    locationRequest.current++
    controller.current?.abort()
    rerankController.current?.abort()
  }, [])

  return { phase, error, result, origin, originKind, locationPermission, reranking, expired, start, refresh, expandRoutes }
}
