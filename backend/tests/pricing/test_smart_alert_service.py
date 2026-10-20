import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gaswise.providers.notifications.webpush import PushSubscriptionCipher
from gaswise.services.pricing.alerts import AlertAuthorizationError, SmartAlerts


def cipher():
    return PushSubscriptionCipher(base64.urlsafe_b64encode(b"a" * 32).decode().rstrip("="))


def subscription():
    return {"endpoint": "https://push.example.test/message/one",
            "keys": {"p256dh": "public-key", "auth": "auth-secret"}}


def test_subscription_cipher_is_randomized_authenticated_encryption():
    codec = cipher()
    first = codec.encrypt(subscription())
    second = codec.encrypt(subscription())
    assert first != second
    assert codec.decrypt(first) == subscription()
    tampered = bytearray(first)
    tampered[-1] ^= 1
    with pytest.raises(Exception):
        codec.decrypt(bytes(tampered))


@pytest.mark.asyncio
async def test_create_returns_rotated_secret_and_store_selected_id():
    store = SimpleNamespace(create_alert_installation=AsyncMock(return_value="existing-installation"))
    alerts = SmartAlerts(store, cipher(), AsyncMock(), "public")
    created = await alerts.create(subscription(), "America/Los_Angeles", "en")
    assert created["installation_id"] == "existing-installation"
    assert len(created["installation_token"]) >= 40
    args = store.create_alert_installation.await_args.args
    assert args[1] != created["installation_token"]
    assert b"push.example.test" not in args[3]
    assert args[5] == "en"


@pytest.mark.asyncio
async def test_invalid_installation_is_indistinguishable():
    store = SimpleNamespace(update_alert_need=AsyncMock(return_value=False))
    alerts = SmartAlerts(store, cipher(), AsyncMock(), "public")
    with pytest.raises(AlertAuthorizationError):
        await alerts.update_need("unknown", "wrong-token", "due", "high", 24)


@pytest.mark.asyncio
async def test_watch_candidate_crosses_single_policy_seam_and_queues_push():
    candidate = dict(watch_id=7, observation_key="new-observation", current_price="4.10",
                     previous_price="4.30", threshold_cents=10, expected_gallons="10",
                     need_state="due", need_confidence="high", quote_age_minutes=20,
                     comparable_observations=4, source_conflict=False, locale="en",
                     station_name="Example Fuel")
    store = SimpleNamespace(claim_alert_candidate=AsyncMock(return_value=candidate),
                            finish_alert_candidate=AsyncMock(), release_alert_candidate=AsyncMock())
    alerts = SmartAlerts(store, cipher(), AsyncMock(), "public")
    assert await alerts.evaluate_step() is True
    payload = store.finish_alert_candidate.await_args.args[3]
    assert payload["title"] == "Example Fuel dropped $0.20/gal"
    assert "estimated savings $2.00" in payload["body"]
    assert store.finish_alert_candidate.await_args.args[4] == "push"
    store.release_alert_candidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_watch_threshold_and_source_conflict_suppress_push():
    base = dict(watch_id=7, observation_key="new", current_price="4.21", previous_price="4.30",
                threshold_cents=10, expected_gallons="10", need_state="due", need_confidence="high",
                quote_age_minutes=10, comparable_observations=3, source_conflict=False,
                locale="en", station_name="Example Fuel")
    store = SimpleNamespace(claim_alert_candidate=AsyncMock(return_value=base),
                            finish_alert_candidate=AsyncMock(), release_alert_candidate=AsyncMock())
    alerts = SmartAlerts(store, cipher(), AsyncMock(), "public")
    await alerts.evaluate_step()
    assert store.finish_alert_candidate.await_args.args[3] is None
    store.claim_alert_candidate = AsyncMock(return_value={**base, "current_price": "4.10", "source_conflict": True})
    await alerts.evaluate_step()
    assert store.finish_alert_candidate.await_args.args[3] is None
