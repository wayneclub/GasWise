from datetime import UTC, datetime, timedelta

from gaswise.domain.pricing.daily_ramp import reviewed_limit


def state(**overrides):
    now = datetime(2026, 10, 15, tzinfo=UTC)
    return {"clock": now, "adaptive_daily_limit": 80, "adaptive_daily_max": 800,
            "daily_review_at": now-timedelta(days=1), "daily_review_requests": 80,
            "last_rejection_at": None, "last_collection_failure_at": None,
            "background_last_request_at": now-timedelta(hours=1), **overrides}


def test_clean_saturated_day_advances_one_stage_and_respects_ceiling():
    assert reviewed_limit(state()) == 160
    assert reviewed_limit(state(adaptive_daily_limit=640, daily_review_requests=640)) == 800
    assert reviewed_limit(state(adaptive_daily_limit=800, daily_review_requests=800)) == 800


def test_underused_idle_and_failed_sources_do_not_increase():
    assert reviewed_limit(state(daily_review_requests=59)) == 80
    assert reviewed_limit(state(background_last_request_at=state()["clock"]-timedelta(days=3))) == 80
    assert reviewed_limit(state(last_rejection_at=state()["clock"]-timedelta(hours=1))) == 80
    assert reviewed_limit(state(last_collection_failure_at=state()["clock"]-timedelta(hours=1))) == 80


def test_review_waits_a_full_day_and_disabled_policy_does_nothing():
    assert reviewed_limit(state(daily_review_at=state()["clock"]-timedelta(hours=23))) is None
    assert reviewed_limit(state(adaptive_daily_limit=None)) is None
    assert reviewed_limit(state(daily_review_requests=60)) == 160
