import json
from datetime import UTC, datetime, timedelta

import pytest

from gaswise.providers.storage.postgres import PostgresPricingCache


class CaptureConnection:
    def __init__(self):
        self.history = []

    async def executemany(self, sql, rows):
        if 'INSERT INTO gaswise.quote_history' in sql:
            self.history.extend(rows)


@pytest.mark.asyncio
async def test_history_identity_preserves_report_time_and_conditions():
    now = datetime.now(UTC)
    quote = dict(source='waze', id='station', name='Test', fuel_type='regular',
                 payment_type='unknown', price_per_gallon='6.399',
                 price_updated_at=now.isoformat(), fetched_at=now.isoformat())
    connection = CaptureConnection()
    store = PostgresPricingCache(None)
    await store._observe(connection, [quote])
    await store._observe(connection, [{**quote, 'fetched_at': (now + timedelta(minutes=5)).isoformat()}])
    await store._observe(connection, [{**quote, 'price_per_gallon': '6.499'}])
    await store._observe(connection, [{**quote, 'payment_type': 'credit'}])
    keys = [row[0] for row in connection.history]
    assert keys[0] == keys[1]
    assert len(set(keys)) == 3
    assert connection.history[0][7] == '6.399'
    assert connection.history[0][8] == now
    assert 'fetched_at' not in json.loads(connection.history[0][10])
