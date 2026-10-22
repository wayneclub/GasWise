import json
from pathlib import Path

FIXTURE = Path(__file__).parents[1] / "fixtures/us_popular_vehicles_2025.json"


def test_market_fixture_has_top_ten_plus_requested_luxury_supplements():
    data = json.loads(FIXTURE.read_text())
    cases = data["cases"]
    top_ten = [case for case in cases if case["group"] == "top10"]
    supplements = [case for case in cases if case["group"] == "supplemental"]

    assert data["year"] == 2025
    assert len(cases) == 60
    assert len(top_ten) == 50
    assert len(supplements) == 10
    assert {case["brand_rank"] for case in top_ten} == set(range(1, 11))
    assert all(sum(case["make"] == make for case in top_ten) == 5 for make in {c["make"] for c in top_ten})
    assert {case["make"] for case in supplements} == {"Mercedes-Benz", "BMW"}
    assert all(
        sum(case["make"] == make for case in supplements) == 5
        for make in {case["make"] for case in supplements}
    )


def test_every_market_case_has_identity_expectations():
    cases = json.loads(FIXTURE.read_text())["cases"]
    identities = {(case["make"], case["query"]) for case in cases}

    assert len(identities) == len(cases)
    assert all(case["expected_prefixes"] for case in cases)
    assert sum(bool(case.get("expected_unavailable")) for case in cases) == 1
    assert next(case for case in cases if case.get("expected_unavailable"))["query"] == "Transit"
