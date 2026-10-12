"""Fresh anonymous HTTP requests with libcurl's standard Chrome TLS profile.

No browser, JavaScript, credential replay, cookie persistence or redirects.
"""

from urllib.parse import urlsplit

from curl_cffi.requests import AsyncSession, RequestsError


class PublicHTTP:
    def __init__(self, session_factory=AsyncSession, *, allowed_hosts=None):
        self.session_factory = session_factory
        self.allowed_hosts = frozenset(allowed_hosts or {"www.edmunds.com", "www.hertzcarsales.com"})

    async def read(self, url, *, params=None, json_body=None, max_bytes=4_000_000, headers=None):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc not in self.allowed_hosts:
            raise ValueError("public_spec_host_not_allowed")
        response = None
        # A new session for each request prevents Set-Cookie from influencing later reads.
        async with self.session_factory(
            impersonate="chrome", trust_env=False, timeout=15, allow_redirects=False, max_clients=1
        ) as session:
            try:
                response = await session.request(
                    "POST" if json_body is not None else "GET",
                    url,
                    params=params,
                    json=json_body,
                    headers=headers,
                    cookies={},
                    auth=None,
                    discard_cookies=True,
                    allow_redirects=False,
                    stream=True,
                )
                if response.status_code != 200:
                    return None
                chunks, size = [], 0
                async for chunk in response.aiter_content():
                    size += len(chunk)
                    if size > max_bytes:
                        return None
                    chunks.append(chunk)
                return b"".join(chunks).decode("utf-8", errors="replace")
            except RequestsError:
                return None
            finally:
                if response is not None:
                    await response.aclose()
