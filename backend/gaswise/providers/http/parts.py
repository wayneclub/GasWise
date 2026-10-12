"""Source-isolated public HTTP reader for parts (no arbitrary URLs or credential replay)."""

from gaswise.providers.http.oreilly_session import OReillyHTTPSession
from gaswise.providers.http.public import PublicHTTP
from gaswise.providers.parts.oreilly_catalog import OReillyCatalog


class PartsHTTP(PublicHTTP):
    def __init__(self):
        self.oreilly_catalog = OReillyCatalog()
        super().__init__(
            allowed_hosts={
                "www.amazon.com",
                "www.mann-filter.com",
                "www.oreillyauto.com",
                "external-api.autozone.com",
                "www.autozone.com",
            }
        )

    def oreilly_session(self):
        return OReillyHTTPSession()
