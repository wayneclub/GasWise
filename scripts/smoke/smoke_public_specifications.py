"""Fresh zero-credential HTTP specification smoke; run from backend via uv."""
import argparse
import asyncio
import json

import httpx

from gaswise.providers.http.public import PublicHTTP
from gaswise.providers.vehicles.specifications import SpecificationProvider
from gaswise.providers.vehicles.catalog import VehicleProvider


async def main(ids):
    async with httpx.AsyncClient(timeout=15) as client:
        vehicles = VehicleProvider(client, SpecificationProvider(client, PublicHTTP()))
        for vehicle_id in ids:
            vehicle = await vehicles.vehicle(vehicle_id)
            requirement = vehicle.fuel_recommendation
            print(json.dumps({'vehicle_id': vehicle_id, 'year': vehicle.year, 'make': vehicle.make,
                'model': vehicle.model, 'recommended_octane_aki': requirement.recommended_octane_aki,
                'assessment_status': requirement.assessment_status,
                'evidence': [r.model_dump(mode='json') for r in requirement.specification_evidence]}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('vehicle_ids', nargs='*', type=int, default=[43305, 43302])
    args = parser.parse_args()
    asyncio.run(main(args.vehicle_ids))
