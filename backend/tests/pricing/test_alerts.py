from decimal import Decimal

from gaswise.domain.pricing.alerts import AlertSignal, SmartAlertPolicy


def signal(**changes):
    values = dict(change_per_gallon=Decimal("-0.12"), expected_gallons=Decimal("10"),
                  need="due", confidence="medium", quote_age_minutes=30,
                  comparable_observations=3, source_conflict=False)
    values.update(changes)
    return AlertSignal(**values)


def test_due_material_drop_pushes_with_explainable_savings():
    decision = SmartAlertPolicy().evaluate(signal())
    assert decision.action == "push"
    assert decision.reason == "due_and_material_savings"
    assert decision.estimated_savings == Decimal("1.20")


def test_low_confidence_need_never_creates_urgency():
    decision = SmartAlertPolicy().evaluate(signal(confidence="low"))
    assert decision.action == "inbox"
    assert decision.reason == "useful_but_not_urgent"


def test_conflict_stale_and_thin_history_are_hard_gates():
    policy = SmartAlertPolicy()
    assert policy.evaluate(signal(source_conflict=True)).reason == "source_conflict"
    assert policy.evaluate(signal(quote_age_minutes=1441)).reason == "quote_too_old"
    assert policy.evaluate(signal(comparable_observations=1)).reason == "insufficient_history"


def test_unknown_need_only_pushes_for_exceptional_savings():
    policy = SmartAlertPolicy()
    ordinary = policy.evaluate(signal(need="unknown", confidence="low"))
    exceptional = policy.evaluate(signal(need="unknown", confidence="low", change_per_gallon=Decimal("-0.30")))
    assert ordinary.action == "inbox"
    assert exceptional.action == "push"
    assert exceptional.reason == "exceptional_savings"


def test_rising_trend_or_cycle_risk_triggers_pre_hike_hedge():
    policy = SmartAlertPolicy()
    # When price is flat but trend is rising and user is due
    flat_rising = policy.evaluate(signal(change_per_gallon=Decimal("0.00"), trend="rising", need="due", confidence="high"))
    assert flat_rising.action == "push"
    assert flat_rising.reason == "pre_hike_hedge_due"
    assert flat_rising.estimated_savings > Decimal("0")

    # When cycle risk is present and user is approaching
    cycle_risk = policy.evaluate(signal(change_per_gallon=Decimal("0.02"), cycle_risk=True, need="approaching", confidence="medium"))
    assert cycle_risk.action == "push"
    assert cycle_risk.reason == "pre_hike_hedge_approaching"

    # Cycle low opportunity
    cycle_low = policy.evaluate(signal(change_per_gallon=Decimal("0.00"), is_cycle_low=True, need="due", confidence="medium"))
    assert cycle_low.action == "push"
    assert cycle_low.reason == "cycle_low_opportunity"
