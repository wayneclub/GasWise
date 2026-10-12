from datetime import UTC, datetime
from decimal import Decimal

import httpx

from gaswise.contracts.common import Point, Route, Station
from gaswise.contracts.search import Search
from gaswise.contracts.sources import GooglePriceSearch
from gaswise.domain.ports import ProviderError


class GoogleProvider:
    types = {"regular": "REGULAR_UNLEADED", "midgrade": "MIDGRADE", "premium": "PREMIUM", "diesel": "DIESEL"}

    def __init__(self, client: httpx.AsyncClient, key: str):
        self.client, self.key = client, key

    async def request(self, url, body, mask):
        # A request is one upstream attempt: no hidden retries consuming quota.
        # Do not propagate upstream bodies, which can expose account information.
        try:
            response = await self.client.post(
                url, json=body, headers={"X-Goog-Api-Key": self.key, "X-Goog-FieldMask": mask}
            )
        except httpx.RequestError:
            raise ProviderError("upstream_unavailable") from None
        if response.status_code == 429:
            raise ProviderError("google_quota_or_rate_limit_exceeded")
        if not response.is_success:
            raise ProviderError(
                "upstream_unavailable" if response.status_code >= 500 else "upstream_rejected_request"
            )
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("expected object")
            return payload
        except ValueError:
            raise ProviderError("upstream_invalid_response") from None

    async def nearby_places(self, query: Search | GooglePriceSearch):
        return await self.request(
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
            # businessStatus/openNow stay within the Enterprise + Atmosphere SKU fuelOptions already triggers.
            "places.id,places.displayName,places.location,places.fuelOptions,places.attributions,"
            "places.addressComponents,places.businessStatus,places.currentOpeningHours.openNow,places.rating,places.userRatingCount",
        )

    async def stations(self, query: Search | GooglePriceSearch) -> list[Station]:
        return self.prices_from_places(await self.nearby_places(query), query)

    @staticmethod
    def opening(place) -> dict:
        open_now = (place.get("currentOpeningHours") or {}).get("openNow")
        return {
            "open_now": open_now if isinstance(open_now, bool) else None,
            "business_status": {
                "OPERATIONAL": "operational",
                "CLOSED_TEMPORARILY": "temporarily_closed",
                "CLOSED_PERMANENTLY": "permanently_closed",
            }.get(place.get("businessStatus")),
        }

    def prices_from_places(self, data, query) -> list[Station]:
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
                            rating=place.get("rating"),
                            review_count=place.get("userRatingCount"),
                            rating_source="Google Maps" if place.get("rating") is not None else None,
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
                            **self.opening(place),
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
        return self.locate_from_places(data, quote)

    @staticmethod
    def locate_from_places(data, quote):
        import re

        def normalized(value):
            return re.sub(r"[^a-z0-9]", "", value.lower())

        try:
            matches = []
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
                matches.append(
                    (
                        place["id"],
                        {
                            "lat": place["location"]["latitude"],
                            "lng": place["location"]["longitude"],
                        },
                    )
                )
            return matches[0] if len(matches) == 1 else None
        except (KeyError, ValueError, TypeError):
            raise ProviderError("station_location_invalid_response") from None
        return None
