from typing import Protocol

from gaswise.models import Point, Route, Search, Station


class ProviderError(Exception):
    pass


class Provider(Protocol):
    async def stations(self, query: Search) -> list[Station]: ...
    async def route(self, origin: Point, destination: Point, via: Point | None = None) -> Route: ...
