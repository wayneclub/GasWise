"""Bounded clean-session probes. Never launches a browser or imports its cookies.

Compares standard HTTP stacks/protocols and normal landing -> search navigation.
Stops at rejection/challenge. Never prints tokens, cookies or upstream bodies.
Run from backend: uv run --with h2 python ../scripts/diagnostics/gasbuddy/probe_gasbuddy_browserless.py
"""

import asyncio
import json
import re
import subprocess
import tempfile
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

from gaswise.providers.gasbuddy.web import PRICE_QUERY

HOME = "https://www.gasbuddy.com/home?search=90015&fuel=3&method=credit&maxAge=0"
GRAPHQL = "https://www.gasbuddy.com/graphql"
BODY = {
    "operationName": "SearchPrices",
    "variables": {"fuel": 3, "maxAge": 0, "search": "90015"},
    "query": PRICE_QUERY,
}


def observe(profile, stage, status, headers, text, cookie_names):
    token = re.search(r'window\.gbcsrf\s*=\s*"([^"\n]+)"', text)
    print(
        json.dumps(
            {
                "client": profile,
                "stage": stage,
                "status": status,
                "content_type": headers.get("content-type"),
                "cf_mitigated": headers.get("cf-mitigated"),
                "has_csrf": token is not None,
                "has_station_state": "__APOLLO_STATE__" in text,
                "cookie_names": sorted(set(cookie_names)),
            }
        ),
        flush=True,
    )
    return token.group(1) if token else None


def api_observation(profile, status, headers, text):
    observation = {
        "client": profile,
        "stage": "graphql",
        "status": status,
        "content_type": headers.get("content-type"),
        "cf_mitigated": headers.get("cf-mitigated"),
    }
    if status == 200:
        try:
            data = json.loads(text)
            observation["graphql_has_errors"] = bool(data.get("errors"))
            observation["station_count"] = len(
                data.get("data", {}).get("locationBySearchTerm", {}).get("stations", {}).get("results", [])
            )
        except (ValueError, TypeError, AttributeError):
            observation["valid_json"] = False
    else:
        observation["mentions_csrf"] = "csrf" in text.lower()
    print(json.dumps(observation), flush=True)


def price_headers(token):
    return {
        "Origin": "https://www.gasbuddy.com",
        "Referer": HOME,
        "Accept": "*/*",
        "apollo-require-preflight": "true",
        "gbcsrf": token,
    }


async def httpx_probe(http2=False, landing=False):
    profile = f"httpx-{'h2' if http2 else 'h1'}-{'landing' if landing else 'direct'}"
    async with httpx.AsyncClient(
        http2=http2,
        follow_redirects=True,
        timeout=15,
        headers={
            "User-Agent": "GasWise/0.4 anonymous fuel comparison",
            "Accept": "text/html,application/xhtml+xml",
        },
    ) as client:
        if landing:
            r = await client.get("https://www.gasbuddy.com/")
            observe(profile, "landing", r.status_code, r.headers, r.text, client.cookies.keys())
            if not r.is_success or r.headers.get("cf-mitigated") == "challenge":
                return
        r = await client.get(HOME)
        token = observe(profile, "home", r.status_code, r.headers, r.text, client.cookies.keys())
        if not r.is_success or token is None:
            return
        r = await client.post(GRAPHQL, headers=price_headers(token), json=BODY)
        api_observation(profile, r.status_code, r.headers, r.text)


async def node_probe():
    profile = "node-http-no-browser"
    async with async_playwright() as playwright:
        client = await playwright.request.new_context(timeout=15000)
        try:
            r = await client.get(HOME)
            token = observe(
                profile,
                "home",
                r.status,
                r.headers,
                await r.text(),
                [c["name"] for c in (await client.storage_state())["cookies"]],
            )
            if not r.ok or token is None:
                return
            r = await client.post(GRAPHQL, data=BODY, headers=price_headers(token))
            api_observation(profile, r.status, r.headers, await r.text())
        finally:
            await client.dispose()


def curl_probe():
    profile = "system-curl-http2"
    with tempfile.TemporaryDirectory(prefix="gaswise-clean-http-") as directory:
        root = Path(directory)
        cookie, headers_path, body_path = root / "cookies", root / "headers", root / "body"

        def send(url, token=None):
            options = {
                "url": url,
                "cookie": str(cookie),
                "cookie-jar": str(cookie),
                "dump-header": str(headers_path),
                "output": str(body_path),
                "max-time": "15",
            }
            config = (
                "silent\nshow-error\nhttp2\n"
                + "\n".join(k + " = " + json.dumps(v) for k, v in options.items())
                + "\n"
            )
            if token is not None:
                if not re.fullmatch(r"[A-Za-z0-9._+/=-]{1,512}", token):
                    raise ValueError("unexpected token encoding")
                payload = root / "query.json"
                payload.write_text(json.dumps(BODY))
                config += 'data-binary = "@' + str(payload) + '"\n'
                for k, v in {**price_headers(token), "Content-Type": "application/json"}.items():
                    config += "header = " + json.dumps(k + ": " + v) + "\n"
            result = subprocess.run(["curl", "--config", "-"], input=config, text=True, capture_output=True)
            if result.returncode:
                raise RuntimeError("curl_transport_error")
            raw = headers_path.read_text()
            status = int(re.findall(r"HTTP/\S+\s+(\d+)", raw)[-1])
            headers = {
                line.split(":", 1)[0].lower(): line.split(":", 1)[1].strip()
                for line in raw.splitlines()
                if ":" in line
            }
            names = [line.split("\t")[-2] for line in cookie.read_text().splitlines() if "\t" in line]
            return status, headers, body_path.read_text(), names

        status, headers, text, names = send(HOME)
        token = observe(profile, "home", status, headers, text, names)
        if status != 200 or token is None:
            return
        status, headers, text, _ = send(GRAPHQL, token)
        api_observation(profile, status, headers, text)


async def main():
    # Sequential and bounded so protocol diagnostics do not create a request burst.
    for name, probe in [
        ("httpx-h1", lambda: httpx_probe()),
        ("httpx-h2", lambda: httpx_probe(True)),
        ("httpx-h2-landing", lambda: httpx_probe(True, True)),
        ("node", node_probe),
        ("curl", lambda: asyncio.to_thread(curl_probe)),
    ]:
        try:
            await probe()
        except Exception as error:
            print(json.dumps({"client": name, "error_type": type(error).__name__}), flush=True)


asyncio.run(main())
