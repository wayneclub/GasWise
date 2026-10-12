"""Runtime registration shared by discovery, quote collection and ranking."""

from gaswise.contracts.common import SourceStatus
from gaswise.domain.ports import PriceSource, Router
from gaswise.providers.pricing.aggregation import MultiSourceProvider


class SourceRegistry:
    def __init__(self):
        self.sources: dict[str, PriceSource] = {}
        self.inactive: list[SourceStatus] = []
        self.timeouts: dict[str, float] = {}

    def register(self, source_id: str, adapter: PriceSource, timeout_seconds: float = 20):
        if source_id in self.sources or any(s.source == source_id for s in self.inactive):
            raise ValueError(f"duplicate source: {source_id}")
        self.sources[source_id] = adapter
        self.timeouts[source_id] = timeout_seconds

    def disabled(self, source_id, detail="source disabled"):
        if source_id in self.sources or any(s.source == source_id for s in self.inactive):
            raise ValueError(f"duplicate source: {source_id}")
        self.inactive.append(SourceStatus(source=source_id, status="not_configured", detail=detail))

    def provider(self, router: Router | None = None):
        return MultiSourceProvider(router, self.sources, self.inactive, self.timeouts)

    def describe(self):
        return [
            {"source": name, "status": "configured", "timeout_seconds": self.timeouts[name]}
            for name in self.sources
        ] + [s.model_dump() for s in self.inactive]
