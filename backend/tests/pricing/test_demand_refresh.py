import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from gaswise.contracts.common import Point
from gaswise.contracts.sources import GooglePriceSearch
from gaswise.domain.pricing.shared_cache import background_acquisition
from gaswise.services.pricing.demand_refresh import DemandQueryRefresh


class DurableCache:
    def __init__(self):
        self.now = datetime(2026, 1, 1, tzinfo=UTC)
        self.jobs = {}
        self.calls = []
        self.budget = {"used": 0, "background_used": 0, "background_day_used": 0}

    async def _db(self, method, *args):
        return await getattr(self, method)(*args)

    async def observe_warm_query(self, key, source, raw_key, interval, request_cost=1):
        job = self.jobs.setdefault(key, {"key": key, "source": source, "raw_key": raw_key,
                                         "next_due": self.now + timedelta(seconds=interval)})
        job.update(last_requested_at=self.now, expires_at=self.now + timedelta(days=14), request_cost=request_cost)

    async def warming_plan(self, source):
        jobs = [j for j in self.jobs.values() if j['source'] == source and j['expires_at'] > self.now
                and j['last_requested_at'] >= self.now - timedelta(days=1)]
        return {'active': len(jobs), 'request_cost': sum(j['request_cost'] for j in jobs)}

    async def claim_warm_query(self, owner, sources):
        for job in sorted(self.jobs.values(), key=lambda row: row["next_due"]):
            if (job["source"] in sources and job["expires_at"] > self.now and job["next_due"] <= self.now
                    and job['last_requested_at'] >= self.now - timedelta(days=1) and not job.get("owner")):
                job["owner"] = owner
                return dict(job)

    async def finish_warm_query(self, key, owner, delay, error):
        job = self.jobs[key]
        assert job["owner"] == owner
        job.update(owner=None, next_due=self.now + timedelta(seconds=delay), error=error)

    async def budget_state(self, source):
        return self.budget

    async def get(self, source, raw_key, operation, **kwargs):
        assert background_acquisition.get()
        assert kwargs == {"wait_refresh": True}
        self.calls.append(raw_key)
        return await operation(), False


def service(cache, provider=None):
    class Provider:
        async def stations(self, query):
            assert isinstance(query, GooglePriceSearch)
            return []
    return SimpleNamespace(shared_cache=cache, gasbuddy=None, maps_web=None, waze=provider or Provider(),
                           source_slots={"waze": asyncio.Semaphore(1)}, background_gasbuddy_slot=asyncio.Semaphore(1))


def raw_key(index=0):
    query = GooglePriceSearch(origin=Point(lat=34 + index * .01, lng=-118))
    return "waze:" + query.model_dump_json()


async def test_first_observation_survives_new_scheduler_and_warms_without_renewing_demand():
    cache = DurableCache()
    first = DemandQueryRefresh(service(cache))
    await first.observe("waze", raw_key())
    job = next(iter(cache.jobs.values()))
    requested, expires = job["last_requested_at"], job["expires_at"]
    cache.now += timedelta(minutes=16)
    restarted = DemandQueryRefresh(service(cache))
    assert await restarted.step()
    assert len(cache.calls) == 1
    assert job["last_requested_at"] == requested
    assert job["expires_at"] == expires == requested + timedelta(days=14)


async def test_two_weeks_without_request_stops_warming_but_new_request_renews_retention():
    cache = DurableCache()
    warmer = DemandQueryRefresh(service(cache))
    await warmer.observe("waze", raw_key())
    cache.now += timedelta(days=13)
    await warmer.observe("waze", raw_key())
    renewed = next(iter(cache.jobs.values()))["expires_at"]
    cache.now += timedelta(days=1)
    assert await warmer.step()  # The day-13 request renewed the window.
    cache.now = renewed
    assert not await warmer.step()  # Exact expiry, even though the job is due.
    assert len(cache.calls) == 1


async def test_registration_has_no_old_twelve_query_cap_and_background_never_renews():
    cache = DurableCache()
    warmer = DemandQueryRefresh(service(cache))
    for index in range(20):
        await warmer.observe("waze", raw_key(index))
    assert len(cache.jobs) == 20
    original = next(iter(cache.jobs.values()))["last_requested_at"]
    cache.now += timedelta(days=2)
    token = background_acquisition.set(True)
    try:
        await warmer.observe("waze", raw_key())
    finally:
        background_acquisition.reset(token)
    assert next(iter(cache.jobs.values()))["last_requested_at"] == original


async def test_shared_lease_prevents_two_workers_from_loading_same_query():
    cache = DurableCache()
    started, release = asyncio.Event(), asyncio.Event()

    class SlowProvider:
        async def stations(self, query):
            started.set()
            await release.wait()
            return []

    first, second = DemandQueryRefresh(service(cache, SlowProvider())), DemandQueryRefresh(service(cache))
    await first.observe("waze", raw_key())
    cache.now += timedelta(minutes=16)
    task = asyncio.create_task(first.step())
    await started.wait()
    assert not await second.step()
    release.set()
    assert await task
    assert len(cache.calls) == 1


