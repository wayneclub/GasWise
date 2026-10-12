"""Query Waze gas stations over HTTP using an existing, authorized session UID."""

import argparse
import base64
import json
import os
import struct
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from gaswise.domain.pricing.grades import california_region, infer_octane
from gaswise.providers.waze.details import DAY_NAMES, SERVICES, opening_status

ENDPOINT = "https://rt-xlb-am.waze.com/rtserver/distrib/command"
DEFAULT_SESSION = Path.home() / ".config/gaswise/waze-http-session.json"
DEFAULT_LOGIN = Path.home() / ".config/gaswise/waze-http-login.bin"


def varint(value):
    value &= (1 << 64) - 1
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def number(field, value):
    return varint(field << 3) + varint(value)


def message(field, value):
    return varint((field << 3) | 2) + varint(len(value)) + value


def decode(data):
    result = {}
    offset = 0

    def read_varint():
        nonlocal offset
        value = shift = 0
        while offset < len(data) and shift < 70:
            byte = data[offset]
            offset += 1
            value |= (byte & 127) << shift
            if byte < 128:
                return value
            shift += 7
        raise ValueError("Invalid Protobuf varint")

    while offset < len(data):
        tag = read_varint()
        field, wire = tag >> 3, tag & 7
        if not field:
            raise ValueError("Invalid Protobuf field")
        if wire == 0:
            value = read_varint()
        elif wire == 2:
            length = read_varint()
            if length > len(data) - offset:
                raise ValueError("Truncated Protobuf message")
            value = data[offset : offset + length]
            offset += length
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            if size > len(data) - offset:
                raise ValueError("Truncated Protobuf scalar")
            value = struct.unpack("<d" if wire == 1 else "<f", data[offset : offset + size])[0]
            offset += size
        else:
            raise ValueError(f"Unsupported Protobuf wire type {wire}")
        result.setdefault(field, []).append(value)
    return result


def first(fields, field, default=None):
    return fields.get(field, [default])[0]


def text(fields, field):
    value = first(fields, field, b"")
    return value.decode("utf-8", errors="replace")


def search_body(lat, lon, radius, limit, venue_id=None):
    coordinate = number(101, round(lon * 1_000_000))
    coordinate += number(102, round(lat * 1_000_000))
    if venue_id:
        location = message(1, coordinate) + message(2, venue_id.encode())
        area = message(7, location)
    else:
        area = message(2, coordinate) + number(4, radius)
    filters = message(2, b"gas_station")
    search = message(1, area) + message(2, filters) + number(5, limit)
    envelope = message(1001, message(2741, search))
    return b"ProtoBase64," + base64.b64encode(envelope) + b"\n"


def parse_stations(payload):
    stations = []
    for envelope in decode(payload).get(1001, []):
        commands = decode(envelope)
        for error in commands.get(2003, []):
            fields = decode(error)
            raise RuntimeError("Waze rejected request: " + text(fields, 10102))
        for response in commands.get(2742, []):
            for result in decode(response).get(1, []):
                venue_data = first(decode(result), 1)
                if venue_data is None:
                    continue
                venue = decode(venue_data)
                location = decode(first(venue, 109, b""))
                brand = text(venue, 125) or text(venue, 104)
                service_ids = [v.decode("utf-8", errors="replace") for v in venue.get(110, [])]
                hours = []
                for raw_hours in venue.get(132, []):
                    h = decode(raw_hours)
                    days = [d for d in h.get(803, []) if isinstance(d, int) and 0 <= d <= 6]
                    start, end = text(h, 801), text(h, 802)
                    hours.append(
                        {
                            "days": days,
                            "day_names": [DAY_NAMES[d] for d in days],
                            "from": start,
                            "to": end,
                            "is_24_hours": start == end == "00:00",
                        }
                    )
                zone = text(venue, 176) or None
                zone_basis = "source" if zone else None
                if not zone and california_region(text(venue, 117), text(venue, 116), text(venue, 119)):
                    zone, zone_basis = "America/Los_Angeles", "california_region"
                google = decode(first(venue, 174, b""))
                rating = decode(first(google, 2, b""))
                business_status = {1: "operational", 2: "temporarily_closed", 3: "permanently_closed"}.get(
                    first(google, 3)
                )
                open_now = opening_status(hours, zone)
                if business_status in {"temporarily_closed", "permanently_closed"}:
                    open_now = False
                elif first(google, 5) is not None:
                    open_now = None  # Exceptional hours cannot be derived from the weekly schedule.
                details = {
                    "brand": brand,
                    "phone": text(venue, 120) or None,
                    "website": text(venue, 124) or None,
                    "description": text(venue, 106) or None,
                    "services": [{"id": v, "label": SERVICES.get(v, v)} for v in service_ids],
                    "accepts_credit_cards": True if "CREDIT_CARDS" in service_ids else None,
                    "opening_hours": hours,
                    "timezone": zone,
                    "timezone_basis": zone_basis,
                    "open_now": open_now,
                    "google_attributes": {
                        "rating": round(first(rating, 1), 2) if first(rating, 1) is not None else None,
                        "ratings_count": first(rating, 2),
                        "business_status": business_status,
                        "price_level": first(google, 1),
                        "price_level_symbol": text(google, 6) or None,
                        "exceptional_hour_days": google.get(5, []),
                        "source": "google_via_waze",
                    },
                    "opening_status_checked_at": datetime.now(timezone.utc).isoformat(),
                    "source": "waze",
                }
                prices = []
                for product in venue.get(150, []):
                    fields = decode(product)
                    timestamp = first(fields, 2)
                    prices.append(
                        {
                            "fuel_type": text(fields, 1),
                            "price": round(first(fields, 4), 3) if 4 in fields else None,
                            "updated_at": datetime.fromtimestamp(timestamp / 1000, timezone.utc).isoformat()
                            if timestamp
                            else None,
                            "updated_by": text(fields, 3),
                            "payment_type": "unknown",
                            "octane": None,
                            "octane_inference": infer_octane(
                                brand, text(venue, 117), text(venue, 116), text(venue, 119), text(fields, 1)
                            ),
                        }
                    )
                stations.append(
                    {
                        "venue_id": text(venue, 152),
                        "name": text(venue, 104),
                        "house_number": text(venue, 113),
                        "street": text(venue, 114),
                        "city": text(venue, 115),
                        "state": text(venue, 116),
                        "country": text(venue, 117),
                        "postal_code": text(venue, 119),
                        "latitude": first(location, 301),
                        "longitude": first(location, 300),
                        "currency": text(venue, 149),
                        "prices": prices,
                        "details": details,
                    }
                )
    return stations


