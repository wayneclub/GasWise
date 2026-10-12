"""Provider capabilities used by application services, independent of adapters."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from gaswise.contracts.common import Point, Route, SourceStatus, Station
from gaswise.contracts.search import Search
from gaswise.contracts.vehicles import PlateRequest, VehicleMenu, VehicleProfile, VinDecoded, VinRequest


class ProviderError(Exception):
    pass


class PriceSource(Protocol):
    async def stations(self, query: Search) -> list[Station]: ...


class Router(Protocol):
    async def route(self, origin: Point, destination: Point, via: Point | None = None) -> Route: ...


class Provider(PriceSource, Router, Protocol):
    pass


@dataclass
class PriceSnapshot:
    stations: list[Station]
    statuses: list[SourceStatus]


@runtime_checkable
class SnapshotSource(Protocol):
    async def snapshot(self, query: Search) -> PriceSnapshot: ...


class VehicleCatalog(Protocol):
    async def vehicle(self, vehicle_id: int) -> VehicleProfile: ...
    async def menu(self, kind: str, **filters) -> VehicleMenu: ...


class VinDecoder(Protocol):
    async def decode(self, request: VinRequest) -> VinDecoded: ...


class PlateLookup(Protocol):
    async def vin(self, request: PlateRequest) -> tuple[str, str | None, str | None]: ...
