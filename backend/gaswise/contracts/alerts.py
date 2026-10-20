from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, HttpUrl, field_validator

from gaswise.contracts.common import Model


class PushKeys(Model):
    p256dh: str = Field(min_length=20, max_length=256)
    auth: str = Field(min_length=8, max_length=128)


class PushSubscription(Model):
    endpoint: HttpUrl
    keys: PushKeys

    @field_validator("endpoint")
    @classmethod
    def https_endpoint(cls, value):
        if value.scheme != "https" or value.username or value.password:
            raise ValueError("Push endpoint must be credential-free HTTPS")
        try:
            # Browser push services use DNS hosts. Rejecting IP literals closes the
            # direct private-network SSRF path; the sender also checks resolved IPs.
            import ipaddress
            ipaddress.ip_address(value.host)
        except ValueError:
            return value
        raise ValueError("Push endpoint must use a DNS host")


class AlertConfig(Model):
    enabled: bool
    vapid_public_key: str | None = None


class InstallationCreate(Model):
    subscription: PushSubscription
    timezone: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_+\-/]+$")
    locale: Literal["en", "zh-TW", "zh-CN", "es", "ja", "ko"] = "en"

    @field_validator("timezone")
    @classmethod
    def real_timezone(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError("Unknown timezone") from None
        return value


class InstallationCreated(Model):
    installation_id: str
    installation_token: str


class InstallationAuth(Model):
    installation_id: str = Field(min_length=20, max_length=100)
    installation_token: str = Field(min_length=32, max_length=200)


class NeedStateUpdate(InstallationAuth):
    state: Literal["not_due", "approaching", "due", "unknown"]
    confidence: Literal["high", "medium", "low"]
    ttl_hours: int = Field(default=48, ge=1, le=168)


class AlertTestRequest(InstallationAuth):
    locale: Literal["en", "zh-TW", "zh-CN", "es", "ja", "ko"] = "en"


class AlertStatus(Model):
    status: Literal["updated", "queued", "disabled"]


class WatchUpdate(InstallationAuth):
    enabled: bool = True
    canonical_id: str | None = Field(default=None, min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=100)
    station_id: str = Field(min_length=1, max_length=200)
    station_name: str = Field(min_length=1, max_length=200)
    fuel_type: Literal["regular", "midgrade", "premium", "diesel"]
    payment_type: Literal["cash", "credit", "unknown"]
    membership_required: str | None = Field(default=None, max_length=100)
    octane: int | None = Field(default=None, ge=80, le=100)
    currency: Literal["USD"] = "USD"
    unit: Literal["US_gallon"] = "US_gallon"
    expected_gallons: int = Field(default=10, ge=1, le=30)
    threshold_cents: int = Field(default=10, ge=5, le=100)


class WatchResult(Model):
    status: Literal["watched", "removed"]


class InboxItem(Model):
    id: int
    title: str
    body: str
    created_at: str


class InboxResult(Model):
    items: list[InboxItem] = Field(max_length=20)
