"""Best-effort warm-up for market-validated public EPA vehicle records."""

import asyncio

# Representative supported configurations selected by the 2025 market validation
# fixture. Identity and MPG are revalidated by VehicleProvider before persistence.
POPULAR_VEHICLE_IDS = (
    48910, 48034, 48872, 48495, 48510, 48884, 48118, 48874, 49053, 48199,
    48089, 47781, 48117, 48621, 47956, 48017, 48504, 47782, 47753, 47793,
    48021, 48269, 47958, 47959, 48540, 48500, 48259, 48606, 48186, 48096,
    48179, 48534, 48101, 47720, 48204, 48625, 48610, 48122, 48887, 48543,
    47740, 47801, 48573, 48507, 48552, 48530, 48095, 48513, 48549, 48276,
    48141, 48570, 47947, 48156, 48078, 47745, 47767, 48163, 47749,
)


async def warm_popular_vehicle_records(provider, concurrency=3):
    semaphore = asyncio.Semaphore(concurrency)

    async def load(vehicle_id):
        async with semaphore:
            try:
                await provider.vehicle(vehicle_id)
                return True
            except Exception:  # best effort: one unavailable record must not stop startup
                return False

    return await asyncio.gather(*(load(vehicle_id) for vehicle_id in POPULAR_VEHICLE_IDS))
