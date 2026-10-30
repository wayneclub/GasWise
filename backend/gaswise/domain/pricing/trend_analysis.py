"""30-day price band, percentile rank, and pre-weekend hike cycle analysis."""

from datetime import UTC, datetime
from decimal import Decimal
from statistics import median
from typing import Literal

BandName = Literal["near_low", "mid_range", "near_high"]
RiskLevel = Literal["low", "medium", "high"]
PriceTrend = Literal["rising", "falling", "stable"]


def calculate_percentile(prices: list[Decimal], target: Decimal) -> float:
    """Calculate percentile rank of target within prices (0.0 to 100.0)."""
    if not prices:
        return 50.0
    less = sum(1 for p in prices if p < target)
    equal = sum(1 for p in prices if p == target)
    return round(((less + 0.5 * equal) / len(prices)) * 100.0, 1)


def analyze_price_band(prices: list[Decimal], current_price: Decimal | None = None) -> dict:
    """Analyze price distribution over historical observations."""
    valid_prices = sorted(p for p in prices if p > 0)
    if not valid_prices:
        return {
            "min_price": None,
            "max_price": None,
            "median_price": None,
            "current_price": str(current_price) if current_price else None,
            "percentile": None,
            "band": "mid_range",
            "is_cycle_low": False,
            "is_cycle_high": False,
            "advice": "數據不足，依常態需求加油",
        }

    min_p = valid_prices[0]
    max_p = valid_prices[-1]
    med_p = Decimal(str(median(valid_prices)))
    target = current_price if current_price is not None else valid_prices[-1]
    percentile = calculate_percentile(valid_prices, target)

    if percentile <= 25.0:
        band: BandName = "near_low"
        is_low = True
        is_high = False
        advice = f"油價處於近期低位（歷史前 {percentile:.0f}% 低點），建議把握時機加滿。"
    elif percentile >= 75.0:
        band = "near_high"
        is_low = False
        is_high = True
        advice = f"油價處於近期高位（歷史第 {percentile:.0f}% 高點），若非急需建議先加半箱應急。"
    else:
        band = "mid_range"
        is_low = False
        is_high = False
        advice = f"油價處於常態價格區間（第 {percentile:.0f}% 百分位），可依一般用車習慣加油。"

    return {
        "min_price": str(min_p),
        "max_price": str(max_p),
        "median_price": str(med_p),
        "current_price": str(target),
        "percentile": percentile,
        "band": band,
        "is_cycle_low": is_low,
        "is_cycle_high": is_high,
        "advice": advice,
    }


def analyze_weekend_cycle(
    observations: list[dict],
    now: datetime | None = None,
) -> dict:
    """Analyze pre-weekend price hike risk and day-of-week patterns."""
    now = now or datetime.now(UTC)
    day_of_week = now.weekday()  # Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    current_day_name = day_names[day_of_week]

    # Pre-weekend window: Thursday (3) or Friday (4)
    is_pre_weekend = day_of_week in {3, 4}

    # Analyze short term trend from recent observations (last 7 days vs older)
    dated_obs = []
    for obs in observations:
        t_str = obs.get("reported_at") or obs.get("observed_at")
        price_val = obs.get("price")
        if not t_str or not price_val:
            continue
        try:
            dt = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
            p = Decimal(str(price_val))
            if p > 0:
                dated_obs.append((dt, p))
        except (ValueError, TypeError):
            continue

    dated_obs.sort(key=lambda x: x[0])

    trend: PriceTrend = "stable"
    if len(dated_obs) >= 3:
        half = len(dated_obs) // 2
        first_half = [p for _, p in dated_obs[:half]]
        second_half = [p for _, p in dated_obs[half:]]
        diff = Decimal(str(median(second_half))) - Decimal(str(median(first_half)))
        if diff >= Decimal("0.05"):
            trend = "rising"
        elif diff <= Decimal("-0.05"):
            trend = "falling"

    # Pre-weekend hike risk assessment
    cycle_risk = False
    risk_level: RiskLevel = "low"
    message = "油價目前處於平穩週期。"

    if is_pre_weekend:
        if trend == "rising":
            cycle_risk = True
            risk_level = "high"
            message = f"適逢 {current_day_name} 且油價呈上漲走勢，週末前調漲風險高，強烈建議今日加滿規避漲價。"
        elif trend == "stable":
            cycle_risk = True
            risk_level = "medium"
            message = f"適逢 {current_day_name} 週末用油高峰前夕，預期可能有週末例行調漲，建議提前加油避險。"
        else:
            cycle_risk = False
            risk_level = "low"
            message = f"適逢 {current_day_name}，但近期油價走勢微幅回落，可按需正常加油。"
    elif day_of_week in {0, 1}:
        risk_level = "low"
        message = f"{current_day_name} 通常為週初油價回檔平穩期，為正常用車加油時機。"
    else:
        risk_level = "low"
        message = "週中油價波動相對平緩，為常態加油時機。"

    return {
        "day_of_week": current_day_name,
        "is_pre_weekend": is_pre_weekend,
        "pre_weekend_hike_risk": cycle_risk,
        "risk_level": risk_level,
        "trend": trend,
        "message": message,
    }


def analyze_station_history(
    observations: list[dict],
    current_price: Decimal | None = None,
    now: datetime | None = None,
) -> dict:
    """Full 30-day price band and weekend cycle analysis for a station."""
    prices = []
    for obs in observations:
        p_val = obs.get("price")
        if p_val:
            try:
                p = Decimal(str(p_val))
                if p > 0:
                    prices.append(p)
            except (ValueError, TypeError):
                continue

    band = analyze_price_band(prices, current_price)
    cycle = analyze_weekend_cycle(observations, now)

    return {
        "price_band": band,
        "weekend_cycle": cycle,
        "observation_count": len(prices),
    }
