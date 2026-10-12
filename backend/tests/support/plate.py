from tests.support.vin import VIN

PLATE = "TEST123"

RESPONSE = {
    "status": "success",
    "data": {
        "intro": {"vin": VIN, "license": PLATE, "state": "CA"},
        "basic": {"make": "BMW", "model": "X3", "year": "2011"},
    },
}
