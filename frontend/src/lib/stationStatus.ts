import type { MessageKey } from '../i18n'
const REASONS = new Set(['routed', 'estimated_route', 'no_matching_fuel_price', 'wrong_fuel_type', 'payment_type_unverified', 'payment_type_mismatch', 'stale_price', 'membership_required', 'octane_not_verified_or_mismatch', 'station_closed', 'opening_status_unknown', 'outside_search_radius', 'route_not_calculated'])
export function reasonKey(status: string): MessageKey {
  return REASONS.has(status) ? `coverage.${status}` as MessageKey : 'coverage.other'
}
