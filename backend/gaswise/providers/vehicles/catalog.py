"""Official EPA/DOE catalog; fixed host, bounded metadata cache, no retries."""

import time
from collections import OrderedDict
from datetime import UTC, datetime

import httpx
from pydantic import ValidationError

from gaswise.contracts.vehicles import VehicleFuelRecommendation, VehicleMenu, VehicleProfile
from gaswise.domain.ports import ProviderError
from gaswise.domain.vehicles.fuel_policy import FUEL_GRADES
from gaswise.domain.vehicles.fuel_policy import check_vehicle_fuel as check_vehicle_fuel
from gaswise.domain.vehicles.fuel_policy import resolve_fuel_query as resolve_fuel_query
from gaswise.domain.vehicles.requirements import manufacturer_fuel_requirement
from gaswise.domain.vehicles.specification_assessment import combine_specifications

BASE_URL = "https://www.fueleconomy.gov/ws/rest/vehicle"


class VehicleProvider:
    def __init__(self, client, specifications=None):
        self.client = client
        self.specifications = specifications
        self.cache = OrderedDict()

    async def get(self, path, params=None):
        key = (path, tuple(sorted((params or {}).items())))
        cached = self.cache.get(key)
        if cached and time.monotonic() - cached[0] < cached[2]:
            self.cache.move_to_end(key)
            return cached[1].model_copy(deep=True)
        try:
            response = await self.client.get(
                BASE_URL + path, params=params, headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError):
            raise ProviderError("vehicle_catalog_unavailable") from None
        if not isinstance(data, dict):
            raise ProviderError("vehicle_catalog_invalid_response")
        return key, data

    def remember(self, key, data, ttl=86400):
        self.cache[key] = (time.monotonic(), data, ttl)
        self.cache.move_to_end(key)
        while len(self.cache) > 128:
            self.cache.popitem(last=False)

    async def menu(self, kind, **params):
        if kind not in {"year", "make", "model", "options"}:
            raise ProviderError("vehicle_catalog_invalid_menu")
        result = await self.get("/menu/" + kind, params)
        if isinstance(result, VehicleMenu):
            return result
        key, data = result
        if "menuItem" not in data:
            raise ProviderError("vehicle_catalog_invalid_menu")
        rows = data["menuItem"]
        if isinstance(rows, dict):
            rows = [rows]
        try:
            menu = VehicleMenu(items=rows)
        except ValidationError:
            raise ProviderError("vehicle_catalog_invalid_menu") from None
        self.remember(key, menu)
        return menu.model_copy(deep=True)

    async def vehicle(self, vehicle_id):
        result = await self.get("/" + str(vehicle_id))
        if isinstance(result, VehicleProfile):
            return result
        key, data = result
        fuel = data.get("fuelType1", "")
        atv = data.get("atvType", data.get("atvtype", ""))
        if (
            fuel not in {"Regular Gasoline", "Premium Gasoline", "Midgrade Gasoline", "Diesel"}
            or data.get("fuelType2") not in {None, ""}
            or atv not in {None, "", "Hybrid", "Diesel"}
        ):
            raise ProviderError("vehicle_powertrain_not_supported")
        try:
            profile = VehicleProfile(
                id=data["id"],
                year=data["year"],
                make=data["make"],
                model=data["model"],
                transmission=data["trany"],
                drive=data["drive"],
                engine_liters=data.get("displ") or None,
                cylinders=data.get("cylinders") or None,
                powertrain="diesel" if fuel == "Diesel" else "hybrid" if atv == "Hybrid" else "gasoline",
                fuel_type=fuel,
                city_mpg=data["city08"],
                highway_mpg=data["highway08"],
                combined_mpg=data["comb08"],
                fetched_at=datetime.now(UTC),
                fuel_recommendation=VehicleFuelRecommendation(fuel_type=FUEL_GRADES[fuel], evidence=fuel),
            )
            if profile.id != vehicle_id:
                raise ValueError("vehicle_id_mismatch")
        except (KeyError, ValueError, TypeError):
            raise ProviderError("vehicle_catalog_invalid_vehicle") from None
        profile.fuel_recommendation = manufacturer_fuel_requirement(profile) or profile.fuel_recommendation
        if self.specifications is not None:
            observations = await self.specifications.observations(profile)
            profile.fuel_recommendation = combine_specifications(profile, observations)
        missing_specs = (
            self.specifications is not None
            and not profile.fuel_recommendation.manufacturer_requirement_verified
            and all(
                e.status != "matched"
                for e in profile.fuel_recommendation.specification_evidence
                if e.source != "fueleconomy_gov"
            )
        )
        self.remember(key, profile, ttl=900 if missing_specs else 86400)
        return profile.model_copy(deep=True)
