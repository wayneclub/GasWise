"""Documented Vehicle Databases plate-to-VIN adapter. One request, no retry or retained plate cache."""

import httpx
from pydantic import ValidationError

from gaswise.contracts.vehicles import PlateRequest, VinRequest
from gaswise.domain.ports import ProviderError

BASE_URL = "https://api.vehicledatabases.com/plate-decode"


class PlateProvider:
    source_id = "vehicle_databases"

    def __init__(self, client, api_key):
        self.client, self.api_key = client, api_key

    async def vin(self, request):
        if not self.api_key:
            raise ProviderError("plate_provider_not_configured")
        try:
            response = await self.client.get(
                f"{BASE_URL}/{request.plate}/{request.state}", headers={"x-authkey": self.api_key}
            )
            if response.status_code == 400:
                raise ProviderError("plate_record_not_found")
            if response.status_code in {401, 403}:
                raise ProviderError("plate_provider_authentication_failed")
            if response.status_code == 429:
                raise ProviderError("plate_provider_rate_limited")
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or data.get("status") != "success":
                raise ValueError("unsuccessful_plate_response")
            intro, basic = data["data"]["intro"], data["data"]["basic"]
            echoed = PlateRequest(plate=intro["license"], state=intro["state"])
            if echoed.plate != request.plate or echoed.state != request.state:
                raise ValueError("plate_identity_mismatch")
            vin = VinRequest(vin=intro["vin"], model_year=basic["year"], vehicle_id=request.vehicle_id)
            if not isinstance(basic.get("make"), str) or not basic["make"].strip():
                raise ValueError("plate_make_missing")
            if not isinstance(basic.get("model"), str) or not basic["model"].strip():
                raise ValueError("plate_model_missing")
        except httpx.HTTPError:
            raise ProviderError("plate_provider_unavailable") from None
        except (KeyError, TypeError, ValueError, ValidationError):
            raise ProviderError("plate_invalid_response") from None
        return vin, basic["make"], basic["model"]


class AutoZonePlateProvider:
    """Observed anonymous HTTPS contract; one request, no cookies or retry."""

    source_id = "autozone"
    url = (
        "https://external-api.autozone.com/sls/b2c/product-discovery-product-data"
        "/v1/vehicles/search-by-vin-or-license-plate"
    )
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.autozone.com/",
        "Origin": "https://www.autozone.com",
        "X-Requested-By": "MF",
        "sales-channel": "AZRMFWEB",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/154.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, client):
        self.client = client

    async def vin(self, request):
        vin, make, model, _ = await self.vehicle_context(request)
        return vin, make, model

    async def vehicle_context(self, request):
        try:
            # Explicit request strips credentials/cookies inherited by shared clients.
            outgoing = self.client.build_request(
                "GET",
                self.url,
                params={
                    "licensePlate": request.plate,
                    "state": request.state,
                    "callingClient": "DIY-DESKTOP",
                    "country": "USA",
                },
                headers=self.headers,
            )
            for key in ("cookie", "authorization", "x-api-key", "x-authkey"):
                outgoing.headers.pop(key, None)
            response = await self.client.send(outgoing, auth=None, follow_redirects=False)
            if response.status_code in {400, 404}:
                raise ProviderError("plate_record_not_found")
            if response.status_code in {401, 403}:
                raise ProviderError("plate_provider_authentication_failed")
            if response.status_code == 429:
                raise ProviderError("plate_provider_rate_limited")
            response.raise_for_status()
            data = response.json()
            if data == []:
                raise ProviderError("plate_record_not_found")
            if not isinstance(data, list) or len(data) != 1:
                raise ValueError("plate_response_not_unique")
            row = data[0]
            attrs = row["acesVehicleAttributes"]
            make, model = row["makeName"], row["modelName"]
            if not all(isinstance(v, str) and v.strip() for v in (make, model)):
                raise ValueError("plate_vehicle_name_missing")
            vin = VinRequest(vin=row["vin"], model_year=attrs["year"], vehicle_id=request.vehicle_id)
        except httpx.HTTPError:
            raise ProviderError("plate_provider_unavailable") from None
        except (KeyError, TypeError, ValueError, ValidationError):
            raise ProviderError("plate_invalid_response") from None
        return vin, make, model, attrs
