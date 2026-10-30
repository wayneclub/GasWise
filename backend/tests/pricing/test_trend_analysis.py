from datetime import UTC, datetime
from decimal import Decimal

from gaswise.domain.pricing.trend_analysis import (
    analyze_price_band,
    analyze_station_history,
    analyze_weekend_cycle,
    calculate_percentile,
)


def test_percentile_calculation():
    prices = [Decimal("5.00"), Decimal("5.10"), Decimal("5.20"), Decimal("5.30")]
    # target is below all
    assert calculate_percentile(prices, Decimal("4.90")) == 0.0
    # target is above all
    assert calculate_percentile(prices, Decimal("5.50")) == 100.0
    # target is min element (less=0, equal=1 -> 0.5/4 = 12.5%)
    assert calculate_percentile(prices, Decimal("5.00")) == 12.5


def test_price_band_near_low_suggests_filling_tank():
    # 30-day prices where latest is near low
    prices = [Decimal("5.50"), Decimal("5.40"), Decimal("5.30"), Decimal("5.20"), Decimal("5.05")]
    analysis = analyze_price_band(prices, current_price=Decimal("5.05"))
    assert analysis["band"] == "near_low"
    assert analysis["is_cycle_low"] is True
    assert analysis["is_cycle_high"] is False
    assert analysis["min_price"] == "5.05"
    assert analysis["max_price"] == "5.50"
    assert "建議把握時機加滿" in analysis["advice"]


def test_price_band_near_high_suggests_partial_fill():
    # 30-day prices where latest is near high
    prices = [Decimal("5.00"), Decimal("5.05"), Decimal("5.10"), Decimal("5.15"), Decimal("5.85")]
    analysis = analyze_price_band(prices, current_price=Decimal("5.85"))
    assert analysis["band"] == "near_high"
    assert analysis["is_cycle_low"] is False
    assert analysis["is_cycle_high"] is True
    assert "先加半箱應急" in analysis["advice"]


def test_price_band_mid_range():
    prices = [Decimal("5.00"), Decimal("5.20"), Decimal("5.40"), Decimal("5.60")]
    analysis = analyze_price_band(prices, current_price=Decimal("5.30"))
    assert analysis["band"] == "mid_range"
    assert analysis["is_cycle_low"] is False
    assert analysis["is_cycle_high"] is False
    assert "常態價格區間" in analysis["advice"]


def test_weekend_cycle_on_thursday_with_rising_trend():
    # Thursday: 2026-10-29
    thursday = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
    observations = [
        {"price": "5.00", "reported_at": "2026-10-22T10:00:00Z"},
        {"price": "5.05", "reported_at": "2026-10-24T10:00:00Z"},
        {"price": "5.25", "reported_at": "2026-10-28T10:00:00Z"},
        {"price": "5.30", "reported_at": "2026-10-29T10:00:00Z"},
    ]
    cycle = analyze_weekend_cycle(observations, now=thursday)
    assert cycle["day_of_week"] == "Thursday"
    assert cycle["is_pre_weekend"] is True
    assert cycle["pre_weekend_hike_risk"] is True
    assert cycle["risk_level"] == "high"
    assert cycle["trend"] == "rising"
    assert "強烈建議今日加滿" in cycle["message"]


def test_weekend_cycle_on_monday_is_low_risk():
    # Monday: 2026-10-26
    monday = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
    observations = [
        {"price": "5.20", "reported_at": "2026-10-24T10:00:00Z"},
        {"price": "5.18", "reported_at": "2026-10-26T10:00:00Z"},
    ]
    cycle = analyze_weekend_cycle(observations, now=monday)
    assert cycle["day_of_week"] == "Monday"
    assert cycle["is_pre_weekend"] is False
    assert cycle["pre_weekend_hike_risk"] is False
    assert cycle["risk_level"] == "low"
    assert "週初油價回檔平穩期" in cycle["message"]


def test_station_history_analysis_integration():
    observations = [
        {"price": "5.10", "reported_at": "2026-10-15T10:00:00Z"},
        {"price": "5.15", "reported_at": "2026-10-20T10:00:00Z"},
        {"price": "5.20", "reported_at": "2026-10-28T10:00:00Z"},
    ]
    now = datetime(2026, 10, 29, 10, 0, tzinfo=UTC)
    result = analyze_station_history(observations, now=now)
    assert result["observation_count"] == 3
    assert result["price_band"]["min_price"] == "5.10"
    assert result["price_band"]["max_price"] == "5.20"
    assert result["weekend_cycle"]["is_pre_weekend"] is True