def query(lat, lon, radius, limit, session, venue_id=None):
    uid = os.environ.get("WAZE_UID") or session.get("uid")
    if not uid:
        raise RuntimeError("A valid authorized Waze UID is required")
    headers = {
        "User-Agent": session.get("user_agent", "5.24.90.901"),
        "Content-Type": "binary/octet-stream",
        "UID": uid,
        "X-Waze-Network-Version": "3",
        "X-Waze-Wait-Timeout": "10500",
    }
    request = Request(
        ENDPOINT, data=search_body(lat, lon, radius, limit, venue_id), headers=headers, method="POST"
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read()
            content_type = response.headers.get("Content-Type", "")
    except HTTPError as error:
        raise RuntimeError(f"Waze HTTP {error.code}; request was not retried") from None
    if "protobuf" not in content_type:
        raise RuntimeError("Unexpected Waze response content type")
    return parse_stations(payload)


def login(login_file, session_file):
    """Use the owner's captured normal login request; never fabricate credentials."""
    if not login_file.exists():
        raise RuntimeError("No authorized login request is configured")
    headers_file = login_file.with_name("waze-http-login-headers.json")
    headers = (
        json.loads(headers_file.read_text())
        if headers_file.exists()
        else {
            "User-Agent": "5.24.90.901",
            "Content-Type": "binary/octet-stream",
            "X-Waze-Network-Version": "3",
            "X-Waze-Wait-Timeout": "10500",
        }
    )
    request = Request(
        ENDPOINT.replace("/command", "/login"), data=login_file.read_bytes(), headers=headers, method="POST"
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read()
    except HTTPError as error:
        raise RuntimeError(f"Waze login HTTP {error.code}; no retry performed") from None
    for envelope in decode(payload).get(1001, []):
        for result in decode(envelope).get(2745, []):
            fields = decode(result)
            if 2 in fields:
                error = decode(first(fields, 2))
                if first(error, 2) == 2 and 5 in error:
                    issue = decode(first(error, 5))
                    if first(issue, 1) == 6:
                        raise RuntimeError("Waze login RATE_LIMIT_FAILURE; no retry performed")
                raise RuntimeError(f"Waze login rejected (error type {first(error, 2)}); no retry performed")
            if 1 in fields:
                success = decode(first(fields, 1))
                if 1 not in success or 3 not in success:
                    raise RuntimeError("Waze login response missing session fields")
                uid = base64.b64encode(number(1, first(success, 1)) + message(2, first(success, 3))).decode()
                session = {"uid": uid, "user_agent": "5.24.90.901"}
                session_file.parent.mkdir(parents=True, exist_ok=True)
                fd = os.open(session_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w") as stream:
                    json.dump(session, stream)
                os.chmod(session_file, 0o600)
                return session
    raise RuntimeError("Waze login did not return a session")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--radius", type=int, default=5000)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--venue-id")
    parser.add_argument("--session-file", type=Path, default=DEFAULT_SESSION)
    parser.add_argument("--login", action="store_true", help="Perform one normal HTTP login before querying")
    parser.add_argument("--login-file", type=Path, default=DEFAULT_LOGIN)
    args = parser.parse_args()
    if not (-90 <= args.lat <= 90 and -180 <= args.lon <= 180):
        parser.error("Coordinates out of range")
    if not (1 <= args.limit <= 20 and 1 <= args.radius <= 50000):
        parser.error("Limit must be 1–20; radius must be 1–50000 meters")
    session = json.loads(args.session_file.read_text()) if args.session_file.exists() else {}
    try:
        if args.login:
            session = login(args.login_file, args.session_file)
        stations = query(args.lat, args.lon, args.radius, args.limit, session, args.venue_id)
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from None
    print(
        json.dumps(
            {
                "source": "waze_http",
                "queried_at": datetime.now(timezone.utc).isoformat(),
                "latitude": args.lat,
                "longitude": args.lon,
                "stations": stations,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
