import asyncio
import pytest
from time import monotonic
from unittest.mock import AsyncMock, MagicMock

from gaswise.contracts.common import Point, Route, SourceStatus, Station
from gaswise.contracts.smart import SmartResult, SmartSearch, SmartSnapshot
from gaswise.domain.ports import PriceSnapshot, ProgressiveSearchCapacityExceeded
from gaswise.services.pricing.progressive import ProgressiveSearchManager


@pytest.mark.asyncio
async def test_progressive_manager_job_lifecycle():
    service = MagicMock()
    service.demo = None
    service.gasbuddy = None
    service.maps_web = None
    service.waze = None
    service.sign.return_value = "dummy-sig"

    manager = ProgressiveSearchManager(service, max_active=2, max_jobs=5, job_ttl_seconds=10.0)

    query = SmartSearch(origin=Point(lat=34.0, lng=-118.0))
    state = await manager.start(query)

    assert state.status == "pending"
    assert state.revision == 0
    assert state.job_id in manager.jobs

    polled = await manager.poll(state.job_id)
    assert polled is not None
    assert polled.job_id == state.job_id

    # Wait for background task to complete
    await asyncio.gather(*manager.tasks)
    polled = await manager.poll(state.job_id)
    assert polled.status == "complete" or polled.status == "failed"

    await manager.close()
    assert len(manager.tasks) == 0
    assert len(manager.jobs) == 0


@pytest.mark.asyncio
async def test_progressive_manager_capacity_exceeded():
    service = MagicMock()
    manager = ProgressiveSearchManager(service, max_active=1)

    # Fake an active job
    manager.jobs["active_1"] = {
        "job_id": "active_1",
        "status": "pending",
        "revision": 0,
        "completed_sources": [],
        "result": None,
        "error": None,
        "updated_at": monotonic(),
    }

    query = SmartSearch(origin=Point(lat=34.0, lng=-118.0))
    with pytest.raises(ProgressiveSearchCapacityExceeded):
        await manager.start(query)


@pytest.mark.asyncio
async def test_progressive_manager_prunes_stale_jobs():
    service = MagicMock()
    manager = ProgressiveSearchManager(service, job_ttl_seconds=50.0)

    # Insert a stale job
    manager.jobs["stale_job"] = {
        "job_id": "stale_job",
        "status": "complete",
        "revision": 1,
        "completed_sources": ["gasbuddy"],
        "result": None,
        "error": None,
        "updated_at": monotonic() - 100.0,
    }

    manager.prune()
    assert "stale_job" not in manager.jobs
