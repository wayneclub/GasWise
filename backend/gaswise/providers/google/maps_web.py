"""Google Maps website HTTP search with optional private session, no Places API.

Observed array protocol, not a documented API. No browser,
challenge bypass, retries, or automatic paid fallback. Optional authorized
Google session cookies are read only from a private local file.
"""

import json
import math
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx

from gaswise.contracts.common import Point, Station
from gaswise.contracts.sources import MAPS_WEB_PAGE_SIZE, MapsWebPrices, MapsWebSearch, MapsWebStation
from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.identity import membership_for_name

# Verified website numeric values and labels; do not infer pump octane from them.
WEB_FUEL_TYPES = {1: "diesel", 3: "regular", 4: "midgrade", 5: "premium"}

FEATURES = "!12m25!1m5!18b1!30b1!31m1!1b1!34e1!2m4!5m1!6e2!20e3!39b1!10b1!12b1!13b1!16b1!17m1!3e1!20m3!5e2!6b1!14b1!46m1!1b0!96b1!99b1!24m109!1m27!13m9!2b1!3b1!4b1!6i1!8b1!9b1!14b1!20b1!25b1!18m16!3b1!4b1!5b1!6b1!9b1!13b1!14b1!17b1!20b1!21b1!22b1!32b1!33m1!1b1!34b1!36e2!10m1!8e3!11m1!3e1!17b1!20m2!1e3!1e6!24b1!25b1!26b1!27b1!29b1!30m1!2b1!36b1!37b1!39m3!2m2!2i1!3i1!43b1!52b1!54m1!1b1!55b1!56m1!1b1!61m2!1m1!1e1!65m5!3m4!1m3!1m2!1i224!2i298!72m22!1m8!2b1!5b1!7b1!12m4!1b1!2b1!4m1!1e1!4b1!8m10!1m6!4m1!1e1!4m1!1e3!4m1!1e4!3sother_user_google_review_posts__and__hotel_and_vr_partner_review_posts!6m1!1e1!9b1!89b1!90m2!1m1!1e2!98m3!1b1!2b1!3b1!103b1!113b1!114m3!1b1!2m1!1b1!117b1!122m1!1b1!126b1!127b1!128m1!1b1"

# Selector block observed on the same Google Maps frontend, without session IDs.
DETAIL_FEATURES = "!15m111!1m29!4e2!13m9!2b1!3b1!4b1!6i1!8b1!9b1!14b1!20b1!25b1!18m17!3b1!4b1!5b1!6b1!9b1!13b1!14b1!17b1!20b1!21b1!22b1!30b1!32b1!33m1!1b1!34b1!36e2!10m1!8e3!11m1!3e1!17b1!20m2!1e3!1e6!24b1!25b1!26b1!27b1!29b1!30m1!2b1!36b1!37b1!39m3!2m2!2i1!3i1!43b1!52b1!54m1!1b1!55b1!56m1!1b1!61m2!1m1!1e1!65m5!3m4!1m3!1m2!1i224!2i298!72m22!1m8!2b1!5b1!7b1!12m4!1b1!2b1!4m1!1e1!4b1!8m10!1m6!4m1!1e1!4m1!1e3!4m1!1e4!3sother_user_google_review_posts__and__hotel_and_vr_partner_review_posts!6m1!1e1!9b1!89b1!90m2!1m1!1e2!98m3!1b1!2b1!3b1!103b1!113b1!114m3!1b1!2m1!1b1!117b1!122m1!1b1!126b1!127b1!128m1!1b1"


def distance(a: Point, b: Point) -> float:
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat, dlng = lat2 - lat1, math.radians(b.lng - a.lng)
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(value)))


