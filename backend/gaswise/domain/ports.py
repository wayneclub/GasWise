"""Provider capabilities used by application services, independent of adapters."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from gaswise.contracts.common import Point, Route, SourceStatus, Station
from gaswise.contracts.search import Search
from gaswise.contracts.vehicles import PlateRequest, VehicleMenu, VehicleProfile, VinDecoded, VinRequest


class ProviderError(Exception):
    """Base exception for provider and upstream operation errors."""
    def __init__(self, message: str = "", code: str = ""):
        super().__init__(message or code)
        self.code = code or message

    @property
    def is_rate_limited(self) -> bool:
        return "rate_limited" in str(self) or isinstance(self, ProviderRateLimitedError)


class ProviderCapacityExceededError(ProviderError):
    """Raised when request volume or progressive search capacity is exceeded."""
    pass


class ProgressiveSearchCapacityExceeded(ProviderCapacityExceededError):
    def __init__(self, message: str = "progressive_search_capacity_exceeded"):
        super().__init__(message)


class ProviderRateLimitedError(ProviderCapacityExceededError):
    """Raised when an upstream provider throttles or rate limits requests."""
    pass


class ProviderUnavailableError(ProviderError):
    """Raised when an upstream provider is offline, unreachable, or failing."""
    pass


class UnsupportedPowertrainError(ProviderError):
    """Raised when vehicle powertrain is unsupported."""
    def __init__(self, message: str = "vehicle_powertrain_not_supported"):
        super().__init__(message)


class SnapshotExpiredError(ProviderError):
    """Raised when a pricing snapshot has passed its validity window."""
    def __init__(self, message: str = "snapshot_expired"):
        super().__init__(message)


class InvalidSnapshotSignatureError(ProviderError):
    """Raised when a pricing snapshot HMAC signature fails verification."""
    def __init__(self, message: str = "invalid_snapshot_signature"):
        super().__init__(message)


class SnapshotNoRoutesError(ProviderError):
    """Raised when ranking is requested on a snapshot without baseline routes."""
    def __init__(self, message: str = "snapshot_has_no_routes"):
        super().__init__(message)


class ConfigurationMissingError(ProviderError):
    """Raised when an optional capability or provider is not configured."""
    pass


class SmartRoutingNotConfiguredError(ConfigurationMissingError):
    def __init__(self, message: str = "smart_routing_not_configured"):
        super().__init__(message)


class VehicleCatalogNotConfiguredError(ConfigurationMissingError):
    def __init__(self, message: str = "vehicle_catalog_not_configured"):
        super().__init__(message)


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
