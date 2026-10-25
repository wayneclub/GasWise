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
