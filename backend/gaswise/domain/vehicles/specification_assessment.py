"""A labeled US planning estimate, never a majority-voted manufacturer minimum."""

from gaswise.contracts.vehicles import FuelSpecificationEvidence

POLICY_URL = "https://www.eia.gov/energyexplained/gasoline/octane-in-depth.php"
GRADES = {
    "Regular Gasoline": "regular",
    "Midgrade Gasoline": "midgrade",
    "Premium Gasoline": "premium",
    "Diesel": "diesel",
}
NORMAL_TARGET = {"regular": 87, "midgrade": 89, "premium": 91}


def combine_specifications(vehicle, observations):
    rule = vehicle.fuel_recommendation.model_copy(deep=True)
    epa = FuelSpecificationEvidence(
        source="fueleconomy_gov",
        source_group="epa_catalog",
        status="matched",
        fuel_grade=GRADES[vehicle.fuel_type],
        observed_label=vehicle.fuel_type,
        source_url=f"https://www.fueleconomy.gov/ws/rest/vehicle/{vehicle.id}",
    )
    evidence = [epa, *observations]
    matched = [e for e in evidence if e.status == "matched" and e.fuel_grade]
    # EPA regular plus an explicitly recommended premium upgrade is not a required-grade conflict.
    # The premium recommendation is not counted as a vote confirming regular or its numeric minimum.
    votes = [
        e
        for e in matched
        if not (epa.fuel_grade == "regular" and e.fuel_grade == "premium" and e.requirement == "recommended")
    ]
    grades = {e.fuel_grade for e in votes}
    groups = {e.source_group for e in votes}
    warnings = []
    if any(e.status != "matched" for e in observations):
        warnings.append(
            "Some specification sources were unavailable, ambiguous or did not match this configuration."
        )
    if len(grades) > 1:
        warnings.append("Specification grades conflict; no grade-derived numeric target is applied.")
    if any(e.requirement == "recommended" and e.fuel_grade == "premium" for e in matched):
        warnings.append("Premium recommended does not establish that premium is the minimum permitted grade.")
        if epa.fuel_grade == "regular":
            warnings.append(
                "EPA regular is retained as the cost-planning category; premium recommendation is an optional upgrade, not a confirming vote."
            )
    if rule.manufacturer_requirement_verified:
        rule.assessment_status = "manufacturer_verified"
        if len(grades) > 1:
            warnings.append(
                "Manufacturer numeric evidence takes precedence over specification grade disagreement."
            )
    else:
        rule.minimum_octane_aki = None
        rule.temporary_octane_aki = None
        rule.recommended_octane_aki = None
        rule.assessment_status = (
            "conflict" if len(grades) > 1 else "agreement" if len(groups) > 1 else "single_source"
        )
        if len(grades) == 1:
            grade = next(iter(grades))
            rule.source = "specification_consensus" if len(groups) > 1 else "fuel_grade_policy"
            rule.fuel_type = grade
            rule.recommended_octane_aki = NORMAL_TARGET.get(grade)
            warnings.append(
                "US planning estimate from fuel category: 87 regular / 89 midgrade / 91 premium. "
                "This is not verified manufacturer minimum AKI; specifications may omit higher requirements."
            )
            if len(groups) == 1:
                warnings.append("Only the EPA grade is available; this is not a multi-source agreement.")
            rule.note = "Normal US planning target only. Exact minimum and exceptional octane requirements remain unverified."
            rule.source_urls = list(dict.fromkeys([e.source_url for e in matched] + [POLICY_URL]))
        else:
            rule.source = "fueleconomy_gov"
    rule.specification_evidence = evidence
    rule.assessment_warnings = warnings
    return rule
