"""Runtime registration shared by discovery, quote collection and ranking."""

from gaswise.models import SourceStatus
from gaswise.providers.multi import MultiSourceProvider


class SourceRegistry:
    def __init__(self):
        self.sources = {}
        self.inactive = []
        self.timeouts = {}

    def register(self, source_id, adapter, timeout_seconds=20):
        if source_id in self.sources or any(s.source == source_id for s in self.inactive):
            raise ValueError(f"duplicate source: {source_id}")
        self.sources[source_id] = adapter
        self.timeouts[source_id] = timeout_seconds

    def disabled(self, source_id, detail="source disabled"):
        if source_id in self.sources or any(s.source == source_id for s in self.inactive):
            raise ValueError(f"duplicate source: {source_id}")
        self.inactive.append(SourceStatus(source=source_id, status="not_configured", detail=detail))

    def provider(self, router=None):
        return MultiSourceProvider(router, self.sources, self.inactive, self.timeouts)

    def describe(self):
        return [
            {"source": name, "status": "configured", "timeout_seconds": self.timeouts[name]}
            for name in self.sources
        ] + [s.model_dump() for s in self.inactive]
