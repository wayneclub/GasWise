import type {
  RankOptions, LocationResult,
  PartsRequest, PartsResult, PartsSearchRequest, PartsSearchResult, VinRequest, VinResolution, PlateRequest, PlateResolution,
  SmartResult,
  SmartSearchBody,
  SmartSnapshot,
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

export const api = {
  resolveLocation: (text: string, signal?: AbortSignal) => post<LocationResult>('/v1/locations/resolve', { text }, signal),
  partsSearch: (body: PartsSearchRequest, signal?: AbortSignal) => post<PartsSearchResult>('/v1/parts/search', body, signal),
  routes: (snapshot: SmartSnapshot, signature: string, signal?: AbortSignal) => post<SmartResult>('/v1/smart/routes', { snapshot, signature, route_limit: 100 }, signal),
  parts: (body: PartsRequest, signal?: AbortSignal) => post<PartsResult>('/v1/parts/fitment', body, signal),
  resolveVin: (body: VinRequest, signal?: AbortSignal) => post<VinResolution>('/v1/vehicles/vin', body, signal),
  resolvePlate: (body: PlateRequest, signal?: AbortSignal) => post<PlateResolution>('/v1/vehicles/plate', body, signal),
  /** Stage 1+2: one price acquisition plus a bounded route shortlist. Consumes upstream quota. */
  search: (body: SmartSearchBody, signal?: AbortSignal) =>
    post<SmartResult>('/v1/smart/search', body, signal),

  /** Recompute from the signed snapshot with zero upstream calls. */
  rerank: (snapshot: SmartSnapshot, signature: string, options: Partial<RankOptions>, signal?: AbortSignal) =>
    post<SmartResult>('/v1/smart/rerank', { snapshot, signature, options }, signal),

  resolveVehicle: (body: VehicleResolveRequest) =>
    post<VehicleResolution>('/v1/vehicles/resolve', body),
}
