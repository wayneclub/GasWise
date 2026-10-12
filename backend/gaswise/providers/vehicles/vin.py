"""NHTSA vPIC POST decoding: no VIN URL, persisted VIN cache, or retries."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import httpx

from gaswise.contracts.vehicles import VinDecoded
from gaswise.domain.ports import ProviderError

URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVINValuesBatch/"


def check_digit(vin):
    letters = dict(
        zip("ABCDEFGHJKLMNPRSTUVWXYZ", [1, 2, 3, 4, 5, 6, 7, 8, 1, 2, 3, 4, 5, 7, 9, 2, 3, 4, 5, 6, 7, 8, 9])
    )
    weights = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]
    remainder = sum((int(c) if c.isdigit() else letters[c]) * w for c, w in zip(vin, weights)) % 11
    return "X" if remainder == 10 else str(remainder)


def number(value, integer=False):
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result <= 0 or (integer and result != result.to_integral_value()):
            raise ValueError("invalid_number")
        return int(result) if integer else result
    except (InvalidOperation, ValueError):
        raise ProviderError("vin_invalid_response") from None


class VinProvider:
    def __init__(self, client):
        self.client = client

    async def decode(self, request):
        data = request.vin + ("," + str(request.model_year) if request.model_year is not None else "")
        try:
            response = await self.client.post(URL, data={"format": "json", "data": data})
            response.raise_for_status()
            result = response.json()
            rows = result["Results"]
            if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
                raise ValueError("invalid_results")
            row = rows[0]
            if row.get("VIN", "").upper() != request.vin:
                raise ValueError("vin_echo_mismatch")
        except httpx.HTTPError:
            raise ProviderError("vin_provider_unavailable") from None
        except (KeyError, ValueError, TypeError, AttributeError):
            raise ProviderError("vin_invalid_response") from None
        code = row.get("ErrorCode")
        if not isinstance(code, str) or not code:
            raise ProviderError("vin_invalid_response")

        def text(key):
            value = row.get(key)
            if value is None or value == "":
                return None
            if not isinstance(value, str):
                raise ProviderError("vin_invalid_response")
            return value

        decoded = VinDecoded(
            vin_masked="*" * 13 + request.vin[-4:],
            fetched_at=datetime.now(UTC),
            check_digit_matches=check_digit(request.vin) == request.vin[8],
            error_codes=[c.strip() for c in code.split(",")],
            year=number(row.get("ModelYear"), integer=True),
            make=text("Make"),
            model=text("Model"),
            series=text("Series"),
            trim=text("Trim"),
            body_class=text("BodyClass"),
            drive=text("DriveType"),
            engine_liters=number(row.get("DisplacementL")),
            cylinders=number(row.get("EngineCylinders"), integer=True),
            engine_model=text("EngineModel"),
            fuel_primary=text("FuelTypePrimary"),
            fuel_secondary=text("FuelTypeSecondary"),
            transmission=text("TransmissionStyle"),
            transmission_speeds=number(row.get("TransmissionSpeeds"), integer=True),
            electrification=text("ElectrificationLevel"),
        )
        if request.model_year is not None and decoded.year is not None and decoded.year != request.model_year:
            raise ProviderError("vin_model_year_mismatch")
        return decoded
