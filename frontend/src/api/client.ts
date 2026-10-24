import type {
  RankOptions, LocationResult,
  PartsRequest, PartsResult, PartsSearchRequest, PartsSearchResult, VinRequest, VinResolution, PlateRequest, PlateResolution,
  SmartResult,
  SmartSearchBody,
  SmartSnapshot,
  ProgressiveSearchState,
  VehicleResolution,
  VehicleResolveRequest,
} from './types'

/** Same-origin path. The dev proxy (and a production gateway) injects the service token. */
const BASE = '/api'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly retryAfterSeconds: number | null

  constructor(status: number, code: string, retryAfterSeconds: number | null = null) {
    super(code)
    this.status = status
    this.code = code
    this.retryAfterSeconds = retryAfterSeconds
  }
}

async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'network_unavailable')
  }
  if (response.ok) return (await response.json()) as T
  let code = `http_${response.status}`
  try {
    const payload = (await response.json()) as { detail?: unknown }
    if (typeof payload.detail === 'string') code = payload.detail
    else if (Array.isArray(payload.detail)) code = 'invalid_request'
  } catch {
    // Non-JSON error bodies keep the status-derived code.
  }
  const retry = Number(response.headers.get('Retry-After'))
  throw new ApiError(response.status, code, Number.isFinite(retry) && retry > 0 ? retry : null)
}

export type PriceObservation = import('./schema').components['schemas']['PriceObservation']
export type PriceHistory = import('./schema').components['schemas']['PriceHistory']

export const api = {
  alertConfig: (signal?: AbortSignal) => post<{ enabled: boolean; vapid_public_key: string | null }>('/v1/alerts/config', {}, signal),
  createAlertInstallation: (body: { subscription: PushSubscriptionJSON; timezone: string; locale: string }) => post<{ installation_id: string; installation_token: string }>('/v1/alerts/installations', body),
  updateAlertNeed: (body: AlertAuth & { state: 'not_due' | 'approaching' | 'due' | 'unknown'; confidence: 'high' | 'medium' | 'low'; ttl_hours: number }) => post<{ status: string }>('/v1/alerts/need-state', body),
  testAlert: (body: AlertAuth & { locale: string }) => post<{ status: string }>('/v1/alerts/test', body),
  disableAlerts: (body: AlertAuth) => post<{ status: string }>('/v1/alerts/disable', body),
  updateAlertWatch: (body: AlertAuth & AlertWatch) => post<{ status: 'watched' | 'removed' }>('/v1/alerts/watches', body),
  alertInbox: (body: AlertAuth) => post<{ items: { id: number; title: string; body: string; created_at: string }[] }>('/v1/alerts/inbox', body),
  priceHistory: (body: import('./schema').components['schemas']['HistoryRequest'], signal?: AbortSignal) => post<PriceHistory>('/v1/prices/history', body, signal),
  resolveLocation: (text: string, signal?: AbortSignal) => post<LocationResult>('/v1/locations/resolve', { text }, signal),
  partsSearch: (body: PartsSearchRequest, signal?: AbortSignal) => post<PartsSearchResult>('/v1/parts/search', body, signal),
  routes: (snapshot: SmartSnapshot, signature: string, signal?: AbortSignal, routeLimit = 3) => post<SmartResult>('/v1/smart/routes', { snapshot, signature, route_limit: routeLimit }, signal),
  parts: (body: PartsRequest, signal?: AbortSignal) => post<PartsResult>('/v1/parts/fitment', body, signal),
  resolveVin: (body: VinRequest, signal?: AbortSignal) => post<VinResolution>('/v1/vehicles/vin', body, signal),
  resolvePlate: (body: PlateRequest, signal?: AbortSignal) => post<PlateResolution>('/v1/vehicles/plate', body, signal),
  /** Stage 1+2: one price acquisition plus a bounded route shortlist. Consumes upstream quota. */
  search: (body: SmartSearchBody, signal?: AbortSignal) =>
    post<SmartResult>('/v1/smart/search', body, signal),

  startSearchJob: (body: SmartSearchBody, signal?: AbortSignal) =>
    post<ProgressiveSearchState>('/v1/smart/search-jobs/start', body, signal),

  pollSearchJob: (jobId: string, afterRevision: number, signal?: AbortSignal) =>
    post<ProgressiveSearchState>('/v1/smart/search-jobs/poll', { job_id: jobId, after_revision: afterRevision }, signal),

  /** Read shared source data while preserving the trip and still-fresh routes. */
  refreshPrices: (snapshot: SmartSnapshot, signature: string, options: Partial<RankOptions>, signal?: AbortSignal) =>
    post<SmartResult>('/v1/smart/refresh-prices', { snapshot, signature, options }, signal),

  /** Recompute from the signed snapshot with zero upstream calls. */
  rerank: (snapshot: SmartSnapshot, signature: string, options: Partial<RankOptions>, signal?: AbortSignal) =>
    post<SmartResult>('/v1/smart/rerank', { snapshot, signature, options }, signal),

  resolveVehicle: (body: VehicleResolveRequest) =>
    post<VehicleResolution>('/v1/vehicles/resolve', body),
}

export interface AlertAuth {
  installation_id: string
  installation_token: string
}

export interface AlertWatch {
  enabled: boolean
  canonical_id: string | null
  source: string
  station_id: string
  station_name: string
  fuel_type: 'regular' | 'midgrade' | 'premium' | 'diesel'
  payment_type: 'cash' | 'credit' | 'unknown'
  membership_required: string | null
  octane: number | null
  currency: 'USD'
  unit: 'US_gallon'
  expected_gallons: number
  threshold_cents: number
}
