"""Credential-free demo integration probe against the Docker frontend gateway."""
import json
import os
from urllib.request import Request, urlopen

base = os.getenv("GASWISE_SMOKE_URL", "http://127.0.0.1:8080")
with urlopen(base, timeout=10) as response:
    assert response.status == 200
    assert b'<div id="root">' in response.read()
request = Request(base + "/api/v1/smart/search", data=json.dumps({
    "origin": {"lat": 34.05, "lng": -118.25},
    "fuel_type": "premium", "mpg": "22", "gallons": "10",
    "calculate_routes": True, "route_limit": 5,
}).encode(), headers={"Content-Type": "application/json", "Origin": base}, method="POST")
with urlopen(request, timeout=30) as response:
    result = json.load(response)
assert result["snapshot"]["stations"]
assert result["ranking"]["results"]
assert not any(result["upstream_calls"].values()), "Demo must not acquire live prices/routes"
print("Container frontend, authenticated gateway and backend demo ranking passed")
