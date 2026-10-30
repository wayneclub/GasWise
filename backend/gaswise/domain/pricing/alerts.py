"""Pure smart-alert policy. Private driving inputs never cross this interface."""

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

NeedState = Literal["not_due", "approaching", "due", "unknown"]
Confidence = Literal["high", "medium", "low"]
AlertAction = Literal["push", "inbox", "ignore"]


def purchase_condition_key(membership_required, octane, currency="USD", unit="US_gallon") -> str:
    """Canonical history/watch partition; callers must not reproduce this hash."""
    return hashlib.sha256(json.dumps({
        "membership_required": membership_required,
        "octane": octane,
        "currency": currency,
        "unit": unit,
    }, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class AlertSignal:
    change_per_gallon: Decimal
    expected_gallons: Decimal
    need: NeedState
    confidence: Confidence
    quote_age_minutes: int
    comparable_observations: int
    source_conflict: bool = False
    trend: str = "stable"  # "rising", "falling", "stable"
    cycle_risk: bool = False  # e.g. Pre-weekend price-hike surge risk
    is_cycle_low: bool = False  # Station is near its 30-day historical low


@dataclass(frozen=True)
class AlertDecision:
    action: AlertAction
    reason: str
    estimated_savings: Decimal


class SmartAlertPolicy:
    """Deep module: one deterministic decision interface hides alert gating."""

    def evaluate(self, signal: AlertSignal) -> AlertDecision:
        savings = max(Decimal("0"), -signal.change_per_gallon * signal.expected_gallons)
        if signal.source_conflict:
            return AlertDecision("ignore", "source_conflict", savings)
        if signal.quote_age_minutes > 24 * 60:
            return AlertDecision("ignore", "quote_too_old", savings)
        if signal.comparable_observations < 2:
            return AlertDecision("ignore", "insufficient_history", savings)

        # Realized price drop savings
        if signal.change_per_gallon < 0:
            if signal.need == "due" and signal.confidence in {"high", "medium"} and savings >= Decimal("1.00"):
                return AlertDecision("push", "due_and_material_savings", savings)
            if signal.need == "approaching" and signal.confidence != "low" and savings >= Decimal("1.50"):
                return AlertDecision("push", "approaching_and_strong_savings", savings)
            if savings >= Decimal("2.50"):
                return AlertDecision("push", "exceptional_savings", savings)
            if savings >= Decimal("0.75"):
                return AlertDecision("inbox", "useful_but_not_urgent", savings)

        # Proactive trend and price-hike hedge when price is flat or trending up (Phase 1)
        if signal.trend == "rising" or signal.cycle_risk:
            hedge_savings = max(Decimal("0.50"), signal.expected_gallons * Decimal("0.15"))
            if signal.need == "due" and signal.confidence in {"high", "medium"}:
                return AlertDecision("push", "pre_hike_hedge_due", hedge_savings)
            if signal.need == "approaching" and signal.confidence != "low":
                return AlertDecision("push", "pre_hike_hedge_approaching", hedge_savings)
            return AlertDecision("inbox", "pre_hike_warning", hedge_savings)

        if signal.is_cycle_low and signal.need in {"due", "approaching"}:
            hedge_savings = max(Decimal("1.00"), signal.expected_gallons * Decimal("0.20"))
            return AlertDecision("push", "cycle_low_opportunity", hedge_savings)

        if signal.change_per_gallon >= 0:
            return AlertDecision("ignore", "no_savings", savings)
        return AlertDecision("ignore", "below_material_threshold", savings)
