"""Bounded async libcurl client with explicit host and session ownership.

A transport capability, not a promise to solve upstream security challenges.
No proxy rotation, JavaScript execution, external CAPTCHA solver or disk cookies.
"""

from urllib.parse import urlsplit

import httpx
from curl_cffi.requests import AsyncSession, RequestsError


class CurlHTTPClient:
    def __init__(
        self, *, allowed_hosts, session_factory=AsyncSession, profile=None, preserve_cookies=False, proxy=None, timeout=15
    ):
        self.allowed_hosts = frozenset(allowed_hosts)
        self.proxy = proxy
        self.session_factory = session_factory
        self.profile = profile
        self.preserve_cookies = preserve_cookies
        self.timeout = timeout
        self.session = None

    def new_session(self):
        options = dict(trust_env=False, timeout=self.timeout, allow_redirects=False, max_clients=1)
        if self.profile:
            options["impersonate"] = self.profile
        if self.proxy:
            options["proxy"] = self.proxy
        return self.session_factory(**options)

    async def get(self, url, **kwargs):
        return await self.request("GET", url, **kwargs)

    async def post(self, url, **kwargs):
        return await self.request("POST", url, **kwargs)

    async def request(self, method, url, *, params=None, headers=None, json=None):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc not in self.allowed_hosts:
            raise ValueError("curl_host_not_allowed")
        request = httpx.Request(method, url, params=params)
        if self.preserve_cookies:
            if self.session is None:
                self.session = self.new_session()
            return await self.read(self.session, request, headers=headers, json=json)
        async with self.new_session() as session:
            return await self.read(session, request, headers=headers, json=json)

    async def read(self, session, request, *, headers, json):
        response = None
        try:
            options = dict(
                headers=headers, stream=True, discard_cookies=not self.preserve_cookies, allow_redirects=False
            )
            if json is not None:
                options["json"] = json
            response = await getattr(session, request.method.lower())(str(request.url), **options)
            chunks, size = [], 0
            if response.status_code == 200:
                async for chunk in response.aiter_content():
                    size += len(chunk)
                    if size > 4_000_000:
                        raise httpx.ReadError("curl_response_too_large", request=request)
                    chunks.append(chunk)
            return httpx.Response(
                response.status_code,
                headers={
                    key: response.headers[key]
                    for key in ("content-type", "cf-mitigated", "retry-after")
                    if key in response.headers
                },
                content=b"".join(chunks),
                request=request,
            )
        except RequestsError:
            raise httpx.RequestError("curl_http_unavailable", request=request) from None
        finally:
            if response is not None:
                await response.aclose()

    async def aclose(self):
        if self.session is not None:
            await self.session.close()
            self.session = None
