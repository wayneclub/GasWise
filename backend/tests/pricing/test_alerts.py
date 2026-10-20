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
