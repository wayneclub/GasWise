"""Transactional attempt journal and durable Telegram outbox, shared across workers."""
import json
from datetime import datetime, time, timedelta

from gaswise.domain.pricing.collection_reporting import LOCAL_ZONE, completion, safe_metrics


def next_local_midnight(clock):
    tomorrow = clock.astimezone(LOCAL_ZONE).date() + timedelta(days=1)
    return datetime.combine(tomorrow, time(), LOCAL_ZONE)


def time_aware_next_due(clock, delay):
    """Align successful base collection with diurnal price change patterns.

    Gas stations in the US rarely change prices overnight (23:00 - 05:00 PT).
    Most morning price adjustments happen between 05:30 and 09:30 PT.
    If next_due falls overnight, push it to 05:30 PT to preserve upstream quota.
    """
    target = clock + timedelta(seconds=delay)
    local = target.astimezone(LOCAL_ZONE)
    if local.hour >= 23 or local.hour < 5 or (local.hour == 5 and local.minute < 30):
        day = local.date() if local.hour < 5 else local.date() + timedelta(days=1)
        return datetime.combine(day, time(5, 30), LOCAL_ZONE)
    return target


class CollectionEvents:
    async def _append_collection_run(self, connection, job, owner, error, quotes=0, stations=0, info=None, retry_at=None):
        info = info or {}
        diagnostic = info.get('failure_code')
        if diagnostic is None and job.get('last_failure_at') and job.get('last_started_at') and job['last_failure_at'] >= job['last_started_at']:
            diagnostic = job.get('last_failure_code')
        outcome, reason = completion(error, diagnostic)
        metrics = safe_metrics(info)
        # A missing coverage target still fetched quotes; keep them visible in the journal.
        fetched = outcome == 'success' or reason == 'coverage_missing'
        run_id = await connection.fetchval("""
            INSERT INTO gaswise.collection_runs(job_id,owner,base,source,fuel,started_at,outcome,reason,
                http_status,phase,egress_lane,http_requests,quote_count,station_count,retry_at,
                canonical_count,new_canonical_count,located_count,priced_count,inventory_overlap_count)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
            ON CONFLICT(job_id,owner) DO NOTHING RETURNING id
        """, job['id'], owner, job['base'], job['source'], job['fuel'], job.get('last_started_at'), outcome, reason,
            metrics['http_status'] if outcome != 'deferred' else None, metrics['phase'], metrics['egress_lane'],
            metrics['http_requests'], quotes if fetched else 0,
            stations if fetched else 0, retry_at,
            metrics['canonical_count'] if outcome == 'success' else 0,
            metrics['new_canonical_count'] if outcome == 'success' else 0,
            metrics['located_count'] if outcome == 'success' else 0,
            metrics['priced_count'] if outcome == 'success' else 0,
            metrics['inventory_overlap_count'] if outcome == 'success' else 0)
        if run_id and outcome in ('failure', 'interrupted'):
            await connection.execute("""INSERT INTO gaswise.collection_notifications(dedupe_key,kind,payload)
                VALUES($1,'failure',$2::jsonb) ON CONFLICT(dedupe_key) DO NOTHING""",
                f'run:{run_id}', json.dumps({'run_id': run_id}))
        return outcome, reason

    async def finish_collection_attempt(self, job_id, owner, delay, error, quotes, stations, info=None):
        async with self.pool.acquire() as connection, connection.transaction():
            # Same lock order as claims: source first, then job. Never lock during HTTP.
            if completion(error)[0] == 'failure':
                source = await connection.fetchval('SELECT source FROM gaswise.base_collection_jobs WHERE id=$1', job_id)
                await connection.fetchrow('SELECT source FROM gaswise.source_limits WHERE source=$1 FOR UPDATE', source)
            row = await connection.fetchrow('SELECT *,now() AS clock FROM gaswise.base_collection_jobs WHERE id=$1 AND lease_owner=$2 FOR UPDATE', job_id, owner)
            if row is None:
                return False
            job = dict(row)
            # Short recovery only for transient Maps/Waze outages. Persisted
            # failure counts survive restarts; repeated outages return to hourly.
            transient = {"maps": "google_maps_web_unavailable", "waze": "waze_upstream_unavailable"}
            if (error == "collection_failed" and job["source"] in transient
                    and (info or {}).get("failure_code") == transient[job["source"]]):
                backoff = (60, 300, 900, 3600)
                delay = min(delay, backoff[min(max(0, job["failures"]), len(backoff) - 1)])
            retry_at = job['clock'] + timedelta(seconds=delay)
            if error is None and delay >= 3600 and not job.get('coverage_station_id'):
                retry_at = time_aware_next_due(job['clock'], delay)
            if error == 'coverage_missing':
                # The station-centred page already listed the target: only a new source
                # report can fill the gap, and later shared fetches will record it if it appears.
                retry_at = next_local_midnight(job['clock'])
            outcome, reason = await self._append_collection_run(connection, job, owner, error, quotes, stations, info, retry_at)
            if outcome == 'failure':
                await connection.execute("""UPDATE gaswise.source_limits SET last_collection_failure_at=now(),
                    daily_review_at=CASE WHEN adaptive_daily_limit IS NULL THEN daily_review_at ELSE now() END,
                    daily_review_requests=0 WHERE source=$1""", job['source'])
                # Cross-source cascade: when GasBuddy fails for a city, accelerate peer sources
                # (maps, waze) in the same area so fresh quotes fill the coverage gap promptly.
                if job.get('source') == 'gasbuddy' and job.get('base'):
                    await connection.execute("""
                        UPDATE gaswise.base_collection_jobs
                        SET next_due = LEAST(next_due, now() + interval '30 seconds')
                        WHERE base = $1 AND source IN ('maps', 'waze') AND enabled
                          AND (next_due > now() + interval '30 seconds')
                    """, job['base'])
            await connection.execute("""
                UPDATE gaswise.base_collection_jobs SET next_due=$3,lease_owner=NULL,lease_until=NULL,last_error=$4,
                    last_success=CASE WHEN $5='success' THEN now() ELSE last_success END,
                    failures=CASE WHEN $5='success' THEN 0 WHEN $5 IN ('failure','interrupted') THEN failures+1 ELSE failures END,
                    quote_count=CASE WHEN $5='success' THEN $6 ELSE quote_count END,
                    station_count=CASE WHEN $5='success' THEN $7 ELSE station_count END,
                    last_failure_code=CASE WHEN $5='failure' THEN $8 ELSE last_failure_code END,
                    last_failure_at=CASE WHEN $5='failure' THEN now() ELSE last_failure_at END
                WHERE id=$1 AND lease_owner=$2
            """, job_id, owner, retry_at, error, outcome, quotes, stations, reason)
            return True

    async def collection_report(self, start, end):
        async with self.pool.acquire() as connection, connection.transaction(isolation='repeatable_read', readonly=True):
            counts = await connection.fetch("""SELECT source,outcome,count(*) AS attempts,
                COALESCE(sum(quote_count),0)::bigint AS quotes,COALESCE(sum(station_count),0)::bigint AS station_returns,
                count(DISTINCT base) AS cities FROM gaswise.collection_runs WHERE finished_at >= $1 AND finished_at < $2
                GROUP BY source,outcome ORDER BY source,outcome""", start, end)
            reasons = await connection.fetch("""SELECT source,reason,http_status,count(*) AS attempts,
                min(finished_at) AS first_at,max(finished_at) AS last_at FROM gaswise.collection_runs
                WHERE finished_at >= $1 AND finished_at < $2 AND outcome IN ('failure','interrupted')
                GROUP BY source,reason,http_status ORDER BY attempts DESC,source,reason""", start, end)
            failures = await connection.fetch("""SELECT * FROM gaswise.collection_runs WHERE finished_at >= $1 AND finished_at < $2
                AND outcome IN ('failure','interrupted') ORDER BY finished_at DESC,id DESC LIMIT 50""", start, end)
            lanes = await connection.fetch("""SELECT source,egress_lane,outcome,count(*) AS attempts,
                COALESCE(sum(http_requests),0)::bigint AS http_requests,COALESCE(sum(quote_count),0)::bigint AS quotes
                FROM gaswise.collection_runs WHERE finished_at >= $1 AND finished_at < $2 AND egress_lane IS NOT NULL
                GROUP BY source,egress_lane,outcome ORDER BY source,egress_lane,outcome""", start, end)
            tracking_since = await connection.fetchval('SELECT min(finished_at) FROM gaswise.collection_runs')
            delivery = await connection.fetchrow("""SELECT count(*) FILTER(WHERE sent_at IS NULL AND expired_at IS NULL) AS pending,
                count(*) FILTER(WHERE sent_at IS NOT NULL) AS sent,
                count(*) FILTER(WHERE sent_at IS NULL AND expired_at IS NULL AND last_error IS NOT NULL) AS retrying,
                count(*) FILTER(WHERE expired_at IS NOT NULL) AS expired
                FROM gaswise.collection_notifications WHERE created_at >= $1 AND created_at < $2""", start, end)
        return {'start': start, 'end': end, 'timezone': 'America/Los_Angeles',
                'counts': [dict(row) for row in counts], 'reasons': [dict(row) for row in reasons],
                'failures': [dict(row) for row in failures], 'delivery': dict(delivery),
                'lanes': [dict(row) for row in lanes], 'tracking_since': tracking_since,
                'history_semantics': 'attempts_since_feature_enabled; quote/station returns are not globally deduplicated'}

    async def queue_collection_summaries(self):
        async with self.pool.acquire() as connection, connection.transaction():
            await connection.execute("""INSERT INTO gaswise.collection_notification_clock(name,next_at)
                VALUES('hourly',(date_trunc('hour',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC')+interval '1 hour') ON CONFLICT DO NOTHING""")
            row = await connection.fetchrow("SELECT next_at,now() AS clock FROM gaswise.collection_notification_clock WHERE name='hourly' FOR UPDATE SKIP LOCKED")
            if row is None:
                return
            end = max(row['next_at'], row['clock'].replace(minute=0, second=0, microsecond=0) - timedelta(hours=23))
            for _ in range(24):
                if end > row['clock']:
                    break
                start = end - timedelta(hours=1)
                exists = await connection.fetchval('SELECT EXISTS(SELECT 1 FROM gaswise.collection_runs WHERE finished_at >= $1 AND finished_at < $2)', start, end)
                if exists:
                    await connection.execute("""INSERT INTO gaswise.collection_notifications(dedupe_key,kind,payload)
                        VALUES($1,'summary',$2::jsonb) ON CONFLICT(dedupe_key) DO NOTHING""",
                        'hour:' + end.isoformat(), json.dumps({'start': start.isoformat(), 'end': end.isoformat()}))
                end += timedelta(hours=1)
            await connection.execute("UPDATE gaswise.collection_notification_clock SET next_at=$1 WHERE name='hourly'", end)

    async def claim_collection_notice(self, owner):
        async with self.pool.acquire() as connection, connection.transaction():
            await connection.execute('SELECT pg_advisory_xact_lock(743103134)')
            await connection.execute("""UPDATE gaswise.collection_notifications SET expired_at=now(),last_error='notification_expired'
                WHERE sent_at IS NULL AND expired_at IS NULL AND created_at<now()-interval '24 hours'""")
            await connection.execute("""INSERT INTO gaswise.collection_notification_clock(name,next_at)
                VALUES('dispatch',now()) ON CONFLICT DO NOTHING""")
            ready = await connection.fetchval("SELECT next_at<=now() FROM gaswise.collection_notification_clock WHERE name='dispatch' FOR UPDATE")
            if not ready:
                return None
            row = await connection.fetchrow("""UPDATE gaswise.collection_notifications SET lease_owner=$1,
                lease_until=now()+interval '2 minutes',attempts=attempts+1,last_attempt_at=now()
                WHERE id=(SELECT id FROM gaswise.collection_notifications WHERE sent_at IS NULL AND expired_at IS NULL AND next_try<=now()
                    AND created_at>=now()-interval '24 hours' AND (lease_until IS NULL OR lease_until<=now())
                    ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING *""", owner)
            if row:
                await connection.execute("UPDATE gaswise.collection_notification_clock SET next_at=now()+interval '3 seconds' WHERE name='dispatch'")
            return dict(row) if row else None

    async def finish_collection_notice(self, notice_id, owner, message_id=None, error=None, retry_seconds=30):
        await self.pool.execute("""UPDATE gaswise.collection_notifications SET lease_owner=NULL,lease_until=NULL,
            sent_at=CASE WHEN $3::bigint IS NOT NULL THEN now() ELSE sent_at END,telegram_message_id=$3,
            last_error=$4,last_error_at=CASE WHEN $4::text IS NOT NULL THEN now() ELSE last_error_at END,
            next_try=now()+$5::double precision*interval '1 second'
            WHERE id=$1 AND lease_owner=$2""", notice_id, owner, message_id, error, float(retry_seconds))

    async def collection_run(self, run_id):
        row = await self.pool.fetchrow('SELECT * FROM gaswise.collection_runs WHERE id=$1', run_id)
        return dict(row) if row else None
