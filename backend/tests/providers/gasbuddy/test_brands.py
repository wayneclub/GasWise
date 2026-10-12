from fastapi.testclient import TestClient

from gaswise.app.settings import Settings
from gaswise.contracts.sources import GasBuddySearch, gasbuddy_variables
from gaswise.main import create_app
from gaswise.providers.gasbuddy.brands import BRANDS


def test_brand_catalog_preserves_verified_ids_and_all_brands():
    app = create_app(Settings(mode="demo", api_token="test-token"))
    with TestClient(app) as client:
        assert client.get("/v1/sources/gasbuddy/brands").status_code == 401
        response = client.get("/v1/sources/gasbuddy/brands", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["all_brands"]["brand_id"] is None
    assert data["exhaustive"] is False
    mapping = {b["name"]: b["brand_id"] for b in data["brands"]}
    assert mapping["Chevron"] == 31
    assert mapping["Shell"] == 122
    assert mapping["ARCO"] == 20
    assert mapping["Costco"] == 38
    assert len(mapping) == len(BRANDS) == 26
    assert len({b["brand_id"] for b in BRANDS}) == 26
    for b in data["brands"]:
        query = GasBuddySearch(search="Los Angeles, CA", brand_id=b["brand_id"])
        assert gasbuddy_variables(query, 3)["brandId"] == b["brand_id"]
    assert "brandId" not in gasbuddy_variables(GasBuddySearch(search="90015"), 3)
