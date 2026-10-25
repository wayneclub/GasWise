"""Daily coverage of known public stations in operator-selected popular areas."""

import json

from gaswise.contracts.common import Point
from gaswise.contracts.sources import GasBuddySearch
from gaswise.domain.pricing.comparison import distance_meters

# Fixed public area, not visitor-derived locations. Extend with reviewed areas as needed.
HOTSPOTS = {"dtla": (Point(lat=34.0407, lng=-118.266), 3000)}


class HotspotCoverage:
    async def hotspot_targets(self):
        rows = await self.pool.fetch("""
            SELECT s.station_id,s.metadata,
                COALESCE(master.metadata->'location',s.metadata->'location') AS location
            FROM gaswise.stations s
            LEFT JOIN gaswise.stations master ON master.canonical_id=s.canonical_id
                AND master.source='google_maps_web'
            WHERE s.source='gasbuddy_web' AND s.seen_at>now()-interval '90 days'
              AND COALESCE(master.metadata->>'business_status',s.metadata->>'business_status','')
                  <> 'permanently_closed'
        """)
        targets = []
        for row in rows:
            location = row['location']
            if isinstance(location, str):
                location = json.loads(location)
            try:
                point = Point.model_validate(location)
            except ValueError:
                continue
            for area, (centre, radius) in HOTSPOTS.items():
                if distance_meters(centre, point) <= radius:
                    for fuel in ('regular', 'premium'):
                        targets.append((area, row['station_id'], fuel, point))
        return targets

    async def sync_hotspot_jobs(self, request_budget=90):
        targets = await self.hotspot_targets()
        async with self.pool.acquire() as connection, connection.transaction():
            await connection.execute('SELECT pg_advisory_xact_lock(743103135)')
            # A covered station can be skipped even if another neighbourhood query found it.
            await connection.execute("""UPDATE gaswise.base_collection_jobs SET enabled=false
                WHERE coverage_station_id IS NOT NULL AND (lease_until IS NULL OR lease_until<=now())""")
            for area, station_id, fuel, point in targets:
                query = GasBuddySearch(origin=point, radius_meters=1500, max_pages=1,
                    max_results=200, fuel_type=fuel, payment_type='cash_or_credit', include_payment_variants=True)
                job_id = f'hotspot:{area}:{fuel}:{station_id}'
                if await self._hotspot_covered(connection, station_id, fuel):
                    continue
                if await connection.fetchval("SELECT enabled FROM gaswise.base_collection_jobs WHERE id=$1", job_id):
                    continue
                reserved = await connection.fetchval("""SELECT COALESCE(sum(request_reserve),0)
                    FROM gaswise.base_collection_jobs WHERE enabled AND coverage_station_id IS NOT NULL""")
                if reserved + 2 > request_budget:
                    break  # Remaining targets stay visible and rotate in as earlier work completes.
                await connection.execute("""
                    INSERT INTO gaswise.base_collection_jobs
                        (id,base,source,fuel,descriptor,mandatory,request_reserve,coverage_station_id)
                    SELECT $1,'la','gasbuddy',$2,$3::jsonb,true,2,$4
                    WHERE (SELECT count(*) FROM gaswise.collection_runs WHERE job_id=$1
                        AND finished_at>=date_trunc('day',now() AT TIME ZONE 'America/Los_Angeles')
                            AT TIME ZONE 'America/Los_Angeles'
                        AND (outcome IN ('success','failure') OR reason='coverage_missing')) < 3
                    ON CONFLICT(id) DO UPDATE SET enabled=true,descriptor=EXCLUDED.descriptor
                """, job_id, fuel, query.model_dump_json(), station_id)

    async def hotspot_job(self, job_id):
        row = await self.pool.fetchrow("""SELECT id,base,source,fuel,descriptor,coverage_station_id
            FROM gaswise.base_collection_jobs WHERE id=$1 AND coverage_station_id IS NOT NULL""", job_id)
        return dict(row) if row else None

    async def hotspot_covered(self, station_id, fuel):
        return await self._hotspot_covered(self.pool, station_id, fuel)

    @staticmethod
    async def _hotspot_covered(connection, station_id, fuel):
        return await connection.fetchval("""SELECT EXISTS(SELECT 1 FROM gaswise.quote_daily
            WHERE source='gasbuddy_web' AND station_id=$1 AND fuel_type=$2
              AND observed_day=(now() AT TIME ZONE 'America/Los_Angeles')::date)
            AND NOT EXISTS(SELECT 1 FROM gaswise.quote_history h
                WHERE h.source='gasbuddy_web' AND h.station_id=$1 AND h.fuel_type=$2
                  AND h.last_seen_at>now()-interval '30 days'
                  AND NOT EXISTS(SELECT 1 FROM gaswise.quote_daily d
                    WHERE d.source=h.source AND d.station_id=h.station_id AND d.fuel_type=h.fuel_type
                      AND d.payment_type=h.payment_type AND d.purchase_condition=h.purchase_condition
                      AND d.observed_day=(now() AT TIME ZONE 'America/Los_Angeles')::date))""", station_id, fuel)

    async def hotspot_status(self):
        targets = await self.hotspot_targets()
        missing = []
        for area, station_id, fuel, _ in targets:
            if not await self.hotspot_covered(station_id, fuel):
                missing.append({'area': area, 'station_id': station_id, 'fuel_type': fuel})
        return {'timezone': 'America/Los_Angeles', 'areas': list(HOTSPOTS),
                'target_station_fuels': len(targets), 'checked_today': len(targets)-len(missing),
                'missing': missing, 'max_attempts_per_station_fuel_day': 3,
                'coverage': 'complete' if targets and not missing else 'partial',
                'semantics': 'actual_fetch_today; source_report_time_unchanged; known_inventory_and_recent_payment_conditions_only'}
