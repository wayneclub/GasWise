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

-- Background counters are shared across workers and reserve foreground capacity.
ALTER TABLE gaswise.source_limits ADD COLUMN IF NOT EXISTS background_count integer NOT NULL DEFAULT 0;
ALTER TABLE gaswise.source_limits ADD COLUMN IF NOT EXISTS background_day_start timestamptz NOT NULL DEFAULT now();
ALTER TABLE gaswise.source_limits ADD COLUMN IF NOT EXISTS background_day_count integer NOT NULL DEFAULT 0;

-- Analytical observations are independent of the short-lived serving cache.
CREATE TABLE IF NOT EXISTS gaswise.quote_history (
    observation_key text PRIMARY KEY,
    source text NOT NULL,
    station_id text NOT NULL,
    canonical_id text,
    fuel_type text NOT NULL,
    payment_type text NOT NULL,
    purchase_condition text NOT NULL,
    price_per_gallon numeric NOT NULL,
    reported_at timestamptz,
    first_seen_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    attributes jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS quote_history_station_time
    ON gaswise.quote_history (source, station_id, fuel_type, reported_at);
CREATE INDEX IF NOT EXISTS quote_history_canonical_time
    ON gaswise.quote_history (canonical_id, fuel_type, reported_at);

-- Fixed public city-base collection; no visitor-derived locations or credentials.
CREATE TABLE IF NOT EXISTS gaswise.base_collection_jobs (
    id text PRIMARY KEY,
    base text NOT NULL,
    source text NOT NULL,
    fuel text NOT NULL,
    descriptor jsonb NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    next_due timestamptz NOT NULL DEFAULT now(),
    lease_owner text,
    lease_until timestamptz,
    last_success timestamptz,
    failures integer NOT NULL DEFAULT 0,
    last_error text,
    quote_count integer NOT NULL DEFAULT 0,
    station_count integer NOT NULL DEFAULT 0
);

ALTER TABLE gaswise.base_collection_jobs ADD COLUMN IF NOT EXISTS population_priority integer NOT NULL DEFAULT 0;

ALTER TABLE gaswise.source_limits ADD COLUMN IF NOT EXISTS adaptive_daily_limit integer;
ALTER TABLE gaswise.source_limits ADD COLUMN IF NOT EXISTS adaptive_daily_floor integer;
ALTER TABLE gaswise.source_limits ADD COLUMN IF NOT EXISTS adaptive_daily_max integer;
ALTER TABLE gaswise.source_limits ADD COLUMN IF NOT EXISTS daily_review_at timestamptz;
ALTER TABLE gaswise.source_limits ADD COLUMN IF NOT EXISTS daily_review_requests integer NOT NULL DEFAULT 0;
ALTER TABLE gaswise.source_limits ADD COLUMN IF NOT EXISTS last_rejection_at timestamptz;
ALTER TABLE gaswise.source_limits ADD COLUMN IF NOT EXISTS last_collection_failure_at timestamptz;
ALTER TABLE gaswise.source_limits ADD COLUMN IF NOT EXISTS background_last_request_at timestamptz;

ALTER TABLE gaswise.base_collection_jobs ADD COLUMN IF NOT EXISTS mandatory boolean NOT NULL DEFAULT false;
ALTER TABLE gaswise.base_collection_jobs ADD COLUMN IF NOT EXISTS request_reserve integer NOT NULL DEFAULT 1;

ALTER TABLE gaswise.source_limits ADD COLUMN IF NOT EXISTS background_job_pacing boolean NOT NULL DEFAULT false;
ALTER TABLE gaswise.source_limits ADD COLUMN IF NOT EXISTS background_next_job_at timestamptz;

ALTER TABLE gaswise.base_collection_jobs ADD COLUMN IF NOT EXISTS last_failure_code text;
ALTER TABLE gaswise.base_collection_jobs ADD COLUMN IF NOT EXISTS last_failure_at timestamptz;

-- Append-only attempt history; public city jobs only, no raw transport payloads.
ALTER TABLE gaswise.base_collection_jobs ADD COLUMN IF NOT EXISTS last_started_at timestamptz;
CREATE TABLE IF NOT EXISTS gaswise.collection_runs (
    id bigserial PRIMARY KEY,
    job_id text NOT NULL, owner text NOT NULL,
    base text NOT NULL, source text NOT NULL, fuel text NOT NULL,
    started_at timestamptz, finished_at timestamptz NOT NULL DEFAULT now(),
    outcome text NOT NULL CHECK(outcome IN ('success','failure','deferred','interrupted')),
    reason text, http_status integer CHECK(http_status BETWEEN 100 AND 599),
    phase text, egress_lane integer CHECK(egress_lane BETWEEN 0 AND 2),
    http_requests integer NOT NULL DEFAULT 0 CHECK(http_requests>=0),
    quote_count integer NOT NULL DEFAULT 0, station_count integer NOT NULL DEFAULT 0,
    retry_at timestamptz,
    UNIQUE(job_id,owner)
);
CREATE INDEX IF NOT EXISTS collection_runs_time ON gaswise.collection_runs(finished_at DESC);
CREATE TABLE IF NOT EXISTS gaswise.collection_notifications (
    id bigserial PRIMARY KEY, dedupe_key text NOT NULL UNIQUE,
    kind text NOT NULL, payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), sent_at timestamptz,
    next_try timestamptz NOT NULL DEFAULT now(), attempts integer NOT NULL DEFAULT 0,
    lease_owner text, lease_until timestamptz, last_error text,
    telegram_message_id bigint
);
CREATE TABLE IF NOT EXISTS gaswise.collection_notification_clock (
    name text PRIMARY KEY, next_at timestamptz NOT NULL
);

ALTER TABLE gaswise.collection_notifications ADD COLUMN IF NOT EXISTS last_attempt_at timestamptz;
ALTER TABLE gaswise.collection_notifications ADD COLUMN IF NOT EXISTS last_error_at timestamptz;
ALTER TABLE gaswise.collection_notifications ADD COLUMN IF NOT EXISTS expired_at timestamptz;

CREATE INDEX IF NOT EXISTS collection_notifications_pending
    ON gaswise.collection_notifications(next_try,created_at) WHERE sent_at IS NULL AND expired_at IS NULL;
