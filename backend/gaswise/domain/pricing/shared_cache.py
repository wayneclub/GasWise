"""Public pricing-cache port. No visitor identities, routes or session credentials."""

from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

collection_attempt = ContextVar("collection_attempt", default=None)

collection_egress_key = ContextVar("collection_egress_key", default="foreground")

mandatory_acquisition = ContextVar("mandatory_pricing_acquisition", default=False)

background_acquisition = ContextVar("background_pricing_acquisition", default=False)


@dataclass
class CachedQuery:
    payload: dict | list
    fresh: bool
    usable: bool
    fetched_at: datetime | None = None


class PricingCacheStore(Protocol):
    async def read(self, key: str) -> CachedQuery | None: ...
    async def claim(self, key: str, source: str, owner: str) -> bool: ...
    async def save(self, key: str, source: str, owner: str, payload: dict | list, fresh_seconds: int) -> datetime | None: ...
    async def renew(self, key: str, owner: str) -> bool: ...
    async def release(self, key: str, owner: str) -> None: ...
    async def observe(self, stations: list) -> None: ...
    async def mappings(self, source: str, ids: list[str]) -> dict[str, str]: ...
    async def cleanup(self) -> None: ...
