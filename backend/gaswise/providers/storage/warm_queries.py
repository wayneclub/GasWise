"""Durable demand for public provider viewports, never visitor identity or routes."""


class WarmQueries:
    async def observe_warm_query(self, key, source, raw_key, interval, request_cost=1):
        await self.pool.execute("""
            INSERT INTO gaswise.warm_queries(key,source,raw_key,next_due,request_cost)
            VALUES($1,$2,$3,now()+$4*interval '1 second',$5)
            ON CONFLICT(key) DO UPDATE SET last_requested_at=now(),request_cost=EXCLUDED.request_cost,
                expires_at=now()+interval '14 days',
                next_due=CASE WHEN warm_queries.expires_at<=now()
                    THEN now()+$4*interval '1 second' ELSE warm_queries.next_due END
        """, key, source, raw_key, interval, request_cost)

    async def warming_plan(self, source):
        return dict(await self.pool.fetchrow("""
            SELECT count(*) AS active, COALESCE(sum(request_cost),0)::int AS request_cost
            FROM gaswise.warm_queries WHERE source=$1 AND expires_at>now()
                AND last_requested_at>=now()-interval '24 hours'
        """, source))

    async def claim_warm_query(self, owner, sources):
        row = await self.pool.fetchrow("""
            UPDATE gaswise.warm_queries SET lease_owner=$1,lease_until=now()+interval '5 minutes',
                last_attempt_at=now()
            WHERE key=(SELECT key FROM gaswise.warm_queries
                WHERE source=ANY($2::text[]) AND expires_at>now() AND next_due<=now()
                  AND last_requested_at>=now()-interval '24 hours'
                  AND (lease_until IS NULL OR lease_until<=now())
                ORDER BY next_due,created_at,key FOR UPDATE SKIP LOCKED LIMIT 1)
            RETURNING key,source,raw_key,request_cost
        """, owner, list(sources))
        return dict(row) if row else None

    async def finish_warm_query(self, key, owner, delay, error=None):
        await self.pool.execute("""
            UPDATE gaswise.warm_queries SET lease_owner=NULL,lease_until=NULL,
                next_due=now()+$3*interval '1 second',last_error=$4,
                last_success_at=CASE WHEN $4::text IS NULL THEN now() ELSE last_success_at END
            WHERE key=$1 AND lease_owner=$2
        """, key, owner, delay, error)

    async def warm_query_status(self):
        row = await self.pool.fetchrow("""
            SELECT count(*) FILTER(WHERE expires_at>now()) AS active,
                count(*) FILTER(WHERE expires_at>now() AND last_requested_at>=now()-interval '24 hours') AS hot,
                count(*) FILTER(WHERE expires_at>now() AND next_due<=now()) AS due,
                count(*) FILTER(WHERE expires_at<=now()) AS expired,
                count(*) FILTER(WHERE expires_at>now() AND last_success_at IS NOT NULL) AS warmed
            FROM gaswise.warm_queries
        """)
        return dict(row)
