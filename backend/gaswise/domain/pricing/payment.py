"""Explainable payment evidence, not calibrated probabilities or pump verification."""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from statistics import median

from gaswise.contracts.common import Station


def source_family(source):
    # Maps and Waze may share OPIS. Never count them as independent confirmation.
    if source in {"gasbuddy", "gasbuddy_web"}:
        return "gasbuddy"
    return "maps_waze_feed" if source in {"google_maps_web", "google_places", "waze"} else source


def payment_price_match(station: Station, peer: Station) -> bool:
    """A rounded Maps quote is compatible evidence, never a recovered pump price."""
    if station.source in {"google_maps_web", "google_places"}:
        price = station.price_per_gallon
        if price == price.quantize(Decimal("0.01")):
            return peer.price_per_gallon.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) == price
        return peer.price_per_gallon == price
    return abs(peer.price_per_gallon-station.price_per_gallon) < Decimal("0.01")


def infer_payment(station: Station, records: list[Station], history: list[Station], now: datetime):
    result = {"classification": station.payment_type, "confidence": "medium" if station.payment_type != "unknown" else "low",
              "basis": "source_reported" if station.payment_type != "unknown" else "unresolved", "reasons": [], "spread": None}
    if station.payment_type != "unknown":
        return result
    def same(r):
        return abs(r.location.lat-station.location.lat) <= 0.0005 and abs(r.location.lng-station.location.lng) <= 0.0005 and (r.canonical_id or (r.source, r.id)) == (station.canonical_id or (station.source, station.id)) and (
            r.fuel_type, r.octane, r.membership_required, r.currency, r.unit
        ) == (station.fuel_type, station.octane, station.membership_required, station.currency, station.unit)
    def fresh(r, days=1):
        return r.price_updated_at is not None and 0 <= (now-r.price_updated_at).total_seconds() <= days*86400
    peers = [r for r in records if same(r) and fresh(r) and r.payment_type != "unknown"]
    matched = [r for r in peers if station.price_updated_at is not None
               and abs((r.price_updated_at-station.price_updated_at).total_seconds()) <= 1800
               and payment_price_match(station, r)]
    matches = {r.payment_type for r in matched}
    if fresh(station) and matches:
        ambiguous = len(matches) == 2 and len({r.price_per_gallon for r in matched}) > 1
        result.update(classification="unknown" if ambiguous else "same_price" if len(matches)==2 else next(iter(matches)),
                      confidence="low" if ambiguous else "medium", basis="ambiguous_price_match" if ambiguous else "contemporaneous_price_match")
        result["matched_quotes"] = [{"source": r.source, "payment_type": r.payment_type,
                                     "price_per_gallon": str(r.price_per_gallon)} for r in matched]
        result["reasons"].append("Price match is evidence, not verified payment terms.")
        if station.source in {"google_maps_web", "google_places"}:
            result["reasons"].append("Maps prices may be rounded to cents. Payment evidence applies only to this fuel grade; raw price and payment type are unchanged.")
    # Same-provider, same-conditions, close-time raw pairs; one observation per day.
    raw = [r for r in history if same(r) and fresh(r, 30) and r.payment_type in {"cash", "credit"} and r.comparison_price_per_gallon is None]
    daily = {}
    for cash in raw:
        if cash.payment_type != "cash":
            continue
        credit = min((r for r in raw if r.payment_type == "credit" and r.source == cash.source and r.id == cash.id
                      and abs((r.price_updated_at-cash.price_updated_at).total_seconds()) <= 1800),
                     key=lambda r: abs((r.price_updated_at-cash.price_updated_at).total_seconds()), default=None)
        if credit is not None:
            gap = credit.price_per_gallon-cash.price_per_gallon
            if Decimal(0) <= gap <= Decimal(1):
                day = cash.price_updated_at.date()
                previous = daily.get(day)
                if previous is None or cash.price_updated_at > previous[0]:
                    daily[day] = (cash.price_updated_at, gap)
    values = [gap for _, gap in daily.values()]
    if len(values) >= 3 and max(values)-min(values) <= Decimal("0.03") and (now-max(t for t, _ in daily.values())).total_seconds() <= 7*86400 and (max(t for t, _ in daily.values())-min(t for t, _ in daily.values())).total_seconds() >= 48*3600:
        result["spread"] = str(median(values))
        result["spread_min"] = str(min(values))
        result["spread_max"] = str(max(values))
        result["history_days"] = len(values)
        result["reasons"].append("Stable raw cash/card pairs on independent observation days; future surcharge may change.")
    return result


def snapshot_history(station, rows):
    """Six daily raw pairs per unknown quote; keep signed rerank requests bounded."""
    from pydantic import ValidationError
    valid = []
    for row in rows:
        try:
            record = Station.model_validate(row)
        except (ValidationError, ValueError, TypeError):
            continue
        if (record.fuel_type, record.octane, record.membership_required, record.currency, record.unit) != (
            station.fuel_type, station.octane, station.membership_required, station.currency, station.unit
        ) or record.price_updated_at is None:
            continue
        valid.append(record)
    pairs = {}
    for cash in sorted(valid, key=lambda r: r.price_updated_at, reverse=True):
        if cash.payment_type != "cash" or cash.price_updated_at.date() in pairs:
            continue
        credits = [r for r in valid if r.payment_type == "credit" and r.source == cash.source and r.id == cash.id
                   and abs((r.price_updated_at-cash.price_updated_at).total_seconds()) <= 1800]
        if credits:
            credit = min(credits, key=lambda r: abs((r.price_updated_at-cash.price_updated_at).total_seconds()))
            pairs[cash.price_updated_at.date()] = [cash.model_dump(mode="json", exclude={"payment_history"}), credit.model_dump(mode="json", exclude={"payment_history"})]
        if len(pairs) == 6:
            break
    return [r for pair in pairs.values() for r in pair]
