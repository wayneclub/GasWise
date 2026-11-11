"""Progressive search manager for streaming and multi-stage fuel price discovery."""

import asyncio
import secrets
from time import monotonic
from typing import Any, Dict, List, Optional, Set

from gaswise.contracts.smart import ProgressiveSearchState, SmartResult, SmartSearch
from gaswise.domain.ports import ProgressiveSearchCapacityExceeded, ProviderError


class ProgressiveSearchManager:
    """Coordinates multi-source progressive searches, jobs lifecycle, and result merging."""

    def __init__(
        self,
        service: Any = None,
        max_active: int = 8,
        max_jobs: int = 100,
        job_ttl_seconds: float = 300.0,
        slots: Optional[asyncio.Semaphore] = None,
    ):
        self.service = service
        self.max_active = max_active
        self.max_jobs = max_jobs
        self.job_ttl_seconds = job_ttl_seconds
        self.slots = slots or asyncio.Semaphore(max_active)
        self.jobs: Dict[str, dict] = {}
        self.tasks: Set[asyncio.Task] = set()

    def _state(self, job: dict) -> ProgressiveSearchState:
        return ProgressiveSearchState(**{key: value for key, value in job.items() if key != "updated_at"})

    def prune(self) -> None:
        cutoff = monotonic() - self.job_ttl_seconds
        for job_id in [key for key, job in self.jobs.items() if job["updated_at"] < cutoff]:
            self.jobs.pop(job_id, None)

    async def start(self, query: SmartSearch) -> ProgressiveSearchState:
        self.prune()
        active = sum(job["status"] in {"pending", "partial"} for job in self.jobs.values())
        if active >= self.max_active:
            raise ProgressiveSearchCapacityExceeded()
        if len(self.jobs) >= self.max_jobs:
            terminal = next(
                (key for key, job in self.jobs.items() if job["status"] in {"complete", "failed"}),
                None,
            )
            if terminal is not None:
                self.jobs.pop(terminal)
        job_id = secrets.token_urlsafe(24)
        job = {
            "job_id": job_id,
            "status": "pending",
            "revision": 0,
            "completed_sources": [],
            "result": None,
            "error": None,
            "updated_at": monotonic(),
        }
        self.jobs[job_id] = job
        task = asyncio.create_task(self._run_search(job, query))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return self._state(job)

    async def poll(self, job_id: str) -> Optional[ProgressiveSearchState]:
        self.prune()
        job = self.jobs.get(job_id)
        return self._state(job) if job is not None else None

    async def close(self) -> None:
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()
        self.jobs.clear()

    async def _run_search(self, job: dict, query: SmartSearch) -> None:
        try:
            async with self.slots:
                if self.service is not None and getattr(self.service, "demo", None) is not None:
                    result = await self.service.search(query)
                    job.update(
                        status="complete",
                        revision=1,
                        completed_sources=["synthetic"],
                        result=result,
                        updated_at=monotonic(),
                    )
                    return

                sources = []
                if self.service is not None:
                    sources = [
                        name
                        for name, provider in (
                            ("gasbuddy", getattr(self.service, "gasbuddy", None)),
                            ("maps", getattr(self.service, "maps_web", None)),
                            ("waze", getattr(self.service, "waze", None)),
                        )
                        if provider is not None
                    ]
                source_query = query

                async def collect_source(source: str):
                    try:
                        return source, await self.service.collect(source_query, sources={source})
                    except ProviderError:
                        return source, None

                tasks = [asyncio.create_task(collect_source(source)) for source in sources]
                results = []
                try:
                    for completed in asyncio.as_completed(tasks):
                        source, result = await completed
                        job["completed_sources"].append(source)
                        if result is not None:
                            results.append(result)
                            merged = await self.merge_results(results)
                            job.update(
                                status="partial" if len(job["completed_sources"]) < len(sources) else "complete",
                                revision=job["revision"] + 1,
                                result=merged,
                                updated_at=monotonic(),
                            )
                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                if job["result"] is None:
                    job.update(status="failed", error="smart_price_sources_unavailable", updated_at=monotonic())
                elif len(job["completed_sources"]) == len(sources):
                    job.update(status="complete", updated_at=monotonic())
        except asyncio.CancelledError:
            raise
        except Exception:
            job.update(status="failed", error="progressive_search_failed", updated_at=monotonic())

    async def merge_results(self, results: List[SmartResult]) -> SmartResult:
        newest = results[-1]
        snapshot = newest.snapshot.model_copy(deep=True)
        snapshot.discovery_metrics = {
            key: value
            for result in results
            for key, value in result.snapshot.discovery_metrics.items()
        }
        stations = {}
        statuses = {}
        inventory = {}
        warnings = []
        unlocated = {}
        upstream_calls = {}
        cache_hits = 0
        for result in results:
            cache_hits += result.cache_hits
            for key, value in result.upstream_calls.items():
                upstream_calls[key] = upstream_calls.get(key, 0) + value
            for station in result.snapshot.stations:
                key = (station.source, station.id, station.payment_type, station.price_per_gallon)
                stations[key] = station
            for status in result.snapshot.source_statuses:
                statuses[status.source] = status
            for item in result.snapshot.inventory:
                inventory[item.place_id] = item
            for warning in result.snapshot.warnings:
                if warning not in warnings:
                    warnings.append(warning)
            for quote in result.snapshot.unlocated_gasbuddy:
                unlocated[quote.id] = quote
        snapshot = snapshot.model_copy(
            update={
                "stations": list(stations.values()),
                "source_statuses": list(statuses.values()),
                "inventory": list(inventory.values()),
                "warnings": warnings,
                "unlocated_gasbuddy": list(unlocated.values()),
            }
        )
        ranking = None
        if self.service is not None and snapshot.baseline is not None:
            ranking = await self.service.rank(snapshot, snapshot.query)
        signature = self.service.sign(snapshot) if self.service is not None else ""
        return SmartResult(
            snapshot=snapshot,
            signature=signature,
            ranking=ranking,
            cache_hits=cache_hits,
            upstream_calls=upstream_calls,
            timings_ms={"total": max(result.timings_ms.get("total", 0) for result in results)},
        )
