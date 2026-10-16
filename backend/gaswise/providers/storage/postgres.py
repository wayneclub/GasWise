"""Shared public pricing cache on the operator's existing PostgreSQL server."""

import hashlib
import json
from datetime import UTC, datetime
from importlib.resources import files

import asyncpg
from pydantic import SecretStr

from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.cache_policy import prune_quotes, public_quotes, quote_expiry
from gaswise.domain.pricing.daily_ramp import reviewed_limit
from gaswise.domain.pricing.shared_cache import CachedQuery


class PostgresPricingCache:
    def __init__(self, pool):
        self.pool = pool

    @classmethod
    async def connect(cls, dsn):
        dsn = SecretStr(dsn)
        pool = None
        try:
            pool = await asyncpg.create_pool(dsn.get_secret_value(), min_size=1, max_size=4, timeout=8, command_timeout=8)
            async with pool.acquire() as connection, connection.transaction():
                await connection.execute("SELECT pg_advisory_xact_lock(743103131)")
                await connection.execute(files("gaswise.providers.storage").joinpath("schema.sql").read_text())
        except Exception:
            if pool is not None:
                await pool.close()
            raise RuntimeError("Shared pricing PostgreSQL startup failed; check private configuration") from None
        return cls(pool)

    async def configure_base_jobs(self, jobs):
        async with self.pool.acquire() as connection, connection.transaction():
            await connection.execute("SELECT pg_advisory_xact_lock(743103132)")
            await connection.execute("UPDATE gaswise.base_collection_jobs SET enabled=false WHERE NOT(id=ANY($1::text[]))", [job["id"] for job in jobs])
            for job in jobs:
                await connection.execute("""
                    INSERT INTO gaswise.base_collection_jobs(id,base,source,fuel,descriptor,population_priority,mandatory,request_reserve)
                    VALUES($1,$2,$3,$4,$5::jsonb,$6,$7,$8) ON CONFLICT(id) DO UPDATE SET enabled=true,
                    next_due=CASE WHEN base_collection_jobs.descriptor IS DISTINCT FROM EXCLUDED.descriptor
                                  THEN now() ELSE base_collection_jobs.next_due END,
                    descriptor=EXCLUDED.descriptor,population_priority=EXCLUDED.population_priority,
                    mandatory=EXCLUDED.mandatory,request_reserve=EXCLUDED.request_reserve
                """, job["id"], job["base"], job["source"], job["fuel"], json.dumps(job["descriptor"]), job["population_priority"], job.get("mandatory", False), job.get("request_reserve", 1))

    async def base_jobs_pending(self, source):
        return await self.pool.fetchval("SELECT EXISTS(SELECT 1 FROM gaswise.base_collection_jobs WHERE enabled AND source=$1 AND next_due<=now())", source)

    async def configure_background_pacing(self, source, enabled):
        await self.pool.execute("""
            INSERT INTO gaswise.source_limits(source,background_job_pacing) VALUES($1,$2)
            ON CONFLICT(source) DO UPDATE SET background_job_pacing=$2
        """, source, enabled)

    async def claim_base_job(self, owner, sources):
        async with self.pool.acquire() as connection, connection.transaction():
            # Serialize job-start reservations across workers; never hold locks during HTTP.
            await connection.fetch("SELECT source FROM gaswise.source_limits WHERE source=ANY($1::text[]) ORDER BY source FOR UPDATE", sources)
            job = await connection.fetchrow("""
                SELECT j.id,j.source,j.request_reserve FROM gaswise.base_collection_jobs j
                WHERE enabled AND next_due<=now() AND source=ANY($1::text[])
                  AND (lease_until IS NULL OR lease_until<=now())
                  AND (mandatory OR NOT EXISTS(SELECT 1 FROM gaswise.source_limits l WHERE l.source=j.source
                       AND l.background_job_pacing AND l.background_next_job_at>now()))
                ORDER BY mandatory DESC,
                    (10*ln(1+population_priority)/ln(10) + 2*GREATEST(0,EXTRACT(EPOCH FROM (now()-next_due))/3600)
                     + CASE WHEN last_success IS NULL THEN 30 ELSE 0 END) DESC,next_due,id
                FOR UPDATE SKIP LOCKED LIMIT 1
            """, sources)
            if job is None:
                return None
            await connection.execute("""UPDATE gaswise.base_collection_jobs SET lease_owner=$2,
                lease_until=now()+interval '15 minutes' WHERE id=$1""", job["id"], owner)
            await connection.execute("""UPDATE gaswise.source_limits SET
                background_next_job_at=now()+($2::double precision*86400/GREATEST(1,adaptive_daily_limit))*interval '1 second'
                WHERE source=$1 AND background_job_pacing AND adaptive_daily_limit IS NOT NULL""",
                job["source"], job["request_reserve"])
            return job["id"]

    async def finish_base_job(self, job_id, owner, delay, error, quotes, stations):
        if error == "collection_failed":
            await self.pool.execute("""
                UPDATE gaswise.source_limits SET last_collection_failure_at=now(),
                    daily_review_at=CASE WHEN adaptive_daily_limit IS NULL THEN daily_review_at ELSE now() END,
                    daily_review_requests=0
                WHERE source=(SELECT source FROM gaswise.base_collection_jobs WHERE id=$1 AND lease_owner=$2)
            """, job_id, owner)
        await self.pool.execute("""
            UPDATE gaswise.base_collection_jobs SET next_due=now()+$3*interval '1 second',
            lease_owner=NULL,lease_until=NULL,last_error=$4,
            last_success=CASE WHEN $4::text IS NULL THEN now() ELSE last_success END,
            failures=CASE WHEN $4::text IS NULL THEN 0 ELSE failures+1 END,
            quote_count=CASE WHEN $4::text IS NULL THEN $5 ELSE quote_count END,
            station_count=CASE WHEN $4::text IS NULL THEN $6 ELSE station_count END
            WHERE id=$1 AND lease_owner=$2
        """, job_id, owner, float(delay), error, quotes, stations)

    async def base_job_status(self):
        rows = await self.pool.fetch("""SELECT id,base,source,fuel,next_due,last_success,failures,last_error,quote_count,station_count,mandatory,request_reserve,
            (10*ln(1+population_priority)/ln(10) + 2*GREATEST(0,EXTRACT(EPOCH FROM (now()-next_due))/3600)
             + CASE WHEN last_success IS NULL THEN 30 ELSE 0 END)::float AS priority_score,
            (mandatory AND next_due<=now()) AS mandatory_due FROM gaswise.base_collection_jobs WHERE enabled ORDER BY mandatory DESC,priority_score DESC,base,fuel,source""")
        return [dict(row) for row in rows]

    async def price_history(self, canonical_id, source, station_id, fuel_type, days):
        rows = await self.pool.fetch("""
            SELECT source, station_id, payment_type, purchase_condition,
                   price_per_gallon, reported_at, first_seen_at, attributes
            FROM gaswise.quote_history
            WHERE ((canonical_id = $1 AND $1::text IS NOT NULL)
                   OR (source = $2 AND station_id = $3))
              AND fuel_type = $4
              AND COALESCE(reported_at, first_seen_at) >= now() - make_interval(days => $5)
              AND COALESCE(reported_at, first_seen_at) <= now()
            ORDER BY COALESCE(reported_at, first_seen_at) DESC, observation_key
            LIMIT 1001
        """, canonical_id, source, station_id, fuel_type, days)
        observations = []
        for row in rows[:1000]:
            attrs = json.loads(row["attributes"]) if isinstance(row["attributes"], str) else row["attributes"]
            observations.append({
                "source": row["source"], "station_id": row["station_id"],
                "payment_type": row["payment_type"], "condition": row["purchase_condition"],
                "price": str(row["price_per_gallon"]),
                "reported_at": row["reported_at"].isoformat() if row["reported_at"] else None,
                "observed_at": row["first_seen_at"].isoformat(),
                "membership": attrs.get("membership_required"), "octane": attrs.get("octane"),
            })
        return {"observations": observations, "truncated": len(rows) > 1000}

    async def payment_history(self, keys, fuel_types):
        rows = await self.pool.fetch("""
            SELECT * FROM (
                SELECT canonical_id, source, station_id, fuel_type, payment_type,
                       price_per_gallon, reported_at, first_seen_at, attributes,
                       row_number() OVER (PARTITION BY canonical_id, fuel_type, payment_type,
                           purchase_condition ORDER BY reported_at DESC) AS position
                FROM gaswise.quote_history
                WHERE canonical_id = ANY($1::text[]) AND fuel_type = ANY($2::text[]) AND reported_at >= now() - interval '30 days'
                  AND payment_type IN ('cash','credit')
            ) history WHERE position <= 30
            ORDER BY canonical_id, position, reported_at DESC
        """, keys, fuel_types)
        result = {}
        for row in rows:
            try:
                attrs = json.loads(row["attributes"])
                if not isinstance(attrs, dict):
                    continue
            except (ValueError, TypeError):
                continue
            if not attrs.get("location") or not attrs.get("name"):
                continue
            quote = {**attrs, "id": row["station_id"], "canonical_id": row["canonical_id"],
                     "source": row["source"], "fuel_type": row["fuel_type"], "payment_type": row["payment_type"],
                     "price_per_gallon": str(row["price_per_gallon"]), "price_updated_at": row["reported_at"].isoformat(),
                     "fetched_at": row["first_seen_at"].isoformat()}
            bucket = result.setdefault(row["canonical_id"], [])
            if len(bucket) < 240:
                bucket.append(quote)
        return result

    async def close(self):
        await self.pool.close()

    async def read(self, key):
        row = await self.pool.fetchrow("""
            SELECT payload, fetched_at, fresh_until > now() AS fresh, stale_until > now() AS usable
            FROM gaswise.query_cache WHERE key=$1 AND payload IS NOT NULL
        """, key)
        if row is None:
            return None
        return CachedQuery(prune_quotes(json.loads(row["payload"])), bool(row["fresh"]), bool(row["usable"]), row["fetched_at"])

    async def claim(self, key, source, owner):
        # A lease replaces a long-held transaction while network I/O is in progress.
        claimed = await self.pool.fetchval("""
            INSERT INTO gaswise.query_cache (key, source, lease_owner, lease_until)
            VALUES ($1, $2, $3, now() + interval '120 seconds')
            ON CONFLICT (key) DO UPDATE SET lease_owner=$3, lease_until=now() + interval '120 seconds'
            WHERE query_cache.lease_until IS NULL OR query_cache.lease_until <= now()
            RETURNING key
        """, key, source, owner)
        return claimed is not None

    async def renew(self, key, owner):
        renewed = await self.pool.fetchval("""
            UPDATE gaswise.query_cache SET lease_until=now()+interval '120 seconds'
            WHERE key=$1 AND lease_owner=$2 AND lease_until > now() RETURNING key
        """,key,owner)
        return renewed is not None

    async def release(self, key, owner):
        await self.pool.execute("""
            UPDATE gaswise.query_cache SET lease_owner=NULL, lease_until=now() + interval '30 seconds'
            WHERE key=$1 AND lease_owner=$2
        """, key, owner)

    async def save(self, key, source, owner, payload, fresh_seconds):
        payload = prune_quotes(payload)
        async with self.pool.acquire() as connection, connection.transaction():
            saved = await connection.fetchval("""
                UPDATE gaswise.query_cache SET payload=$3::jsonb, fetched_at=now(),
                fresh_until=now() + $4 * interval '1 second',
                stale_until=now() + interval '1 hour', lease_owner=NULL, lease_until=NULL
                WHERE key=$1 AND lease_owner=$2 AND lease_until > now() RETURNING fetched_at
            """, key, owner, json.dumps(payload), fresh_seconds)
            if saved:
                await self._observe(connection, public_quotes(payload))
            return saved

    async def observe(self, stations):
        async with self.pool.acquire() as connection, connection.transaction():
            await self._observe(connection, [station.model_dump(mode="json") for station in stations])

    async def _observe(self, connection, quotes):
        now = datetime.now(UTC)
        stations, prices, history = [], [], []
        for quote in quotes:
            source = quote.get("source", "unknown")
            station_id = str(quote["id"])
            metadata = {k: quote[k] for k in ("name", "address", "location") if k in quote}
            fetched = datetime.fromisoformat(quote["fetched_at"].replace("Z", "+00:00"))
            stations.append((source, station_id, quote.get("canonical_id"), json.dumps(metadata), fetched))
            expires = quote_expiry(quote)
            if expires is None or expires <= now:
                continue
            reported = datetime.fromisoformat(quote["price_updated_at"].replace("Z", "+00:00")) if quote.get("price_updated_at") else None
            condition = hashlib.sha256(json.dumps({k: quote.get(k) for k in (
                "membership_required", "octane", "currency", "unit"
            )}, sort_keys=True).encode()).hexdigest()
            # Exclude retrieval time from identity: duplicate searches must not
            # look like new price reports. Unknown-time observations get daily buckets.
            identity = (source, station_id, quote["fuel_type"], quote["payment_type"],
                        condition, str(quote["price_per_gallon"]),
                        reported.isoformat() if reported else fetched.date().isoformat())
            observation = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
            attributes = {k: quote.get(k) for k in (
                "name", "address", "location", "membership_required", "octane", "currency", "unit"
            )}
            history.append((observation, source, station_id, quote.get("canonical_id"),
                            quote["fuel_type"], quote["payment_type"], condition,
                            quote["price_per_gallon"], reported, fetched, json.dumps(attributes)))
            prices.append((source, station_id, quote["fuel_type"], quote["payment_type"], condition,
                           json.dumps(quote), reported, fetched, expires))
        # Pipeline batches instead of making two network round-trips per quote.
        if stations:
            await connection.executemany("""
                INSERT INTO gaswise.stations (source, station_id, canonical_id, metadata, seen_at)
                VALUES ($1,$2,$3,$4::jsonb,$5) ON CONFLICT (source,station_id) DO UPDATE
                SET canonical_id=COALESCE(EXCLUDED.canonical_id, stations.canonical_id),
                    metadata=EXCLUDED.metadata, seen_at=GREATEST(stations.seen_at, EXCLUDED.seen_at)
                WHERE stations.metadata IS DISTINCT FROM EXCLUDED.metadata
                   OR EXCLUDED.canonical_id IS NOT NULL AND stations.canonical_id IS DISTINCT FROM EXCLUDED.canonical_id
                   OR EXCLUDED.seen_at > stations.seen_at
            """, stations)
        if prices:
            await connection.executemany("""
                INSERT INTO gaswise.quotes VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9)
                ON CONFLICT (source,station_id,fuel_type,payment_type,purchase_condition)
                DO UPDATE SET payload=EXCLUDED.payload, reported_at=EXCLUDED.reported_at,
                fetched_at=EXCLUDED.fetched_at, expires_at=EXCLUDED.expires_at
                WHERE EXCLUDED.fetched_at > quotes.fetched_at AND (
                    quotes.reported_at IS NULL OR EXCLUDED.reported_at >= quotes.reported_at
                    OR quotes.expires_at <= now())
            """, prices)

        if history:
            await connection.executemany("""
                INSERT INTO gaswise.quote_history
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8::numeric,$9,$10,$10,$11::jsonb)
                ON CONFLICT (observation_key) DO UPDATE
                SET first_seen_at=LEAST(quote_history.first_seen_at, EXCLUDED.first_seen_at),
                    last_seen_at=GREATEST(quote_history.last_seen_at, EXCLUDED.last_seen_at),
                    canonical_id=COALESCE(EXCLUDED.canonical_id,quote_history.canonical_id),
                    attributes=quote_history.attributes || jsonb_strip_nulls(EXCLUDED.attributes)
            """, history)

    async def mappings(self, source, ids):
        rows = await self.pool.fetch("""
            SELECT station_id, canonical_id FROM gaswise.stations
            WHERE source=$1 AND station_id=ANY($2::text[]) AND canonical_id LIKE 'google_places:%'
        """, source, ids)
        return {row["station_id"]: row["canonical_id"] for row in rows}

    async def configure_daily_ramp(self, sources, initial, floor, ceiling):
        async with self.pool.acquire() as connection, connection.transaction():
            for source in sources:
                await connection.execute("""
                    INSERT INTO gaswise.source_limits(source,adaptive_daily_limit,adaptive_daily_floor,
                        adaptive_daily_max,daily_review_at) VALUES($1,$2,$3,$4,now())
                    ON CONFLICT(source) DO UPDATE SET
                        adaptive_daily_limit=LEAST($4,GREATEST($3,COALESCE(source_limits.adaptive_daily_limit,$2))),
                        adaptive_daily_floor=$3,adaptive_daily_max=$4,
                        daily_review_at=COALESCE(source_limits.daily_review_at,now())
                """, source, initial, floor, ceiling)

    async def disable_daily_ramp(self, sources):
        await self.pool.execute("UPDATE gaswise.source_limits SET adaptive_daily_limit=NULL WHERE source=ANY($1::text[])", sources)

    async def _review_daily(self, connection, row):
        row = dict(row)
        limit = reviewed_limit(row)
        if limit is not None:
            await connection.execute("""
                UPDATE gaswise.source_limits SET adaptive_daily_limit=$2,daily_review_at=now(),
                    daily_review_requests=0 WHERE source=$1
            """, row["source"], limit)
            row.update(adaptive_daily_limit=limit, daily_review_at=row["clock"], daily_review_requests=0)
        return row

    async def budget_state(self, source):
        async with self.pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow("SELECT *,now() AS clock FROM gaswise.source_limits WHERE source=$1 FOR UPDATE", source)
            if row is None:
                return {"used": 0,"background_used": 0,"background_day_used": 0,"window_seconds": 0,"blocked_seconds": 0}
            row = await self._review_daily(connection, row)
            age = (row["clock"] - row["window_start"]).total_seconds()
            day_age = (row["clock"] - row["background_day_start"]).total_seconds()
            reservation = await connection.fetchrow("""
                SELECT COALESCE(SUM(request_reserve),0) AS requests,
                    COALESCE(bool_or(next_due<=now()),false) AS due
                FROM gaswise.base_collection_jobs WHERE enabled AND mandatory AND source=$1
                    AND next_due <= $2::timestamptz + interval '24 hours'
            """, source, row["clock"] if day_age >= 86400 else row["background_day_start"])
            return {
                "mandatory_reserved_requests": reservation["requests"],
                "mandatory_due": reservation["due"],
                "background_job_pacing": row["background_job_pacing"],
                "background_next_job_at": row["background_next_job_at"],
                "background_pacing_seconds": max(0, (row["background_next_job_at"]-row["clock"]).total_seconds())
                    if row["background_job_pacing"] and row["background_next_job_at"] else 0,
                "used": row["request_count"] if age < 60 else 0,
                "background_used": row["background_count"] if age < 60 else 0,
                "background_day_used": row["background_day_count"] if day_age < 86400 else 0,
                "window_seconds": max(0,60-age),
                "blocked_seconds": max(0,(row["blocked_until"]-row["clock"]).total_seconds()) if row["blocked_until"] else 0,
                "daily_limit": row["adaptive_daily_limit"],
                "daily_ramp_floor": row["adaptive_daily_floor"] if row["adaptive_daily_limit"] is not None else None,
                "daily_ramp_max": row["adaptive_daily_max"] if row["adaptive_daily_limit"] is not None else None,
                "daily_review_at": row["daily_review_at"],
                "daily_review_requests": row["daily_review_requests"],
            }

    async def consume(self, source, limit, *, background=False, background_daily_limit=100, mandatory=False):
        async with self.pool.acquire() as connection, connection.transaction():
            await connection.execute("INSERT INTO gaswise.source_limits(source) VALUES($1) ON CONFLICT DO NOTHING", source)
            row = await connection.fetchrow("""
                SELECT *, now() AS clock FROM gaswise.source_limits WHERE source=$1 FOR UPDATE
            """, source)
            row = await self._review_daily(connection, row)
            background_daily_limit = row["adaptive_daily_limit"] or background_daily_limit
            if row["blocked_until"] and row["blocked_until"] > row["clock"]:
                raise ProviderError(f"{source}_rate_limited")
            reset = (row["clock"] - row["window_start"]).total_seconds() >= 60
            day_reset = (row["clock"] - row["background_day_start"]).total_seconds() >= 86400
            used = 0 if reset else row["request_count"]
            bg_used = 0 if reset else row["background_count"]
            day_used = 0 if day_reset else row["background_day_count"]
            if used >= limit:
                raise ProviderError(f"{source}_request_budget_exhausted")
            if background and day_used >= background_daily_limit:
                raise ProviderError(f"{source}_background_daily_budget_exhausted")
            if background and not mandatory:
                reserved = await connection.fetchval("""
                    SELECT COALESCE(SUM(request_reserve),0) FROM gaswise.base_collection_jobs
                    WHERE enabled AND mandatory AND source=$1 AND next_due <= $2::timestamptz + interval '24 hours'
                """, source, row["clock"] if day_reset else row["background_day_start"])
                if day_used >= max(0, background_daily_limit - reserved):
                    raise ProviderError(f"{source}_mandatory_budget_reserved")
            if background and (used >= max(1, limit // 2) or bg_used >= max(1, limit // 5)):
                raise ProviderError(f"{source}_background_budget_exhausted")
            await connection.execute("""
                UPDATE gaswise.source_limits SET request_count=$2, background_count=$4,
                window_start=CASE WHEN $3 THEN now() ELSE window_start END,
                background_day_count=$5,
                background_day_start=CASE WHEN $6 THEN now() ELSE background_day_start END,
                daily_review_requests=CASE WHEN $7 THEN daily_review_requests+1 ELSE daily_review_requests END,
                background_last_request_at=CASE WHEN $7 THEN now() ELSE background_last_request_at END WHERE source=$1
            """, source, used + 1, reset, bg_used + int(background), day_used + int(background), day_reset, background)

    async def cooldown(self, source, retry_seconds=None):
        await self.pool.execute("""
            INSERT INTO gaswise.source_limits(source,blocked_until,failure_count,last_rejection_at)
            VALUES($1, now() + $2 * interval '1 second', 1,now())
            ON CONFLICT(source) DO UPDATE SET
            blocked_until=GREATEST(source_limits.blocked_until,
                now() + GREATEST($2, LEAST(3600, 120 * power(2, LEAST(source_limits.failure_count,5)))) * interval '1 second'),
            failure_count=LEAST(source_limits.failure_count+1,6),last_rejection_at=now(),
            adaptive_daily_limit=CASE WHEN source_limits.adaptive_daily_limit IS NULL THEN NULL
                ELSE GREATEST(source_limits.adaptive_daily_floor,source_limits.adaptive_daily_limit/2) END,
            daily_review_at=CASE WHEN source_limits.adaptive_daily_limit IS NULL THEN source_limits.daily_review_at ELSE now() END,
            daily_review_requests=0
        """, source, float(retry_seconds or 120))

    async def cleanup(self):
        await self.pool.execute("DELETE FROM gaswise.quote_history WHERE last_seen_at < now() - interval '90 days'")
        await self.pool.execute("DELETE FROM gaswise.quotes WHERE expires_at <= now()")
        await self.pool.execute("""
            DELETE FROM gaswise.query_cache WHERE
            (stale_until <= now() OR payload IS NULL) AND (lease_until IS NULL OR lease_until <= now())
        """)
        # Expired quotes must also disappear from still-live response blobs.
        rows = await self.pool.fetch("SELECT key,payload FROM gaswise.query_cache WHERE payload IS NOT NULL")
        for row in rows:
            payload = json.loads(row["payload"])
            pruned = prune_quotes(payload)
            if pruned != payload:
                await self.pool.execute("""
                    UPDATE gaswise.query_cache SET payload=$2::jsonb WHERE key=$1 AND payload=$3::jsonb
                """, row["key"], json.dumps(pruned), json.dumps(payload))
