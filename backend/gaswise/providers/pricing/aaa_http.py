"""Anonymous AAA page reads using standard libcurl, without browser emulation.

Fresh bounded sessions; no imported cookies, proxy, or challenge execution.
"""

from urllib.parse import urlsplit

import httpx
from curl_cffi.requests import AsyncSession, RequestsError


class AAAHTTP:
    def __init__(self, session_factory=AsyncSession):
        self.session_factory = session_factory

    async def get(self, url, *, params=None, headers=None):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "gasprices.aaa.com":
            raise ValueError("aaa_host_not_allowed")
        request = httpx.Request("GET", url, params=params)
        async with self.session_factory(
            trust_env=False, timeout=15, allow_redirects=False, max_clients=1
        ) as session:
            response = None
            try:
                response = await session.get(
                    str(request.url),
                    headers=headers,
                    stream=True,
                    discard_cookies=True,
                    allow_redirects=False,
                )
                chunks, size = [], 0
                if response.status_code == 200:
                    async for chunk in response.aiter_content():
                        size += len(chunk)
                        if size > 4_000_000:
                            raise httpx.ReadError("aaa_response_too_large", request=request)
                        chunks.append(chunk)
                return httpx.Response(
                    response.status_code,
                    headers={
                        key: response.headers[key]
                        for key in ("content-type", "cf-mitigated")
                        if key in response.headers
                    },
                    content=b"".join(chunks),
                    request=request,
                )
            except RequestsError:
                raise httpx.RequestError("aaa_http_unavailable", request=request) from None
            finally:
                if response is not None:
                    await response.aclose()
