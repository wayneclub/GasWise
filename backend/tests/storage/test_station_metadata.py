import json
from datetime import UTC, datetime, timedelta

import pytest

from gaswise.providers.storage.postgres import (
    PostgresPricingCache,
    station_attributes,
    station_checked_at,
    station_metadata,
)


class CaptureConnection:
    def __init__(self):
        self.stations = []
        self.history = []
        self.sql = []

    async def executemany(self, sql, rows):
        self.sql.append(sql)
        if "INSERT INTO gaswise.stations" in sql:
            self.stations.extend(rows)
        if "INSERT INTO gaswise.quote_history" in sql:
            self.history.extend(rows)


def quote(**overrides):
    now = datetime.now(UTC)
    values = {
        "source": "gasbuddy_web",
        "id": "station-1",
        "name": "Test Fuel",
        "address": "1 Main St, Los Angeles, CA 90001",
        "location": {"lat": 34.05, "lng": -118.24},
        "fuel_type": "regular",
        "payment_type": "unknown",
        "price_per_gallon": "6.399",
        "price_updated_at": now.isoformat(),
        "fetched_at": now.isoformat(),
    }
    values.update(overrides)
    return values


def test_station_metadata_keeps_only_valid_provider_coordinates():
    assert station_metadata(quote())["location"] == {"lat": 34.05, "lng": -118.24}
    assert station_metadata(quote())["location_source"] == "gasbuddy_web"
    for invalid in (
        None,
        {},
        {"lat": None, "lng": -118.24},
        {"lat": 91, "lng": 0},
        {"lat": 0, "lng": 0},
        {"lat": True, "lng": -118.24},
    ):
        assert "location" not in station_metadata(quote(location=invalid))
    assert station_metadata(quote(location=None)) == {
        "name": "Test Fuel",
        "address": "1 Main St, Los Angeles, CA 90001",
    }


def test_station_metadata_records_google_facts_hours_and_status():
    metadata = station_metadata(
        quote(
            rating=4.5,
            review_count=120,
            rating_source="Google Maps",
            open_now=False,
            business_status="permanently_closed",
            details={
                "location_source": "google_maps_web",
                "opening_status": "Permanently closed",
                "opening_hours": [
                    {"days": [1], "from": "06:00", "to": "22:00", "is_24_hours": False}
                ],
                "opening_hours_text": ["Monday: 6 AM–10 PM"],
                "opening_status_checked_at": "2026-10-23T00:00:00+00:00",
            },
        )
    )
    assert metadata["location_source"] == "google_maps_web"
    assert metadata["rating"] == 4.5
    assert metadata["review_count"] == 120
    assert metadata["rating_source"] == "Google Maps"
    assert metadata["open_now"] is False
    assert metadata["business_status"] == "permanently_closed"
    assert metadata["opening_status"] == "Permanently closed"
    assert metadata["opening_hours"][0]["from"] == "06:00"
    assert metadata["opening_hours_text"] == ["Monday: 6 AM–10 PM"]
    assert metadata["opening_status_checked_at"] == "2026-10-23T00:00:00+00:00"


def test_station_attributes_record_hours_and_status():
    attributes = station_attributes(
        quote(
            rating=4.2,
            review_count=10,
            rating_source="Google Maps",
            open_now=True,
            business_status="operational",
            details={
                "location_source": "google_places",
                "opening_hours": [
                    {"days": [0], "from": "00:00", "to": "00:00", "is_24_hours": True}
                ],
            },
        )
    )
    assert attributes["location_source"] == "google_places"
    assert attributes["rating"] == 4.2
    assert attributes["open_now"] is True
    assert attributes["business_status"] == "operational"
    assert attributes["opening_hours"][0]["is_24_hours"] is True


def test_station_checked_at_parses_provider_time_and_falls_back_to_fetch_time():
    fallback = datetime(2026, 10, 23, 1, tzinfo=UTC)
    assert station_checked_at(
        {"opening_status_checked_at": "2026-10-23T00:00:00Z"}, fallback
    ) == datetime(2026, 10, 23, 0, tzinfo=UTC)
    assert station_checked_at(
        {"opening_status_checked_at": "2026-10-23T00:00:00"}, fallback
    ) == datetime(2026, 10, 23, 0, tzinfo=UTC)
    assert station_checked_at({}, fallback) == fallback
    assert station_checked_at({"opening_status_checked_at": "not-a-time"}, fallback) == fallback


@pytest.mark.asyncio
async def test_locationless_observation_does_not_replace_stored_coordinates():
    connection = CaptureConnection()
    store = PostgresPricingCache(None)
    now = datetime.now(UTC)
    await store._observe(connection, [quote()])
    await store._observe(
        connection,
        [quote(location=None, fetched_at=(now + timedelta(minutes=5)).isoformat())],
    )
    assert json.loads(connection.stations[0][3])["location"] == {"lat": 34.05, "lng": -118.24}
    assert "location" not in json.loads(connection.stations[1][3])
    sql = connection.sql[0]
    assert "COALESCE(stations.metadata->>'location_source', stations.source)" in sql
    assert "stations.canonical_id LIKE 'google_places:%'" in sql
    assert "THEN EXCLUDED.metadata || stations.metadata" in sql
    assert "ELSE stations.metadata || EXCLUDED.metadata" in sql
    assert "THEN stations.canonical_id" in sql


@pytest.mark.asyncio
async def test_history_keeps_hours_status_and_rating():
    connection = CaptureConnection()
    await PostgresPricingCache(None)._observe(
        connection,
        [
            quote(
                rating=4.2,
                review_count=10,
                rating_source="Google Maps",
                open_now=True,
                business_status="operational",
                details={
                    "location_source": "google_places",
                    "opening_hours": [
                        {"days": [0], "from": "00:00", "to": "00:00", "is_24_hours": True}
                    ],
                },
            )
        ],
    )
    attributes = json.loads(connection.history[0][-1])
    assert attributes["location_source"] == "google_places"
    assert attributes["rating"] == 4.2
    assert attributes["open_now"] is True
    assert attributes["business_status"] == "operational"
    assert attributes["opening_hours"][0]["is_24_hours"] is True
