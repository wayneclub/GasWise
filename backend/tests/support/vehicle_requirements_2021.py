import json

from gaswise.contracts.vehicles import VehicleProfile
from tests.support.paths import FIXTURES as FIXTURE_ROOT

PROFILES = {
    p["id"]: VehicleProfile.model_validate(p)
    for p in json.loads((FIXTURE_ROOT / "epa_2021_vehicle_validation.json").read_text())
}
