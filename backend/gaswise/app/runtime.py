"""Explicit application dependencies; HTTP handlers never construct providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gaswise.domain.ports import PlateLookup, Provider, VehicleCatalog, VinDecoder
    from gaswise.providers.gasbuddy.web import GasBuddyWebProvider
    from gaswise.providers.geocoding import LocationProvider
    from gaswise.providers.google.maps_web import MapsWebProvider
    from gaswise.providers.google.places import GoogleProvider
    from gaswise.providers.pricing.aaa import AAAProvider
    from gaswise.providers.pricing.aggregation import MultiSourceProvider
    from gaswise.providers.pricing.registry import SourceRegistry
    from gaswise.providers.quality.top_tier import TopTierProvider
    from gaswise.providers.vehicles.hertz import HertzProvider
    from gaswise.providers.waze.provider import WazeProvider
    from gaswise.services.parts.fitment import PartsProvider
    from gaswise.services.pricing.alerts import SmartAlerts
    from gaswise.services.pricing.search import SearchService
    from gaswise.services.pricing.smart import SmartService


@dataclass
class ProviderOverrides:
    provider: Provider | None = None
    vehicles: VehicleCatalog | None = None
    vin: VinDecoder | None = None
    plate: PlateLookup | None = None


@dataclass
class Services:
    vehicles: VehicleCatalog
    vin: VinDecoder
    hertz: HertzProvider
    parts: PartsProvider
    plate: PlateLookup | None
    google_prices: GoogleProvider | None
    aaa: AAAProvider
    maps_web: MapsWebProvider
    waze: WazeProvider | None
    gasbuddy_web: GasBuddyWebProvider
    source_registry: SourceRegistry
    price_provider: MultiSourceProvider
    service: SearchService | None
    smart: SmartService
    locations: LocationProvider | None = None
    top_tier: TopTierProvider | None = None
    alerts: SmartAlerts | None = None
