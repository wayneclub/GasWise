"""Cross-process reuse and demand-driven refresh of public provider observations."""

import asyncio
import hashlib
import logging
import uuid
from contextvars import ContextVar
from time import monotonic

from pydantic import TypeAdapter

from gaswise.contracts.common import Station
from gaswise.contracts.sources import GasBuddyPrices, MapsWebPrices
from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.cache_policy import prune_quotes
from gaswise.domain.pricing.shared_cache import (
    PricingCacheStore,
    acquisition_purpose,
    background_acquisition,
    mandatory_acquisition,
)

CODECS = {"gasbuddy": GasBuddyPrices, "maps": MapsWebPrices, "waze": TypeAdapter(list[Station])}
logger = logging.getLogger(__name__)
cache_observations = ContextVar("pricing_cache_observations", default=None)


def record_check(source, fetched_at, state):
    observations = cache_observations.get()
    if observations is None or fetched_at is None:
        return
    previous = observations.get(source)
    observations[source] = {
        "checked_at": min(previous["checked_at"], fetched_at) if previous else fetched_at,
        "state": "stale" if state == "stale" or previous and previous["state"] == "stale" else "fresh",
    }


class SharedPricingCache:
    def __init__(self, store: PricingCacheStore, fresh_seconds=900):
        self.store, self.fresh_seconds = store, fresh_seconds
        self.tasks = set()
        self.closed = False

    async def price_history(self, canonical_id, source, station_id, fuel_type, days):
        if not hasattr(self.store, "price_history"):
            raise ProviderError("price_history_unavailable")
        return await self._db("price_history", canonical_id, source, station_id, fuel_type, days)

    async def payment_history(self, stations):
        if not hasattr(self.store, "payment_history"):
            return {}
        return await self._db("payment_history", list({s.canonical_id for s in stations if s.canonical_id}), list({s.fuel_type for s in stations}))

    async def _db(self, method, *args):
        try:
            return await getattr(self.store, method)(*args)
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("shared_pricing_cache_unavailable") from None

    def decode(self, source, payload, stale=False):
        codec = CODECS[source]
        if source == "waze":
            return codec.validate_python(prune_quotes(payload))
        result = codec.model_validate(prune_quotes(payload))
        if stale:
            result.warnings.append("Cached source data is older than the refresh window; background refresh is subject to source limits. Original report times are unchanged.")
        return result

    async def get(self, source, raw_key, operation, *, wait_refresh=False):
        # Versioned adapter/query keys exclude visitors, sessions, vehicle options and routes.
        key = hashlib.sha256(("pricing-v1:" + raw_key).encode()).hexdigest()
        record = await self._db("read", key)
        if record and record.fresh:
            record_check(source, record.fetched_at, "fresh")
            return self.decode(source, record.payload), True
        if record and record.usable and not wait_refresh:
            record_check(source, record.fetched_at, "stale")
            owner = uuid.uuid4().hex
            if not self.closed and await self._db("claim", key, source, owner):
                task = asyncio.create_task(self._background(source, key, owner, operation))
                self.tasks.add(task)
                task.add_done_callback(self.tasks.discard)
            return self.decode(source, record.payload, stale=True), True
        owner = uuid.uuid4().hex
        if await self._db("claim", key, source, owner):
            return await self._load(source, key, owner, operation)
        # Another process is loading a cold query. Wait for its DB result, never duplicate I/O.
        deadline = monotonic() + 20
        while monotonic() < deadline:
            await asyncio.sleep(.1)
            record = await self._db("read", key)
            if record and record.usable:
                record_check(source, record.fetched_at, "fresh" if record.fresh else "stale")
                return self.decode(source, record.payload), True
        raise ProviderError("shared_pricing_refresh_pending")

    async def _load(self, source, key, owner, operation):
        heartbeat = None
        try:
            # Recheck after claiming: another worker may have just completed a refresh.
            record = await self._db("read", key)
            if record and record.fresh:
                record_check(source, record.fetched_at, "fresh")
                return self.decode(source, record.payload), True
            operation_task = asyncio.create_task(operation())
            lease_errors = []
            heartbeat = asyncio.create_task(self._keep_lease(key, owner, operation_task, lease_errors))
            try:
                value = await operation_task
            except asyncio.CancelledError:
                if lease_errors:
                    raise lease_errors[0] from None
                raise
            payload = (
                [station.model_dump(mode="json") for station in value]
                if source == "waze" else value.model_dump(mode="json")
            )
            payload = prune_quotes(payload)
            checked_at = await self._db("save", key, source, owner, payload, self.fresh_seconds)
            if checked_at is None:
                raise ProviderError("shared_pricing_refresh_lease_lost")
            record_check(source, checked_at, "fresh")
            return self.decode(source, payload), False
        finally:
            if heartbeat is not None:
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)
            await self._db("release", key, owner)

    async def _keep_lease(self, key, owner, operation_task, errors):
        while not operation_task.done():
            await asyncio.sleep(30)
            try:
                if not await self._db("renew", key, owner):
                    raise ProviderError("shared_pricing_refresh_lease_lost")
            except ProviderError as error:
                errors.append(error)
                operation_task.cancel()
                return

    async def _background(self, source, key, owner, operation):
        # Tasks inherit the foreground caller's context. Revalidation is optional
        # background work and must not consume foreground or reserved allowance.
        background_token = background_acquisition.set(True)
        mandatory_token = mandatory_acquisition.set(False)
        purpose_token = acquisition_purpose.set("revalidation")
        try:
            await self._load(source, key, owner, operation)
        except Exception:
            # Log no URLs, DSNs, cookies, payloads or caller coordinates.
            logger.warning("Shared public pricing refresh deferred for %s", source)
        finally:
            acquisition_purpose.reset(purpose_token)
            mandatory_acquisition.reset(mandatory_token)
            background_acquisition.reset(background_token)

    async def budget_state(self, source):
        return await self._db("budget_state", source)

    async def observe(self, stations):
        await self._db("observe", stations)

    async def mappings(self, source, ids):
        return await self._db("mappings", source, ids)

    async def maintain(self):
        while not self.closed:
            try:
                await self._db("cleanup")
            except ProviderError:
                logger.warning("Shared pricing cleanup unavailable")
            await asyncio.sleep(3600)

    async def close(self):
        self.closed = True
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
