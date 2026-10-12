import json

import httpx

from gaswise.contracts.common import Point

ORIGIN = Point(lat=34.03938, lng=-118.2663)


def transport(price=6.95, credit=True, timestamp=None, blocked=False, cash=True):
    metadata = {
        "Station:11034": {
            "name": "Chevron",
            "priceUnit": "dollars_per_gallon",
            "address": {
                "country": "US",
                "line1": "1516 S Main St",
                "locality": "Los Angeles",
                "region": "CA",
                "postalCode": "90015-2504",
            },
        }
    }
    html = (
        "<script>window.__APOLLO_STATE__ = "
        + json.dumps(metadata)
        + '; window.gbcsrf = "fixture-session-token";</script>'
    )

    def handler(request):
        if request.method == "GET":
            assert "search=90015" in str(request.url)
            return httpx.Response(200, text=html)
        assert request.url.path == "/graphql"
        assert request.headers["gbcsrf"] == "fixture-session-token"
        payload = json.loads(request.content)
        assert payload["variables"]["fuel"] == 3
        assert payload["variables"]["maxAge"] == 0
        if blocked:
            return httpx.Response(403, text="blocked")
        return httpx.Response(
            200,
            json={
                "data": {
                    "locationBySearchTerm": {
                        "stations": {
                            "count": 1,
                            "cursor": {"next": None},
                            "results": [
                                {
                                    "id": "11034",
                                    "prices": [
                                        {
                                            "fuelProduct": "premium_gas",
                                            "cash": {
                                                "price": 6.79,
                                                "postedTime": timestamp,
                                                "nickname": "DataFeed",
                                            }
                                            if cash
                                            else None,
                                            "credit": {
                                                "price": price,
                                                "postedTime": timestamp,
                                                "nickname": "DataFeed",
                                            }
                                            if credit
                                            else None,
                                        }
                                    ],
                                }
                            ],
                        }
                    }
                }
            },
        )

    return httpx.MockTransport(handler)
