import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from gaswise.models import GooglePriceSearch, Point, Route, Search, Station
from gaswise.providers.base import ProviderError


class GoogleProvider:
    types = {"regular": "REGULAR_UNLEADED", "midgrade": "MIDGRADE", "premium": "PREMIUM", "diesel": "DIESEL"}

    def __init__(self, client: httpx.AsyncClient, key: str):
        self.client, self.key = client, key

    async def request(self, url, body, mask):
        # Do not propagate upstream bodies, which can expose account information.
        for attempt in range(3):
            try:
                response = await self.client.post(
                    url, json=body, headers={"X-Goog-Api-Key": self.key, "X-Goog-FieldMask": mask}
                )
            except httpx.RequestError:
                if attempt == 2:
                    raise ProviderError("upstream_unavailable") from None
            else:
                if response.is_success:
                    try:
                        payload = response.json()
                        if not isinstance(payload, dict):
                            raise ValueError("expected object")
                        return payload
                    except ValueError:
                        raise ProviderError("upstream_invalid_response") from None
                if response.status_code not in (429, 500, 502, 503, 504):
                    raise ProviderError("upstream_rejected_request")
                if attempt == 2:
                    raise ProviderError("upstream_unavailable")
            await asyncio.sleep(0.25 * 2**attempt)

    async def stations(self, query: Search | GooglePriceSearch) -> list[Station]:
        data = await self.request(
            "https://places.googleapis.com/v1/places:searchNearby",
            {
                "includedTypes": ["gas_station"],
                "maxResultCount": query.max_results,
                "locationRestriction": {
                    "circle": {
                        "center": {"latitude": query.origin.lat, "longitude": query.origin.lng},
                        "radius": query.radius_meters,
                    }
                },
            },
            "places.id,places.displayName,places.location,places.fuelOptions,places.attributions,places.addressComponents",
        )
        now = datetime.now(UTC)
        stations = []
        try:
            for place in data.get("places", []):
                if not any(
                    "country" in c.get("types", []) and c.get("shortText") == "US"
                    for c in place.get("addressComponents", [])
                ):
                    continue
                for fuel in place.get("fuelOptions", {}).get("fuelPrices", []):
                    money = fuel.get("price", {})
                    if fuel.get("type") != self.types[query.fuel_type] or money.get("currencyCode") != "USD":
                        continue
                    price = Decimal(money.get("units", "0")) + Decimal(str(money.get("nanos", 0))) / Decimal(
                        10**9
                    )
                    if price <= 0:
                        continue
                    stations.append(
                        Station(
                            id=place["id"],
                            name=place.get("displayName", {}).get("text", "Gas station"),
                            location=Point(
                                lat=place["location"]["latitude"], lng=place["location"]["longitude"]
                            ),
                            price_per_gallon=price,
                            fuel_type=query.fuel_type,
                            price_updated_at=datetime.fromisoformat(fuel["updateTime"].replace("Z", "+00:00"))
                            if fuel.get("updateTime")
                            else None,
                            fetched_at=now,
                            source="google_places",
                            # Premium has no numeric octane guarantee. Membership also needs a separate verified source.
                            membership_required="costco"
                            if "costco" in place.get("displayName", {}).get("text", "").lower()
                            else "sams_club"
                            if "sam's club" in place.get("displayName", {}).get("text", "").lower()
                            else None,
                            attribution=[a.get("provider", "") for a in place.get("attributions", [])],
                        )
                    )
        except (KeyError, ValueError, TypeError, ArithmeticError, AttributeError):
            raise ProviderError("upstream_invalid_response") from None
        return stations

    async def route(self, origin: Point, destination: Point, via: Point | None = None) -> Route:
        def waypoint(point):
            return {"location": {"latLng": {"latitude": point.lat, "longitude": point.lng}}}

        body = {
            "origin": waypoint(origin),
            "destination": waypoint(destination),
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",
        }
        if via:
            body["intermediates"] = [waypoint(via)]
        data = await self.request(
            "https://routes.googleapis.com/directions/v2:computeRoutes",
            body,
            "routes.distanceMeters,routes.duration",
        )
        try:
            route = data["routes"][0]
            return Route(
                distance_meters=route["distanceMeters"],
                duration_seconds=float(route["duration"].removesuffix("s")),
                source="google_routes",
            )
        except (KeyError, IndexError, ValueError, TypeError, AttributeError):
            raise ProviderError("route_unavailable") from None

    async def locate_station(self, quote):
        """Resolve an address, then verify street/number/city before cross-provider joining."""
        import re

        def normalized(value):
            return re.sub(r"[^a-z0-9]", "", value.lower())

        data = await self.request(
            "https://places.googleapis.com/v1/places:searchText",
            {
                "textQuery": f"{quote.name} {quote.address}",
                "includedType": "gas_station",
                "strictTypeFiltering": True,
                "maxResultCount": 1,
            },
            "places.id,places.location,places.addressComponents",
        )
        try:
            for place in data.get("places", []):
                components = {
                    kind: c for c in place.get("addressComponents", []) for kind in c.get("types", [])
                }
                if components.get("country", {}).get("shortText") != "US":
                    continue
                street = (
                    components.get("street_number", {}).get("longText", "")
                    + " "
                    + components.get("route", {}).get("shortText", "")
                )
                if normalized(street) != normalized(quote.street):
                    continue
                if normalized(components.get("locality", {}).get("longText", "")) != normalized(quote.city):
                    continue
                if components.get("administrative_area_level_1", {}).get("shortText") != quote.region:
                    continue
                if components.get("postal_code", {}).get("longText") != quote.postal_code[:5]:
                    continue
                return place["id"], {
                    "lat": place["location"]["latitude"],
                    "lng": place["location"]["longitude"],
                }
        except (KeyError, ValueError, TypeError):
            raise ProviderError("station_location_invalid_response") from None
        return None
