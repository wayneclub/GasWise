import type { SessionError } from './session'

const CODES: Record<string, string> = {
  prompt: 'prompt',
  permission_pending: 'permissionPending',
  denied: 'denied',
  unavailable: 'unavailable',
  location_timeout: 'locationTimeout',
  unsupported: 'unsupported',
  network_unavailable: 'network',
  invalid_api_token: 'auth',
  smart_routing_not_configured: 'routing',
  smart_price_sources_unavailable: 'sources',
  search_capacity_exceeded: 'busy',
  http_429: 'busy',
  gateway_rate_limit: 'busy',
  gateway_unavailable: 'network',
  http_504: 'timeout',
}

export function messageId(error: SessionError): string {
  return CODES[error.code] ?? (error.code.includes('timeout') ? 'timeout' : 'generic')
}
