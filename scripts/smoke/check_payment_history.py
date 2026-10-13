"""Run inside backend container; transactional DB proof, zero upstream requests."""
import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import asyncpg

from gaswise.app.settings import Settings
from gaswise.contracts.common import Point, Station
from gaswise.contracts.search import Search
from gaswise.domain.pricing.comparison import select_prices
from gaswise.providers.storage.postgres import PostgresPricingCache


async def main():
    connection = await asyncpg.connect(Settings().database_url.get_secret_value())
    transaction = connection.transaction()
    await transaction.start()
    try:
        now = datetime.now(UTC)
        key = 'validation:' + uuid4().hex
        cash = Station(id=key, canonical_id=key, name='Transactional payment validation',
                       source='gasbuddy_web', location=Point(lat=34.04, lng=-118.27),
                       fuel_type='premium', payment_type='cash', price_per_gallon=Decimal('6.00'),
                       price_updated_at=now, fetched_at=now)
        rows = []
        for days in (0, 1, 2):
            stamp = now-timedelta(days=days)
            for method, price in [('cash','6.00'), ('credit','6.10')]:
                rows.append(cash.model_copy(update={'payment_type':method, 'price_per_gallon':Decimal(price),
                                                   'price_updated_at':stamp}).model_dump(mode='json'))
        store = PostgresPricingCache(connection)
        await store._observe(connection, rows)
        history = await store.payment_history([key], ['premium'])
        assert len(history[key]) == 6
        raw = cash.model_copy(update={'source':'waze', 'payment_type':'unknown', 'payment_history':history[key]})
        query = Search(origin=cash.location, fuel_type='premium', payment_type='credit', allow_unknown_payment=True)
        selected, _, _ = select_prices([raw, cash], query, now)
        assert selected[0].station.comparison_price_per_gallon == Decimal('6.10')
        assert selected[0].station.price_per_gallon == Decimal('6.00')
        assert selected[0].station.payment_type == 'unknown'
        again, _, _ = select_prices([selected[0].station, cash], query, now)
        assert again[0].station.comparison_price_per_gallon == Decimal('6.10')
        raw.payment_history = []
        no_history, _, _ = select_prices([raw, cash], query, now)
        assert no_history[0].station.comparison_price_per_gallon is None
        print('PASS: PostgreSQL raw history, paired estimate, repeat ranking and insufficient-history fallback; zero upstream calls')
    finally:
        await transaction.rollback()
        await connection.close()
    print('PASS: validation observations rolled back')


asyncio.run(main())
