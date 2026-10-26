"""Restart-safe warming for public queries requested in the last fourteen days."""

import asyncio
import hashlib
import logging
import uuid
from time import monotonic

from gaswise.contracts.sources import GasBuddySearch, GooglePriceSearch, MapsWebSearch
from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.background_policy import optional_allowance, warming_interval
from gaswise.domain.pricing.collection_errors import safe_failure_code
from gaswise.domain.pricing.shared_cache import acquisition_purpose, background_acquisition
from gaswise.services.pricing.hot_refresh import SourcePace

logger = logging.getLogger(__name__)
QUERY_MODELS = {"gasbuddy": GasBuddySearch, "maps": MapsWebSearch, "waze": GooglePriceSearch}


def query_payload(source, raw_key):
    prefix = "waze:all-fuels-v1:" if source == "waze" and raw_key.startswith("waze:all-fuels-v1:") else source + ":"
    return raw_key.removeprefix(prefix)


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
        query = QUERY_MODELS[source].model_validate_json(query_payload(source, raw_key))
        cost = (1 + query.max_pages) if source == "gasbuddy" else 1 + query.detail_limit if source == "maps" else 3
        key = hashlib.sha256(("pricing-v1:" + raw_key).encode()).hexdigest()
        try:
            await self.cache._db("observe_warm_query", key, source, raw_key, self.interval, cost)
        except Exception:
            logger.warning("Public pricing demand registration unavailable for %s", source)

    def provider(self, source):
        return {"gasbuddy": self.service.gasbuddy, "maps": self.service.maps_web,
                "waze": self.service.waze}.get(source)

    async def step(self, only_source=None):
        available = []
        now = self.clock()
        for source, pace in self.paces.items():
            if (only_source is not None and source != only_source) or self.provider(source) is None or pace.not_before > now:
                continue
            state = await self.cache.budget_state(source)
            allowance = optional_allowance(state.get("daily_limit") or self.daily_limit)
            usage = state.get("background_usage", {})
            if (sum(usage.get(name, 0) for name in ("demand", "revalidation")) >= allowance
                    or state.get("blocked_seconds", 0)
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
        daily, cost, delay = self.daily_limit, job.get("request_cost", 1), self.interval
        token = background_acquisition.set(True)
        purpose_token = acquisition_purpose.set("demand")
        try:
            plan = await self.cache._db("warming_plan", source)
            daily = (await self.cache.budget_state(source)).get("daily_limit") or self.daily_limit
            delay = warming_interval(self.interval, cost, plan["request_cost"], daily)
            query = QUERY_MODELS[source].model_validate_json(query_payload(source, job["raw_key"]))

            async def load():
                slot = self.service.background_gasbuddy_slot if source == "gasbuddy" else self.service.source_slots[source]
                async with slot:
                    provider = self.provider(source)
                    if source == "waze" and job["raw_key"].startswith("waze:all-fuels-v1:"):
                        value = await provider.stations(query, all_fuels=True)
                    else:
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
            if isinstance(caught, ProviderError) and any(str(caught).endswith(suffix) for suffix in (
                    "budget_exhausted", "budget_reserved", "refresh_pending")):
                error, delay = "source_budget_deferred", 60
                return False
            error = safe_failure_code(caught)
            pace.failures = min(5, pace.failures + 1)
            pace.errors += 1
            delay = min(21600, self.interval * 2 ** pace.failures)
            pace.not_before = self.clock() + delay
            logger.warning("Demand pricing refresh deferred for %s", source)
        finally:
            acquisition_purpose.reset(purpose_token)
            background_acquisition.reset(token)
            # Finishing a background job deliberately does not touch request time
            # or retention. Only a new foreground observation renews those.
            await self.cache._db("finish_warm_query", job["key"], owner, delay, error)
            if error is None:
                pace.not_before = self.clock() + max(60, 86400 * cost / max(1, optional_allowance(daily)))
        return True

    async def status(self):
        counts = await self.cache._db("warm_query_status")
        sources = {}
        for source, pace in self.paces.items():
            state = await self.cache.budget_state(source)
            plan = await self.cache._db("warming_plan", source)
            daily = state.get("daily_limit") or self.daily_limit
            sources[source] = {
                **state,
                "optional_http_ceiling": optional_allowance(daily),
                "planned_interval_seconds": warming_interval(self.interval, 1, plan["request_cost"], daily),
                "minute_limit": self.limits[source],
                "warming_plan": plan,
                "backoff_seconds": max(0, round(pace.not_before - self.clock())),
                "completed_loads": pace.loads, "errors": pace.errors, "deferred": pace.deferred,
            }
        return {"enabled": True, "mode": "persistent_demand", "retention_days": 14,
                "minimum_observations": 1, "warming_demand_window_hours": 24, "registered_queries": counts["active"],
                "hot_queries": counts["hot"], "due_queries": counts["due"],
                "expired_queries": counts["expired"], "warmed_queries": counts["warmed"],
                "minimum_interval_seconds": self.interval, "sources": sources}

    async def run(self):
        async with asyncio.TaskGroup() as group:
            for source in self.paces:
                if self.provider(source) is not None:
                    group.create_task(self._run_source(source))

    async def _run_source(self, source):
        while True:
            await asyncio.sleep(60)
            try:
                await self.step(source)
            except Exception:
                logger.warning("Demand pricing scheduler unavailable; retrying next minute")
