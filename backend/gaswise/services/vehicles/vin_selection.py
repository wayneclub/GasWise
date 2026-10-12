"""Conservative NHTSA-to-EPA crosswalk; bounded candidates, never guessed MPG from a VIN."""

import re
from decimal import Decimal

from gaswise.contracts.vehicles import VehicleChoice, VinResolution
from gaswise.domain.ports import ProviderError
from gaswise.domain.vehicles.matching import drive_class
from gaswise.services.vehicles.selection import body, compact


def compatible(decoded, vehicle):
    if decoded.fuel_primary == "Diesel" and vehicle.powertrain != "diesel":
        return False
    if decoded.fuel_primary == "Gasoline" and vehicle.powertrain == "diesel":
        return False
    if decoded.engine_liters is not None:
        if vehicle.engine_liters is None or abs(decoded.engine_liters - vehicle.engine_liters) > Decimal(
            "0.06"
        ):
            return False
    if decoded.cylinders is not None and decoded.cylinders != vehicle.cylinders:
        return False
    if decoded.drive and drive_class(decoded.drive):
        if drive_class(decoded.drive) != drive_class(vehicle.drive):
            return False
    if decoded.transmission:
        value = decoded.transmission.casefold()
        if "manual" in value and "manual" not in vehicle.transmission.casefold():
            return False
        if "automatic" in value and "automatic" not in vehicle.transmission.casefold():
            return False
    if decoded.transmission_speeds is not None:
        speeds = re.search(r"\b(\d+)-spd\b|\(S(\d+)\)", vehicle.transmission)
        if speeds is None or int(speeds[1] or speeds[2]) != decoded.transmission_speeds:
            return False
    return True


