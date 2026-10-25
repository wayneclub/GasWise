from datetime import UTC, datetime, timedelta

from gaswise.providers.storage.postgres import PostgresPricingCache


class Connection:
    def __init__(self):
        self.daily = []

    async def executemany(self, sql, rows):
        if 'INSERT INTO gaswise.quote_daily' in sql:
            self.daily.extend(rows)


async def test_repeated_report_is_observed_on_each_actual_fetch_day_without_fabricating_gap_days():
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    quote = dict(source='gasbuddy_web', id='10929', name='Speedway', fuel_type='premium',
                 payment_type='credit', price_per_gallon='6.15',
                 price_updated_at=(now-timedelta(days=2)).isoformat(), fetched_at=now.isoformat())
    connection = Connection()
    store = PostgresPricingCache(None)
    await store._observe(connection, [quote])
    await store._observe(connection, [{**quote, 'fetched_at': (now-timedelta(days=1)).isoformat()}])
    assert len(connection.daily) == 2
    assert connection.daily[0][8] == connection.daily[1][8]  # source report time is unchanged
    assert connection.daily[0][9] != connection.daily[1][9]  # real fetch dates remain distinct
