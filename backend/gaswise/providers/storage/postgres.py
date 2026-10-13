"""Shared public pricing cache on the operator's existing PostgreSQL server."""

import hashlib
import json
from datetime import UTC, datetime
from importlib.resources import files

import asyncpg
from pydantic import SecretStr

from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.cache_policy import prune_quotes, public_quotes, quote_expiry
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
        stations, prices = [], []
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

    async def mappings(self, source, ids):
        rows = await self.pool.fetch("""
            SELECT station_id, canonical_id FROM gaswise.stations
            WHERE source=$1 AND station_id=ANY($2::text[]) AND canonical_id LIKE 'google_places:%'
        """, source, ids)
        return {row["station_id"]: row["canonical_id"] for row in rows}

    async def consume(self, source, limit):
        async with self.pool.acquire() as connection, connection.transaction():
            await connection.execute("INSERT INTO gaswise.source_limits(source) VALUES($1) ON CONFLICT DO NOTHING", source)
            row = await connection.fetchrow("""
                SELECT *, now() AS clock FROM gaswise.source_limits WHERE source=$1 FOR UPDATE
            """, source)
            if row["blocked_until"] and row["blocked_until"] > row["clock"]:
                raise ProviderError(f"{source}_rate_limited")
            reset = (row["clock"] - row["window_start"]).total_seconds() >= 60
            if not reset and row["request_count"] >= limit:
                raise ProviderError(f"{source}_request_budget_exhausted")
            await connection.execute("""
                UPDATE gaswise.source_limits SET request_count=$2,
                window_start=CASE WHEN $3 THEN now() ELSE window_start END WHERE source=$1
            """, source, 1 if reset else row["request_count"] + 1, reset)

    async def cooldown(self, source, retry_seconds=None):
        await self.pool.execute("""
            INSERT INTO gaswise.source_limits(source,blocked_until,failure_count)
            VALUES($1, now() + $2 * interval '1 second', 1)
            ON CONFLICT(source) DO UPDATE SET
            blocked_until=GREATEST(source_limits.blocked_until,
                now() + GREATEST($2, LEAST(3600, 120 * power(2, LEAST(source_limits.failure_count,5)))) * interval '1 second'),
            failure_count=LEAST(source_limits.failure_count+1,6)
        """, source, float(retry_seconds or 120))

    async def cleanup(self):
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
