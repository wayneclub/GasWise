"""Observed GasBuddy website protocol. Not a documented/contracted public API.

Read one search page and its normal anonymous SearchPrices request. Session CSRF
is obtained from that same page, never from a user's account or hardcoded token.
No challenge solving, stealth, proxy rotation, private account data or retries.
"""

import asyncio
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlencode

import httpx

from gaswise.contracts.common import Point, Station
from gaswise.contracts.search import Search
from gaswise.contracts.sources import GasBuddyPrices, GasBuddyQuote, GasBuddySearch, gasbuddy_variables
from gaswise.domain.ports import ProviderError

# Exact public SearchPrices document observed from normal page loading.
PRICE_QUERY = """query SearchPrices($brandId: Int, $cursor: String, $fuel: Int, $lat: Float, $lng: Float, $maxAge: Int, $search: String) {
  locationBySearchTerm(
    lat: $lat
    lng: $lng
    search: $search
    priority: "locality"
  ) {
    displayName
    stations(
      brandId: $brandId
      cursor: $cursor
      fuel: $fuel
      lat: $lat
      lng: $lng
      maxAge: $maxAge
      priority: "locality"
    ) {
      count
      cursor {
        next
        __typename
      }
      results {
        id
        offers {
          discounts {
            grades
            highlight
            pwgbDiscount
            receiptDiscount
            __typename
          }
          highlight
          id
          types
          use
          __typename
        }
        payStatus {
          isPayAvailable
          __typename
        }
        prices {
          cash {
            nickname
            postedTime
            price
            formattedPrice
            __typename
          }
          credit {
            nickname
            postedTime
            price
            formattedPrice
            __typename
          }
          discount
          fuelProduct
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}"""


