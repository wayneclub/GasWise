import { describe, expect, it } from 'vitest'
import {
  inferVehicleArchetype,
  inferVehicleSilhouette,
  VEHICLE_COLOR_PRESETS,
} from './vehicleStyle'

describe('inferVehicleSilhouette & inferVehicleArchetype', () => {
  it('identifies real vehicle silhouettes accurately', () => {
    // E-Class Coupe
    expect(inferVehicleSilhouette('2018 Mercedes-Benz E400 Coupe')).toBe('e_class_coupe')
    expect(inferVehicleArchetype('2018 Mercedes-Benz E400 Coupe')).toBe('coupe')

    // Muscle Coupe
    expect(inferVehicleSilhouette('2020 Ford Mustang GT')).toBe('muscle_coupe')
    expect(inferVehicleArchetype('2020 Ford Mustang GT')).toBe('coupe')

    // Porsche 911
    expect(inferVehicleSilhouette('2021 Porsche 911 Carrera S')).toBe('porsche_coupe')

    // Tesla Model 3
    expect(inferVehicleSilhouette('2022 Tesla Model 3 Long Range')).toBe('tesla_sedan')
    expect(inferVehicleArchetype('2022 Tesla Model 3 Long Range')).toBe('sedan')

    // Cybertruck
    expect(inferVehicleSilhouette('Tesla Cybertruck')).toBe('cybertruck')
    expect(inferVehicleArchetype('Tesla Cybertruck')).toBe('truck')

    // Pickup Truck
    expect(inferVehicleSilhouette('2020 Ford F-150 SuperCrew')).toBe('pickup_truck')
    expect(inferVehicleArchetype('2020 Ford F-150 SuperCrew')).toBe('truck')

    // Boxy SUV (Wrangler, G-Class)
    expect(inferVehicleSilhouette('2022 Jeep Wrangler Rubicon')).toBe('boxy_suv')
    expect(inferVehicleArchetype('2022 Jeep Wrangler Rubicon')).toBe('suv')

    // Crossover SUV
    expect(inferVehicleSilhouette('2021 Toyota RAV4 Hybrid')).toBe('crossover_suv')
    expect(inferVehicleArchetype('2021 Toyota RAV4 Hybrid')).toBe('suv')

    // Roadster
    expect(inferVehicleSilhouette('2016 Mazda MX-5 Miata Club')).toBe('roadster_convertible')
    expect(inferVehicleArchetype('2016 Mazda MX-5 Miata Club')).toBe('convertible')

    // Aero Hatchback (Prius)
    expect(inferVehicleSilhouette('2020 Toyota Prius Prime')).toBe('aero_hatch_prius')
    expect(inferVehicleArchetype('2020 Toyota Prius Prime')).toBe('hatchback')

    // Classic Hatchback (Golf)
    expect(inferVehicleSilhouette('2018 Volkswagen Golf GTI')).toBe('hatchback_golf')
    expect(inferVehicleArchetype('2018 Volkswagen Golf GTI')).toBe('hatchback')

    // Wagon
    expect(inferVehicleSilhouette('2022 Subaru Outback Touring')).toBe('wagon_estate')
    expect(inferVehicleArchetype('2022 Subaru Outback Touring')).toBe('wagon')

    // Minivan
    expect(inferVehicleSilhouette('2022 Toyota Sienna XLE')).toBe('minivan')
    expect(inferVehicleArchetype('2022 Toyota Sienna XLE')).toBe('van')

    // Default Sedan
    expect(inferVehicleSilhouette('2019 Honda Civic EX')).toBe('executive_sedan')
    expect(inferVehicleArchetype('2019 Honda Civic EX')).toBe('sedan')
  })

  it('provides rich automotive color presets', () => {
    expect(VEHICLE_COLOR_PRESETS.length).toBeGreaterThanOrEqual(8)
    expect(VEHICLE_COLOR_PRESETS.some((c) => c.id === 'obsidian')).toBe(true)
    expect(VEHICLE_COLOR_PRESETS.some((c) => c.id === 'red')).toBe(true)
    expect(VEHICLE_COLOR_PRESETS.some((c) => c.id === 'blue')).toBe(true)
  })
})
