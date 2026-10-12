"""Opt-in HTTP adapter for Waze's undocumented US fuel protocol."""

import asyncio
import base64
import json
import math
import os
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx

from gaswise.contracts.common import Point, Station
from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.identity import membership_for_name
from gaswise.providers.waze.protocol import (
    ENDPOINT,
    decode,
    first,
    message,
    number,
    parse_stations,
    search_body,
)


class WazeProvider:
    def __init__(self, client, session_file, login_file, auto_login=True):
        self.client = client
        self.session_file, self.login_file = Path(session_file), Path(login_file)
        self.auto_login = auto_login
        self.lock = asyncio.Lock()
        self.blocked_until = 0

    def session(self):
        try:
            value = json.loads(self.session_file.read_text())
            if not isinstance(value.get("uid"), str) or not value["uid"]:
                raise ValueError
            return value
        except (OSError, ValueError, AttributeError):
            return {}

    async def request(self, endpoint, body, headers):
        if time.monotonic() < self.blocked_until:
            raise ProviderError("waze_rate_limited")
        try:
            response = await self.client.post(endpoint, content=body, headers=headers, timeout=20)
        except httpx.RequestError:
            raise ProviderError("waze_upstream_unavailable") from None
        if response.status_code == 429:
            self.blocked_until = time.monotonic() + 120
            raise ProviderError("waze_rate_limited")
        if not response.is_success:
            raise ProviderError("waze_upstream_rejected_request")
        if "protobuf" not in response.headers.get("content-type", ""):
            raise ProviderError("waze_invalid_response")
        return response.content

    async def login(self):
        if not self.auto_login:
            raise ProviderError("waze_reauthentication_required")
        try:
            body = self.login_file.read_bytes()
            header_file = self.login_file.with_name("waze-http-login-headers.json")
            headers = json.loads(header_file.read_text()) if header_file.exists() else {}
        except (OSError, ValueError):
            raise ProviderError("waze_login_not_configured") from None
        # Use only functional headers from the owner's normal authorized login.
        headers = {
            k: v
            for k, v in headers.items()
            if k.lower()
            in {
                "user-agent",
                "content-type",
                "sequence-number",
                "x-waze-network-version",
                "x-waze-wait-timeout",
                "cache-control",
            }
        }
        headers.setdefault("User-Agent", "5.24.90.901")
        headers.setdefault("Content-Type", "binary/octet-stream")
        headers.setdefault("X-Waze-Network-Version", "3")
        payload = await self.request(ENDPOINT.replace("/command", "/login"), body, headers)
        try:
            for envelope in decode(payload).get(1001, []):
                for result in decode(envelope).get(2745, []):
                    fields = decode(result)
                    if 2 in fields:
                        error = decode(first(fields, 2))
                        if first(error, 2) == 2 and 5 in error:
                            issue = decode(first(error, 5))
                            if first(issue, 1) == 6:
                                self.blocked_until = time.monotonic() + 120
                                raise ProviderError("waze_rate_limited")
                        raise ProviderError("waze_reauthentication_required")
                    if 1 in fields:
                        success = decode(first(fields, 1))
                        uid = base64.b64encode(number(1, success[1][0]) + message(2, success[3][0])).decode()
                        session = {"uid": uid, "user_agent": "5.24.90.901"}
                        self.save_session(session)
                        return session
        except (ValueError, KeyError, TypeError, IndexError):
            raise ProviderError("waze_invalid_response") from None
        raise ProviderError("waze_invalid_response")

    def save_session(self, session):
        # Atomic replace prevents partial credentials after a crash.
        temp = self.session_file.with_name(self.session_file.name + ".tmp")
        try:
            self.session_file.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            os.chmod(temp, 0o600)
            with os.fdopen(fd, "w") as stream:
                json.dump(session, stream)
            os.replace(temp, self.session_file)
        except OSError:
            raise ProviderError("waze_session_storage_unavailable") from None

    async def prices(self, query):
        async with self.lock:
            session = self.session()
            if not session:
                session = await self.login()
            for attempt in range(2):
                headers = {
                    "User-Agent": session.get("user_agent", "5.24.90.901"),
                    "Content-Type": "binary/octet-stream",
                    "UID": session["uid"],
                    "X-Waze-Network-Version": "3",
                    "X-Waze-Wait-Timeout": "10500",
                }
                body = search_body(
                    query.origin.lat,
                    query.origin.lng,
                    int(query.radius_meters),
                    query.max_results,
                    getattr(query, "venue_id", None),
                )
                payload = await self.request(ENDPOINT, body, headers)
                try:
                    rows = parse_stations(payload)
                    postal_code = getattr(query, "postal_code", None)
                    return [
                        row
                        for row in rows
                        if row["country"] == "US"
                        and (not postal_code or row["postal_code"][:5] == postal_code)
                    ]
                except RuntimeError as error:
                    # Only an explicit expired session can cause one login + retry.
                    if "Client should relogin" in str(error) or "UID expected" in str(error):
                        if attempt == 0:
                            session = await self.login()
                            continue
                        raise ProviderError("waze_reauthentication_required") from None
                    raise ProviderError("waze_upstream_rejected_request") from None
                except (ValueError, TypeError, KeyError, OverflowError, OSError):
                    raise ProviderError("waze_invalid_response") from None

    async def stations(self, query):
        rows = await self.prices(query)
        stations = []
        try:
            for row in rows:
                if row["currency"] not in ("$", "USD"):
                    continue
                info = row["details"].get("google_attributes", {})
                rating = info.get("rating")
                count = info.get("ratings_count")
                rating = rating if type(rating) in (float, int) and math.isfinite(rating) and 0 <= rating <= 5 else None
                count = count if type(count) is int and count >= 0 else None
                for price in row["prices"]:
                    if price["fuel_type"] != "gas_" + query.fuel_type or not price["price"]:
                        continue
                    if price["price"] <= 0:
                        continue
                    stations.append(
                        Station(
                            id=row["venue_id"],
                            name=row["name"],
                            details=row["details"],
                            rating=rating,
                            review_count=count,
                            rating_source="Google via Waze" if rating is not None else None,
                            octane_inference=price["octane_inference"],
                            location=Point(lat=row["latitude"], lng=row["longitude"]),
                            address=" ".join(
                                x
                                for x in [
                                    row["house_number"],
                                    row["street"],
                                    row["city"],
                                    row["state"],
                                    row["postal_code"],
                                ]
                                if x
                            ),
                            price_per_gallon=Decimal(str(price["price"])),
                            fuel_type=query.fuel_type,
                            price_updated_at=price["updated_at"],
                            fetched_at=datetime.now(UTC),
                            source="waze",
                            payment_type="unknown",
                            octane=None,
                            attribution=["Waze"],
                            membership_required=membership_for_name(row["name"]),
                            open_now=row["details"].get("open_now"),
                            business_status=row["details"]
                            .get("google_attributes", {})
                            .get("business_status"),
                        )
                    )
        except (ValueError, TypeError, KeyError):
            raise ProviderError("waze_invalid_response") from None
        return stations