def opening_from_row(row) -> dict:
    """Observed field 203 status labels; the search request pins hl=en for these strings."""
    # Observed field 23 = 1 on the native permanently-closed Shell page.
    if len(row) > 23 and row[23] == 1:
        return {"open_now": False, "business_status": "permanently_closed", "opening_status": "Permanently closed"}
    try:
        block = row[203][1]
        label = block[4][0] if isinstance(block[4], list) else None
        short = block[8][0] if isinstance(block[8], list) else label
    except (IndexError, TypeError, KeyError):
        return {"open_now": None, "business_status": None, "opening_status": None}
    text = " ".join(x for x in (short, label) if isinstance(x, str)).lower()
    business = (
        "permanently_closed"
        if "permanently closed" in text
        else "temporarily_closed"
        if "temporarily closed" in text
        else None
    )
    first = short.lower() if isinstance(short, str) else ""
    if business or first.startswith(("closed", "opens")):
        open_now = False
    elif first.startswith(("open", "closes")):
        open_now = True
    else:
        open_now = None
    return {
        "open_now": open_now,
        "business_status": business or ("operational" if open_now is not None else None),
        "opening_status": label if isinstance(label, str) else None,
    }


def records(node):
    if not isinstance(node, list):
        return
    if len(node) > 243 and isinstance(node[10], str) and isinstance(node[11], str):
        yield node
        return  # Never attribute nested neighboring places' prices to this station.
    for child in node:
        yield from records(child)


