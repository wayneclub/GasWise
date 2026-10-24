import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../api/client'
import type { RankOptions, SmartResult, SmartSearchBody } from '../api/types'
import { type Prefs } from './prefs'
import { clearFuelSession, loadFuelSession, saveFuelSession } from './fuelSessionStorage'

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

function rankOptions(prefs: Prefs): Partial<RankOptions> {
  return {
    strategy: prefs.preference === 'money' ? 'cheapest_overall' : prefs.preference === 'time' ? 'fastest_stop' : 'best_value',
    gallons: String(prefs.gallons),
    payment_type: prefs.payment,
    credit_cashback_percent: prefs.creditCashbackPercent || '0',
    memberships: prefs.costco ? ['costco'] : [],
    time_value_per_hour: String(prefs.timeValuePerHour ?? 15),
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
    radius_meters: (prefs.searchRadiusMiles ?? 5) * 1609.344,
    max_results: 100,
    calculate_routes: true,
    // Fast First Render: route_limit 0 gives instant (<1s) straight-line road-factor estimate;
    // the background task then enriches top candidates with real Google Maps routes asynchronously.
    route_limit: 0,
    estimate_unrouted_routes: true,
    discovery_tiles: 8,
    // Keep a cold search to one GasBuddy page so pagination does not delay the
    // first result. Shared cache and background collection can still add coverage.
    gasbuddy_page_limit: 1,
    station_lookup_limit: 5,
    maps_detail_limit: 5,
    trip_mode: prefs.tripMode,
    ...(prefs.tripMode === 'on_route' && prefs.destination ? { destination: prefs.destination } : {}),
    ...(prefs.vehicle
      ? { vehicle_id: prefs.vehicle.id }
      : { fuel_type: prefs.fuelType, mpg: prefs.mpg }),
  } as SmartSearchBody
}

export function backgroundGasBuddyPageLimit(prefs: Prefs): number {
  return (prefs.vehicle?.fuelType ?? prefs.fuelType) === 'regular' ? 3 : 5
}

