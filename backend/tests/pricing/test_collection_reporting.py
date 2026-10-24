import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from gaswise.domain.pricing.collection_reporting import (
    completion,
    failure_message,
    safe_metrics,
    summary_message,
)
from gaswise.providers.notifications.telegram import TelegramDeliveryError, TelegramSender
from gaswise.services.pricing.collection_notifications import CollectionNotifications

NOW = datetime(2026, 10, 19, 20, 0, tzinfo=UTC)


def run():
    return {'id': 123, 'source': 'gasbuddy', 'base': 'irvine', 'fuel': 'premium', 'outcome': 'failure',
            'reason': 'gasbuddy_http_api_rejected', 'started_at': NOW - timedelta(seconds=64),
            'finished_at': NOW, 'http_status': 503, 'phase': 'graphql', 'egress_lane': 1,
            'http_requests': 4, 'retry_at': NOW + timedelta(hours=1)}


def test_failure_is_localized_and_has_reason_status_time_and_lane():
    text = failure_message(run())
    assert 'Irvine' in text and 'HTTP：503' in text and '出口：2' in text
    assert '2026-10-19 13:00:00 PDT' in text and '64.0 秒' in text
    assert 'gasbuddy_http_api_rejected' in text and '#run-123' in text


def test_internal_budget_and_interruptions_do_not_inflate_source_failure_statistics():
    assert completion('gasbuddy_background_daily_budget_exhausted') == ('deferred', 'gasbuddy_background_daily_budget_exhausted')
    assert completion('interrupted') == ('interrupted', 'interrupted')
    assert completion('collection_failed', 'secret=abc') == ('failure', 'unclassified')
    assert safe_metrics({'http_status': 'token=private', 'phase': 'private URL', 'egress_lane': 99}) == {
        'http_status': None, 'http_requests': 0, 'phase': None, 'egress_lane': None,
        'canonical_count': 0, 'new_canonical_count': 0, 'located_count': 0,
        'priced_count': 0, 'inventory_overlap_count': 0}


def test_hourly_summary_distinguishes_deferral_and_does_not_claim_unique_stations():
    report = {'start': NOW - timedelta(hours=1), 'end': NOW, 'reasons': [], 'counts': [
        {'source': 'gasbuddy', 'outcome': 'success', 'attempts': 3, 'quotes': 180},
        {'source': 'gasbuddy', 'outcome': 'failure', 'attempts': 1, 'quotes': 0},
        {'source': 'gasbuddy', 'outcome': 'deferred', 'attempts': 5, 'quotes': 0}]}
    text = summary_message(report)
    assert '成功 3｜失敗 1｜延後 5' in text and '油價 180 筆' in text and '跨任務未去重' in text


class Connection:
    def __init__(self, status=200, data=None):
        self.status, self.data = status, data or {'ok': True, 'result': {'message_id': 42}}
        self.closed = False
    def request(self, *args):
        self.request_args = args
    def getresponse(self):
        return self
    def read(self, size):
        return json.dumps(self.data).encode()
    def close(self):
        self.closed = True


async def test_bot_posts_to_the_selected_topic_and_returns_receipt_without_logging_token(caplog):
    connection = Connection()
    sender = TelegramSender(SecretStr('PRIVATE_TOKEN'), SecretStr('-123'), 77, connection_factory=lambda: connection)
    assert await sender.send('test') == 42
    payload = json.loads(connection.request_args[2])
    assert payload['message_thread_id'] == 77 and payload['chat_id'] == '-123'
    assert connection.closed and 'PRIVATE_TOKEN' not in caplog.text


async def test_bot_error_descriptions_are_not_forwarded_and_retry_after_is_honored():
    connection = Connection(429, {'ok': False, 'error_code': 429, 'description': '/botPRIVATE_TOKEN/private', 'parameters': {'retry_after': 93}})
    sender = TelegramSender(SecretStr('PRIVATE_TOKEN'), SecretStr('-123'), connection_factory=lambda: connection)
    with pytest.raises(TelegramDeliveryError) as caught:
        await sender.send('test')
    assert str(caught.value) == 'telegram_api_429' and caught.value.retry_seconds == 93
    assert 'PRIVATE_TOKEN' not in str(caught.value) and connection.closed


async def test_outbox_acknowledges_only_after_send_and_preserves_retry_reason():
    finished = []
    class Store:
        async def queue_collection_summaries(self):
            pass
        async def claim_collection_notice(self, owner):
            return {'id': 5, 'kind': 'failure', 'payload': {'run_id': 123}, 'attempts': 1}
        async def collection_run(self, run_id):
            return run()
        async def finish_collection_notice(self, *args, **kwargs):
            finished.append(kwargs)
    class Sender:
        async def send(self, text):
            raise TelegramDeliveryError('telegram_api_429', 93)
    notifier = CollectionNotifications(Store(), Sender())
    assert not await notifier.step()
    assert finished == [{'error': 'telegram_api_429', 'retry_seconds': 93}]
    async def sent(text):
        return 42
    notifier.sender = SimpleNamespace(send=sent)
    assert await notifier.step()
    assert finished[-1] == {'message_id': 42}


def test_lane_success_rate_excludes_internal_deferrals():
    report = {'start': NOW - timedelta(hours=1), 'end': NOW, 'counts': [], 'reasons': [], 'lanes': [
        {'source': 'gasbuddy', 'egress_lane': 1, 'outcome': 'success', 'attempts': 3, 'http_requests': 12, 'quotes': 180},
        {'source': 'gasbuddy', 'egress_lane': 1, 'outcome': 'failure', 'attempts': 1, 'http_requests': 2, 'quotes': 0},
        {'source': 'gasbuddy', 'egress_lane': 1, 'outcome': 'deferred', 'attempts': 9, 'http_requests': 0, 'quotes': 0}]}
    text = summary_message(report)
    assert '出口2 gasbuddy：成功率 75%，HTTP 14 次，回傳 180 筆' in text


async def test_attempt_trace_is_shared_with_child_tasks_but_reset_between_jobs():
    import asyncio

    from gaswise.domain.pricing.shared_cache import collection_attempt
    trace = {}
    token = collection_attempt.set(trace)
    try:
        async def request():
            collection_attempt.get().update(http_requests=1, http_status=503)
        await asyncio.create_task(request())
        assert trace == {'http_requests': 1, 'http_status': 503}
    finally:
        collection_attempt.reset(token)
    assert collection_attempt.get() is None
