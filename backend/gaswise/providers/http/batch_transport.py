"""One budgeted same-exit retry for background read-only source queries.

Never retries an HTTP response, login, foreground request, proxy rejection or
local budget failure. Logs only bounded exception classes, never URLs/headers.
"""
import asyncio
import logging

import httpx

from gaswise.domain.pricing.shared_cache import background_acquisition, collection_attempt

logger = logging.getLogger(__name__)
TRANSIENT = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError,
             httpx.ReadTimeout, httpx.RemoteProtocolError)


async def source_request(client, method, url, *, source, budget=None, read_only=False, **kwargs):
    attempts = 2 if read_only and background_acquisition.get() else 1
    for attempt in range(attempts):
        if budget is not None:
            await budget.before(source)
        try:
            return await getattr(client, method)(url, **kwargs)
        except httpx.HTTPError as error:
            # A fixed whitelist prevents upstream exception text leaking secrets.
            kind = next((cls.__name__ for cls in (*TRANSIENT, httpx.ProxyError, httpx.HTTPError)
                         if isinstance(error, cls)), 'HTTPError')
            trace = collection_attempt.get() or {}
            retry = isinstance(error, TRANSIENT) and attempt + 1 < attempts
            logger.warning('pricing_transport source=%s kind=%s lane=%s attempt=%s retry=%s',
                           source, kind, trace.get('egress_lane'), attempt + 1, retry)
            if not retry:
                raise
            await asyncio.sleep(.25)
