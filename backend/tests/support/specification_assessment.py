import json

from gaswise.contracts.vehicles import FuelSpecificationEvidence, VehicleProfile
from tests.support.paths import FIXTURES as FIXTURE_ROOT

FIXTURES = FIXTURE_ROOT

EPA = {
    v["id"]: VehicleProfile.model_validate(v)
    for v in json.loads((FIXTURES / "epa_spec_assessment_profiles.json").read_text())
}

HERTZ = (FIXTURES / "hertz_camry_specs.html").read_text()

EDM_URL = "https://www.edmunds.com/toyota/camry/2021/features-specs/"

HERTZ_URL = "https://www.hertzcarsales.com/used/Toyota/2021-Toyota-Camry-example.htm"


def observation(grade="regular", requirement="unspecified", source="edmunds", group="edmunds_specs"):
    return FuelSpecificationEvidence(
        source=source,
        source_group=group,
        status="matched",
        fuel_grade=grade,
        requirement=requirement,
        source_url=EDM_URL,
        observed_label=grade,
    )


def specs_html(
    make="Toyota",
    model="Camry",
    year=2021,
    engine="2.5",
    cylinders=4,
    drive="Front wheel drive",
    fuel="Regular unleaded",
    trim="SE",
    transmission="8-speed automatic",
):
    # Representative HTML from observed public field labels, not a claim of a live HTTP response.
    return (
        f"<h1>Used {year} {make} {model} Specs</h1><p>{trim}</p><h2>Fuel & MPG</h2><p>Fuel type</p><p>{fuel}</p>"
        f"<h2>Engine</h2><p>Base engine size</p><p>{engine} L</p><p>Cylinders</p><p>Inline {cylinders}</p>"
        f"<p>Transmission</p><p>{transmission}</p><p>Drive type</p><p>{drive}</p><h2>Suspension</h2>"
    )


def raw_profile(v):
    return {
        "id": v.id,
        "year": v.year,
        "make": v.make,
        "model": v.model,
        "trany": v.transmission,
        "drive": v.drive,
        "displ": str(v.engine_liters),
        "cylinders": v.cylinders,
        "fuelType1": v.fuel_type,
        "city08": str(v.city_mpg),
        "highway08": str(v.highway_mpg),
        "comb08": str(v.combined_mpg),
    }