class GasBuddyWebProvider:
    fuels = {
        "regular": (1, "regular_gas"),
        "midgrade": (2, "midgrade_gas"),
        "premium": (3, "premium_gas"),
        "diesel": (4, "diesel"),
    }

    def __init__(self, client: httpx.AsyncClient, locator=None, snapshot_loader=None, transport="browser"):
        self.client, self.locator = client, locator
        self.lock = asyncio.Lock()
        self.snapshot_loader = snapshot_loader
        self.transport = transport if snapshot_loader else "http"

    async def prices(self, query: Search) -> GasBuddyPrices:
        if (
            not query.postal_code
            and not getattr(query, "search", None)
            and (not isinstance(query, GasBuddySearch) or query.origin is None)
        ):
            raise ProviderError("gasbuddy_postal_code_required")
        fuel, product = self.fuels[query.fuel_type]
        params = {k: v for k, v in gasbuddy_variables(query, fuel).items() if v is not None}
        params["method"] = "all" if query.payment_type == "cash_or_credit" else query.payment_type
        url = "https://www.gasbuddy.com/home?" + urlencode(params)
        if self.snapshot_loader is not None:
            state, listing = await self.snapshot_loader(query, url, fuel)
        else:
            # Serialize the page + CSRF request so concurrent searches cannot cross sessions.
            async with self.lock:
                try:
                    headers = {"User-Agent": "GasWise/0.2 price comparison prototype"}
                    home = await self.client.get(url, headers=headers)
                    if not home.is_success:
                        raise ProviderError("gasbuddy_web_access_rejected")
                    marker = "window.__APOLLO_STATE__ = "
                    offset = home.text.index(marker) + len(marker)
                    state, _ = json.JSONDecoder().raw_decode(home.text[offset:])
                    token = re.search(r'window\.gbcsrf\s*=\s*"([^"\n]+)"', home.text)
                    if token is None:
                        raise ProviderError("gasbuddy_web_schema_changed")
                    response = await self.client.post(
                        "https://www.gasbuddy.com/graphql",
                        headers={
                            **headers,
                            "Referer": url,
                            "Origin": "https://www.gasbuddy.com",
                            "apollo-require-preflight": "true",
                            "gbcsrf": token.group(1),
                        },
                        json={
                            "operationName": "SearchPrices",
                            "query": PRICE_QUERY,
                            "variables": gasbuddy_variables(query, fuel),
                        },
                    )
                    if not response.is_success:
                        raise ProviderError("gasbuddy_web_access_rejected")
                    data = response.json()
                    if data.get("errors"):
                        raise ProviderError("gasbuddy_web_query_rejected")
                    listing = data["data"]["locationBySearchTerm"]["stations"]
                except httpx.RequestError:
                    raise ProviderError("gasbuddy_web_unavailable") from None
                except (ValueError, KeyError, TypeError, AttributeError):
                    raise ProviderError("gasbuddy_web_schema_changed") from None
        fetched = datetime.now(UTC)
        quotes = []
        try:
            for item in listing["results"]:
                metadata = state.get(f"Station:{item['id']}", {})
                address = metadata.get("address", {})
                if address.get("country") != "US" or metadata.get("priceUnit") != "dollars_per_gallon":
                    continue
                for report in item.get("prices", []):
                    if report.get("fuelProduct") != product:
                        continue
                    # Explicit payment requests never substitute another payment basis.
                    method = query.payment_type
                    if method == "cash_or_credit":
                        available = [
                            (Decimal(str(report[m]["price"])), m)
                            for m in ("cash", "credit")
                            if report.get(m) and Decimal(str(report[m].get("price", 0))) > 0
                        ]
                        if not available:
                            continue
                        method = min(available)[1]
                    methods = [method]
                    if isinstance(query, GasBuddySearch) and query.include_payment_variants and query.payment_type == "cash_or_credit":
                        methods = [m for m in ("cash", "credit") if report.get(m)]
                    for method in methods:
                        price = report.get(method)
                        if not price or Decimal(str(price.get("price", 0))) <= 0:
                            continue
                        posted = datetime.fromisoformat(price["postedTime"]) if price.get("postedTime") else None
                        age_limit = query.max_price_age_minutes if isinstance(query, GasBuddySearch) else None
                        if age_limit is not None and (
                            posted is None
                            or posted.tzinfo is None
                            or (fetched - posted).total_seconds() < 0
                            or (fetched - posted).total_seconds() > age_limit * 60
                        ):
                            continue
                        quotes.append(
                            GasBuddyQuote(
                                id=str(item["id"]),
                                name=metadata["name"],
                                membership_required="costco"
                                if metadata["name"].strip().casefold() == "costco"
                                else None,
                                address=f"{address['line1']}, {address['locality']}, {address['region']} {address['postalCode']}",
                                street=address["line1"],
                                city=address["locality"],
                                region=address["region"],
                                postal_code=address["postalCode"],
                                price_per_gallon=Decimal(str(price["price"])),
                                fuel_type=query.fuel_type,
                                payment_type=method,
                                price_updated_at=posted,
                                fetched_at=fetched,
                                source_url=f"https://www.gasbuddy.com/station/{item['id']}",
                                report_kind="datafeed"
                                if (price.get("nickname") or "").lower() == "datafeed"
                                else "community"
                                if price.get("nickname")
                                else "unknown",
                            )
                        )
        except (ValueError, KeyError, TypeError, AttributeError, ArithmeticError):
            raise ProviderError("gasbuddy_web_schema_changed") from None
        quotes.sort(key=lambda quote: (quote.price_per_gallon, quote.id))
        station_ids = list(dict.fromkeys(quote.id for quote in quotes))
        truncated = len(station_ids) > query.max_results
        allowed_ids = set(station_ids[:query.max_results])
        return GasBuddyPrices(
            fetched_at=fetched,
            transport=self.transport,
            postal_code=query.postal_code,
            search=getattr(query, "search", None) or query.postal_code,
            prices=[quote for quote in quotes if quote.id in allowed_ids],
            partial=bool((listing.get("cursor") or {}).get("next")) or truncated,
            warnings=[
                "Website protocol is undocumented and can change or reject access.",
                "Premium does not verify numeric octane; source timestamps are not retrieval timestamps.",
                "Prices sorted after filtering the complete fetched page; additional upstream pages may exist.",
                "ZIP search uses upstream ZIP coverage, not a nearby radius; use city search to include surrounding stations.",
            ],
        )

    async def stations(self, query: Search) -> list[Station]:
        if self.locator is None:
            raise ProviderError("gasbuddy_station_locator_not_configured")
        prices = await self.prices(query)

        async def locate(quote):
            located = await self.locator.locate_station(quote)
            if located is None:
                return None
            place_id, point = located
            return Station(
                id=quote.id,
                canonical_id=f"google_places:{place_id}",
                name=quote.name,
                location=Point(**point),
                address=quote.address,
                price_per_gallon=quote.price_per_gallon,
                fuel_type=quote.fuel_type,
                octane=None,
                price_updated_at=quote.price_updated_at,
                fetched_at=quote.fetched_at,
                source="gasbuddy_web",
                payment_type=quote.payment_type,
                membership_required="costco"
                if "costco" in quote.name.lower()
                else "sams_club"
                if "sam's club" in quote.name.lower()
                else None,
                attribution=["GasBuddy", "Google Maps"],
            )

        stations = await asyncio.gather(*(locate(q) for q in prices.prices))
        return [station for station in stations if station is not None]
