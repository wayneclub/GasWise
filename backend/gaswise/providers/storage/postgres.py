"""Shared public pricing cache on the operator's existing PostgreSQL server."""

import hashlib
import json
from datetime import UTC, datetime
from importlib.resources import files

import asyncpg
from pydantic import SecretStr

from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.alerts import purchase_condition_key
from gaswise.domain.pricing.cache_policy import prune_quotes, public_quotes, quote_expiry
from gaswise.domain.pricing.daily_ramp import reviewed_limit
from gaswise.domain.pricing.shared_cache import CachedQuery
from gaswise.providers.storage.collection_events import CollectionEvents
from gaswise.providers.storage.warm_queries import WarmQueries

GOOGLE_LOCATION_SOURCES = {"google_maps_web", "google_places"}
STATION_DETAIL_KEYS = (
    "opening_status",
    "opening_hours",
    "opening_hours_text",
    "opening_status_checked_at",
    "services",
    "source_url",
)


def station_metadata(quote):
    """Provider coordinates and station facts; Google Maps remains the master record."""
    metadata = {key: quote[key] for key in ("name", "address") if quote.get(key) is not None}
    details = quote.get("details") if isinstance(quote.get("details"), dict) else {}
    location = quote.get("location")
    if isinstance(location, dict):
        lat, lng = location.get("lat"), location.get("lng")
        if (
            isinstance(lat, int | float) and not isinstance(lat, bool)
            and isinstance(lng, int | float) and not isinstance(lng, bool)
            and -90 <= lat <= 90 and -180 <= lng <= 180
            and (lat, lng) != (0, 0)
        ):
            metadata["location"] = {"lat": lat, "lng": lng}
            metadata["location_source"] = details.get("location_source") or quote.get("source", "unknown")
    for key in ("rating", "review_count", "rating_source", "open_now", "business_status"):
        if quote.get(key) is not None:
            metadata[key] = quote[key]
    for key in STATION_DETAIL_KEYS:
        value = details.get(key)
        if value not in (None, [], {}):
            metadata[key] = value
    return metadata


def station_attributes(quote):
    """History attributes include hours/status so later changes are retained."""
    attributes = {
        key: quote.get(key)
        for key in (
            "name", "address", "location", "membership_required", "octane", "currency", "unit",
            "rating", "review_count", "rating_source", "open_now", "business_status",
        )
    }
    details = quote.get("details") if isinstance(quote.get("details"), dict) else {}
    if quote.get("location") is not None:
        attributes["location_source"] = details.get("location_source") or quote.get("source", "unknown")
    for key in STATION_DETAIL_KEYS:
        value = details.get(key)
        if value not in (None, [], {}):
            attributes[key] = value
    return attributes


def station_checked_at(metadata, fallback):
    """Provider status-check time, or the fetch time when the provider did not send one."""
    value = metadata.get("opening_status_checked_at")
    if isinstance(value, datetime):
        checked = value
    elif isinstance(value, str):
        try:
            checked = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return fallback
    else:
        return fallback
    return checked.replace(tzinfo=UTC) if checked.tzinfo is None else checked


