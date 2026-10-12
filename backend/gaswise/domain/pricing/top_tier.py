"""Match stations to TOP TIER licensed brands by name; licensing is brand-level, not per station."""

import re

# Names made of everyday words collide with unrelated local stations, so they must match exactly.
GENERIC_BRANDS = {
    "BEACON",
    "EXPRESS MART",
    "FAST FUEL",
    "FUEL DEPOT",
    "FUEL UP",
    "GO HAPPY",
    "GOLD MEDAL GASOLINE",
    "HFN",
    "MEGA SAVER",
    "WIN WIN",
    "WOW",
}


def normalize(text: str) -> str:
    text = text.upper().replace("&", " AND ")
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", text).split())


def aliases(brand: str) -> list[str]:
    # "Costco / Kirkland Signature" is one licensed brand with two retail names.
    return [alias for alias in (normalize(part) for part in brand.split("/")) if alias]


def us_brand_index(brands) -> list[tuple[str, str, bool]]:
    """(alias, display brand, exact-only), longest alias first so 'PHILLIPS 66' wins over shorter ones."""
    index = []
    for brand in brands:
        if "USA" not in brand.countries:
            continue
        for alias in aliases(brand.name):
            index.append((alias, brand.name, alias in GENERIC_BRANDS))
    return sorted(index, key=lambda row: len(row[0]), reverse=True)


def match_top_tier(name: str, brand_hint: str | None, index) -> str | None:
    candidates = [normalize(value) for value in (brand_hint, name) if value]
    for alias, brand, exact in index:
        for candidate in candidates:
            if candidate == alias or (not exact and candidate.startswith(alias + " ")):
                return brand
    return None


def tag_top_tier(stations, index):
    if not index:
        return stations
    tagged = []
    for station in stations:
        hint = station.details.get("brand") if isinstance(station.details.get("brand"), str) else None
        brand = match_top_tier(station.name, hint, index)
        tagged.append(
            station.model_copy(update={"top_tier_brand": brand})
            if brand != station.top_tier_brand
            else station
        )
    return tagged
