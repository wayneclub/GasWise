"""Aggregate fuel balance; no invented speed cycle, grade, or weather correction."""

from decimal import Decimal

from gaswise.contracts.common import Route
from gaswise.contracts.search import FuelModelInfo, Search

METERS_PER_MILE = Decimal("1609.344")


def fuel_model(query: Search, vehicle=None) -> FuelModelInfo:
    miles = sum((cycle.distance_miles for cycle in query.fuel_cycles), Decimal(0))
    gallons = sum((cycle.consumed_gallons for cycle in query.fuel_cycles), Decimal(0))
    basis = (
        "full_tank_calibrated_estimate"
        if gallons
        else ("epa_combined_estimate" if query.mpg is None and vehicle else "user_mpg_estimate")
    )
    return FuelModelInfo(
        basis=basis,
        mpg_used=miles / gallons
        if gallons
        else query.mpg
        if query.mpg is not None
        else (vehicle.combined_mpg if vehicle else Decimal(20)),
        vehicle=vehicle,
        calibration_cycles=len(query.fuel_cycles),
        calibration_miles=miles,
        calibration_gallons=gallons,
        assumptions=[
            "Same aggregate fuel consumption rate for baseline and candidate routes.",
            "Tank cycles must be non-overlapping, same-vehicle full-to-full intervals including all fuel added.",
            "Tank-average calibration does not measure this route's traffic, grade, weather or cold-start effects.",
            "No manufacturer certification or empirically validated prediction interval is claimed.",
            "EPA combined MPG is a vehicle baseline, not this route's measured consumption.",
            "Without a vehicle, explicit MPG or tank records, the legacy 20 MPG assumption is used.",
        ],
    )


def route_fuel(route: Route, model: FuelModelInfo) -> Decimal:
    return Decimal(str(route.distance_meters)) / METERS_PER_MILE / model.mpg_used
