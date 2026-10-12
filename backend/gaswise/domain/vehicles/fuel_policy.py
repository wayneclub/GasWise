"""Vehicle fuel policy shared by discovery and ranking; no upstream IO."""

from gaswise.domain.ports import ProviderError

FUEL_GRADES = {
    "Regular Gasoline": "regular",
    "Midgrade Gasoline": "midgrade",
    "Premium Gasoline": "premium",
    "Diesel": "diesel",
}


def check_vehicle_fuel(vehicle, query):
    if (vehicle.powertrain == "diesel") != (query.fuel_type == "diesel"):
        raise ProviderError("vehicle_fuel_type_mismatch")


def resolve_fuel_query(query, vehicle):
    if (
        vehicle
        and vehicle.fuel_recommendation
        and vehicle.fuel_recommendation.assessment_status == "conflict"
        and (query.fuel_type is None or query.required_octane is None)
    ):
        raise ProviderError("vehicle_fuel_specification_conflict")
    if query.fuel_type is None:
        grade = FUEL_GRADES[vehicle.fuel_type] if vehicle else "premium"
        query = query.model_copy(update={"fuel_type": grade})
    if vehicle and vehicle.fuel_recommendation:
        requirement = vehicle.fuel_recommendation
        # A performance recommendation must not override a verified permitted minimum.
        # When the minimum is unknown, retain the normal recommendation; temporary exceptions never qualify.
        threshold = requirement.minimum_octane_aki or requirement.recommended_octane_aki
        if threshold is not None:
            query = query.model_copy(update={"required_octane": max(threshold, query.required_octane or 0)})
    return query
