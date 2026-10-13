from fastapi.testclient import TestClient

from gaswise.app.settings import Settings
from gaswise.main import create_app


def test_validation_does_not_echo_personal_inputs():
    secret = "invalid_private_identifier"
    with TestClient(create_app(Settings(api_token="test"))) as client:
        for path, body in (
            ("/v1/vehicles/vin", {"vin": secret, secret: "extra"}),
            ("/v1/vehicles/plate", {"state": "CA", "plate": secret}),
            ("/v1/parts/search", {"keyword": "brakes", "vin": {"vin": secret}}),
        ):
            response = client.post(path, json=body, headers={"Authorization": "Bearer test"})
            assert response.status_code == 422
            assert secret not in response.text
            assert all(set(error) == {"type", "loc", "msg"} for error in response.json()["detail"])
            assert response.headers["cache-control"] == "no-store"
