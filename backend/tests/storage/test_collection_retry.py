from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from gaswise.providers.storage.collection_events import CollectionEvents


class Scope:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *args):
        pass


@pytest.mark.parametrize('source,code,failures,expected', [
    ('maps', 'google_maps_web_unavailable', 0, 60),
    ('maps', 'google_maps_web_unavailable', 1, 300),
    ('waze', 'waze_upstream_unavailable', 2, 900),
    ('waze', 'waze_upstream_unavailable', 100, 3600),
    ('maps', 'google_maps_web_rate_limited', 0, 3600),
    ('maps', 'google_maps_web_session_rejected', 0, 3600),
    ('waze', 'waze_reauthentication_required', 0, 3600),
    ('gasbuddy', 'gasbuddy_http_unavailable', 0, 3600),
])
async def test_durable_failure_backoff_updates_schedule_and_journal_together(source, code, failures, expected):
    now = datetime(2026, 10, 25, tzinfo=UTC)
    job = dict(id='test', source=source, clock=now, failures=failures)
    connection = AsyncMock()
    connection.transaction = lambda: Scope(None)
    connection.fetchval.return_value = source
    connection.fetchrow.side_effect = [None, job]
    events = CollectionEvents()
    events.pool = type('Pool', (), {'acquire': lambda self: Scope(connection)})()
    events._append_collection_run = AsyncMock(return_value=('failure', code))
    assert await events.finish_collection_attempt('test', 'owner', 3600, 'collection_failed', 0, 0,
                                                {'failure_code': code})
    retry_at = events._append_collection_run.call_args.args[7]
    assert (retry_at - now).total_seconds() == expected
    update = connection.execute.call_args.args
    assert update[3] == retry_at
    assert update[5] == 'failure'


@pytest.mark.parametrize('clock,expected', [
    # 10:00 PDT -> next Los Angeles midnight, not an hourly retry.
    (datetime(2026, 10, 25, 17, tzinfo=UTC), datetime(2026, 10, 26, 7, tzinfo=UTC)),
    # 23:30 PDT on the night clocks fall back; midnight is still PDT.
    (datetime(2026, 11, 1, 6, 30, tzinfo=UTC), datetime(2026, 11, 1, 7, tzinfo=UTC)),
    # 00:30 PST after the change -> following midnight is 08:00 UTC.
    (datetime(2026, 11, 2, 8, 30, tzinfo=UTC), datetime(2026, 11, 3, 8, tzinfo=UTC)),
])
async def test_checked_hotspot_target_without_new_daily_price_waits_for_next_la_day(clock, expected):
    # The station-centred fetch already lists the target nearest-first; refetching the same
    # day cannot create a fresh report, so it must not spend more source requests today.
    job = dict(id='hotspot:dtla:premium:10929', source='gasbuddy', clock=clock, failures=0)
    connection = AsyncMock()
    connection.transaction = lambda: Scope(None)
    connection.fetchrow.side_effect = [job]
    events = CollectionEvents()
    events.pool = type('Pool', (), {'acquire': lambda self: Scope(connection)})()
    events._append_collection_run = AsyncMock(return_value=('deferred', 'coverage_missing'))
    assert await events.finish_collection_attempt(job['id'], 'owner', 3600, 'coverage_missing', 7, 5)
    assert events._append_collection_run.call_args.args[7] == expected
    assert connection.execute.call_args.args[3] == expected


async def test_coverage_missing_journal_keeps_fetched_quote_counts():
    # A missing target is not an empty fetch: the run journal must show what came back.
    job = dict(id='hotspot:dtla:regular:336', owner='owner', base='la', source='gasbuddy', fuel='regular',
               clock=datetime(2026, 10, 25, 17, tzinfo=UTC), failures=0)
    connection = AsyncMock()
    connection.transaction = lambda: Scope(None)
    connection.fetchrow.side_effect = [job]
    connection.fetchval.return_value = 42
    events = CollectionEvents()
    events.pool = type('Pool', (), {'acquire': lambda self: Scope(connection)})()
    assert await events.finish_collection_attempt(job['id'], 'owner', 3600, 'coverage_missing', 7, 5,
                                                {'http_requests': 1, 'priced_count': 5})
    insert = connection.fetchval.call_args.args
    assert insert[7:9] == ('deferred', 'coverage_missing')
    assert insert[13:15] == (7, 5)
