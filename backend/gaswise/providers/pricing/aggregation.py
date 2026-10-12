import asyncio

from gaswise.contracts.common import Point, Route, SourceStatus, Station
from gaswise.contracts.search import Search
from gaswise.domain.ports import PriceSnapshot as PriceSnapshot
from gaswise.domain.ports import PriceSource as PriceSource
from gaswise.domain.ports import ProviderError, Router


class MultiSourceProvider:
    """Price failures are isolated per source; routing stays with the configured router."""

    def __init__(
        self,
        router: Router | None,
        sources: dict[str, PriceSource],
        inactive: list[SourceStatus] | None = None,
        timeouts: dict[str, float] | None = None,
    ):
        self.router, self.sources, self.inactive = router, sources, inactive or []
        self.timeouts = timeouts or {}

    async def snapshot(self, query: Search) -> PriceSnapshot:
        async def fetch(name, source):
            try:
                async with asyncio.timeout(self.timeouts.get(name, 20)):
                    quotes = await source.stations(query)
                if any(station.source != name for station in quotes):
                    raise ProviderError("source_provenance_mismatch")
                return quotes, SourceStatus(source=name, status="ok", quote_count=len(quotes))
            except TimeoutError:
                return [], SourceStatus(source=name, status="unavailable", detail="source_timeout")
            except ProviderError as error:
                return [], SourceStatus(source=name, status="unavailable", detail=str(error))
            except Exception:
                return [], SourceStatus(source=name, status="unavailable", detail="source_internal_error")

        fetched = await asyncio.gather(*(fetch(name, source) for name, source in self.sources.items()))
        statuses = [status for _, status in fetched] + self.inactive
        if not any(status.status == "ok" for status in statuses):
            raise ProviderError("all_price_sources_unavailable")
        return PriceSnapshot([station for quotes, _ in fetched for station in quotes], statuses)

    async def stations(self, query: Search) -> list[Station]:
        return (await self.snapshot(query)).stations

    async def route(self, origin: Point, destination: Point, via: Point | None = None) -> Route:
        if self.router is None:
            raise ProviderError("routing_provider_not_configured")
        return await self.router.route(origin, destination, via)
