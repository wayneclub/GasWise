"""Restart-safe warming for public queries requested in the last fourteen days."""

import asyncio
import hashlib
import logging
import uuid
from time import monotonic

from gaswise.contracts.sources import GasBuddySearch, GooglePriceSearch, MapsWebSearch
from gaswise.domain.pricing.collection_errors import safe_failure_code
from gaswise.domain.pricing.shared_cache import background_acquisition
from gaswise.services.pricing.hot_refresh import SourcePace

logger = logging.getLogger(__name__)
QUERY_MODELS = {"gasbuddy": GasBuddySearch, "maps": MapsWebSearch, "waze": GooglePriceSearch}


class DemandQueryRefresh:
    def __init__(self, service, *, interval=900, limits=None, daily_limit=100, clock=monotonic):
        self.service = service
        self.cache = service.shared_cache
        self.interval = interval
        self.limits = limits or {"gasbuddy": 12, "maps": 60, "waze": 20}
        self.daily_limit = daily_limit
        self.clock = clock
        self.paces = {source: SourcePace() for source in self.limits}

    async def observe(self, source, raw_key, operation=None):
        if background_acquisition.get() or source not in QUERY_MODELS:
            return
        if len(raw_key) > 16384 or not raw_key.startswith(source + ":"):
            return
        # Persist only the provider's bounded public query, never the user's Search,
        # route, vehicle, credentials or identity. Refuse unexpected fields.
        QUERY_MODELS[source].model_validate_json(raw_key.split(":", 1)[1])
        key = hashlib.sha256(("pricing-v1:" + raw_key).encode()).hexdigest()
        try:
            await self.cache._db("observe_warm_query", key, source, raw_key, self.interval)
        except Exception:
            logger.warning("Public pricing demand registration unavailable for %s", source)

    def provider(self, source):
        return {"gasbuddy": self.service.gasbuddy, "maps": self.service.maps_web,
                "waze": self.service.waze}.get(source)

    async def step(self):
        available = []
        now = self.clock()
        for source, pace in self.paces.items():
            if self.provider(source) is None or pace.not_before > now:
                continue
            state = await self.cache.budget_state(source)
            if (state.get("blocked_seconds", 0)
                    or state["used"] >= max(1, self.limits[source] // 2)
                    or state.get("background_used", 0) >= max(1, self.limits[source] // 5)
                    or state.get("background_day_used", 0) >= max(0,
                        (state.get("daily_limit") or self.daily_limit) - state.get("mandatory_reserved_requests", 0))):
                pace.deferred += 1
                continue
            available.append(source)
        if not available:
            return False
        owner = uuid.uuid4().hex
        job = await self.cache._db("claim_warm_query", owner, available)
        if job is None:
            return False
        source = job["source"]
        pace = self.paces[source]
        error = None
        delay = self.interval
        token = background_acquisition.set(True)
        try:
            query = QUERY_MODELS[source].model_validate_json(job["raw_key"].split(":", 1)[1])

            async def load():
                slot = self.service.background_gasbuddy_slot if source == "gasbuddy" else self.service.source_slots[source]
                async with slot:
                    provider = self.provider(source)
                    value = await (provider.stations(query) if source == "waze" else provider.prices(query))
                pace.loads += 1
                return value

            # Bounded below the five-minute job lease. The shared cache also owns
            # its cross-process source lease and renews it during upstream I/O.
            async with asyncio.timeout(180):
                await self.cache.get(source, job["raw_key"], load, wait_refresh=True)
            pace.failures = max(0, pace.failures - 1)
        except asyncio.CancelledError:
            error, delay = "service_shutdown", 60
            raise
        except Exception as caught:
            error = safe_failure_code(caught)
            pace.failures = min(5, pace.failures + 1)
            pace.errors += 1
            delay = min(21600, self.interval * 2 ** pace.failures)
            pace.not_before = self.clock() + delay
            logger.warning("Demand pricing refresh deferred for %s", source)
        finally:
            background_acquisition.reset(token)
            # Finishing a background job deliberately does not touch request time
            # or retention. Only a new foreground observation renews those.
            await self.cache._db("finish_warm_query", job["key"], owner, delay, error)
        return True

    async def status(self):
        counts = await self.cache._db("warm_query_status")
        sources = {}
        for source, pace in self.paces.items():
            sources[source] = {
                **await self.cache.budget_state(source),
                "minute_limit": self.limits[source],
                "backoff_seconds": max(0, round(pace.not_before - self.clock())),
                "completed_loads": pace.loads, "errors": pace.errors, "deferred": pace.deferred,
            }
        return {"enabled": True, "mode": "persistent_demand", "retention_days": 14,
                "minimum_observations": 1, "registered_queries": counts["active"],
                "hot_queries": counts["active"], "due_queries": counts["due"],
                "expired_queries": counts["expired"], "warmed_queries": counts["warmed"],
                "minimum_interval_seconds": self.interval, "sources": sources}

    async def run(self):
        while True:
            await asyncio.sleep(60)
            try:
                await self.step()
            except Exception:
                logger.warning("Demand pricing scheduler unavailable; retrying next minute")
