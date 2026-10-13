CREATE SCHEMA IF NOT EXISTS gaswise;
CREATE TABLE IF NOT EXISTS gaswise.query_cache (
    key text PRIMARY KEY,
    source text NOT NULL,
    payload jsonb,
    fetched_at timestamptz,
    fresh_until timestamptz,
    stale_until timestamptz,
    lease_owner text,
    lease_until timestamptz,
    CHECK (length(key) = 64)
);
CREATE INDEX IF NOT EXISTS query_cache_expiry ON gaswise.query_cache (stale_until);
CREATE TABLE IF NOT EXISTS gaswise.stations (
    source text NOT NULL,
    station_id text NOT NULL,
    canonical_id text,
    metadata jsonb NOT NULL,
    seen_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source, station_id)
);
CREATE TABLE IF NOT EXISTS gaswise.quotes (
    source text NOT NULL,
    station_id text NOT NULL,
    fuel_type text NOT NULL,
    payment_type text NOT NULL,
    purchase_condition text NOT NULL,
    payload jsonb NOT NULL,
    reported_at timestamptz,
    fetched_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    PRIMARY KEY (source, station_id, fuel_type, payment_type, purchase_condition)
);
CREATE INDEX IF NOT EXISTS quotes_expiry ON gaswise.quotes (expires_at);
CREATE TABLE IF NOT EXISTS gaswise.source_limits (
    source text PRIMARY KEY,
    window_start timestamptz NOT NULL DEFAULT now(),
    request_count integer NOT NULL DEFAULT 0,
    blocked_until timestamptz,
    failure_count integer NOT NULL DEFAULT 0
);
