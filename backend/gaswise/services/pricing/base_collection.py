"""Persistent fixed public city-base sampling, independent of visitor searches."""

import asyncio
import logging
import uuid
from dataclasses import dataclass

from gaswise.contracts.common import Point
from gaswise.contracts.sources import GasBuddySearch, GooglePriceSearch, MapsWebSearch
from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.collection_bases import BASE_CATALOG, BASES
from gaswise.domain.pricing.shared_cache import background_acquisition, mandatory_acquisition
from gaswise.services.pricing.discovery import shared_viewport

logger = logging.getLogger(__name__)



@dataclass
class CollectionJob:
    id: str
    base: str
    source: str
    fuel: str
    query: object
    provider: object

    @property
    def raw_key(self):
        namespace = "waze:all-fuels-v1:" if self.source == "waze" else self.source + ":"
        return namespace + self.query.model_dump_json()


def collection_jobs(service, bases):
    jobs = {}
    for base in bases:
        centre, radius = shared_viewport(Point(lat=BASES[base][0], lng=BASES[base][1]), 10000)
        for fuel in ("regular", "premium"):
            for source, provider, query in (
                ("gasbuddy", service.gasbuddy, GasBuddySearch(
                    origin=centre, radius_meters=radius, fuel_type=fuel, max_pages=3,
                    max_results=100, payment_type="cash_or_credit", include_payment_variants=True)),
                ("maps", service.maps_web, MapsWebSearch(
                    origin=centre, radius_meters=radius, fuel_type=fuel, detail_limit=3 if fuel == "premium" else 0)),
                ("waze", service.waze, GooglePriceSearch(
                    origin=centre, radius_meters=radius, fuel_type=fuel)),
            ):
                if provider is not None and not (source == "waze" and fuel == "premium"):
                    job_fuel = "all" if source == "waze" else fuel
                    job_id = f"{base}:{job_fuel}:{source}"
                    jobs[job_id] = CollectionJob(job_id, base, source, job_fuel, query, provider)
    return jobs


class BaseCollection:
    def __init__(self, service, bases, *, interval=86400, limits=None, daily_limit=40):
        self.service = service
        self.cache = service.shared_cache
        self.jobs = collection_jobs(service, bases)
        self.interval = interval
        self.limits = limits or {"gasbuddy": 12, "maps": 60, "waze": 20}
        self.daily_limit = daily_limit

    async def initialize(self):
        populations = {base["id"]: base["population_2026"] or 0 for base in BASE_CATALOG["bases"]}
        descriptors = [{"id": job.id, "population_priority": populations[job.base], "base": job.base, "source": job.source,
                        "fuel": job.fuel, "mandatory": job.base == "la",
                        "request_reserve": 4 if job.source == "gasbuddy" else (3 if job.source == "waze" else 1 + job.query.detail_limit), "descriptor": job.query.model_dump(mode="json")}
                       for job in self.jobs.values()]
        await self.cache._db("configure_base_jobs", descriptors)

    async def pending(self, source):
        return await self.cache._db("base_jobs_pending", source)

    async def step(self):
        # Skip exhausted sources without moving their due dates behind newer jobs.
        # Thus older, unvisited bases keep priority across days and restarts.
        available = []
        for source in {job.source for job in self.jobs.values()}:
            state = await self.cache.budget_state(source)
            if (not state.get("blocked_seconds", 0) and state["background_day_used"] < (state.get("daily_limit") or self.daily_limit)
                    and (state.get("mandatory_due", False) or state["background_day_used"] <
                         (state.get("daily_limit") or self.daily_limit) - state.get("mandatory_reserved_requests", 0))
                    and (state.get("mandatory_due", False) or not state.get("background_pacing_seconds", 0))
                    and state["used"] < max(1, self.limits[source] // 2)
                    and state.get("background_used", 0) < max(1, self.limits[source] // 5)):
                available.append(source)
        if not available:
            return False
        owner = uuid.uuid4().hex
        job_id = await self.cache._db("claim_base_job", owner, available)
        if job_id is None:
            return False
        job = self.jobs.get(job_id)
        if job is None:
            await self.cache._db("finish_base_job", job_id, owner, 3600, "configuration_changed", 0, 0)
            return False
        completed = False
        token = background_acquisition.set(True)
        mandatory_token = mandatory_acquisition.set(job.base == "la")
        try:
            state = await self.cache.budget_state(job.source)
            if (state.get("blocked_seconds", 0) or state["background_day_used"] >= (state.get("daily_limit") or self.daily_limit)
                    or state["used"] >= max(1, self.limits[job.source] // 2)
                    or state.get("background_used", 0) >= max(1, self.limits[job.source] // 5)):
                await self.cache._db("finish_base_job", job.id, owner, 900, "source_budget_deferred", 0, 0)
                completed = True
                return False

            async def load():
                slot = self.service.background_gasbuddy_slot if job.source == "gasbuddy" else self.service.source_slots[job.source]
                async with slot:
                    if job.source == "waze":
                        return await job.provider.stations(job.query, all_fuels=True)
                    return await job.provider.prices(job.query)

            result, _ = await self.cache.get(job.source, job.raw_key, load, wait_refresh=True)
            quotes = result if job.source == "waze" else result.prices if job.source == "gasbuddy" else result.all_prices or result.stations
            await self.cache._db("finish_base_job", job.id, owner, self.interval, None,
                                 len(quotes), len({quote.id for quote in quotes}))
            completed = True
            return True
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # Deliberately exclude transport messages, query data and secrets.
            reason = str(error)
            local_reasons = {f"{job.source}_{suffix}" for suffix in (
                "mandatory_budget_reserved", "background_daily_budget_exhausted", "background_budget_exhausted",
                "request_budget_exhausted", "background_wait_exhausted")}
            deferred = isinstance(error, ProviderError) and reason in local_reasons
            await self.cache._db("finish_base_job", job.id, owner, 60 if deferred else 3600,
                                 reason if deferred else "collection_failed", 0, 0)
            completed = True
            logger.warning("Fixed base collection deferred for %s", job.id)
            return False
        finally:
            background_acquisition.reset(token)
            mandatory_acquisition.reset(mandatory_token)
            if not completed:
                try:
                    await self.cache._db("finish_base_job", job.id, owner, 60, "interrupted", 0, 0)
                except Exception:
                    logger.warning("Fixed base lease release deferred to expiry")

    async def status(self):
        return {"enabled": True, "interval_seconds": self.interval,
                "radius_meters": 10000, "coverage": "partial",
                "base_count": len({job.base for job in self.jobs.values()}),
                "total_jobs": len(self.jobs), "schedule": "weighted_rotation",
                "mandatory_bases": ["la"] if any(job.base == "la" for job in self.jobs.values()) else [],
                "score_policy": {"population_log_weight": 10, "overdue_hour_weight": 2, "never_sampled_bonus": 30},
                "mandatory_target_seconds": self.interval,
                "jobs": await self.cache._db("base_job_status")}

    async def run(self):
        while True:
            try:
                progressed = await self.step()
            except Exception:
                logger.warning("Fixed base collection database unavailable")
                progressed = False
            await asyncio.sleep(10 if progressed else 60)
