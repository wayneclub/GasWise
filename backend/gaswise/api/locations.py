"""Bounded address, place-name and US ZIP lookup. No automatic acquisition or persistence."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from gaswise.api.dependencies import authorize, get_operations, get_services
from gaswise.api.operations import OperationRunner
from gaswise.app.runtime import Services
from gaswise.contracts.common import Model, Point
from gaswise.domain.ports import ProviderError


class LocationQuery(Model):
    # Two characters admit state and city abbreviations such as NY, LA and SF.
    text: str = Field(min_length=2, max_length=200)
    locale: str | None = Field(default=None, max_length=16)

class LocationCandidate(Model):
    id: str
    label: str
    location: Point

class LocationResult(Model):
    candidates: list[LocationCandidate]
    # Set when Google found only places outside the US, which no price source covers.
    reason: Literal['unsupported_area'] | None = None
    source: str = "google_maps_web"

router = APIRouter()

@router.post('/v1/locations/resolve', response_model=LocationResult, dependencies=[Depends(authorize)])
async def resolve_location(query: LocationQuery, services: Services = Depends(get_services), operations: OperationRunner = Depends(get_operations)):
    if not services.locations:
        raise HTTPException(503, 'location_not_configured')
    async def run():
        try:
            return LocationResult(**await services.locations.search(query.text, locale=query.locale))
        except ProviderError as error:
            raise HTTPException(503, str(error)) from None
        except (KeyError, TypeError, ValueError):
            raise HTTPException(502, 'location_invalid_response') from None
    return await operations.run(run)
