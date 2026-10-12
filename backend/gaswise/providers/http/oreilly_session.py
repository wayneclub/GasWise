"""Per-operation anonymous HTTP session; server-issued CSRF, no browser replay."""

import json
import re
from urllib.parse import urlsplit

from curl_cffi.requests import AsyncSession, RequestsError

ROOT = "https://www.oreillyauto.com"


def csrf_from_html(html):
    match = re.search(r'[^A-Za-z]csrfToken["\x27]?\s*:\s*(["\x27])([^"\x27]+)\1', html or "")
    return match[2] if match and 8 <= len(match[2]) <= 512 else None


def browser_verification(body):
    if not body:
        return False
    try:
        data = json.loads(body)
    except (TypeError, ValueError):
        data = None
    return (
        isinstance(data, dict)
        and str(data.get("cpr_chlge")).lower() == "true"
        or "scf-akamai-logo" in body
        and "Powered and protected by" in body
    )


class OReillyHTTPSession:
    def __init__(self, session_factory=AsyncSession):
        self.session_factory = session_factory
        self.session = None
        self.csrf = None
        self._public_search_key = None
        self.failure = None
        self.stages = []
        self.selected_vehicle = None

    async def __aenter__(self):
        self.session = self.session_factory(
            impersonate="chrome", trust_env=False, timeout=15, allow_redirects=False, max_clients=1
        )
        await self.session.__aenter__()
        html = await self.read(ROOT + "/", headers={"Accept": "text/html"})
        self.csrf = csrf_from_html(html)
        key = re.search(r'["\x27]apiKey["\x27]\s*:\s*["\x27]([^"\x27]+)', html or "")
        if key and 8 <= len(key[1]) <= 512:
            self._public_search_key = key[1]
        if self.csrf:
            self.stages.append("anonymous_session_csrf")
        return self

    async def __aexit__(self, *args):
        self.csrf = None
        self._public_search_key = None
        self.selected_vehicle = None
        await self.session.__aexit__(*args)
        self.session = None

    async def search_suggestions(self, query, *, year, make, model, market_id):
        """Native type-ahead terms, never product inventory or fitment evidence."""
        if not self._public_search_key:
            self.failure = "public_search_configuration_unavailable"
            return None
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 200:
            raise ValueError("invalid_search_query")
        body = await self.read(
            ROOT + "/es/product-autocomplete/v1/autocomplete",
            params={
                "q": query.strip(),
                "size": 8,
                "marketId": market_id,
                "year": year,
                "make": make,
                "model": model,
            },
            headers={"Accept": "application/json"},
        )
        try:
            data = json.loads(body or "null")
        except ValueError:
            return None
        rows = data.get("suggestions") if isinstance(data, dict) else None
        if not isinstance(rows, list) or len(rows) > 8:
            return None
        if any(
            not isinstance(row, dict)
            or not isinstance(row.get("suggestion"), str)
            or not 1 <= len(row["suggestion"]) <= 200
            for row in rows
        ):
            return None
        self.stages.append("native_search_suggestions")
        return [row["suggestion"] for row in rows]

    async def select_vehicle(self, *, base_vehicle_id, submodel_id, engine_id, vehicle_type_id=1):
        """Set public catalog selection cookies, then verify the server's exact selection.

        These are configuration identifiers, not browser authentication cookies.
        Obtain IDs from retailer catalog responses; never guess them from vehicle names.
        """
        self.selected_vehicle = None
        if self.session is None:
            raise RuntimeError("oreilly_session_not_active")
        ids = [str(v) for v in (vehicle_type_id, base_vehicle_id, submodel_id, engine_id)]
        if any(not re.fullmatch(r"[1-9][0-9]{0,11}", v) for v in ids):
            raise ValueError("invalid_vehicle_catalog_identifier")
        selection = "-".join(ids)
        for name in ("ECV", "EGV"):
            self.session.cookies.set(name, selection, domain="www.oreillyauto.com", path="/")
        self.failure = None
        body = await self.read(ROOT + "/header/data", json_body={}, headers={"Accept": "application/json"})
        try:
            data = json.loads(body or "null")
        except (TypeError, ValueError):
            data = None
        selected = data.get("selectedVehicle") if isinstance(data, dict) else None
        if not isinstance(selected, dict) or any(
            str(selected.get(key)) != value
            for key, value in (
                ("baseVehicleId", ids[1]),
                ("vehicleId", "-".join(ids[1:])),
                ("engineId", ids[3]),
                ("vehicleTypeId", ids[0]),
            )
        ):
            self.failure = self.failure or "selected_vehicle_not_verified"
            return None
        self.selected_vehicle = selected
        self.stages.append("public_catalog_selection_verified")
        return selected

    async def vin_configuration(self, vin, *, year, make, model):
        """Resolve VIN to retailer IDs, rejecting mismatched or ambiguous configurations."""
        if not isinstance(vin, str) or not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", vin):
            raise ValueError("invalid_vin")
        body = await self.read(ROOT + "/vehicle/vin/" + vin, headers={"Accept": "application/json"})
        try:
            data = json.loads(body or "null")
        except (TypeError, ValueError):
            data = None
        if not isinstance(data, dict) or data.get("vinIsValid") is not True:
            self.failure = self.failure or "vin_configuration_unavailable"
            return None
        rows = data.get("vins")

        def normalize(value):
            return re.sub(r"[^A-Z0-9]", "", str(value).upper())

        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            self.failure = "vin_configuration_ambiguous"
            return None
        row = rows[0]
        if any(
            normalize(row.get(k)) != normalize(v)
            for k, v in (("year", year), ("make", make), ("model", model))
        ):
            self.failure = "vin_configuration_mismatch"
            return None
        result = {k: row.get(k) for k in ("year", "make", "makeId", "model", "modelId")}
        for source, destination in (("subModel", "submodel_options"), ("engine", "engine_options")):
            options = row.get(source)
            if not isinstance(options, list) or not options or len(options) > 100:
                self.failure = "vin_configuration_incomplete"
                return None
            result[destination] = []
            for option in options:
                if not isinstance(option, dict) or not re.fullmatch(
                    r"[1-9][0-9]{0,11}", str(option.get("id"))
                ):
                    self.failure = "vin_configuration_incomplete"
                    return None
                result[destination].append(
                    {"id": str(option["id"]), "description": str(option.get("value", ""))}
                )
        if any(not re.fullmatch(r"[1-9][0-9]{0,11}", str(result[k])) for k in ("makeId", "modelId")):
            self.failure = "vin_configuration_incomplete"
            return None
        self.stages.append("native_vin_configuration")
        return result

    async def read(self, url, *, params=None, json_body=None, headers=None, max_bytes=4_000_000):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "www.oreillyauto.com":
            raise ValueError("oreilly_session_host_not_allowed")
        if self.session is None:
            raise RuntimeError("oreilly_session_not_active")
        outgoing = {
            k: v
            for k, v in (headers or {}).items()
            if k.lower() not in {"cookie", "authorization", "x-api-key", "x-authkey", "x-csrf-token"}
        }
        if (
            parsed.path == "/es/product-autocomplete/v1/autocomplete"
            and json_body is None
            and self._public_search_key
        ):
            outgoing["X-Client"] = "OST"
            outgoing["x-api-key"] = self._public_search_key
        if json_body is not None:
            outgoing.setdefault("Origin", ROOT)
            outgoing.setdefault("Referer", ROOT + "/")
        if self.csrf and (json_body is not None or "application/json" in outgoing.get("Accept", "")):
            outgoing["X-CSRF-TOKEN"] = self.csrf
        response = None
        try:
            response = await self.session.request(
                "POST" if json_body is not None else "GET",
                url,
                params=params,
                json=json_body,
                headers=outgoing,
                auth=None,
                allow_redirects=False,
                stream=True,
            )
            chunks, size = [], 0
            async for chunk in response.aiter_content():
                size += len(chunk)
                if size > max_bytes:
                    self.failure = "response_limit_exceeded"
                    return None
                chunks.append(chunk)
            body = b"".join(chunks).decode("utf-8", errors="replace")
            if browser_verification(body):
                self.failure = "browser_verification_required"
                return None
            if response.status_code != 200:
                self.failure = "rate_limited" if response.status_code == 429 else "upstream_unavailable"
                return None
            return body
        except RequestsError:
            self.failure = "transport_unavailable"
            return None
        finally:
            if response is not None:
                await response.aclose()

    async def read_sitemap(self, url):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "www.oreillyauto.com"
            or not re.fullmatch(r"/sitemap\d+\.xml\.gz", parsed.path)
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("invalid_sitemap_url")
        response = None
        try:
            response = await self.session.get(url, allow_redirects=False, stream=True)
            if response.status_code != 200:
                return None
            chunks, size = [], 0
            async for chunk in response.aiter_content():
                size += len(chunk)
                if size > 4_000_000:
                    return None
                chunks.append(chunk)
            return b"".join(chunks)
        except RequestsError:
            return None
        finally:
            if response is not None:
                await response.aclose()
