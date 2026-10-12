"""Normalize snapshot-aware and single-source adapters through capabilities."""

from gaswise.contracts.common import SourceStatus
from gaswise.contracts.search import Search
from gaswise.domain.ports import PriceSnapshot, PriceSource, SnapshotSource


async def collect_prices(source: PriceSource, query: Search) -> PriceSnapshot:
    if isinstance(source, SnapshotSource):
        return await source.snapshot(query)
    stations = await source.stations(query)
    statuses = [
        SourceStatus(source=name, status="ok", quote_count=sum(s.source == name for s in stations))
        for name in sorted({station.source for station in stations})
    ]
    return PriceSnapshot(stations, statuses)
