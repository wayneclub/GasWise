"""Sourced grade estimates; never replace a pump-verified numeric octane."""

CA_SOURCE = "https://www.energy.ca.gov/sites/default/files/2025-05/2021-10_Petroleum_Watch_ada.pdf"
SHELL_SOURCE = "https://www.shell.us/fuels-oils-and-coolants/shell-fuels.html"
SINCLAIR_SOURCE = (
    "https://www.sinclairoil.com/news/sinclair-oil-expands-dino-days-customer-promotion-across-dino-footprint"
)
GRADE_ALIASES = {"plus": "midgrade", "supreme": "premium", "super": "premium"}
CA_TYPICAL_AKI = {"regular": 87, "midgrade": 89, "premium": 91}
BRAND_US_RANGES = {
    "shell": {"regular": (85, 87), "midgrade": (88, 90), "premium": (91, 93)},
    "sinclair": {"premium": (91, 93)},
}


def california_region(country, state, postal_code):
    if country != "US":
        return None
    if state.casefold() in {"ca", "california"}:
        return "source_state"
    if state.strip():
        return None
    zip5 = postal_code[:5]
    if len(zip5) == 5 and zip5.isdigit() and 90001 <= int(zip5) <= 96162:
        return "postal_code_range"
    return None


def infer_octane(brand, country, state, postal_code, fuel_type):
    grade = GRADE_ALIASES.get(fuel_type.removeprefix("gas_"), fuel_type.removeprefix("gas_"))
    if country != "US" or grade not in CA_TYPICAL_AKI:
        return None
    region_basis = california_region(country, state, postal_code)
    bounds = BRAND_US_RANGES.get(brand.strip().casefold(), {}).get(grade)
    if not region_basis and not bounds:
        return None
    sources = []
    if region_basis:
        sources.append(CA_SOURCE)
    if bounds:
        sources.append(SHELL_SOURCE if brand.strip().casefold() == "shell" else SINCLAIR_SOURCE)
    return {
        "scale": "AKI",
        "region": "US-CA" if region_basis else "US",
        "region_basis": region_basis,
        "brand": brand,
        "estimated_octane": CA_TYPICAL_AKI[grade] if region_basis else None,
        "brand_octane_range": list(bounds) if bounds else None,
        "basis": "regional_typical_grade" if region_basis else "brand_grade_range",
        "station_verified": False,
        "source_urls": sources,
        "checked_on": "2026-10-10",
    }


EIA_SOURCE = "https://www.eia.gov/energyexplained/gasoline/octane-in-depth.php"
EIA_GLOSSARY = "https://www.eia.gov/tools/glossary/index.php?id=Gasoline"
US_STATES = set(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)
# National ranges are estimates, not state laws or a promise about a particular pump.
US_TYPICAL_RANGES = {"regular": (85, 87), "midgrade": (88, 90), "premium": (91, 94)}


def station_octane_inference(station, query):
    import re

    if station.fuel_type == "diesel":
        return None
    details = station.details or {}
    if details.get("country") not in (None, "", "US", "USA"):
        return None
    state = details.get("state", "")
    basis = "station_state"
    # Only accept an address with a US state + ZIP, not arbitrary 'CA' text.
    match = re.search(r"\b([A-Z]{2})\s+(\d{5})(?:-\d{4})?\b", station.address or "")
    if not state and match:
        state = match[1]
    if not state:
        existing = station.octane_inference or {}
        if existing.get("region") == "US-CA":
            state = "CA"
    if not state:
        state = query.current_state
        basis = "origin_state_fallback"
    if state not in US_STATES:
        return None
    result = infer_octane(station.name, "US", state, "", station.fuel_type)
    if result is None:
        bounds = US_TYPICAL_RANGES.get(station.fuel_type)
        if bounds is None:
            return None
        result = {
            "scale": "AKI",
            "region": "US-" + state,
            "estimated_octane": None,
            "estimated_range": list(bounds),
            "basis": "national_typical_grade_range",
            "station_verified": False,
            "source_urls": [EIA_SOURCE, EIA_GLOSSARY],
            "checked_on": "2026-10-10",
        }
    else:
        bounds = result.get("brand_octane_range")
        estimate = result.get("estimated_octane")
        result["estimated_range"] = (
            [estimate, max(estimate, bounds[1] if bounds else estimate)]
            if estimate is not None
            else list(bounds)
        )
    result["state_basis"] = basis
    return result


def octane_floor(station, query):
    if station.octane is not None:
        return station.octane
    if query.octane_policy == "verified_only":
        return None
    inference = station_octane_inference(station, query)
    if inference is None:
        return None
    # Use the conservative lower end, never a national upper end (e.g. Premium 94).
    return inference["estimated_range"][0]
