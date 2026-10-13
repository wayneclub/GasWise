"""Adaptive, bounded warming of recently used public provider queries."""

import asyncio
import hashlib
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from time import monotonic

from gaswise.domain.pricing.shared_cache import background_acquisition

logger = logging.getLogger(__name__)


@dataclass
class HotQuery:
    source: str
    raw_key: str
    operation: Callable[[], Awaitable]
    last_seen: float
    last_attempt: float
    uses: deque = field(default_factory=lambda: deque(maxlen=100))


@dataclass
class SourcePace:
    failures: int = 0
    not_before: float = 0
    loads: int = 0
    errors: int = 0
    deferred: int = 0


class HotQueryRefresh:
    def __init__(self, cache, *, max_queries=20, interval=900, idle_seconds=3600,
                 limits=None, daily_limit=100, clock=monotonic):
        self.cache = cache
        self.max_queries = max_queries
        self.interval = interval
        self.idle_seconds = idle_seconds
        self.clock = clock
        self.limits = limits or {"gasbuddy": 12, "maps": 60, "waze": 20}
        self.daily_limit = daily_limit
        self.queries = {}
        self.paces = {source: SourcePace() for source in self.limits}

    def observe(self, source, raw_key, operation):
        now = self.clock()
        self._prune(now)
        key = hashlib.sha256(raw_key.encode()).hexdigest()
        if key in self.queries:
            query = self.queries[key]
            query.last_seen, query.operation = now, operation
        else:
            if len(self.queries) >= self.max_queries or source not in self.paces:
                return
            query = HotQuery(source, raw_key, operation, now, now)
            self.queries[key] = query
        query.uses.append(now)

    def _prune(self, now):
        self.queries = {key: query for key, query in self.queries.items()
                        if now - query.last_seen < self.idle_seconds}
        for query in self.queries.values():
            while query.uses and now - query.uses[0] >= self.idle_seconds:
                query.uses.popleft()

    def demand_interval(self, query):
        multiplier = 1 if len(query.uses) >= 12 else 2 if len(query.uses) >= 6 else 4
        return min(3600, self.interval * multiplier)

    def _failed(self, source):
        pace = self.paces[source]
        pace.failures = min(pace.failures + 1, 5)
        pace.errors += 1
        pace.not_before = self.clock() + min(21600, self.interval * 2 ** pace.failures)
        logger.warning("Hot pricing refresh backed off for %s", source)

    async def step(self):
        now = self.clock()
        self._prune(now)
        eligible = [query for query in self.queries.values()
                    if len(query.uses) >= 3
                    and now - query.last_attempt >= self.demand_interval(query)
                    and now >= self.paces[query.source].not_before]
        # Oldest due first prevents one popular query from starving other cells.
        for query in sorted(eligible, key=lambda item: (item.last_attempt, -len(item.uses))):
            pace = self.paces[query.source]
            try:
                state = await self.cache.budget_state(query.source)
                blocked = float(state.get("blocked_seconds") or 0)
                if (blocked > 0 or state["used"] >= max(1, self.limits[query.source] // 2)
                        or state.get("background_used", 0) >= max(1, self.limits[query.source] // 5)
                        or state.get("background_day_used", 0) >= self.daily_limit):
                    pace.deferred += 1
                    pace.not_before = now + max(60, blocked)
                    continue
            except Exception:
                self._failed(query.source)
                continue
            query.last_attempt = now
            invoked = False

            async def load(query=query, pace=pace):
                nonlocal invoked
                invoked = True
                try:
                    value = await query.operation()
                except Exception:
                    self._failed(query.source)
                    raise
                pace.loads += 1
                # Recover gradually; a successful HTTP observation is required.
                pace.failures = max(0, pace.failures - 1)
                pace.not_before = self.clock() + (self.interval * 2 ** pace.failures if pace.failures else 0)
                return value

            token = background_acquisition.set(True)
            try:
                await self.cache.get(query.source, query.raw_key, load)
            except Exception:
                if not invoked:
                    self._failed(query.source)
            finally:
                background_acquisition.reset(token)
            return True
        return False

    async def status(self):
        self._prune(self.clock())
        sources = {}
        for source, pace in self.paces.items():
            state = await self.cache.budget_state(source)
            sources[source] = {
                **state, "minute_limit": self.limits[source],
                "background_minute_limit": max(1, self.limits[source] // 5),
                "background_daily_limit": self.daily_limit,
                "backoff_seconds": max(0, round(pace.not_before - self.clock())),
                "completed_loads": pace.loads, "errors": pace.errors, "deferred": pace.deferred,
            }
        return {"enabled": True, "registered_queries": len(self.queries),
                "hot_queries": sum(len(query.uses) >= 3 for query in self.queries.values()),
                "max_queries": self.max_queries, "minimum_interval_seconds": self.interval,
                "sources": sources}

    async def run(self):
        while True:
            await asyncio.sleep(60)
            await self.step()