class PostgresPricingCache(CollectionEvents, WarmQueries):
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

    async def read_vehicle(self, vehicle_id):
        payload = await self.pool.fetchval(
            """SELECT payload FROM gaswise.vehicle_records
               WHERE vehicle_id=$1 AND source='fueleconomy_gov' AND refresh_after>now()""",
            vehicle_id,
        )
        if isinstance(payload, str):
            payload = json.loads(payload)
        return payload

    async def write_vehicle(self, vehicle, refresh_days=30):
        await self.pool.execute(
            """INSERT INTO gaswise.vehicle_records
                   (vehicle_id,source,model_year,make,model,payload,fetched_at,refresh_after)
               VALUES($1,$2,$3,$4,$5,$6::jsonb,$7,now()+make_interval(days=>$8))
               ON CONFLICT(vehicle_id) DO UPDATE SET
                   source=EXCLUDED.source,model_year=EXCLUDED.model_year,make=EXCLUDED.make,
                   model=EXCLUDED.model,payload=EXCLUDED.payload,fetched_at=EXCLUDED.fetched_at,
                   refresh_after=EXCLUDED.refresh_after,updated_at=now()""",
            vehicle.id,
            vehicle.source,
            vehicle.year,
            vehicle.make,
            vehicle.model,
            json.dumps(vehicle.model_dump(mode="json")),
            vehicle.fetched_at,
            refresh_days,
        )

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
                SELECT j.* FROM gaswise.base_collection_jobs j
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
            if job['lease_owner'] is not None:
                await self._append_collection_run(connection, dict(job), job['lease_owner'], 'lease_expired')
            await connection.execute("""UPDATE gaswise.base_collection_jobs SET lease_owner=$2,last_started_at=now(),
                lease_until=now()+interval '15 minutes' WHERE id=$1""", job["id"], owner)
            await connection.execute("""UPDATE gaswise.source_limits SET
                background_next_job_at=now()+($2::double precision*86400/GREATEST(1,adaptive_daily_limit))*interval '1 second'
                WHERE source=$1 AND background_job_pacing AND adaptive_daily_limit IS NOT NULL""",
                job["source"], job["request_reserve"])
            return job["id"]

    async def record_base_failure_diagnostic(self, job_id, owner, code):
        await self.pool.execute("""UPDATE gaswise.base_collection_jobs SET
            last_failure_code=$3,last_failure_at=now() WHERE id=$1 AND lease_owner=$2""", job_id, owner, code)

    async def new_collection_canonical_count(self, job_id, station_keys):
        if not station_keys:
            return 0
        return await self.pool.fetchval("""
            WITH incoming AS (
                SELECT source,station_id,canonical_id
                FROM jsonb_to_recordset($2::jsonb)
                AS x(source text,station_id text,canonical_id text)
            ), started AS (
                SELECT last_started_at FROM gaswise.base_collection_jobs WHERE id=$1
            )
            SELECT count(DISTINCT COALESCE(i.canonical_id,i.source||':'||i.station_id))
            FROM incoming i,started r
            WHERE NOT EXISTS (
                SELECT 1 FROM gaswise.stations old
                WHERE old.seen_at < r.last_started_at AND (
                    (i.canonical_id IS NOT NULL AND old.canonical_id=i.canonical_id)
                    OR (i.canonical_id IS NULL AND old.source=i.source AND old.station_id=i.station_id)
                )
            )
        """, job_id, json.dumps(station_keys))

    async def finish_base_job(self, job_id, owner, delay, error, quotes, stations, info=None):
        return await self.finish_collection_attempt(job_id, owner, delay, error, quotes, stations, info)

    async def base_job_status(self):
        rows = await self.pool.fetch("""SELECT id,base,source,fuel,next_due,last_success,failures,last_error,quote_count,station_count,mandatory,request_reserve,last_failure_code,last_failure_at,
            (10*ln(1+population_priority)/ln(10) + 2*GREATEST(0,EXTRACT(EPOCH FROM (now()-next_due))/3600)
             + CASE WHEN last_success IS NULL THEN 30 ELSE 0 END)::float AS priority_score,
            (mandatory AND next_due<=now()) AS mandatory_due FROM gaswise.base_collection_jobs WHERE enabled ORDER BY mandatory DESC,priority_score DESC,base,fuel,source""")
        return [dict(row) for row in rows]

    async def price_history(self, canonical_id, source, station_id, fuel_type, days):
        if canonical_id:
            rows = await self.pool.fetch("""
                SELECT source, station_id, payment_type, purchase_condition,
                       price_per_gallon, reported_at, first_seen_at, attributes
                FROM gaswise.quote_history
                WHERE (canonical_id = $1 OR (source = $2 AND station_id = $3))
                  AND fuel_type = $4
                  AND COALESCE(reported_at, first_seen_at) >= now() - make_interval(days => $5)
                  AND COALESCE(reported_at, first_seen_at) <= now()
                ORDER BY COALESCE(reported_at, first_seen_at) DESC, observation_key
                LIMIT 1001
            """, canonical_id, source, station_id, fuel_type, days)
        else:
            rows = await self.pool.fetch("""
                SELECT source, station_id, payment_type, purchase_condition,
                       price_per_gallon, reported_at, first_seen_at, attributes
                FROM gaswise.quote_history
                WHERE source = $1 AND station_id = $2
                  AND fuel_type = $3
                  AND COALESCE(reported_at, first_seen_at) >= now() - make_interval(days => $4)
                  AND COALESCE(reported_at, first_seen_at) <= now()
                ORDER BY COALESCE(reported_at, first_seen_at) DESC, observation_key
                LIMIT 1001
            """, source, station_id, fuel_type, days)
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

    async def create_alert_installation(self, installation_id, token_hash, endpoint_hash, ciphertext, timezone, locale):
        return await self.pool.fetchval("""
            INSERT INTO gaswise.alert_installations
                (id,token_hash,endpoint_hash,subscription_ciphertext,timezone,locale)
            VALUES($1,$2,$3,$4,$5,$6)
            ON CONFLICT(endpoint_hash) DO UPDATE SET token_hash=$2,
                subscription_ciphertext=$4,timezone=$5,locale=$6,confirmed_at=now(),disabled_at=NULL
            RETURNING id
        """, installation_id, token_hash, endpoint_hash, ciphertext, timezone, locale)

    async def set_alert_watch(self, installation_id, token_hash, enabled, canonical_id, source,
                              station_id, station_name, fuel_type, payment_type, condition,
                              expected_gallons, threshold_cents):
        async with self.pool.acquire() as connection, connection.transaction():
            valid = await connection.fetchval("""SELECT 1 FROM gaswise.alert_installations
                WHERE id=$1 AND token_hash=$2 AND disabled_at IS NULL FOR UPDATE""",
                installation_id, token_hash)
            if not valid:
                return False
            await connection.execute("UPDATE gaswise.alert_installations SET confirmed_at=now() WHERE id=$1", installation_id)
            if not enabled:
                await connection.execute("""DELETE FROM gaswise.alert_watches WHERE installation_id=$1
                    AND source=$2 AND station_id=$3 AND fuel_type=$4 AND payment_type=$5
                    AND purchase_condition=$6""", installation_id, source, station_id,
                    fuel_type, payment_type, condition)
                return True
            exists = await connection.fetchval("""SELECT EXISTS(SELECT 1 FROM gaswise.alert_watches
                WHERE installation_id=$1 AND source=$2 AND station_id=$3 AND fuel_type=$4
                  AND payment_type=$5 AND purchase_condition=$6)""", installation_id, source,
                station_id, fuel_type, payment_type, condition)
            count = await connection.fetchval("SELECT count(*) FROM gaswise.alert_watches WHERE installation_id=$1", installation_id)
            if not exists and count >= 20:
                return "limit"
            await connection.execute("""
                INSERT INTO gaswise.alert_watches(installation_id,canonical_id,source,station_id,
                    station_name,fuel_type,payment_type,purchase_condition,expected_gallons,threshold_cents)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                ON CONFLICT(installation_id,source,station_id,fuel_type,payment_type,purchase_condition)
                DO UPDATE SET canonical_id=EXCLUDED.canonical_id,station_name=EXCLUDED.station_name,
                    expected_gallons=EXCLUDED.expected_gallons,threshold_cents=EXCLUDED.threshold_cents
            """, installation_id, canonical_id, source, station_id, station_name, fuel_type,
                payment_type, condition, expected_gallons, threshold_cents)
            return True

    async def claim_alert_candidate(self, owner):
        async with self.pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow("""
                SELECT w.id AS watch_id,current.observation_key FROM gaswise.alert_watches w
                JOIN gaswise.alert_installations i ON i.id=w.installation_id AND i.disabled_at IS NULL
                JOIN LATERAL (SELECT observation_key FROM gaswise.quote_history h
                    WHERE h.source=w.source AND h.station_id=w.station_id AND h.fuel_type=w.fuel_type
                      AND h.payment_type=w.payment_type AND h.purchase_condition=w.purchase_condition
                    ORDER BY COALESCE(h.reported_at,h.first_seen_at) DESC,observation_key DESC LIMIT 1) current ON true
                WHERE current.observation_key IS DISTINCT FROM w.last_evaluated_observation
                  AND (w.lease_until IS NULL OR w.lease_until<=now())
                ORDER BY w.created_at FOR UPDATE OF w SKIP LOCKED LIMIT 1
            """)
            if row is None:
                return None
            watch_id = row["watch_id"]
            await connection.execute("""UPDATE gaswise.alert_watches SET lease_owner=$2,
                lease_until=now()+interval '2 minutes' WHERE id=$1""", watch_id, owner)
            candidate = await connection.fetchrow("""
                SELECT w.id AS watch_id,w.station_name,w.expected_gallons,w.threshold_cents,
                       i.locale,current.observation_key,current.price_per_gallon AS current_price,
                       previous.price_per_gallon AS previous_price,
                       GREATEST(0,EXTRACT(EPOCH FROM (now()-COALESCE(current.reported_at,current.first_seen_at)))/60)::int AS quote_age_minutes,
                       history.count::int AS comparable_observations,
                       COALESCE(CASE WHEN n.expires_at>now() THEN n.state END,'unknown') AS need_state,
                       COALESCE(CASE WHEN n.expires_at>now() THEN n.confidence END,'low') AS need_confidence,
                       EXISTS(SELECT 1 FROM gaswise.quote_history conflict
                           WHERE w.canonical_id IS NOT NULL AND conflict.canonical_id=w.canonical_id
                             AND conflict.source<>w.source AND conflict.fuel_type=w.fuel_type
                             AND conflict.payment_type=w.payment_type
                             AND conflict.purchase_condition=w.purchase_condition
                             AND COALESCE(conflict.reported_at,conflict.first_seen_at) >=
                                 COALESCE(current.reported_at,current.first_seen_at)-interval '6 hours'
                             AND abs(conflict.price_per_gallon-current.price_per_gallon)>=0.10
                       ) AS source_conflict
                FROM gaswise.alert_watches w
                JOIN gaswise.alert_installations i ON i.id=w.installation_id
                LEFT JOIN gaswise.alert_need_state n ON n.installation_id=i.id
                JOIN LATERAL (SELECT observation_key,price_per_gallon,reported_at,first_seen_at
                    FROM gaswise.quote_history h WHERE h.source=w.source AND h.station_id=w.station_id
                      AND h.fuel_type=w.fuel_type AND h.payment_type=w.payment_type
                      AND h.purchase_condition=w.purchase_condition
                    ORDER BY COALESCE(h.reported_at,h.first_seen_at) DESC,observation_key DESC LIMIT 1) current ON true
                JOIN LATERAL (SELECT price_per_gallon FROM gaswise.quote_history h
                    WHERE h.source=w.source AND h.station_id=w.station_id AND h.fuel_type=w.fuel_type
                      AND h.payment_type=w.payment_type AND h.purchase_condition=w.purchase_condition
                      AND h.observation_key<>current.observation_key
                    ORDER BY COALESCE(h.reported_at,h.first_seen_at) DESC,observation_key DESC LIMIT 1) previous ON true
                JOIN LATERAL (SELECT count(*) FROM gaswise.quote_history h
                    WHERE h.source=w.source AND h.station_id=w.station_id AND h.fuel_type=w.fuel_type
                      AND h.payment_type=w.payment_type AND h.purchase_condition=w.purchase_condition
                      AND COALESCE(h.reported_at,h.first_seen_at)>=now()-interval '30 days') history ON true
                WHERE w.id=$1 AND w.lease_owner=$2
            """, watch_id, owner)
            if candidate is None:
                await connection.execute("""UPDATE gaswise.alert_watches SET lease_owner=NULL,
                    lease_until=NULL,last_evaluated_observation=$3 WHERE id=$1 AND lease_owner=$2""",
                    watch_id, owner, row["observation_key"])
                return None
            return dict(candidate)

    async def finish_alert_candidate(self, watch_id, owner, observation_key, payload, delivery):
        async with self.pool.acquire() as connection, connection.transaction():
            watch = await connection.fetchrow("""UPDATE gaswise.alert_watches SET
                last_evaluated_observation=$3,lease_owner=NULL,lease_until=NULL,
                last_alert_at=CASE WHEN $4::jsonb IS NOT NULL THEN now() ELSE last_alert_at END
                WHERE id=$1 AND lease_owner=$2 RETURNING installation_id,last_alert_at""",
                watch_id, owner, observation_key, json.dumps(payload) if payload else None)
            if watch is None or payload is None:
                return False
            dedupe = f"watch:{watch_id}:{observation_key}"
            await connection.execute("""INSERT INTO gaswise.alert_inbox
                (installation_id,dedupe_key,payload,expires_at) VALUES($1,$2,$3::jsonb,now()+interval '30 days')
                ON CONFLICT(dedupe_key) DO NOTHING""", watch["installation_id"], dedupe, json.dumps(payload))
            if delivery != "push":
                return True
            # A delivered or queued alert suppresses the same watch for 24 hours.
            recent = await connection.fetchval("""SELECT EXISTS(SELECT 1 FROM gaswise.alert_outbox
                WHERE installation_id=$1 AND dedupe_key LIKE $2 AND created_at>now()-interval '24 hours')""",
                watch["installation_id"], f"watch:{watch_id}:%")
            if recent:
                return False
            await connection.execute("""INSERT INTO gaswise.alert_outbox
                (installation_id,dedupe_key,payload,expires_at) VALUES($1,$2,$3::jsonb,now()+interval '6 hours')
                ON CONFLICT(dedupe_key) DO NOTHING""", watch["installation_id"],
                dedupe, json.dumps(payload))
            return True

    async def alert_inbox(self, installation_id, token_hash):
        if not await self._valid_alert_installation(installation_id, token_hash):
            return None
        rows = await self.pool.fetch("""SELECT id,payload,created_at FROM gaswise.alert_inbox
            WHERE installation_id=$1 AND expires_at>now() ORDER BY created_at DESC LIMIT 20""", installation_id)
        result = []
        for row in rows:
            payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
            result.append({"id": row["id"], "title": payload.get("title", "GasWise"),
                           "body": payload.get("body", ""), "created_at": row["created_at"].isoformat()})
        return result

    async def release_alert_candidate(self, watch_id, owner):
        await self.pool.execute("""UPDATE gaswise.alert_watches SET lease_owner=NULL,
            lease_until=now()+interval '1 minute' WHERE id=$1 AND lease_owner=$2""", watch_id, owner)

    async def update_alert_need(self, installation_id, token_hash, state, confidence, expires_at):
        result = await self.pool.execute("""
            INSERT INTO gaswise.alert_need_state(installation_id,state,confidence,expires_at)
            SELECT id,$3,$4,$5 FROM gaswise.alert_installations
            WHERE id=$1 AND token_hash=$2 AND disabled_at IS NULL
            ON CONFLICT(installation_id) DO UPDATE SET state=$3,confidence=$4,
                calculated_at=now(),expires_at=$5
        """, installation_id, token_hash, state, confidence, expires_at)
        if result == "INSERT 0 1":
            await self.pool.execute("UPDATE gaswise.alert_installations SET confirmed_at=now() WHERE id=$1", installation_id)
        return result == "INSERT 0 1"

    async def queue_alert_test(self, installation_id, token_hash, locale):
        titles = {"zh-TW": "GasWise 智能提醒已啟用", "zh-CN": "GasWise 智能提醒已启用",
                  "es": "Alertas inteligentes activadas", "ja": "GasWise スマート通知が有効です",
                  "ko": "GasWise 스마트 알림이 켜졌습니다"}
        bodies = {"zh-TW": "之後只會在值得採取行動時通知你。", "zh-CN": "之后只会在值得采取行动时通知你。",
                  "es": "Solo te avisaremos cuando valga la pena actuar.", "ja": "行動する価値があるときだけ通知します。",
                  "ko": "행동할 가치가 있을 때만 알려드립니다."}
        payload = json.dumps({"title": titles.get(locale, "GasWise smart alerts are on"),
                              "body": bodies.get(locale, "You will only be notified when an opportunity is worth acting on."),
                              "url": "/?smart-alert=test", "tag": "gaswise-alert-test"})
        # One test per installation per minute prevents a valid token from becoming a push flood tool.
        result = await self.pool.execute("""
            INSERT INTO gaswise.alert_outbox(installation_id,dedupe_key,payload,expires_at)
            SELECT id,'test:'||id||':'||to_char(now(),'YYYYMMDDHH24MI'),$3::jsonb,now()+interval '5 minutes'
            FROM gaswise.alert_installations WHERE id=$1 AND token_hash=$2 AND disabled_at IS NULL
            ON CONFLICT(dedupe_key) DO NOTHING
        """, installation_id, token_hash, payload)
        return result in {"INSERT 0 1", "INSERT 0 0"} and await self._valid_alert_installation(installation_id, token_hash)

    async def _valid_alert_installation(self, installation_id, token_hash):
        return bool(await self.pool.fetchval("""SELECT 1 FROM gaswise.alert_installations
            WHERE id=$1 AND token_hash=$2 AND disabled_at IS NULL""", installation_id, token_hash))

    async def disable_alert_installation(self, installation_id, token_hash):
        result = await self.pool.execute("""DELETE FROM gaswise.alert_installations
            WHERE id=$1 AND token_hash=$2""", installation_id, token_hash)
        return result == "DELETE 1"

    async def claim_alert_notice(self, owner):
        async with self.pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow("""
                UPDATE gaswise.alert_outbox o SET lease_owner=$1,lease_until=now()+interval '2 minutes',
                    attempts=attempts+1
                FROM gaswise.alert_installations i
                WHERE o.id=(SELECT pending.id FROM gaswise.alert_outbox pending
                    JOIN gaswise.alert_installations target ON target.id=pending.installation_id
                    WHERE pending.sent_at IS NULL AND pending.expires_at>now() AND pending.next_try<=now()
                      AND (pending.lease_until IS NULL OR pending.lease_until<=now())
                      AND (pending.payload->>'tag'='gaswise-alert-test' OR
                           (EXTRACT(HOUR FROM now() AT TIME ZONE target.timezone)>=7 AND
                            EXTRACT(HOUR FROM now() AT TIME ZONE target.timezone)<22))
                    ORDER BY pending.created_at FOR UPDATE OF pending SKIP LOCKED LIMIT 1)
                  AND i.id=o.installation_id AND i.disabled_at IS NULL
                RETURNING o.id,o.payload,o.lease_owner,i.subscription_ciphertext
            """, owner)
            return dict(row) if row else None

    async def finish_alert_notice(self, notice_id, owner, retry=False, permanent=False):
        if permanent:
            await self.pool.execute("""DELETE FROM gaswise.alert_installations i USING gaswise.alert_outbox o
                WHERE o.id=$1 AND o.lease_owner=$2 AND i.id=o.installation_id""", notice_id, owner)
            return
        if retry:
            await self.pool.execute("""UPDATE gaswise.alert_outbox SET lease_owner=NULL,lease_until=NULL,
                next_try=now()+LEAST(3600,30*power(2,LEAST(attempts,7)))*interval '1 second',
                last_error='delivery_deferred' WHERE id=$1 AND lease_owner=$2""", notice_id, owner)
        else:
            await self.pool.execute("""UPDATE gaswise.alert_outbox SET sent_at=now(),lease_owner=NULL,
                lease_until=NULL,last_error=$3 WHERE id=$1 AND lease_owner=$2""",
                notice_id, owner, "endpoint_gone" if permanent else None)

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
            metadata = station_metadata(quote)
            fetched = datetime.fromisoformat(quote["fetched_at"].replace("Z", "+00:00"))
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=UTC)
            stations.append((source, station_id, quote.get("canonical_id"), json.dumps(metadata), fetched))
            expires = quote_expiry(quote)
            if expires is None or expires <= now:
                continue
            reported = datetime.fromisoformat(quote["price_updated_at"].replace("Z", "+00:00")) if quote.get("price_updated_at") else None
            condition = purchase_condition_key(
                quote.get("membership_required"), quote.get("octane"),
                quote.get("currency"), quote.get("unit"),
            )
            # Exclude retrieval time from identity: duplicate searches must not
            # look like new price reports. Unknown-time observations get daily buckets.
            identity = (source, station_id, quote["fuel_type"], quote["payment_type"],
                        condition, str(quote["price_per_gallon"]),
                        reported.isoformat() if reported else fetched.date().isoformat())
            observation = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
            attributes = station_attributes(quote)
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
                SET canonical_id=CASE
                        WHEN (
                            COALESCE(stations.metadata->>'location_source', stations.source) IN ('google_maps_web','google_places')
                            OR (stations.metadata->>'location_source' IS NULL AND stations.canonical_id LIKE 'google_places:%')
                        )
                             AND COALESCE(EXCLUDED.metadata->>'location_source', '') NOT IN ('google_maps_web','google_places')
                        THEN stations.canonical_id
                        ELSE COALESCE(EXCLUDED.canonical_id, stations.canonical_id)
                    END,
                    metadata=CASE
                        WHEN (
                            COALESCE(stations.metadata->>'location_source', stations.source) IN ('google_maps_web','google_places')
                            OR (stations.metadata->>'location_source' IS NULL AND stations.canonical_id LIKE 'google_places:%')
                        )
                             AND COALESCE(EXCLUDED.metadata->>'location_source', '') NOT IN ('google_maps_web','google_places')
                        THEN EXCLUDED.metadata || stations.metadata
                        ELSE stations.metadata || EXCLUDED.metadata
                    END,
                    seen_at=GREATEST(stations.seen_at, EXCLUDED.seen_at)
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
        await self.pool.execute("""DELETE FROM gaswise.warm_queries WHERE expires_at<=now()
            AND (lease_until IS NULL OR lease_until<=now())""")
        await self.pool.execute("DELETE FROM gaswise.alert_installations WHERE confirmed_at < now() - interval '180 days'")
        await self.pool.execute("DELETE FROM gaswise.alert_need_state WHERE expires_at < now() - interval '30 days'")
        await self.pool.execute("DELETE FROM gaswise.alert_outbox WHERE expires_at < now() - interval '7 days'")
        await self.pool.execute("DELETE FROM gaswise.alert_inbox WHERE expires_at < now()")
        await self.pool.execute("DELETE FROM gaswise.collection_notifications WHERE created_at < now() - interval '90 days'")
        await self.pool.execute("DELETE FROM gaswise.collection_runs WHERE finished_at < now() - interval '90 days'")
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
