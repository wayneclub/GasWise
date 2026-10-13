"""Observed Google Maps website directions over HTTP; no paid API fallback."""

import json
import math
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit

import httpx

from gaswise.contracts.common import Route
from gaswise.domain.ports import ProviderError


class WebRouteError(ProviderError):
    def __init__(self, code, upstream_http_requests=0):
        super().__init__(code)
        self.upstream_http_requests = upstream_http_requests


class DirectionsPreload(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag != "link" or "preload" not in attrs.get("rel", "").split() or attrs.get("as") != "fetch":
            return
        href = attrs.get("href", "")
        url = urlsplit(href)
        # Never forward credentials to a page-supplied host or arbitrary endpoint.
        if not url.scheme and not url.netloc and url.path == "/maps/preview/directions" and not url.fragment:
            self.links.append(href)


def nonnegative_number(value):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError("invalid route number")
    return value


class MapsWebRouteProvider:
    http_counter_name = "maps_web_route_http_requests"

    def __init__(self, client, maps_source=None):
        self.client, self.maps_source = client, maps_source
        self.request_budget = None

    async def route(self, origin, destination, via=None):
        points = [origin, via, destination] if via is not None else [origin, destination]
        headers = (
            self.maps_source.headers()
            if self.maps_source
            else {
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        attempted = 0

        async def get(path, **kwargs):
            nonlocal attempted
            if self.request_budget:
                try:
                    await self.request_budget.before("maps")
                except ProviderError as error:
                    raise WebRouteError(str(error), attempted) from None
            attempted += 1
            try:
                response = await self.client.get(
                    "https://www.google.com" + path, headers=headers, follow_redirects=False, **kwargs
                )
            except httpx.HTTPError:
                raise WebRouteError("google_maps_web_route_unavailable", attempted) from None
            if self.request_budget:
                try:
                    await self.request_budget.after("maps", response)
                except ProviderError as error:
                    raise WebRouteError(str(error), attempted) from None
            if response.status_code == 429:
                raise WebRouteError("google_maps_web_route_rate_limited", attempted)
            if response.is_redirect or response.status_code in (401, 403):
                raise WebRouteError("google_maps_web_route_blocked_or_redirected", attempted)
            if response.status_code != 200:
                raise WebRouteError("google_maps_web_route_unavailable", attempted)
            return response

        path = "/maps/dir/" + "/".join(f"{p.lat},{p.lng}" for p in points) + "/data=!4m2!4m1!3e0"
        page = await get(path, params={"hl": "en", "gl": "us"})
        parser = DirectionsPreload()
        try:
            parser.feed(page.text)
            if len(parser.links) != 1:
                raise ValueError("missing or ambiguous directions preload")
        except (ValueError, TypeError):
            raise WebRouteError("google_maps_web_route_schema_changed", attempted) from None
        response = await get(parser.links[0])
        if not response.text.startswith(")]}'\n"):
            raise WebRouteError("google_maps_web_route_schema_changed", attempted)
        try:
            data = json.loads(response.text.split("\n", 1)[1])
            route = self.parse(data, points)
        except (ValueError, TypeError, IndexError, KeyError, OverflowError):
            raise WebRouteError("google_maps_web_route_invalid_response", attempted) from None
        except ProviderError as error:
            raise WebRouteError(str(error), attempted) from None
        return route.model_copy(update={"upstream_http_requests": attempted})

    @staticmethod
    def parse(data, points):
        try:
            # Field positions observed in the browser's own directions response.
            echoed = data[0][0]
            if len(echoed) != len(points):
                raise ProviderError("google_maps_web_route_waypoint_mismatch")
            for row, point in zip(echoed, points, strict=True):
                lat, lng = row[0][0][2][2:4]
                if (
                    isinstance(lat, bool)
                    or isinstance(lng, bool)
                    or not isinstance(lat, (int, float))
                    or not isinstance(lng, (int, float))
                    or not math.isfinite(lat)
                    or not math.isfinite(lng)
                    or abs(lat - point.lat) > 0.000001
                    or abs(lng - point.lng) > 0.000001
                ):
                    raise ProviderError("google_maps_web_route_waypoint_mismatch")
            driving = [row for row in data[0][1] if type(row[0][0]) is int and row[0][0] == 0]
            if not driving:
                raise ProviderError("google_maps_web_no_driving_route")
            summary = driving[0][0]  # Google's first recommended driving route.
            meters = nonnegative_number(summary[2][0])
            seconds = nonnegative_number(summary[3][0])
            basis = "maps_estimate"
            if len(summary) > 10 and summary[10] is not None:
                seconds = nonnegative_number(summary[10][0][0])
                basis = "maps_traffic_estimate"
            if any(point != points[0] for point in points[1:]):
                if meters <= 0 or seconds <= 0:
                    raise ValueError("unexpected empty route")
            return Route(
                distance_meters=meters,
                duration_seconds=seconds,
                source="google_maps_web_directions",
                duration_basis=basis,
                fetched_at=datetime.now(UTC),
            )
        except (ValueError, TypeError, IndexError, KeyError, OverflowError):
            raise ProviderError("google_maps_web_route_invalid_response") from None