async function progressiveSearch(
  body: SmartSearchBody,
  signal: AbortSignal,
  onRevision: (result: SmartResult) => void,
): Promise<SmartResult> {
  const started = await api.startSearchJob(body, signal)
  // Test/dev adapters created before the job API may still return a SmartResult directly.
  if ('snapshot' in (started as unknown as object)) return started as unknown as SmartResult
  let state = started
  let revision = 0
  while (!signal.aborted) {
    if (state.result && state.revision > revision) {
      revision = state.revision
      onRevision(state.result)
    }
    if (state.status === 'complete' && state.result) return state.result
    if (state.status === 'failed') throw new ApiError(503, state.error ?? 'progressive_search_failed')
    await new Promise((resolve) => window.setTimeout(resolve, 500))
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
    state = await api.pollSearchJob(state.job_id, revision, signal)
  }
  throw new DOMException('Aborted', 'AbortError')
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

export function haversineDistanceMeters(a: Origin, b: Origin): number {
  const R = 6371e3
  const dLat = ((b.lat - a.lat) * Math.PI) / 180
  const dLng = ((b.lng - a.lng) * Math.PI) / 180
  const lat1 = (a.lat * Math.PI) / 180
  const lat2 = (b.lat * Math.PI) / 180
  const sinDlat = Math.sin(dLat / 2)
  const sinDlng = Math.sin(dLng / 2)
  const aVal = sinDlat * sinDlat + Math.cos(lat1) * Math.cos(lat2) * sinDlng * sinDlng
  return R * 2 * Math.atan2(Math.sqrt(aVal), Math.sqrt(1 - aVal))
}

/**
 * One fuel decision transaction: locate once, refresh visible prices on a bounded interval, then rerank
 * locally-held snapshots with zero upstream calls. No polling in hidden tabs; manual refresh still respects the shared price freshness window and provider budgets.
 */
export function useFuelSession(prefs: Prefs, active = true) {
  const rankKey = JSON.stringify(rankOptions(prefs))
  const searchKey = JSON.stringify([prefs.vehicle?.id ?? null, prefs.fuelType, prefs.mpg, prefs.tripMode, prefs.destination, prefs.searchRadiusMiles])
  const [restored] = useState(() => loadFuelSession(searchKey, rankKey))
  const [phase, setPhase] = useState<Phase>(restored ? 'ready' : 'idle')
  const [error, setError] = useState<SessionError | null>(null)
  const [result, setResult] = useState<SmartResult | null>(restored?.result ?? null)
  const [locationPermission, setLocationPermission] = useState<PermissionState | 'unknown'>('unknown')
  const [originKind, setOriginKind] = useState<'device' | 'manual' | null>(restored?.originKind ?? null)
  const [originLabel, setOriginLabel] = useState<string | null>(restored?.originLabel ?? null)
  const resultRef = useRef<SmartResult | null>(restored?.result ?? null)
  const [origin, setOrigin] = useState<Origin | null>(restored?.origin ?? null)
  const [reranking, setReranking] = useState(false)
  const [expired, setExpired] = useState(() => !!restored && Date.parse(restored.result.snapshot.expires_at) <= Date.now())
  const [refreshing, setRefreshing] = useState(false)
  const [completing, setCompleting] = useState(false)
  const lastTrackedOrigin = useRef<Origin | null>(restored?.origin ?? null)
  const lastCheck = useRef(restored?.checkedAt ?? 0)
  const needsRecoveryCheck = useRef(expired)
  const retryDelay = useRef(120000)
  const locationRequest = useRef(0)
  const controller = useRef<AbortController | null>(null)
  const rerankController = useRef<AbortController | null>(null)
  const prefsRef = useRef(prefs)

  useEffect(() => {
    prefsRef.current = prefs
  }, [prefs])

  // Ranking choices rerank the held snapshot. Vehicle or fuel changes need new prices.
  const lastRankKey = useRef(rankKey)
  const lastSearchKey = useRef(searchKey)

  useEffect(() => {
    if (phase === 'ready' && result && origin && originKind &&
        lastSearchKey.current === searchKey && lastRankKey.current === rankKey) {
      saveFuelSession({ result, origin, originKind, originLabel, searchKey, rankKey, checkedAt: lastCheck.current })
    }
  }, [phase, result, origin, originKind, originLabel, searchKey, rankKey])

  const search = useCallback(async (at: Origin, force = false, background = false) => {
    controller.current?.abort()
    rerankController.current?.abort()
    setReranking(false)
    lastTrackedOrigin.current = at
    const abort = new AbortController()
    controller.current = abort
    if (!background) setPhase('searching')
    if (!background) clearFuelSession()
    setRefreshing(background)
    setCompleting(true)
    lastCheck.current = Date.now()
    setError(null)
    try {
      const requestedPrefs = prefsRef.current
      const body = searchBody(requestedPrefs, at)
      const held = resultRef.current
      const trip = held?.snapshot.query
      const sameSearch = trip && trip.origin.lat === at.lat && trip.origin.lng === at.lng &&
        trip.radius_meters === body.radius_meters && trip.trip_mode === body.trip_mode &&
        JSON.stringify(trip.destination ?? null) === JSON.stringify(body.destination ?? null) &&
        (trip.vehicle_id ?? null) === (body.vehicle_id ?? null) &&
        (body.vehicle_id != null || trip.fuel_type === body.fuel_type)
      const canRefreshPrices = (force || background) && held && sameSearch && Date.parse(held.snapshot.expires_at) > Date.now()
      let next: SmartResult
      if (canRefreshPrices) {
        try {
          next = await api.refreshPrices(held.snapshot, held.signature, rankOptions(requestedPrefs), abort.signal)
        } catch (caught) {
          // Expired/restart-invalid signatures need one new transaction, not an upstream retry loop.
          if (!(caught instanceof ApiError) || caught.status !== 409 ||
              !['snapshot_expired', 'invalid_snapshot_signature'].includes(caught.code)) throw caught
          next = await api.search({ ...body, force_refresh: false }, abort.signal)
        }
      } else {
        next = await progressiveSearch(
          { ...body, force_refresh: force },
          abort.signal,
          (revision) => {
            if (abort.signal.aborted) return
            resultRef.current = revision
            setResult(revision)
            setExpired(false)
            setPhase('ready')
          },
        )
      }
      if (abort.signal.aborted) return
      lastRankKey.current = JSON.stringify(rankOptions(requestedPrefs))
      resultRef.current = next
      setResult(next)
      setExpired(false)
      retryDelay.current = 120000
      setPhase('ready')
      const enhance = async () => {
        let latest = next
        const coldOnePageSearch = !canRefreshPrices && next.snapshot.acquisition_options?.gasbuddy_page_limit === 1
        if (coldOnePageSearch) {
          try {
            latest = await api.search({
              ...body,
              gasbuddy_page_limit: backgroundGasBuddyPageLimit(requestedPrefs),
              force_refresh: false,
            }, abort.signal)
            if (abort.signal.aborted) return
            resultRef.current = latest
            setResult(latest)
          } catch {
            // Non-fatal: keep the fast one-page result if background coverage fails.
          }
        }
        if (!latest.ranking?.results.some((r) => r.route.source === 'straight_line_estimate')) return
        void api.routes(latest.snapshot, latest.signature, abort.signal, 3)
          .then((routed) => {
            if (!abort.signal.aborted && routed.ranking) {
              resultRef.current = routed
              setResult(routed)
            }
          })
          .catch(() => {
            // Non-fatal: straight-line estimated ranking remains active if Google Maps route enrichment fails
          })
      }
      void enhance()
    } catch (caught) {
      if (abort.signal.aborted) return
      const apiError = caught instanceof ApiError ? caught : new ApiError(0, 'unexpected_error')
      setError({ kind: 'api', code: apiError.code, retryAfterSeconds: apiError.retryAfterSeconds, at: Date.now() })
      retryDelay.current = Math.min(600000, retryDelay.current * 2)
      setPhase(background && resultRef.current ? 'ready' : 'error')
    } finally {
      if (!abort.signal.aborted) { setRefreshing(false); setCompleting(false) }
    }
  }, [])

  const start = useCallback(
    async (options: { override?: Origin; label?: string; userInitiated?: boolean } = {}) => {
      const request = ++locationRequest.current
      const { override, userInitiated = false } = options
      if (override) {
        setOriginKind('manual')
        setOriginLabel(options.label ?? null)
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
        setOriginLabel(null)
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

  const refresh = useCallback(() => (origin ? search(origin, true) : start({ userInitiated: true })), [origin, search, start])

  const expandRoutes = useCallback(async () => {
    if (!result) return
    controller.current?.abort()
    rerankController.current?.abort()
    setReranking(false)
    const abort = new AbortController()
    controller.current = abort
    setPhase('searching'); setError(null)
    try {
      const next = await api.routes(result.snapshot, result.signature, abort.signal, 100)
      if (abort.signal.aborted) return
      resultRef.current = next
      setResult(next); setPhase('ready')
    } catch (caught) {
      if (abort.signal.aborted) return
      if (caught instanceof ApiError && caught.status === 409) setExpired(true)
      else setError({ kind: 'api', code: caught instanceof ApiError ? caught.code : 'unexpected_error', at: Date.now() })
      setPhase('ready')
    }
  }, [result])

  useEffect(() => {
    if (searchKey !== lastSearchKey.current) {
      lastSearchKey.current = searchKey
      lastRankKey.current = rankKey
      if (!origin || phase === 'idle') return
      const timer = window.setTimeout(() => { void search(origin) }, 0)
      return () => window.clearTimeout(timer)
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
        resultRef.current = next
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

  useEffect(() => {
    if (!result) return
    const remaining = Date.parse(result.snapshot.expires_at) - Date.now()
    const timer = window.setTimeout(() => setExpired(true), Math.max(0, remaining))
    return () => window.clearTimeout(timer)
  }, [result])

  useEffect(() => {
    if (!active || !origin || !result || phase !== 'ready') return
    const check = () => {
      if (document.visibilityState !== 'visible' || navigator.onLine === false || refreshing || reranking) return
      if (needsRecoveryCheck.current || Date.now() - lastCheck.current >= retryDelay.current) {
        needsRecoveryCheck.current = false
        void search(origin, false, true)
      }
    }
    check()
    const timer = window.setInterval(check, 120000)
    document.addEventListener('visibilitychange', check)
    return () => { window.clearInterval(timer); document.removeEventListener('visibilitychange', check) }
  }, [active, origin, result, phase, refreshing, reranking, search])

  // Dynamic movement tracking: when moving with device GPS, recalculate routes & ranks in background
  useEffect(() => {
    if (
      !active ||
      originKind !== 'device' ||
      !origin ||
      phase !== 'ready' ||
      typeof navigator === 'undefined' ||
      !('geolocation' in navigator) ||
      typeof navigator.geolocation?.watchPosition !== 'function'
    ) {
      return
    }

    let watchId: number | null = null
    try {
      watchId = navigator.geolocation.watchPosition(
        (position) => {
          const newOrigin: Origin = {
            lat: position.coords.latitude,
            lng: position.coords.longitude,
          }
          const base = lastTrackedOrigin.current ?? origin
          const distance = haversineDistanceMeters(base, newOrigin)
          // 400m movement threshold (~0.25 mi) avoids jitter while capturing meaningful route change
          if (distance >= 400 && document.visibilityState === 'visible' && !refreshing && !reranking) {
            lastTrackedOrigin.current = newOrigin
            setOrigin(newOrigin)
            void search(newOrigin, false, true)
          }
        },
        () => {
          // Transient watchPosition error in background is non-fatal
        },
        { enableHighAccuracy: true, maximumAge: 30000, timeout: 20000 },
      )
    } catch {
      // Ignored if watchPosition throws in non-supporting runtime
    }

    return () => {
      if (watchId !== null && typeof navigator.geolocation?.clearWatch === 'function') {
        navigator.geolocation.clearWatch(watchId)
      }
    }
  }, [active, originKind, origin, phase, refreshing, reranking, search])

  useEffect(() => () => {
    locationRequest.current++
    controller.current?.abort()
    rerankController.current?.abort()
  }, [])

  return { phase, error, result, origin, originKind, originLabel, locationPermission, reranking, refreshing, completing, expired, start, refresh, expandRoutes }
}
