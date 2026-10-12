from fastapi import APIRouter, Depends, HTTPException, Path, Query

from gaswise.api.dependencies import authorize, get_operations, get_services
from gaswise.api.operations import OperationRunner
from gaswise.app.runtime import Services
from gaswise.contracts.vehicles import (
    FuelAssessment,
    FuelAssessmentRequest,
    PlateRequest,
    PlateResolution,
    VehicleMenu,
    VehicleProfile,
    VehicleResolution,
    VehicleResolveRequest,
    VinRequest,
    VinResolution,
)
from gaswise.services.vehicles.fuel_assessment import assess_fuel
from gaswise.services.vehicles.plate_selection import PlateSelector
from gaswise.services.vehicles.selection import VehicleSelector
from gaswise.services.vehicles.vin_selection import VinSelector

router = APIRouter()


@router.post("/v1/vehicles/plate", response_model=PlateResolution, dependencies=[Depends(authorize)])
async def resolve_plate(
    query: PlateRequest,
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    if services.plate is None:
        raise HTTPException(503, "plate_provider_not_configured")
    return await operations.run(
        lambda: PlateSelector(services.plate, VinSelector(services.vin, services.vehicles)).resolve(query)
    )


@router.post("/v1/vehicles/vin", response_model=VinResolution, dependencies=[Depends(authorize)])
async def resolve_vin(
    query: VinRequest,
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    return await operations.run(lambda: VinSelector(services.vin, services.vehicles).resolve(query))


@router.post("/v1/vehicles/resolve", response_model=VehicleResolution, dependencies=[Depends(authorize)])
async def resolve_vehicle(
    query: VehicleResolveRequest,
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    return await operations.run(lambda: VehicleSelector(services.vehicles).resolve(query))


@router.post("/v1/vehicles/fuel-assessment", response_model=FuelAssessment, dependencies=[Depends(authorize)])
async def fuel_assessment(
    query: FuelAssessmentRequest,
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    return await operations.run(lambda: assess_fuel(query, services.vehicles, services.vin, services.hertz))


@router.get("/v1/vehicles/years", response_model=VehicleMenu, dependencies=[Depends(authorize)])
async def vehicle_years(
    *, services: Services = Depends(get_services), operations: OperationRunner = Depends(get_operations)
):
    return await operations.run(lambda: services.vehicles.menu("year"))


@router.get("/v1/vehicles/makes", response_model=VehicleMenu, dependencies=[Depends(authorize)])
async def vehicle_makes(
    year: int = Query(ge=1984, le=2100),
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    return await operations.run(lambda: services.vehicles.menu("make", year=year))


@router.get("/v1/vehicles/models", response_model=VehicleMenu, dependencies=[Depends(authorize)])
async def vehicle_models(
    year: int = Query(ge=1984, le=2100),
    make: str = Query(min_length=1, max_length=100),
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    return await operations.run(lambda: services.vehicles.menu("model", year=year, make=make))


@router.get("/v1/vehicles/options", response_model=VehicleMenu, dependencies=[Depends(authorize)])
async def vehicle_options(
    year: int = Query(ge=1984, le=2100),
    make: str = Query(min_length=1, max_length=100),
    model: str = Query(min_length=1, max_length=200),
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    return await operations.run(lambda: services.vehicles.menu("options", year=year, make=make, model=model))


@router.get("/v1/vehicles/{vehicle_id}", response_model=VehicleProfile, dependencies=[Depends(authorize)])
async def vehicle_record(
    vehicle_id: int = Path(ge=1, le=1000000),
    *,
    services: Services = Depends(get_services),
    operations: OperationRunner = Depends(get_operations),
):
    return await operations.run(lambda: services.vehicles.vehicle(vehicle_id))
