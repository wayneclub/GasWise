"""Regional context is separate from station eligibility and ranking."""
import re

from gaswise.contracts.search import RegionalBenchmark

ADDRESS = re.compile(r",\s*([^,]+),\s*([A-Z]{2})\s+\d{5}(?:-\d{4})?\s*$")


def address_region(address):
    match = ADDRESS.search(address or "")
    if match:
        return match[1].strip(), match[2]
    tail = re.search(r"\b([A-Z]{2})\s+\d{5}(?:-\d{4})?\s*$", address or "")
    return (None, tail[1]) if tail else (None, None)


def benchmarks(data, fuel):
    grade = "mid_grade" if fuel == "midgrade" else fuel
    return [RegionalBenchmark(
        state=data.state, region=region.name, scope=region.level, fuel_type=fuel,
        price_per_gallon=price, price_as_of=data.price_as_of,
        retrieved_at=data.retrieved_at, source_url=data.source_url,
    ) for region in data.regions if region.level in {"state", "metro"}
       and (price := region.prices.get("current", {}).get(grade)) is not None]


def match_benchmark(station, averages):
    city, state = address_region(station.details.get("regional_address") or station.address)
    available = [b for b in averages if b.state == state and b.fuel_type == station.fuel_type]
    if city:
        # Only exact named metro components, never substring/fuzzy geographic guesses.
        metros = [b for b in available if b.scope == "metro" and city.casefold() in
                  [part.strip().casefold() for part in b.region.split("-")]]
        if len(metros) == 1:
            return metros[0]
    return next((b for b in available if b.scope == "state"), None)
