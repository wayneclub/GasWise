"""One interface for the complete installation and push-delivery lifecycle."""

import asyncio
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from gaswise.domain.pricing.alerts import AlertSignal, SmartAlertPolicy, purchase_condition_key
from gaswise.providers.notifications.webpush import PushDeliveryError, PushEndpointGone


class AlertAuthorizationError(Exception):
    pass


class AlertWatchLimitError(Exception):
    pass


class SmartAlerts:
    def __init__(self, store, cipher, sender, public_key: str, policy=None):
        self.store, self.cipher, self.sender, self.public_key = store, cipher, sender, public_key
        self.policy = policy or SmartAlertPolicy()

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    async def create(self, subscription: dict, timezone: str, locale: str) -> dict:
        installation_id = secrets.token_urlsafe(24)
        token = secrets.token_urlsafe(32)
        endpoint_hash = self._hash(subscription["endpoint"])
        encrypted = self.cipher.encrypt(subscription)
        installation_id = await self.store.create_alert_installation(
            installation_id, self._hash(token), endpoint_hash, encrypted, timezone, locale
        )
        return {"installation_id": installation_id, "installation_token": token}

    async def update_need(self, installation_id, token, state, confidence, ttl_hours):
        expires = datetime.now(UTC) + timedelta(hours=ttl_hours)
        if not await self.store.update_alert_need(
            installation_id, self._hash(token), state, confidence, expires
        ):
            raise AlertAuthorizationError

    async def queue_test(self, installation_id, token, locale):
        if not await self.store.queue_alert_test(installation_id, self._hash(token), locale):
            raise AlertAuthorizationError

    async def disable(self, installation_id, token):
        if not await self.store.disable_alert_installation(installation_id, self._hash(token)):
            raise AlertAuthorizationError

    async def update_watch(self, body):
        condition = purchase_condition_key(
            body["membership_required"], body["octane"], body["currency"], body["unit"]
        )
        valid = await self.store.set_alert_watch(
            body["installation_id"], self._hash(body["installation_token"]), body["enabled"],
            body["canonical_id"], body["source"], body["station_id"], body["station_name"],
            body["fuel_type"], body["payment_type"], condition,
            body["expected_gallons"], body["threshold_cents"],
        )
        if valid == "limit":
            raise AlertWatchLimitError
        if not valid:
            raise AlertAuthorizationError

    async def inbox(self, installation_id, token):
        result = await self.store.alert_inbox(installation_id, self._hash(token))
        if result is None:
            raise AlertAuthorizationError
        return result

    async def evaluate_step(self):
        owner = secrets.token_hex(16)
        candidate = await self.store.claim_alert_candidate(owner)
        if candidate is None:
            return False
        try:
            change = Decimal(str(candidate["current_price"])) - Decimal(str(candidate["previous_price"]))
            threshold = Decimal(candidate["threshold_cents"]) / 100
            trend = candidate.get("trend", "stable")
            cycle_risk = bool(candidate.get("cycle_risk", False))
            is_cycle_low = bool(candidate.get("is_cycle_low", False))

            if change > -threshold and not (trend == "rising" or cycle_risk or is_cycle_low):
                await self.store.finish_alert_candidate(candidate["watch_id"], owner,
                                                        candidate["observation_key"], None, "ignore")
                return True
            decision = self.policy.evaluate(AlertSignal(
                change, Decimal(str(candidate["expected_gallons"])), candidate["need_state"],
                candidate["need_confidence"], candidate["quote_age_minutes"],
                candidate["comparable_observations"], candidate["source_conflict"],
                trend=trend, cycle_risk=cycle_risk, is_cycle_low=is_cycle_low,
            ))
            payload = self._opportunity_payload(candidate, decision) if decision.action != "ignore" else None
            await self.store.finish_alert_candidate(candidate["watch_id"], owner,
                                                    candidate["observation_key"], payload, decision.action)
        except Exception:
            await self.store.release_alert_candidate(candidate["watch_id"], owner)
            raise
        return True

    @staticmethod
    def _opportunity_payload(candidate, decision):
        locale = candidate["locale"]
        is_hike = decision.reason in {"pre_hike_hedge_due", "pre_hike_hedge_approaching", "pre_hike_warning"}
        is_low = decision.reason == "cycle_low_opportunity"

        if is_hike:
            if locale == "zh-TW":
                title = f'⚠️ {candidate["station_name"]} 預期將調漲，建議提前加油'
                body = f'油價呈現上漲趨勢或適逢週末調漲期，目前每加侖 ${Decimal(str(candidate["current_price"])):.2f}，提前加滿可規避後續漲幅（預估省 ${decision.estimated_savings:.2f}）。'
            elif locale == "zh-CN":
                title = f'⚠️ {candidate["station_name"]} 预期将调涨，建议提前加油'
                body = f'油价呈现上涨趋势或适逢周末调涨期，目前每加仑 ${Decimal(str(candidate["current_price"])):.2f}，提前加满可规避后续涨幅（预估省 ${decision.estimated_savings:.2f}）。'
            else:
                title = f'⚠️ {candidate["station_name"]} price hike risk: refuel advised'
                body = f'Prices are trending up before the weekend. Refuel now at ${Decimal(str(candidate["current_price"])):.2f}/gal to hedge against hikes (estimated savings ${decision.estimated_savings:.2f}).'
        elif is_low:
            if locale == "zh-TW":
                title = f'✨ {candidate["station_name"]} 來到近期低點'
                body = f'目前每加侖 ${Decimal(str(candidate["current_price"])):.2f}，處於近期低位，建議把握時機加油（預估省 ${decision.estimated_savings:.2f}）。'
            elif locale == "zh-CN":
                title = f'✨ {candidate["station_name"]} 处于近期低点'
                body = f'目前每加仑 ${Decimal(str(candidate["current_price"])):.2f}，处于近期低位，建议把握时机加油（预估省 ${decision.estimated_savings:.2f}）。'
            else:
                title = f'✨ {candidate["station_name"]} is near 30-day low'
                body = f'Currently ${Decimal(str(candidate["current_price"])):.2f}/gal. Great timing to refuel (estimated savings ${decision.estimated_savings:.2f}).'
        else:
            drop = abs(Decimal(str(candidate["current_price"])) - Decimal(str(candidate["previous_price"])))
            if locale == "zh-TW":
                title = f'{candidate["station_name"]} 降價 {drop:.2f} 美元'
                body = f'目前每加侖 ${Decimal(str(candidate["current_price"])):.2f}，預估這次可省 ${decision.estimated_savings:.2f}。'
            elif locale == "zh-CN":
                title = f'{candidate["station_name"]} 降价 {drop:.2f} 美元'
                body = f'目前每加仑 ${Decimal(str(candidate["current_price"])):.2f}，预计本次可省 ${decision.estimated_savings:.2f}。'
            else:
                title = f'{candidate["station_name"]} dropped ${drop:.2f}/gal'
                body = f'Now ${Decimal(str(candidate["current_price"])):.2f}/gal; estimated savings ${decision.estimated_savings:.2f}.'
        return {"title": title, "body": body, "url": "/?smart-alert=opportunity",
                "tag": f'gaswise-watch-{candidate["watch_id"]}'}

    async def step(self):
        notice = await self.store.claim_alert_notice(secrets.token_hex(16))
        if notice is None:
            return False
        try:
            subscription = self.cipher.decrypt(bytes(notice["subscription_ciphertext"]))
            payload = notice["payload"]
            if isinstance(payload, str):
                import json
                payload = json.loads(payload)
            await self.sender.send(subscription, dict(payload))
        except PushEndpointGone:
            await self.store.finish_alert_notice(notice["id"], notice["lease_owner"], permanent=True)
        except (PushDeliveryError, ValueError, KeyError):
            await self.store.finish_alert_notice(notice["id"], notice["lease_owner"], retry=True)
        else:
            await self.store.finish_alert_notice(notice["id"], notice["lease_owner"])
        return True

    async def run(self):
        while True:
            try:
                worked = await self.evaluate_step() or await self.step()
            except Exception:
                worked = False
            await asyncio.sleep(1 if worked else 15)
