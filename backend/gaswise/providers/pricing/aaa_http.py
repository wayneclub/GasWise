"""Anonymous AAA reads using the shared standard libcurl transport."""

from curl_cffi.requests import AsyncSession

from gaswise.providers.http.curl_client import CurlHTTPClient


class AAAHTTP(CurlHTTPClient):
    def __init__(self, session_factory=AsyncSession):
        super().__init__(allowed_hosts={"gasprices.aaa.com"}, session_factory=session_factory)

    async def get(self, url, **kwargs):
        try:
            return await super().get(url, **kwargs)
        except ValueError:
            raise ValueError("aaa_host_not_allowed") from None
