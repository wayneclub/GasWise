"""Waze venue details and source-declared weekly opening hours."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SERVICES = {
    "RESTROOMS": "Restrooms",
    "PARKING_FOR_CUSTOMERS": "Parking for customers",
    "CREDIT_CARDS": "Accepts credit cards",
    "WHEELCHAIR_ACCESSIBLE": "Wheelchair accessible",
    "AIR_CONDITIONING": "Air conditioning",
    "DELIVERIES": "Deliveries",
    "WIFI": "Wi-Fi",
    "DRIVE_THROUGH": "Drive-through",
}
DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def opening_status(hours, zone, now=None):
    if not hours:
        return None
    if all(any(h["is_24_hours"] and day in h["days"] for h in hours) for day in range(7)):
        return True
    if not zone:
        return None
    try:
        local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(zone))
        day = (local.weekday() + 1) % 7
        minute = local.hour * 60 + local.minute
        for h in hours:
            start, end = [
                sum(int(x) * factor for x, factor in zip(t.split(":"), [60, 1], strict=True))
                for t in [h["from"], h["to"]]
            ]
            if not (0 <= start < 1440 and 0 <= end <= 1440):
                return None
            if h["is_24_hours"] and day in h["days"]:
                return True
            if start < end and day in h["days"] and start <= minute < end:
                return True
            if start > end and (
                (day in h["days"] and minute >= start) or ((day - 1) % 7 in h["days"] and minute < end)
            ):
                return True
        return False
    except (ValueError, TypeError, ZoneInfoNotFoundError):
        return None
