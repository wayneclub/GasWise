from gaswise.contracts.vehicles import FuelAssessment, FuelSpecificationEvidence, VinRequest
from gaswise.domain.ports import ProviderError
from gaswise.domain.vehicles.specification_assessment import combine_specifications
from gaswise.providers.vehicles.hertz import validate_listing_url
from gaswise.services.vehicles.vin_selection import VinSelector


async def assess_fuel(request, catalog, decoder, hertz):
    if request.hertz_listing_url:
        validate_listing_url(request.hertz_listing_url)
    vehicle = await catalog.vehicle(request.vehicle_id)
    rule = vehicle.fuel_recommendation
    minimum = rule.minimum_octane_aki if rule and rule.manufacturer_requirement_verified else None
    normal = rule.recommended_octane_aki if rule and rule.manufacturer_requirement_verified else None
    estimate = (
        rule.recommended_octane_aki
        if rule and rule.source in {"specification_consensus", "fuel_grade_policy"}
        else None
    )
    result = FuelAssessment(
        vehicle=vehicle,
        target_octane_aki=minimum or normal or estimate,
        target_basis="manufacturer_minimum"
        if minimum
        else "manufacturer_normal_recommendation"
        if normal
        else "specification_estimate"
        if estimate
        else "unresolved",
        source_urls=list(rule.source_urls) if rule else [],
        warnings=list(rule.assessment_warnings) if rule else [],
    )
    if minimum is None and normal is not None:
        result.warnings.append(
            "Target is a normal manufacturer recommendation; absolute minimum remains unknown."
        )
    if request.hertz_listing_url:
        try:
            vin, grade = await hertz.listing(request.hertz_listing_url)
            match = await VinSelector(decoder, catalog).resolve(VinRequest(vin=vin, vehicle_id=vehicle.id))
            if match.status != "resolved" or not match.vehicle or match.vehicle.id != vehicle.id:
                result.hertz_status = "mismatch"
                result.warnings.append(
                    "Hertz listing could not be confirmed as the selected EPA configuration."
                )
            else:
                result.hertz_status = "matched"
                result.hertz_recommended_grade = grade
                result.source_urls.append(request.hertz_listing_url)
                normalized = {
                    "regular unleaded": "regular",
                    "premium unleaded": "premium",
                    "diesel": "diesel",
                }[grade]
                observations = (
                    [e for e in rule.specification_evidence if e.source not in {"hertz", "fueleconomy_gov"}]
                    if rule
                    else []
                )
                observations.append(
                    FuelSpecificationEvidence(
                        source="hertz",
                        source_group="dealer_specs",
                        status="matched",
                        fuel_grade=normalized,
                        requirement="recommended",
                        observed_label=grade,
                        source_url=request.hertz_listing_url,
                    )
                )
                if rule:
                    vehicle.fuel_recommendation = combine_specifications(vehicle, observations)
                    if vehicle.fuel_recommendation.assessment_status == "conflict":
                        result.target_octane_aki = None
                        result.target_basis = "unresolved"
                        result.warnings.extend(vehicle.fuel_recommendation.assessment_warnings)
                expected = (
                    {"regular": "regular unleaded", "premium": "premium unleaded", "diesel": "diesel"}.get(
                        rule.fuel_type
                    )
                    if rule
                    else None
                )
                if expected != grade:
                    result.warnings.append(
                        "Hertz recommended grade differs from the catalog; manufacturer numeric evidence takes precedence."
                    )
        except ProviderError:
            result.hertz_status = "unavailable"
            result.warnings.append("Hertz evidence unavailable or ambiguous; no dealer evidence was applied.")
    rule = vehicle.fuel_recommendation
    if rule:
        minimum = rule.minimum_octane_aki if rule.manufacturer_requirement_verified else None
        normal = rule.recommended_octane_aki if rule.manufacturer_requirement_verified else None
        estimate = (
            rule.recommended_octane_aki
            if rule.source in {"specification_consensus", "fuel_grade_policy"}
            else None
        )
        result.target_octane_aki = minimum or normal or estimate
        result.target_basis = (
            "manufacturer_minimum"
            if minimum
            else "manufacturer_normal_recommendation"
            if normal
            else "specification_estimate"
            if estimate
            else "unresolved"
        )
        result.warnings = list(dict.fromkeys(result.warnings + rule.assessment_warnings))
        result.source_urls = list(dict.fromkeys(result.source_urls + rule.source_urls))
        hertz_evidence = next((e for e in rule.specification_evidence if e.source == "hertz"), None)
        if not request.hertz_listing_url and hertz_evidence:
            result.hertz_status = (
                hertz_evidence.status
                if hertz_evidence.status in {"matched", "mismatch", "unavailable"}
                else "unavailable"
            )
            result.hertz_recommended_grade = (
                hertz_evidence.observed_label if hertz_evidence.status == "matched" else None
            )
    if result.target_octane_aki is None and vehicle.powertrain != "diesel":
        result.warnings.append(
            "No verified manufacturer numeric rule for this configuration; dealer grade cannot establish a minimum."
        )
    return result
