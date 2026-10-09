"""GasWise-owned normalized feed adapter, NOT a GasBuddy public API client.

A contracted upstream adapter must translate the actual licensed GasBuddy payload
into this explicit contract. Endpoint is fixed at startup, never accepted from users.
"""

from typing import Literal

import httpx
from pydantic import Field, ValidationError

from gaswise.models import Model, Search, Station
from gaswise.providers.base import ProviderError


class GasBuddyFeed(Model):
    schema_version: Literal["gaswise.gasbuddy-feed.v1"]
    stations: list[Station] = Field(max_length=100)


class GasBuddyFeedProvider:
    def __init__(self, client: httpx.AsyncClient, url: str, token: str):
        self.client, self.url, self.token = client, url, token

    async def stations(self, query: Search) -> list[Station]:
        try:
            response = await self.client.post(
                self.url,
                json=query.model_dump(mode="json"),
                headers={"Authorization": f"Bearer {self.token}"},
            )
        except httpx.RequestError:
            raise ProviderError("gasbuddy_feed_unavailable") from None
        if not response.is_success:
            raise ProviderError("gasbuddy_feed_rejected_request")
        try:
            feed = GasBuddyFeed.model_validate(response.json())
            if feed.schema_version != "gaswise.gasbuddy-feed.v1" or any(
                s.source != "gasbuddy" for s in feed.stations
            ):
                raise ValueError("invalid feed provenance or version")
            return feed.stations
        except (ValidationError, ValueError, TypeError):
            raise ProviderError("gasbuddy_feed_invalid_response") from None
