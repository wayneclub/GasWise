"""Safe one-request upstream probes; no cookies or tokens are logged."""

import asyncio
import json
import re

import httpx


async def main():
    for name, url, ua in [
        ("aaa", "https://gasprices.aaa.com/?state=CA", "GasWise/0.5 fuel comparison (regional averages)"),
        ("gasbuddy", "https://www.gasbuddy.com/", "GasWise/0.5 anonymous fuel comparison"),
    ]:
        async with httpx.AsyncClient(
            http2=True,
            follow_redirects=True,
            timeout=20,
            headers={"User-Agent": ua, "Accept": "text/html"},
        ) as c:
            r = await c.get(url)
            title = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S | re.I)
            print(
                json.dumps(
                    {
                        "source": name,
                        "status": r.status_code,
                        "http": r.http_version,
                        "bytes": len(r.content),
                        "server": r.headers.get("server"),
                        "mitigated": r.headers.get("cf-mitigated"),
                        "title": title.group(1)[:100] if title else None,
                        "csrf_present": "window.gbcsrf" in r.text,
                        "publication_present": "Price as of" in r.text,
                    }
                )
            )


if __name__ == "__main__":
    asyncio.run(main())
