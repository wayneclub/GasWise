"""Bounded address and US ZIP lookup. No automatic acquisition or persistence."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from gaswise.api.dependencies import authorize, get_operations, get_services
from gaswise.api.operations import OperationRunner
from gaswise.app.runtime import Services
from gaswise.contracts.common import Model, Point
from gaswise.domain.ports import ProviderError


class LocationQuery(Model):
    text: str = Field(min_length=3, max_length=200)

class LocationCandidate(Model):
    id: str
    label: str
    location: Point

class LocationResult(Model):
    candidates: list[LocationCandidate]
    source: str = "google_maps_web"

router = APIRouter()

@router.post('/v1/locations/resolve', response_model=LocationResult, dependencies=[Depends(authorize)])
async def resolve_location(query: LocationQuery, services: Services = Depends(get_services), operations: OperationRunner = Depends(get_operations)):
    if not services.locations:
        raise HTTPException(503, 'location_not_configured')
    async def run():
        try:
            data = await services.locations.search(query.text.strip())
            return LocationResult(candidates=data)
        except ProviderError as error:
            raise HTTPException(503, str(error)) from None
        except (KeyError, TypeError, ValueError):
            raise HTTPException(502, 'location_invalid_response') from None
    return await operations.run(run)