class MapsWebProvider:
    def __init__(self, client: httpx.AsyncClient, session_file: Path | None = None):
        self.client = client
        self.session_file = session_file

    async def stations(self, query):
        # Normalized browsing stays one search; detail enrichment belongs to the
        # explicitly bounded smart-search request.
        return (
            await self.prices(
                MapsWebSearch(
                    origin=query.origin,
                    fuel_type=query.fuel_type,
                    radius_meters=query.radius_meters,
                    max_results=20,
                    detail_limit=0,
                )
            )
        ).stations

    def headers(self):
        headers = {
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
            "x-maps-diversion-context-bin": "CAE=",
        }
        if self.session_file is None:
            return headers
        try:
            path = Path(self.session_file)
            if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
                raise ValueError()
            if path.stat().st_size > 100000:
                raise ValueError()
            payload = json.loads(path.read_text())
            cookies = []
            now = datetime.now(UTC).timestamp()
            for cookie in payload["cookies"]:
                if cookie["domain"] not in (".google.com", "www.google.com") or cookie["path"] != "/":
                    continue
                name, value = cookie["name"], cookie["value"]
                if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", name):
                    raise ValueError()
                if not isinstance(value, str) or not value.isascii() or any(c in value for c in "\r\n;"):
                    raise ValueError()
                expires = cookie.get("expires", -1)
                if not isinstance(expires, (int, float)) or not math.isfinite(expires):
                    raise ValueError()
                if expires > 0 and expires <= now:
                    continue
                cookies.append((name, value))
            if not any(name in ("SID", "__Secure-3PSID", "__Secure-1PSID") for name, _ in cookies):
                raise ProviderError("google_maps_web_session_expired")
            headers["Cookie"] = "; ".join(name + "=" + value for name, value in cookies)
        except ProviderError:
            raise
        except (OSError, ValueError, KeyError, TypeError):
            raise ProviderError("google_maps_web_private_session_invalid") from None
        return headers

    async def get_data(self, path, params, headers):
        # Both paths are fixed Google endpoints, never caller-controlled URLs.
        if path not in ("/search", "/maps/preview/place"):
            raise ProviderError("google_maps_web_invalid_endpoint")
        try:
            response = await self.client.get(
                "https://www.google.com" + path,
                params=params,
                headers=headers,
                follow_redirects=False,
            )
        except httpx.HTTPError:
            raise ProviderError("google_maps_web_unavailable") from None
        if response.status_code in (401, 403) or response.is_redirect:
            raise ProviderError(
                "google_maps_web_session_rejected"
                if "Cookie" in headers
                else "google_maps_web_blocked_or_redirected"
            )
        if response.status_code == 429:
            raise ProviderError("google_maps_web_rate_limited")
        if response.status_code != 200:
            raise ProviderError("google_maps_web_unavailable")
        if not response.text.startswith(")]}'"):
            raise ProviderError("google_maps_web_unexpected_response")
        try:
            return json.loads(response.text.split("\n", 1)[1])
        except (ValueError, IndexError):
            raise ProviderError("google_maps_web_unexpected_response") from None

    async def prices(self, query: MapsWebSearch) -> MapsWebPrices:
        headers = self.headers()  # Validate credentials before making any request.
        pb = (
            f"!4m12!1m3!1d{query.radius_meters * 5}!2d{query.origin.lng}!3d{query.origin.lat}"
            f"!2m3!1f0!2f0!3f0!3m2!1i1280!2i720!4f13.1!7i{MAPS_WEB_PAGE_SIZE}!10b1" + FEATURES
        )
        data = await self.get_data(
            "/search", {"tbm": "map", "hl": "en", "gl": "us", "pb": pb, "q": query.search_text}, headers
        )
        initial = self.parse(data, query)
        indexed = {}
        for row in records(data):
            if isinstance(row[78], str):
                indexed.setdefault(row[78], row)
        priced = {s.canonical_id for s in initial.stations}
        count, warnings = 0, []
        # Regular search cards stay a single request. Other grades get bounded detail enrichment.
        if self.session_file is not None and query.fuel_type != "regular":
            for candidate in initial.inventory:
                if count >= query.detail_limit:
                    break
                if "google_places:" + candidate.place_id in priced:
                    continue
                row = indexed[candidate.place_id]
                if not re.fullmatch(r"0x[0-9a-f]+:0x[0-9a-f]+", row[10], re.IGNORECASE):
                    continue
                detail_pb = (
                    f"!1m6!1s{row[10]}!3m1!1d1000!4m2!3d{candidate.location.lat}!4d{candidate.location.lng}"
                    "!3m1!1e3" + DETAIL_FEATURES
                )
                count += 1
                try:
                    detail = await self.get_data(
                        "/maps/preview/place",
                        {
                            "authuser": "0",
                            "hl": "en",
                            "gl": "us",
                            "pb": detail_pb,
                            "q": candidate.name,
                        },
                        headers,
                    )
                    matching = [r for r in records(detail) if r[78] == candidate.place_id]
                    if not matching:
                        raise ProviderError("google_maps_web_detail_identity_mismatch")
                    row[86] = matching[0][86]
                except ProviderError as error:
                    warnings.append(str(error))
                    # A rejected/limited request ends enrichment, avoiding repeated failures.
                    break
        result = self.parse(data, query)
        result.authentication = "session" if self.session_file is not None else "anonymous"
        result.detail_requests = count
        result.upstream_http_requests = 1 + count
        result.warnings.extend(warnings)
        if count:
            result.warnings.append(
                "Only a bounded candidate subset was checked for full fuel tables; use detail_limit to control requests."
            )
        return result

    @staticmethod
    def parse(data, query: MapsWebSearch) -> MapsWebPrices:
        now = datetime.now(UTC)
        inventory, quotes, all_quotes, seen = [], [], [], set()
        found = False
        candidates, reach = set(), None
        for row in records(data):
            found = True
            try:
                if isinstance(row[78], str) and isinstance(row[9], list):
                    candidates.add(row[78])
                    meters = distance(query.origin, Point(lat=row[9][2], lng=row[9][3]))
                    reach = meters if reach is None else max(reach, meters)
            except (ValueError, TypeError, IndexError):
                pass
            try:
                if (
                    row[243] != "US"
                    or not isinstance(row[9], list)
                    or not isinstance(row[13], list)
                    or not {"Gas station", "Truck stop", "Diesel fuel supplier"}.intersection(row[13])
                ):
                    continue
                place_id = row[78]
                if not isinstance(place_id, str) or place_id in seen:
                    continue
                point = Point(lat=row[9][2], lng=row[9][3])
                meters = distance(query.origin, point)
                if meters > query.radius_meters:
                    continue
                seen.add(place_id)
                address = ", ".join(row[2]) if isinstance(row[2], list) else None
                prices = []
                # Observed place response field 86; field 88 is the search summary.
                # This is not a Places API field number or an official wire contract.
                block = row[86]
                if isinstance(block, list) and block and isinstance(block[0], list):
                    for fuel in block[0]:
                        if not isinstance(fuel, list) or len(fuel) < 8:
                            continue
                        if fuel[3] != "gallon" or fuel[5] != "USD":
                            continue
                        kind = str(fuel[7]).lower()
                        if WEB_FUEL_TYPES.get(fuel[1]) != kind:
                            continue
                        try:
                            price = Decimal(str(fuel[6]))
                            if not price.is_finite() or price <= 0:
                                continue
                            stamp = (
                                datetime.fromtimestamp(fuel[2], UTC)
                                if type(fuel[2]) in (int, float)
                                else None
                            )
                        except (ValueError, OverflowError, TypeError, ArithmeticError, OSError):
                            continue
                        prices.append((kind, price, stamp))
                # Search card summaries have no price-update timestamp.
                if not prices and isinstance(row[88], list) and row[88]:
                    match = re.fullmatch(
                        r"\$(\d+(?:\.\d+)?)/(Regular|Midgrade|Premium|Diesel)", str(row[88][0])
                    )
                    if match:
                        prices.append((match[2].lower(), Decimal(match[1]), None))
                opening = opening_from_row(row)
                rating_block = row[4] if isinstance(row[4], list) else []
                rating = rating_block[7] if len(rating_block) > 7 else None
                reviews = rating_block[8] if len(rating_block) > 8 else None
                rating = rating if type(rating) in (int, float) and math.isfinite(rating) and 0 <= rating <= 5 else None
                reviews = reviews if type(reviews) is int and reviews >= 0 else None
                rating_fields = {"rating": rating, "review_count": reviews, "rating_source": "Google Maps" if rating is not None else None}
                inventory.append(
                    MapsWebStation(
                        place_id=place_id,
                        name=row[11],
                        location=point,
                        address=address,
                        distance_meters=round(meters, 1),
                        **rating_fields,
                        available_fuel_types=[p[0] for p in prices],
                        **opening,
                    )
                )
                for kind, price, stamp in prices:
                    if price <= 0:
                        continue
                    station = Station(
                        id=f"google_maps_web:{place_id}",
                        canonical_id=f"google_places:{place_id}",
                        name=row[11],
                        location=point,
                        address=address,
                        price_per_gallon=price,
                        fuel_type=kind,
                        price_updated_at=stamp,
                        fetched_at=now,
                        source="google_maps_web",
                        attribution=["Google Maps"],
                        **rating_fields,
                        membership_required=membership_for_name(row[11]),
                        open_now=opening["open_now"],
                        business_status=opening["business_status"],
                        details={"opening_status": opening["opening_status"]}
                        if opening["opening_status"]
                        else {},
                    )
                    all_quotes.append(station)
                    if kind == query.fuel_type:
                        quotes.append(station)
            except (ValueError, TypeError, IndexError, OverflowError):
                continue
        if not found:
            # Empty recognized search is distinct from a changed wire format.
            if not (
                isinstance(data, list)
                and data
                and isinstance(data[0], list)
                and len(data[0]) > 1
                and isinstance(data[0][1], list)
            ):
                raise ProviderError("google_maps_web_schema_changed")
        inventory.sort(key=lambda item: item.distance_meters)
        inventory = inventory[: query.max_results]
        ids = {item.place_id for item in inventory}
        quotes = [q for q in quotes if q.id.split(":", 1)[1] in ids]
        all_quotes = [q for q in all_quotes if q.id.split(":", 1)[1] in ids]
        warnings = [
            "Undocumented website protocol; results are a bounded sample, not every station in the area.",
            "Search summaries usually provide Regular only; missing fuel types are not substituted.",
            "Payment conditions and octane are unknown. A missing update time remains unknown.",
            "Opening status is the website's label at retrieval time, not a pump-level availability check.",
        ]
        if not quotes:
            warnings.append(f"No {query.fuel_type} price was supplied for the returned candidates.")
        return MapsWebPrices(
            stations=quotes,
            all_prices=all_quotes,
            inventory=inventory,
            warnings=warnings,
            candidate_count=len(candidates),
            candidate_reach_meters=reach,
        )