async def test_exhausted_budget_never_claims_a_job_or_loads_provider():
    cache = DurableCache()
    warmer = DemandQueryRefresh(service(cache))
    await warmer.observe("waze", raw_key())
    cache.now += timedelta(minutes=16)
    cache.budget["background_day_used"] = 100
    assert not await warmer.step()
    assert cache.calls == []
    assert not next(iter(cache.jobs.values())).get("owner")


async def test_failures_back_off_without_extending_retention_or_storing_transport_details():
    cache = DurableCache()

    class BrokenProvider:
        async def stations(self, query):
            raise RuntimeError("private transport diagnostics")

    warmer = DemandQueryRefresh(service(cache, BrokenProvider()))
    await warmer.observe("waze", raw_key())
    job = next(iter(cache.jobs.values()))
    expires = job["expires_at"]
    cache.now += timedelta(minutes=16)
    assert await warmer.step()
    assert job["error"] == "unclassified"
    assert job["expires_at"] == expires
    assert job["next_due"] > cache.now


async def test_shutdown_releases_the_durable_lease_without_renewing_demand():
    cache = DurableCache()
    started = asyncio.Event()

    class SlowProvider:
        async def stations(self, query):
            started.set()
            await asyncio.Event().wait()

    warmer = DemandQueryRefresh(service(cache, SlowProvider()))
    await warmer.observe("waze", raw_key())
    job = next(iter(cache.jobs.values()))
    expires = job["expires_at"]
    cache.now += timedelta(minutes=16)
    task = asyncio.create_task(warmer.step())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert job["owner"] is None
    assert job["error"] == "service_shutdown"
    assert job["expires_at"] == expires


async def test_registration_cannot_persist_routes_or_visitor_fields():
    cache = DurableCache()
    warmer = DemandQueryRefresh(service(cache))
    with pytest.raises(ValueError):
        await warmer.observe("waze", 'waze:{"origin":{"lat":34,"lng":-118},"vehicle_id":123}')
    assert not cache.jobs


async def test_versioned_waze_query_warms_all_grades_after_restart():
    from tests.pricing.test_waze_acquisition import AllFuels

    cache = DurableCache()
    provider = AllFuels()
    first = DemandQueryRefresh(service(cache, provider))
    key = 'waze:all-fuels-v1:' + raw_key().split(':', 1)[1]
    await first.observe('waze', key)
    assert next(iter(cache.jobs.values()))['raw_key'] == key
    cache.now += timedelta(minutes=16)
    captured = []
    original_get = cache.get
    async def get(*args, **kwargs):
        rows, hit = await original_get(*args, **kwargs)
        captured.extend(rows)
        return rows, hit
    cache.get = get
    restarted = DemandQueryRefresh(service(cache, provider))
    assert await restarted.step()
    assert provider.calls == 1
    assert {r.fuel_type for r in captured} == {'regular', 'premium'}
    assert next(iter(cache.jobs.values()))['error'] is None


async def test_warming_cost_sets_durable_interval_without_renewing_demand():
    cache = DurableCache()
    warmer = DemandQueryRefresh(service(cache))
    for index in range(8):
        await warmer.observe('waze', raw_key(index))
    cache.now += timedelta(minutes=16)
    assert await warmer.step()
    completed = next(j for j in cache.jobs.values() if j.get('error') is None and j.get('owner') is None
                     and j['next_due'] > cache.now)
    assert completed['next_due'] - cache.now == timedelta(seconds=103680)
    assert completed['last_requested_at'] < cache.now


async def test_optional_daily_share_defers_before_claiming():
    cache = DurableCache()
    warmer = DemandQueryRefresh(service(cache))
    await warmer.observe('waze', raw_key())
    cache.now += timedelta(minutes=16)
    cache.budget['background_usage'] = {'demand': 19, 'revalidation': 1}
    assert not await warmer.step()
    assert cache.calls == []


async def test_budget_deferral_is_not_source_failure_and_releases_warm_lease():
    from gaswise.domain.ports import ProviderError
    cache = DurableCache()
    class Deferred:
        async def stations(self, query):
            raise ProviderError('waze_optional_daily_budget_exhausted')
    warmer = DemandQueryRefresh(service(cache, Deferred()))
    await warmer.observe('waze', raw_key())
    cache.now += timedelta(minutes=16)
    assert not await warmer.step()
    job = next(iter(cache.jobs.values()))
    assert job['owner'] is None and job['error'] == 'source_budget_deferred'
    assert warmer.paces['waze'].errors == 0


async def test_retained_old_demand_is_dormant_until_a_new_foreground_request():
    cache = DurableCache()
    warmer = DemandQueryRefresh(service(cache))
    await warmer.observe('waze', raw_key())
    cache.now += timedelta(days=2)
    assert not await warmer.step()
    assert len(cache.jobs) == 1
    assert (await cache.warming_plan('waze'))['active'] == 0
    await warmer.observe('waze', raw_key())
    assert await warmer.step()
