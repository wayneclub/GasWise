"""Bounded public diagnostic codes. Never persist transport text, tokens or payloads."""
from gaswise.domain.ports import ProviderError

SAFE_CODES = frozenset({
    'gasbuddy_http_unavailable', 'gasbuddy_http_schema_changed', 'gasbuddy_http_csrf_missing',
    'gasbuddy_http_query_rejected', 'gasbuddy_http_bootstrap_rejected', 'gasbuddy_http_api_rejected',
    'gasbuddy_http_bootstrap_challenge', 'gasbuddy_http_api_challenge', 'gasbuddy_rate_limited',
    'gasbuddy_access_rejected_cooldown', 'gasbuddy_web_schema_changed',
    'shared_pricing_cache_unavailable', 'shared_pricing_refresh_pending', 'shared_pricing_refresh_lease_lost',
    'shared_pricing_budget_unavailable', 'gasbuddy_web_access_rejected', 'gasbuddy_web_query_rejected',
    'google_maps_web_unavailable', 'google_maps_web_unexpected_response', 'google_maps_web_rate_limited',
    'google_maps_web_session_rejected', 'google_maps_web_blocked_or_redirected',
    'google_maps_web_session_expired', 'google_maps_web_private_session_invalid',
    'waze_upstream_unavailable', 'waze_upstream_rejected_request', 'waze_invalid_response',
    'waze_rate_limited', 'waze_reauthentication_required',
})


def safe_failure_code(error):
    if isinstance(error, ProviderError) and str(error) in SAFE_CODES:
        return str(error)
    for kind in (TimeoutError, ValueError, TypeError, KeyError):
        if isinstance(error, kind):
            return kind.__name__
    return 'unclassified'
