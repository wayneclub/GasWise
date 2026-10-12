"""Bounded anonymous HTTPX reads shared by specification and parts adapters."""

import httpx


class HTTPXPublicReader:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def read(self, url, *, params=None, headers=None, json_body=None, max_bytes=4_000_000):
        request = self.client.build_request(
            "POST" if json_body is not None else "GET",
            url,
            params=params,
            json=json_body,
            headers=headers or {"User-Agent": "Mozilla/5.0", "Accept": "text/html"},
        )
        for key in ("cookie", "authorization", "x-api-key", "x-authkey"):
            request.headers.pop(key, None)
        response = None
        try:
            response = await self.client.send(request, auth=None, follow_redirects=False, stream=True)
            if response.status_code != 200:
                return None
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    return None
                chunks.append(chunk)
            return b"".join(chunks).decode("utf-8", errors="replace")
        except httpx.HTTPError:
            return None
        finally:
            if response is not None:
                await response.aclose()