class VinSelector:
    def __init__(self, decoder, catalog):
        self.decoder, self.catalog = decoder, catalog

    async def resolve(self, request):
        decoded = await self.decoder.decode(request)
        return await self.resolve_decoded(request, decoded)

    async def resolve_decoded(self, request, decoded):
        result = VinResolution(
            decoded=decoded,
            status="decoded",
            upstream_calls={"nhtsa_decode": 1, "epa_lookup": 0},
            warnings=["VIN decoding does not directly provide MPG or verified minimum octane."],
        )
        if set(decoded.error_codes) != {"0"} or not decoded.check_digit_matches:
            result.status = "partial"
            result.question = "VIN 解碼有錯誤或檢查碼未通過，請確認 VIN；未自動套用車型油耗。"
            return result
        if not decoded.year or not decoded.make or not decoded.model:
            result.status = "partial"
            result.question = "解碼缺少年份、品牌或車型；請改用文字選車確認。"
            return result
        if (
            decoded.year < 1984
            or decoded.year > 2100
            or decoded.fuel_primary not in {"Gasoline", "Diesel"}
            or "plug" in (decoded.electrification or "").casefold()
            or decoded.fuel_secondary not in {None, "", "Electric"}
        ):
            result.status = "unsupported"
            return result

        async def menu(kind, **params):
            result.upstream_calls["epa_lookup"] += 1
            return await self.catalog.menu(kind, **params)

        makes = await menu("make", year=decoded.year)
        makes = [m.value for m in makes.items if compact(m.value) == compact(decoded.make)]
        if len(makes) != 1:
            result.status = "no_match"
            result.question = "VIN 品牌無法唯一對應 EPA 目錄；請改用文字選車。"
            return result
        make = makes[0]
        models = await menu("model", year=decoded.year, make=make)

        def matches(term, name):
            term = compact(term)
            name = compact(re.sub(r"\b4\s*matic\b", "", name, flags=re.IGNORECASE))
            return name.startswith(term) and (len(name) == len(term) or not name[len(term)].isdigit())

        names = [m.value for m in models.items if matches(decoded.model, m.value)]
        series = [m.value for m in models.items if decoded.series and matches(decoded.series, m.value)]
        if series:
            names = series
        # Family names can differ: NHTSA E-Class trim E 400 maps to EPA E400.
        if not names and decoded.trim:
            names = [m.value for m in models.items if matches(decoded.trim, m.value)]
        if decoded.trim:
            trimmed = [name for name in names if compact(decoded.trim) in compact(name)]
            if trimmed:
                names = trimmed
        if decoded.body_class:
            style = decoded.body_class.casefold()
            if "coupe" in style:
                names = [name for name in names if body(name) == "coupe"]
            elif "convertible" in style:
                names = [name for name in names if body(name) == "convertible"]
            elif "wagon" in style:
                names = [name for name in names if body(name) == "wagon"]
            elif "sedan" in style:
                names = [name for name in names if body(name) == "other"]
        if not names or len(names) > 5:
            result.status = "no_match"
            result.question = "VIN 車型無法在有限候選內可靠對應 EPA；請改用文字選車確認。"
            return result
        options = []
        for name in names:
            selected = await menu("options", year=decoded.year, make=make, model=name)
            options.extend((name, option) for option in selected.items)
        if len(options) > 10:
            result.status = "needs_input"
            result.question = "符合 VIN 的配置仍超過查詢上限，請改用文字選車縮小範圍。"
            return result
        candidates = []
        for name, option in options:
            try:
                vehicle_id = int(option.value)
                if request.vehicle_id is not None and vehicle_id != request.vehicle_id:
                    continue
                result.upstream_calls["epa_lookup"] += 1
                vehicle = await self.catalog.vehicle(vehicle_id)
            except ValueError:
                raise ProviderError("vehicle_catalog_invalid_option") from None
            except ProviderError as error:
                if str(error) == "vehicle_powertrain_not_supported":
                    continue
                raise
            if vehicle.year != decoded.year or vehicle.make != make or vehicle.model != name:
                raise ProviderError("vehicle_catalog_selection_mismatch")
            if compatible(decoded, vehicle):
                candidates.append(vehicle)
        if not candidates:
            result.status = "no_match"
            result.question = "沒有與 VIN 引擎、燃料和已知驅動資訊一致的 EPA 配置。"
            return result
        # Common grade does not establish MPG, drive or numeric octane.
        grades = {v.fuel_recommendation.fuel_type for v in candidates if v.fuel_recommendation}
        if len(grades) == 1 and all(v.fuel_recommendation for v in candidates):
            result.fuel_recommendation = candidates[0].fuel_recommendation.model_copy(
                update={
                    "evidence": "EPA candidates "
                    + ", ".join(str(v.id) for v in candidates)
                    + ": "
                    + candidates[0].fuel_type
                    + "; "
                    + candidates[0].fuel_recommendation.evidence,
                }
            )
            requirements = [v.fuel_recommendation for v in candidates]
            same_requirement = (
                len(
                    {
                        (r.source, r.recommended_octane_aki, r.minimum_octane_aki, r.assessment_status)
                        for r in requirements
                    }
                )
                == 1
            )
            if not same_requirement:
                result.fuel_recommendation = result.fuel_recommendation.model_copy(
                    update={
                        "source": "fueleconomy_gov",
                        "octane_aki": None,
                        "minimum_octane_aki": None,
                        "recommended_octane_aki": None,
                        "temporary_octane_aki": None,
                        "manufacturer_requirement_verified": False,
                        "source_urls": [],
                        "assessment_status": "not_assessed",
                        "specification_evidence": [],
                        "assessment_warnings": [],
                    }
                )
            result.fuel_status = (
                "manufacturer_manual"
                if same_requirement and requirements[0].source == "manufacturer_manual"
                else "epa_catalog"
            )
            if same_requirement and requirements[0].source in {
                "specification_consensus",
                "fuel_grade_policy",
            }:
                result.fuel_status = "specification_estimate"
        if len(candidates) > 1 or (request.vehicle_id is None and decoded.engine_liters is None):
            result.status = "needs_input"
            result.mpg_status = "needs_confirmation"
            result.question = "VIN 未唯一確定配置，請確認下列 EPA 車型。"
            result.choices = [
                VehicleChoice(
                    value=str(v.id), label=f"{v.model} · {v.engine_liters} L · {v.transmission} · {v.drive}"
                )
                for v in candidates
            ]
            return result
        result.status = "resolved"
        result.mpg_status = "confirmed"
        result.fuel_status = (
            "manufacturer_manual"
            if candidates[0].fuel_recommendation.source == "manufacturer_manual"
            else "epa_catalog"
        )
        if candidates[0].fuel_recommendation.source in {"specification_consensus", "fuel_grade_policy"}:
            result.fuel_status = "specification_estimate"
        result.vehicle = candidates[0]
        result.fuel_recommendation = candidates[0].fuel_recommendation
        result.warnings.append(
            "Selected the unique EPA candidate consistent with available decoded fields; not factory build-sheet verification."
        )
        return result
