"""Auditable multi-source rules, not a learned estimate of source accuracy."""

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from gaswise.models import PriceEvidence, Search, Station


@dataclass
class Selection:
    station: Station
    key: str
    quotes: list[Station]
    evidence: list[PriceEvidence]
    reason: str


def distance_meters(a, b):
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    h = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b.lng - a.lng) / 2) ** 2
    )
    return 6371000 * 2 * math.asin(math.sqrt(min(1, h)))


def ineligible(station: Station, query: Search, now: datetime) -> str | None:
    if station.fuel_type != query.fuel_type:
        return "wrong_fuel_type"
    if distance_meters(query.origin, station.location) > query.radius_meters:
        return "outside_search_radius"
    if station.membership_required and station.membership_required not in query.memberships:
        return "membership_required"
    if query.required_octane is not None and station.octane != query.required_octane:
        return "octane_not_verified_or_mismatch"
    if query.payment_type == "credit" and station.payment_type == "cash":
        return "payment_type_mismatch"
    age = (now - station.price_updated_at).total_seconds() / 60 if station.price_updated_at else None
    if age is not None and age < -5:
        return "future_price_timestamp"
    if age is not None and age > query.max_price_age_minutes:
        return "stale_price"
    return None


def select_prices(stations: list[Station], query: Search, now: datetime):
    groups: dict[str, list[Station]] = {}
    for station in stations:
        # Explicit crosswalk only. Nearby stations or similar brand names are not sufficient identity evidence.
        key = station.canonical_id or f"{station.source}:{station.id}"
        groups.setdefault(key, []).append(station)
    selected, excluded, warnings = [], 0, []
    for key, records in groups.items():
        eligible, evidence = [], []
        anchor = records[0]
        for record in records:
            reason = ineligible(record, query, now)
            if distance_meters(anchor.location, record.location) > 75:
                reason = "station_mapping_location_mismatch"
            evidence.append(
                PriceEvidence(
                    source=record.source,
                    provider_station_id=record.id,
                    price_per_gallon=record.price_per_gallon,
                    price_updated_at=record.price_updated_at,
                    payment_type=record.payment_type,
                    octane=record.octane,
                    eligible=reason is None,
                    exclusion_reason=reason,
                )
            )
            if reason:
                excluded += 1
            else:
                eligible.append(record)
        if not eligible:
            continue
        # Use known timestamps first. A user source preference breaks ties within 30 minutes
        # of the newest quote, never outweighs an arbitrarily newer observation.
        dated = [r for r in eligible if r.price_updated_at is not None]
        newest = max((r.price_updated_at for r in dated), default=None)
        cohort = (
            [r for r in dated if (newest - r.price_updated_at).total_seconds() <= 1800]
            if newest
            else eligible
        )

        def preference(record):
            priority = (
                query.preferred_sources.index(record.source)
                if record.source in query.preferred_sources
                else len(query.preferred_sources)
            )
            return (
                record.payment_type == "unknown",
                priority,
                -(record.price_updated_at.timestamp() if record.price_updated_at else 0),
                record.source,
                record.id,
            )

        winner = min(cohort, key=preference)
        # Only compare quotes with exactly the selected purchase conditions. Unknown conditions
        # are kept in evidence, but never counted as corroborating a cash/card or octane-specific quote.
        quotes = [
            r
            for r in eligible
            if (r.payment_type, r.octane, r.membership_required)
            == (winner.payment_type, winner.octane, winner.membership_required)
        ]
        for item, record in zip(evidence, records, strict=True):
            item.comparable = item.eligible and (
                record.payment_type,
                record.octane,
                record.membership_required,
            ) == (winner.payment_type, winner.octane, winner.membership_required)
            if not item.comparable:
                item.comparison_exclusion_reason = (
                    item.exclusion_reason or "purchase_conditions_not_comparable"
                )
        reason = (
            "Known-time quotes within 30 minutes of newest; verified payment then user source preference breaks ties."
            if newest
            else "Source time unknown; payment specificity then user preference breaks ties."
        )
        if winner.payment_type == "unknown":
            warnings.append(f"Payment basis is unknown for {key}; cash/credit price not verified.")
        if len(quotes) < len(eligible):
            warnings.append(
                f"Different or unknown purchase conditions for {key}; see evidence, not treated as corroboration."
            )
        selected.append(Selection(winner, key, quotes, evidence, reason))
    return selected, excluded, warnings


def comparable_prices(selection: Selection, now: datetime | None = None):
    """Deduplicate each source so repeated observations cannot masquerade as consensus."""
    per_source = {}
    for quote in selection.quotes:
        current = per_source.get(quote.source)
        if current is None or (quote.price_updated_at.timestamp() if quote.price_updated_at else 0) > (
            current.price_updated_at.timestamp() if current.price_updated_at else 0
        ):
            per_source[quote.source] = quote
    prices = [s.price_per_gallon for s in per_source.values()]
    spread = max(prices) - min(prices)
    known_conditions = selection.station.payment_type != "unknown"
    known_times = all(s.price_updated_at for s in per_source.values())
    fresh_times = known_times and (
        now is None
        or all(0 <= (now - s.price_updated_at).total_seconds() <= 3600 for s in per_source.values())
    )
    agreement = (
        "single_source" if len(prices) < 2 else "consistent" if spread <= Decimal("0.05") else "conflicting"
    )
    quality = (
        "disputed"
        if agreement == "conflicting"
        else "corroborated"
        if len(prices) >= 2 and known_conditions and fresh_times
        else "limited"
    )
    return min(prices), max(prices), spread, agreement, quality, len(prices)
