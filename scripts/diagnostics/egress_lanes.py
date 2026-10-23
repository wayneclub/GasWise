"""Prove each configured pricing egress lane with a real HTTPS request.

A VPN container can be running while its tunnel is dead, so container health is
not evidence. Each lane passes only when an HTTPS request through that proxy
returns 200 and a US location. The operator heartbeat is reported for context
but never treated as proof.

Run from ``backend/`` so the repository's dependencies are available::

    uv run python ../scripts/diagnostics/egress_lanes.py
    uv run python ../scripts/diagnostics/egress_lanes.py --json

Lanes come from ``GASWISE_PRICING_EGRESS_PROXIES`` (JSON array, same variable
the service uses), then ``GASWISE_GASBUDDY_HTTP_PROXY`` as a single lane.
Proxy credentials, if present, are never printed. Exit status is 1 when any
configured lane fails.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx

# One request proves HTTPS interception and location. ipapi.co is a fallback for
# networks that block ipinfo.io; both return a two-letter country only.
LOOKUPS = (
    ("https://ipinfo.io/json", ("country",)),
    ("https://ipapi.co/json/", ("country_code", "country")),
)
USER_AGENT = "GasWise/0.5 pricing egress validation (operator diagnostic)"


def configured_lanes() -> list[str]:
    raw = os.environ.get("GASWISE_PRICING_EGRESS_PROXIES", "").strip()
    lanes: list[str] = []
    if raw:
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = [part.strip() for part in raw.split(",") if part.strip()]
        if isinstance(parsed, str):
            parsed = [parsed]
        lanes.extend(str(item) for item in parsed)
    single = os.environ.get("GASWISE_GASBUDDY_HTTP_PROXY", "").strip()
    if single and single not in lanes:
        lanes.append(single)
    return lanes


def redact(proxy: str) -> str:
    """Show scheme, host and port only; never credentials."""
    parts = urlsplit(proxy if "://" in proxy else "http://" + proxy)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme or "http", host, parts.path, "", ""))


def heartbeat(path: str | None) -> dict | None:
    if not path:
        return None
    file = Path(path)
    try:
        age = round(time.time() - file.stat().st_mtime, 1)
        data = json.loads(file.read_text())
    except (OSError, ValueError):
        return {"path": path, "readable": False}
    return {
        "path": path,
        "readable": True,
        "age_seconds": age,
        "stale": age > 30,
        "unavailable_lanes": data.get("unavailable_lanes"),
    }


async def probe(proxy: str, timeout: float) -> dict:
    started = time.perf_counter()
    # trust_env=False keeps a shell HTTP(S)_PROXY from silently replacing the lane.
    async with httpx.AsyncClient(proxy=proxy, trust_env=False, timeout=timeout,
                                 headers={"User-Agent": USER_AGENT, "Accept": "application/json"}) as client:
        for url, fields in LOOKUPS:
            try:
                response = await client.get(url)
            except httpx.HTTPError as error:
                last = type(error).__name__
                continue
            if response.status_code != 200:
                last = f"http_{response.status_code}"
                continue
            try:
                payload = response.json()
            except ValueError:
                last = "invalid_json"
                continue
            country = next((payload.get(field) for field in fields if payload.get(field)), None)
            if country is None:
                last = "no_country"
                continue
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            region = payload.get("region") or payload.get("region_code")
            city = payload.get("city")
            return {
                "verified": str(country).upper() == "US",
                "status": 200,
                "country": str(country).upper(),
                "region": region,
                "city": city,
                "elapsed_ms": elapsed,
            }
    return {"verified": False, "status": None, "error": last,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1)}


async def run(args) -> dict:
    lanes = configured_lanes()
    results = await asyncio.gather(*(probe(lane, args.timeout) for lane in lanes))
    rows = [
        {"lane": index, "proxy": redact(lane), **result}
        for index, (lane, result) in enumerate(zip(lanes, results, strict=True))
    ]
    return {
        "lanes": rows,
        "verified_lanes": [row["lane"] for row in rows if row["verified"]],
        "heartbeat": heartbeat(os.environ.get("GASWISE_PRICING_EGRESS_HEALTH_FILE")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=float, default=20)
    args = parser.parse_args()
    report = asyncio.run(run(args))
    if not report["lanes"]:
        print("No pricing egress lanes configured "
              "(GASWISE_PRICING_EGRESS_PROXIES / GASWISE_GASBUDDY_HTTP_PROXY).")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for row in report["lanes"]:
            state = "VERIFIED US" if row["verified"] else "FAILED"
            where = " ".join(str(item) for item in (row.get("city"), row.get("region"), row.get("country")) if item)
            detail = row.get("error") or where or "no location"
            print(f"lane {row['lane']}  {state:<11} {row['elapsed_ms']:>8.1f}ms  {row['proxy']}  {detail}")
        beat = report["heartbeat"]
        if beat is not None:
            print(f"heartbeat {beat['path']}: {beat}")
    return 0 if all(row["verified"] for row in report["lanes"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
