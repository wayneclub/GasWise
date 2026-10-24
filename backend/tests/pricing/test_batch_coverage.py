from gaswise.domain.pricing.batch_coverage import requested_radii, simulated_area
from gaswise.domain.pricing.collection_bases import BASES


def test_adaptive_plan_increases_area_without_increasing_overlap_share():
    legacy = requested_radii(list(BASES), strategy="legacy")
    adaptive = requested_radii(list(BASES), strategy="isolated_radius_v1")
    before = simulated_area(legacy, cell_km=2)
    after = simulated_area(adaptive, cell_km=2)

    assert after["covered_km2"] > before["covered_km2"]
    assert after["overlap_share"] <= before["overlap_share"]
    assert sum(radius > 10000 for radius in adaptive.values()) == 8
    assert max(adaptive.values()) == 20000


def test_legacy_plan_is_exact_rollback_and_reports_geographic_gaps():
    legacy = requested_radii(list(BASES), strategy="legacy")
    report = simulated_area(legacy, cell_km=2)
    assert set(legacy.values()) == {10000.0}
    assert report["largest_gaps"][0]["gap_km"] > 80
