"""Read-only probe of the undocumented endpoint used by WME community scripts.

Not a production provider. No authentication, cookies, retries or challenge handling.
"""

import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venue-id", default="158400853.1584008528.5847665")
    parser.add_argument("--lat", type=float, default=34.0833736)
    parser.add_argument("--lon", type=float, default=-118.3008564)
    parser.add_argument("--http-session", action="store_true", help="Test ordinary HTTP/2 editor session bootstrap")
    args = parser.parse_args()
    url = "https://www.waze.com/SearchServer/mozi?" + urlencode(
        {"lon": args.lon, "lat": args.lat, "format": "PROTO_JSON_FULL", "venue_id": f"venues.{args.venue_id}"}
    )
    if args.http_session:
        import httpx

        with httpx.Client(
            http2=True,
            follow_redirects=True,
            timeout=20,
            headers={"User-Agent": "GasWise/0.5 anonymous fuel comparison"},
        ) as client:
            for landing in ("https://www.waze.com/", "https://www.waze.com/editor"):
                response = client.get(landing)
                print(json.dumps({"step": "landing", "http_status": response.status_code, "http_version": response.http_version, "cookie_count": len(client.cookies)}))
                if not response.is_success:
                    return 1
            headers = {"Referer": "https://www.waze.com/editor", "Accept": "application/json"}
            response = client.get("https://www.waze.com/Descartes/app/Session", params={"language": "en"}, headers=headers)
            print(json.dumps({"step": "editor_session", "http_status": response.status_code, "cookie_count": len(client.cookies)}))
            if not response.is_success:
                print(json.dumps({"status": "session_rejected", "prices_verified": False}))
                return 1
            response = client.get(url + "&origin=editor", headers=headers)
            if not response.is_success:
                print(json.dumps({"status": "rejected", "http_status": response.status_code, "prices_verified": False}))
                return 1
            try:
                payload = response.json()
            except ValueError:
                print(json.dumps({"status": "invalid_json", "prices_verified": False}))
                return 1
            products = (payload.get("venue") or {}).get("product") or []
            fuels = [{key: p.get(key) for key in ("id", "price", "last_updated")} for p in products if str(p.get("id", "")).startswith("gas.")]
            print(json.dumps({"status": "received", "fuels": fuels, "prices_verified": bool(fuels)}))
            return 0 if fuels else 1
    try:
        with urlopen(url, timeout=20) as response:
            payload = json.load(response)
    except HTTPError as error:
        print(json.dumps({"status": "rejected", "http_status": error.code, "prices_verified": False}))
        return 1
    except (URLError, ValueError) as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__, "prices_verified": False}))
        return 1
    venue = payload.get("venue") or {}
    products = venue.get("product") or []
    fuels = [
        {key: product.get(key) for key in ("id", "price", "last_updated")}
        for product in products
        if str(product.get("id", "")).startswith("gas.")
    ]
    print(json.dumps({"status": "received", "venue_id": args.venue_id, "price_unit": payload.get("price_unit"), "fuels": fuels, "prices_verified": bool(fuels)}))
    return 0 if fuels else 1


if __name__ == "__main__":
    raise SystemExit(main())
