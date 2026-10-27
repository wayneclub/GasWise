"""Durable public station identities and coarse survey cells; no visitor identity."""
import json
import math
from datetime import datetime

import h3

from gaswise.contracts.common import Point
from gaswise.domain.pricing.cache_policy import public_quotes
from gaswise.domain.pricing.cells import grid_points
from gaswise.domain.pricing.comparison import distance_meters


class StationInventory:
    async def _remember_inventory(self, connection, source, payload, checked_at):
        rows = {}
        for quote in public_quotes(payload):
            if not quote.get('location'):
                continue
            stamp = datetime.fromisoformat(quote['fetched_at'].replace('Z', '+00:00'))
            metadata = {k: quote[k] for k in ('name', 'address', 'location', 'open_now', 'business_status') if quote.get(k) is not None}
            metadata['location_source'] = quote.get('details', {}).get('location_source', quote['source'])
            rows[(quote['source'], str(quote['id']))] = (quote['source'], str(quote['id']), quote.get('canonical_id'), json.dumps(metadata), stamp)
        inventory = payload.get('inventory', []) if isinstance(payload, dict) else []
        for item in inventory:
            if item.get('discovery_state', 'observed') != 'observed':
                continue
            metadata = {k: item[k] for k in ('name', 'address', 'location', 'open_now', 'business_status', 'rating', 'review_count', 'rating_source') if item.get(k) is not None}
            metadata['location_source'] = 'google_maps_web'
            identifier = 'google_maps_web:' + item['place_id']
            rows[('google_maps_web', identifier)] = ('google_maps_web', identifier, 'google_places:' + item['place_id'], json.dumps(metadata),
                datetime.fromisoformat(item['last_seen_at'].replace('Z', '+00:00')) if item.get('last_seen_at') else checked_at)
        await self._upsert_stations(connection, list(rows.values()))
        if isinstance(payload, dict) and payload.get('survey_cell'):
            ids = sorted({item['place_id'] for item in inventory})
            await connection.execute("""
                INSERT INTO gaswise.discovery_cells(source,cell_id,radius_meters,checked_at,station_ids,capped)
                VALUES($1,$2,$3,$4,$5::jsonb,$6)
                ON CONFLICT(source,cell_id,radius_meters) DO UPDATE SET
                    checked_at=GREATEST(discovery_cells.checked_at,EXCLUDED.checked_at),
                    station_ids=EXCLUDED.station_ids,capped=EXCLUDED.capped,
                    observations=discovery_cells.observations+1
                WHERE EXCLUDED.checked_at>discovery_cells.checked_at
            """, source, payload['survey_cell'], payload['survey_radius_meters'], checked_at,
                json.dumps(ids), payload.get('candidate_count', 0) >= 15)
            if payload.get('candidate_count', 0) >= 15:
                await self._seed_patrol(connection, payload['survey_cell'], payload['survey_radius_meters'], checked_at)

    async def _seed_patrol(self, connection, cell, radius, checked_at):
        if radius <= 800:
            return
        size = 3200 if radius > 3200 else 1600 if radius > 1600 else 800
        latitude, longitude = h3.cell_to_latlng(cell)
        centre = Point(lat=latitude, lng=longitude)
        selected = []
        for point in grid_points(centre, radius):
            if all(distance_meters(point, old) > size * 1.5 for old in selected):
                selected.append(point)
            if len(selected) >= 64:
                break
        await connection.executemany("""
            INSERT INTO gaswise.discovery_patrol(source,cell_id,radius_meters,descriptor,last_relevant_at)
            VALUES('maps',$1,$2,$3::jsonb,$4) ON CONFLICT(source,cell_id,radius_meters) DO UPDATE SET
                last_relevant_at=GREATEST(discovery_patrol.last_relevant_at,EXCLUDED.last_relevant_at)
        """, [(h3.latlng_to_cell(point.lat,point.lng,8), size,
               json.dumps(dict(origin=point.model_dump(),radius_meters=size,fuel_type='regular',max_results=20,detail_limit=0)), checked_at)
              for point in selected])

    async def claim_inventory_patrol(self, owner):
        row = await self.pool.fetchrow("""
            UPDATE gaswise.discovery_patrol SET lease_owner=$1,lease_until=now()+interval '2 minutes'
            WHERE (source,cell_id,radius_meters)=(
                SELECT source,cell_id,radius_meters FROM gaswise.discovery_patrol
                WHERE next_due<=now() AND last_relevant_at>now()-interval '90 days' AND (lease_until IS NULL OR lease_until<=now())
                ORDER BY next_due,cell_id LIMIT 1 FOR UPDATE SKIP LOCKED)
            RETURNING source,cell_id,radius_meters,descriptor
        """, owner)
        return dict(row) if row else None

    async def finish_inventory_patrol(self, job, owner, success):
        await self.pool.execute("""
            UPDATE gaswise.discovery_patrol SET lease_owner=NULL,lease_until=NULL,
                next_due=now()+CASE WHEN $5 THEN interval '24 hours' ELSE interval '15 minutes' END,
                last_success=CASE WHEN $5 THEN now() ELSE last_success END
            WHERE source=$1 AND cell_id=$2 AND radius_meters=$3 AND lease_owner=$4
        """, job['source'],job['cell_id'],job['radius_meters'],owner,success)

    async def inventory_patrol_status(self):
        return dict(await self.pool.fetchrow("""
            SELECT count(*) AS cells,count(*) FILTER(WHERE next_due<=now()) AS due,
                max(last_success) AS last_success FROM gaswise.discovery_patrol WHERE last_relevant_at>now()-interval '90 days'
        """))

    async def nearby_inventory(self, origin, radius):
        latitude = radius / 110000
        longitude = latitude / max(.1, math.cos(math.radians(origin.lat)))
        rows = await self.pool.fetch("""
            SELECT source,station_id,canonical_id,metadata,seen_at FROM gaswise.stations
            WHERE seen_at>now()-interval '90 days' AND metadata?'location'
                AND COALESCE(metadata->>'business_status','')<>'permanently_closed'
                AND (metadata->'location'->>'lat')::float BETWEEN $1 AND $2
                AND (metadata->'location'->>'lng')::float BETWEEN $3 AND $4
            ORDER BY seen_at DESC LIMIT 2500
        """, origin.lat-latitude, origin.lat+latitude, origin.lng-longitude, origin.lng+longitude)
        result = []
        for row in rows:
            metadata = json.loads(row['metadata'])
            point = Point.model_validate(metadata['location'])
            if distance_meters(origin, point) <= radius:
                result.append(dict(source=row['source'], station_id=row['station_id'], canonical_id=row['canonical_id'],
                                   name=metadata.get('name', ''), address=metadata.get('address'),
                                   location=point.model_dump(), last_seen_at=row['seen_at'].isoformat()))
        return result

    async def seed_station_inventory(self):
        # Old response blobs have a real fetch timestamp; never mark seeding as a new fetch.
        async with self.pool.acquire() as connection, connection.transaction():
            for row in await connection.fetch('SELECT source,payload,fetched_at FROM gaswise.query_cache WHERE payload IS NOT NULL AND fetched_at IS NOT NULL'):
                await self._remember_inventory(connection, row['source'], json.loads(row['payload']), row['fetched_at'])
