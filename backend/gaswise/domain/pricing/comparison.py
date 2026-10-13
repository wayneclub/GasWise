"""Auditable multi-source rules, not a learned estimate of source accuracy."""

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from gaswise.contracts.common import Station
from gaswise.contracts.search import PriceEvidence, Search
from gaswise.domain.pricing.grades import octane_floor, station_octane_inference


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


def search_limit_meters(query) -> float:
    """Soft boundary: a station just past the chosen radius stays eligible and detour cost ranks it."""
    return min(50000, query.radius_meters + max(800, query.radius_meters * 0.2))


def ineligible(station: Station, query: Search, now: datetime) -> str | None:
    if station.fuel_type != query.fuel_type:
        return "wrong_fuel_type"
    if distance_meters(query.origin, station.location) > search_limit_meters(query):
        return "outside_search_radius"
    if station.membership_required and station.membership_required not in query.memberships:
        return "membership_required"
    if query.required_octane is not None:
        floor = octane_floor(station, query)
        if floor is None or floor < query.required_octane:
            return "octane_not_verified_or_mismatch"
    if station.payment_type == "unknown" and not query.allow_unknown_payment:
        return "payment_type_unverified"
    if query.payment_type != "cash_or_credit" and station.payment_type != "unknown" and station.payment_type != query.payment_type:
        return "payment_type_mismatch"
    age = (now - station.price_updated_at).total_seconds() / 60 if station.price_updated_at else None
    if age is not None and age < -5:
        return "future_price_timestamp"
    if age is not None and age > query.max_price_age_minutes:
        return "stale_price"
    return None


CLOSED_BUSINESS = {"temporarily_closed", "permanently_closed"}


def merged_opening(*records) -> dict:
    """Combine one station's opening evidence: any closed report wins over open or unknown."""
    open_values = [r.open_now for r in records if r is not None]
    statuses = [r.business_status for r in records if r is not None and r.business_status]
    return {
        "open_now": False if False in open_values else True if True in open_values else None,
        "business_status": next((s for s in statuses if s in CLOSED_BUSINESS), None)
        or next(iter(statuses), None),
    }


def closed_reason(records: list[Station], query: Search) -> str | None:
    """Opening status belongs to the station, so any source reporting it closed excludes all quotes."""
    if query.opening_policy == "ignore":
        return None
    if any(r.business_status in CLOSED_BUSINESS or r.open_now is False for r in records):
        return "station_closed"
    if query.opening_policy == "require_open" and not any(r.open_now for r in records):
        return "opening_status_unknown"
    return None


def top_tier_reason(records: list[Station], query: Search) -> str | None:
    if query.top_tier_only and not any(r.top_tier_brand for r in records):
        return "not_top_tier"
    return None


def comparison_price(station: Station) -> Decimal:
    return station.comparison_price_per_gallon or station.price_per_gallon


def cashback_rate(station: Station, query: Search) -> Decimal:
    # Keep raw payment provenance intact. Unknown quotes use the user's selected
    # card assumption only when explicitly allowed; cash never earns card rewards.
    uses_credit = station.payment_type == "credit" or (
        station.payment_type == "unknown" and query.payment_type != "cash"
    )
    return query.credit_cashback_percent / 100 if uses_credit else Decimal(0)


def net_purchase_price(station: Station, query: Search) -> Decimal:
    return comparison_price(station) * (1 - cashback_rate(station, query))


def select_prices(stations: list[Station], query: Search, now: datetime):
    groups: dict[str, list[Station]] = {}
    for station in stations:
        inference = station_octane_inference(station, query)
        adjustment = query.unknown_payment_credit_markup if station.payment_type == "unknown" and query.payment_type != "cash" else Decimal(0)
        station = station.model_copy(update={"octane_inference": inference, "comparison_price_per_gallon": station.price_per_gallon + adjustment if adjustment else None, "payment_price_adjustment": adjustment})
        # Explicit crosswalk only. Nearby stations or similar brand names are not sufficient identity evidence.
        key = station.canonical_id or f"{station.source}:{station.id}"
        groups.setdefault(key, []).append(station)
    selected, excluded, warnings, unknown_hours = [], 0, [], 0
    for key, records in groups.items():
        eligible, evidence = [], []
        anchor = records[0]
        # A mislocated crosswalk record is not evidence about this station's hours.
        in_place = [r for r in records if distance_meters(anchor.location, r.location) <= 75]
        closed = closed_reason(in_place, query) or top_tier_reason(in_place, query)
        for record in records:
            reason = closed or ineligible(record, query, now)
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
                    octane_inference=record.octane_inference,
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
        if query.required_octane is not None and any(r.octane is None for r in eligible):
            warnings.append(
                "Octane eligibility uses a sourced regional estimate; confirm the pump label. "
                "Station " + key + " is not pump-verified."
            )
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

        # All-payment searches compare net purchase prices, retaining raw payment provenance.
        winner = (
            min(cohort, key=lambda r: (r.payment_type == "unknown", net_purchase_price(r, query), preference(r)))
            if query.payment_type == "cash_or_credit" else min(cohort, key=preference)
        )
        metadata = {}
        peers = [r for r in records if distance_meters(winner.location, r.location) <= 75]
        for peer in peers:
            for field, value in peer.details.items():
                if value is not None and value != []:
                    metadata.setdefault(field, value)
        metadata.update({k: v for k, v in winner.details.items() if v is not None and v != []})
        rating_record = next((r for r in [winner, *peers] if r.rating is not None), winner)
        winner = winner.model_copy(update={"details": metadata, "rating": rating_record.rating, "review_count": rating_record.review_count, "rating_source": rating_record.rating_source})
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
        if query.payment_type == "cash_or_credit" and query.credit_cashback_percent:
            reason += " Eligible payment quotes compared after user-estimated card rewards."
        if winner.payment_type == "unknown":
            warnings.append(f"Payment basis is unknown for {key}; cash/credit price not verified.")
        if len(quotes) < len(eligible):
            warnings.append(
                f"Different or unknown purchase conditions for {key}; see evidence, not treated as corroboration."
            )
        if not any(r.open_now for r in records):
            unknown_hours += 1
        selected.append(Selection(winner, key, quotes, evidence, reason))
    if unknown_hours and query.opening_policy == "exclude_closed":
        warnings.append(
            f"Opening status is unknown for {unknown_hours} eligible stations; confirm hours before driving."
        )
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
    prices = [comparison_price(s) for s in per_source.values()]
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
