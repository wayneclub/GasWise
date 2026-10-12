"""Scoped manufacturer evidence; never infer requirements from brand or EPA grade."""

import re

from gaswise.contracts.vehicles import VehicleFuelRecommendation

E_COUPE_MANUAL = (
    "https://static.oneweb.mercedes-benz.com/css-oom-assets/en-ca/pdf/"
    "mercedes-e-class-coupe-2018-september-c238-comand-operators-manual-1.pdf"
)
C_SEDAN_MANUAL = (
    "https://www.mbusa.com/content/dam/mb-nafta/us/owners/manuals/2021/Operators/MY21_C%20Sedan_OM.pdf"
)
X3_MANUAL = "https://www.carmanualsonline.info/bmw-x3-2021-owners-manual/29"
M4_MANUAL = "https://manuals.plus/wp-content/uploads/2022/06/BMW_OwnersManual_01405A1E430-1-1.pdf"


def manufacturer_fuel_requirement(vehicle):
    if vehicle.powertrain != "gasoline" or vehicle.fuel_type != "Premium Gasoline":
        return None
    if vehicle.year == 2021:
        if (
            vehicle.make == "Mercedes-Benz"
            and vehicle.model in {"C300", "C300 4matic"}
            and vehicle.engine_liters == 2
            and vehicle.cylinders == 4
        ):
            return VehicleFuelRecommendation(
                fuel_type="premium",
                source="manufacturer_manual",
                evidence="US 2021 C-Class Sedan manual, edition B-2021, p.371-372: gasoline fuel grades.",
                recommended_octane_aki=91,
                temporary_octane_aki=87,
                manufacturer_requirement_verified=True,
                source_urls=[C_SEDAN_MANUAL],
                note="Normal target: at least 91 AKI. Absolute minimum must be checked on the fuel flap. "
                "87 AKI is temporary only: half tank maximum, refill premium promptly; "
                "avoid maximum speed, sudden acceleration and engine speeds over 3000 rpm.",
            )
        if vehicle.make == "BMW":
            x3_30i = (
                vehicle.model in {"X3 sDrive30i", "X3 xDrive30i"}
                and vehicle.engine_liters == 2
                and vehicle.cylinders == 4
            )
            x3_m40i = vehicle.model == "X3 M40i" and vehicle.engine_liters == 3 and vehicle.cylinders == 6
            m4 = (
                vehicle.model in {"M4 Coupe", "M4 Competition Coupe"}
                and vehicle.engine_liters == 3
                and vehicle.cylinders == 6
            )
            if x3_30i or x3_m40i or m4:
                minimum, recommended = (91, 93) if m4 else (89, 93 if x3_m40i else 91)
                return VehicleFuelRecommendation(
                    fuel_type="premium",
                    source="manufacturer_manual",
                    evidence=(
                        "US M4 Coupe manual 01405A1E430 X/20, p.344"
                        if m4
                        else "US X3 manual 01405A10E93 VI/20, p.285; M Performance recommendation applies to M40i"
                    ),
                    minimum_octane_aki=minimum,
                    recommended_octane_aki=recommended,
                    manufacturer_requirement_verified=True,
                    source_urls=[M4_MANUAL if m4 else X3_MANUAL],
                    note=f"Minimum permitted: {minimum} AKI; rated performance and consumption use {recommended} AKI. "
                    "Lower-than-recommended fuel does not establish the same MPG; EPA MPG remains an estimate. "
                    "US-market factory configuration only; vehicle labels and current integrated manual take precedence.",
                )
    # North American C238 gasoline instructions, narrowly scoped to verified EPA configurations.
    # Fuel-door absolute minimum is not established by this manual passage.
    if (
        vehicle.year == 2018
        and vehicle.make == "Mercedes-Benz"
        and re.fullmatch(r"E400(?: 4matic)? Coupe", vehicle.model)
        and vehicle.engine_liters == 3
        and vehicle.cylinders == 6
        and vehicle.powertrain == "gasoline"
        and vehicle.fuel_type == "Premium Gasoline"
    ):
        return VehicleFuelRecommendation(
            fuel_type="premium",
            source="manufacturer_manual",
            evidence="North American 2018 C238 COMAND manual: gasoline fuel grades; 91 AKI for maximum output.",
            recommended_octane_aki=91,
            temporary_octane_aki=87,
            manufacturer_requirement_verified=True,
            source_urls=[E_COUPE_MANUAL],
            note="Normal refueling target: at least 91 AKI. Absolute fuel-door minimum remains unverified. "
            "87 AKI is a temporary manual exception, not a normal ranking target; performance/MPG may decrease.",
        )
    return None
