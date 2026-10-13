from datetime import UTC, datetime, timedelta

from gaswise.contracts.search import Search
from gaswise.domain.pricing.cache_policy import prune_quotes
from gaswise.domain.pricing.comparison import ineligible
from tests.support.service import FixtureProvider


def test_today_fetch_does_not_renew_four_day_old_price_and_unknown_time_has_short_expiry():
    now = datetime.now(UTC)
    rows = [
        {"id":"old", "price_updated_at":(now-timedelta(days=4)).isoformat(), "fetched_at":now.isoformat()},
        {"id":"known", "price_updated_at":(now-timedelta(days=2)).isoformat(), "fetched_at":now.isoformat()},
        {"id":"unknown-expired", "price_updated_at":None, "fetched_at":(now-timedelta(hours=7)).isoformat()},
        {"id":"unknown-new", "price_updated_at":None, "fetched_at":now.isoformat()},
    ]
    assert [row["id"] for row in prune_quotes(rows,now)] == ["known","unknown-new"]
    response = {"prices":rows, "inventory":[{"id":"old"}], "partial":True}
    pruned = prune_quotes(response,now)
    assert pruned["inventory"] == response["inventory"] and pruned["partial"] is True
    assert rows[0]["price_updated_at"] == (now-timedelta(days=4)).isoformat()


async def test_seventy_two_hour_limit_cannot_be_relaxed_by_query_or_held_snapshot():
    station = (await FixtureProvider().stations(None))[0]
    now = datetime.now(UTC)
    query = Search(origin=station.location,max_price_age_minutes=10080)
    station.price_updated_at = now-timedelta(hours=72)
    assert ineligible(station,query,now) == "stale_price"
    station.price_updated_at = None
    station.fetched_at = now-timedelta(hours=6)
    assert ineligible(station,query,now) == "stale_price"
