"""Versioned contract for independently deployed price services."""

from typing import Literal

import httpx
from pydantic import Field, ValidationError

from gaswise.models import Model, Search, Station
from gaswise.providers.base import ProviderError


class PriceFeed(Model):
    schema_version: Literal["gaswise.price-feed.v1"]
    stations: list[Station] = Field(max_length=100)


class HTTPPriceSource:
    def __init__(self, client, source_id, url, token, timeout_seconds=15):
        self.client, self.source_id, self.url, self.token = client, source_id, url, token
        self.timeout_seconds = timeout_seconds

    async def stations(self, query: Search) -> list[Station]:
        try:
            response = await self.client.post(
                self.url,
                json=query.model_dump(mode="json"),
                headers={"Authorization": f"Bearer {self.token}"} if self.token else {},
                timeout=self.timeout_seconds,
            )
            if not response.is_success:
                raise ProviderError("feed_request_rejected")
            feed = PriceFeed.model_validate(response.json())
            if any(station.source != self.source_id for station in feed.stations):
                raise ProviderError("feed_provenance_mismatch")
            return feed.stations
        except httpx.RequestError:
            raise ProviderError("feed_unavailable") from None
        except (ValidationError, ValueError, TypeError):
            raise ProviderError("feed_invalid_response") from None
