import httpx

from gaswise.providers.vehicles.vin import check_digit
from tests.support.vehicles import RECORD

PATTERN = "5UXWX7C50BA000000"

VIN = PATTERN[:8] + check_digit(PATTERN) + PATTERN[9:]

DECODE = {
    "VIN": VIN,
    "ErrorCode": "0",
    "Make": "BMW",
    "Model": "X3",
    "ModelYear": "2011",
    "Trim": "xDrive35i",
    "DisplacementL": "3.0",
    "EngineCylinders": "6",
    "DriveType": "AWD/All-Wheel Drive",
    "FuelTypePrimary": "Gasoline",
    "BodyClass": "Sport Utility Vehicle [SUV]/Multipurpose Vehicle [MPV]",
}


def decoder(changes=None):
    def handle(request):
        assert request.method == "POST"
        assert VIN not in str(request.url)
        assert VIN.encode() in request.content
        return httpx.Response(200, json={"Results": [{**DECODE, **(changes or {})}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handle))


def catalog(request):
    if request.url.path.endswith("/menu/make"):
        rows = [{"text": "BMW", "value": "BMW"}]
    elif request.url.path.endswith("/menu/model"):
        rows = [{"text": "X3 xDrive35i", "value": "X3 xDrive35i"}]
    elif request.url.path.endswith("/menu/options"):
        rows = [{"text": "Automatic 8-spd, 6 cyl, 3.0 L", "value": "123"}]
    else:
        return httpx.Response(
            200,
            json={
                **RECORD,
                "year": "2011",
                "make": "BMW",
                "model": "X3 xDrive35i",
                "displ": "3.0",
                "cylinders": "6",
                "drive": "All-Wheel Drive",
            },
        )
    return httpx.Response(200, json={"menuItem": rows})
