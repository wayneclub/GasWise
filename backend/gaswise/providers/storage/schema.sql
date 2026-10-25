CREATE SCHEMA IF NOT EXISTS gaswise;
-- Public EPA reference data only. This table never stores a user's selected car.
CREATE TABLE IF NOT EXISTS gaswise.vehicle_records (
    vehicle_id integer PRIMARY KEY CHECK(vehicle_id > 0),
    source text NOT NULL CHECK(source = 'fueleconomy_gov'),
    model_year integer NOT NULL CHECK(model_year BETWEEN 1984 AND 2100),
    make text NOT NULL,
    model text NOT NULL,
    payload jsonb NOT NULL,
    fetched_at timestamptz NOT NULL,
    refresh_after timestamptz NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS vehicle_records_identity
    ON gaswise.vehicle_records(model_year,make,model);
CREATE INDEX IF NOT EXISTS vehicle_records_refresh
    ON gaswise.vehicle_records(refresh_after);
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
-- Only public provider queries are retained. Background refresh never renews demand.
CREATE TABLE IF NOT EXISTS gaswise.warm_queries (
    key text PRIMARY KEY CHECK(length(key)=64),
    source text NOT NULL CHECK(source IN ('gasbuddy','maps','waze')),
    raw_key text NOT NULL CHECK(length(raw_key)<=16384),
    created_at timestamptz NOT NULL DEFAULT now(),
    last_requested_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now()+interval '14 days',
    next_due timestamptz NOT NULL,
    lease_owner text,
    lease_until timestamptz,
    last_attempt_at timestamptz,
    last_success_at timestamptz,
    last_error text
);
CREATE INDEX IF NOT EXISTS warm_queries_due ON gaswise.warm_queries(next_due,source);
CREATE INDEX IF NOT EXISTS warm_queries_expiry ON gaswise.warm_queries(expires_at);
CREATE TABLE IF NOT EXISTS gaswise.stations (
    source text NOT NULL,
    station_id text NOT NULL,
    canonical_id text,
    metadata jsonb NOT NULL,
    seen_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source, station_id)
);
CREATE INDEX IF NOT EXISTS stations_canonical_id ON gaswise.stations (canonical_id);
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
    ON gaswise.quote_history (source, station_id, fuel_type, reported_at DESC);
CREATE INDEX IF NOT EXISTS quote_history_canonical_time
    ON gaswise.quote_history (canonical_id, fuel_type, reported_at DESC);

-- Actual daily fetches, independent of source report identity. Never backfilled.
CREATE TABLE IF NOT EXISTS gaswise.quote_daily (
    observation_key text NOT NULL,
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
    attributes jsonb NOT NULL,
    observed_day date NOT NULL,
    PRIMARY KEY (observation_key, observed_day)
);
CREATE INDEX IF NOT EXISTS quote_daily_station_day
    ON gaswise.quote_daily(source, station_id, fuel_type, observed_day);
CREATE INDEX IF NOT EXISTS quote_daily_canonical_time
    ON gaswise.quote_daily(canonical_id, fuel_type, first_seen_at DESC);

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
ALTER TABLE gaswise.base_collection_jobs ADD COLUMN IF NOT EXISTS coverage_station_id text;

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
ALTER TABLE gaswise.collection_runs ADD COLUMN IF NOT EXISTS canonical_count integer NOT NULL DEFAULT 0;
ALTER TABLE gaswise.collection_runs ADD COLUMN IF NOT EXISTS new_canonical_count integer NOT NULL DEFAULT 0;
ALTER TABLE gaswise.collection_runs ADD COLUMN IF NOT EXISTS located_count integer NOT NULL DEFAULT 0;
ALTER TABLE gaswise.collection_runs ADD COLUMN IF NOT EXISTS priced_count integer NOT NULL DEFAULT 0;
ALTER TABLE gaswise.collection_runs ADD COLUMN IF NOT EXISTS inventory_overlap_count integer NOT NULL DEFAULT 0;
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

-- User smart alerts are isolated from operator collection notifications. Push
-- subscriptions are application-encrypted; only endpoint hashes are queryable.
CREATE TABLE IF NOT EXISTS gaswise.alert_installations (
    id text PRIMARY KEY,
    token_hash text NOT NULL,
    endpoint_hash text NOT NULL UNIQUE,
    subscription_ciphertext bytea NOT NULL,
    timezone text NOT NULL,
    locale text NOT NULL DEFAULT 'en',
    created_at timestamptz NOT NULL DEFAULT now(),
    confirmed_at timestamptz NOT NULL DEFAULT now(),
    disabled_at timestamptz
);
ALTER TABLE gaswise.alert_installations ADD COLUMN IF NOT EXISTS locale text NOT NULL DEFAULT 'en';
CREATE TABLE IF NOT EXISTS gaswise.alert_watches (
    id bigserial PRIMARY KEY,
    installation_id text NOT NULL REFERENCES gaswise.alert_installations(id) ON DELETE CASCADE,
    canonical_id text,
    source text NOT NULL,
    station_id text NOT NULL,
    station_name text NOT NULL,
    fuel_type text NOT NULL,
    payment_type text NOT NULL,
    purchase_condition text NOT NULL,
    expected_gallons numeric NOT NULL CHECK(expected_gallons BETWEEN 1 AND 30),
    threshold_cents integer NOT NULL CHECK(threshold_cents BETWEEN 5 AND 100),
    created_at timestamptz NOT NULL DEFAULT now(),
    last_evaluated_observation text,
    last_alert_at timestamptz,
    lease_owner text,
    lease_until timestamptz,
    UNIQUE(installation_id,source,station_id,fuel_type,payment_type,purchase_condition)
);
CREATE TABLE IF NOT EXISTS gaswise.alert_need_state (
    installation_id text PRIMARY KEY REFERENCES gaswise.alert_installations(id) ON DELETE CASCADE,
    state text NOT NULL CHECK (state IN ('not_due','approaching','due','unknown')),
    confidence text NOT NULL CHECK (confidence IN ('high','medium','low')),
    calculated_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS gaswise.alert_outbox (
    id bigserial PRIMARY KEY,
    installation_id text NOT NULL REFERENCES gaswise.alert_installations(id) ON DELETE CASCADE,
    dedupe_key text NOT NULL UNIQUE,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    attempts integer NOT NULL DEFAULT 0,
    next_try timestamptz NOT NULL DEFAULT now(),
    lease_owner text,
    lease_until timestamptz,
    sent_at timestamptz,
    last_error text
);
CREATE TABLE IF NOT EXISTS gaswise.alert_inbox (
    id bigserial PRIMARY KEY,
    installation_id text NOT NULL REFERENCES gaswise.alert_installations(id) ON DELETE CASCADE,
    dedupe_key text NOT NULL UNIQUE,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS alert_inbox_recent ON gaswise.alert_inbox(installation_id,created_at DESC);
CREATE INDEX IF NOT EXISTS alert_outbox_pending ON gaswise.alert_outbox(next_try,created_at)
    WHERE sent_at IS NULL;

ALTER TABLE gaswise.collection_notifications ADD COLUMN IF NOT EXISTS last_attempt_at timestamptz;
ALTER TABLE gaswise.collection_notifications ADD COLUMN IF NOT EXISTS last_error_at timestamptz;
ALTER TABLE gaswise.collection_notifications ADD COLUMN IF NOT EXISTS expired_at timestamptz;

CREATE INDEX IF NOT EXISTS collection_notifications_pending
    ON gaswise.collection_notifications(next_try,created_at) WHERE sent_at IS NULL AND expired_at IS NULL;
