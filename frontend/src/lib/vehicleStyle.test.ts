import { describe, expect, it } from 'vitest'
import {
  inferVehicleArchetype,
  inferVehicleSilhouette,
  resolveVehiclePhoto,
  VEHICLE_COLOR_PRESETS,
  getVehicleColorPresets,
  VEHICLE_IMAGE_CACHE_VERSION,
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

  it('provides brand-aware authentic automotive factory color presets', () => {
    expect(VEHICLE_COLOR_PRESETS.length).toBeGreaterThanOrEqual(6)
    expect(VEHICLE_COLOR_PRESETS.some((c) => c.id === 'obsidian')).toBe(true)
    expect(VEHICLE_COLOR_PRESETS.some((c) => c.id === 'red')).toBe(true)
    expect(VEHICLE_COLOR_PRESETS.some((c) => c.id === 'blue')).toBe(true)

    // Tesla has authentic Ultra Red and Quicksilver
    const teslaPresets = getVehicleColorPresets('Tesla Model Y')
    expect(teslaPresets.some((c) => c.id === 'ultra_red')).toBe(true)
    expect(teslaPresets.some((c) => c.id === 'quicksilver')).toBe(true)

    // Toyota has Blueprint and Wind Chill Pearl
    const toyotaPresets = getVehicleColorPresets('Toyota RAV4')
    expect(toyotaPresets.some((c) => c.id === 'blueprint')).toBe(true)
    expect(toyotaPresets.some((c) => c.id === 'wind_chill_pearl')).toBe(true)

    // Porsche has Guards Red and Racing Yellow
    const porschePresets = getVehicleColorPresets('Porsche 911 Carrera')
    expect(porschePresets.some((c) => c.id === 'guards_red')).toBe(true)
    expect(porschePresets.some((c) => c.id === 'racing_yellow')).toBe(true)

    // BMW has Isle of Man Green and Portimao Blue
    const bmwPresets = getVehicleColorPresets('BMW 4 Series')
    expect(bmwPresets.some((c) => c.id === 'isle_of_man_green')).toBe(true)
    expect(bmwPresets.some((c) => c.id === 'portimao_blue')).toBe(true)

    // Ford has Oxford White and Grabber Blue
    const fordPresets = getVehicleColorPresets('Ford Mustang')
    expect(fordPresets.some((c) => c.id === 'oxford_white')).toBe(true)
    expect(fordPresets.some((c) => c.id === 'grabber_blue')).toBe(true)

    // Universal Fallback
    const fallbackPresets = getVehicleColorPresets('Unknown Brand Car')
    expect(fallbackPresets.some((c) => c.id === 'pearl_white')).toBe(true)
  })

  it('resolves vehicle photo URLs accurately with cache-busting version parameters', () => {
    const v = VEHICLE_IMAGE_CACHE_VERSION
    // Custom URL priority (no version query injected into custom user URLs)
    expect(resolveVehiclePhoto('2018 Mercedes-Benz E400 Coupe', 'https://example.com/mycar.jpg')).toBe('https://example.com/mycar.jpg')
    // Carvana listing URL translation
    expect(resolveVehiclePhoto('Any Car', 'https://www.carvana.com/vehicle/4856325?store=Carvla3')).toBe(`/vehicles/2018_mercedes_benz_e400_coupe_white.png?v=${v}`)
    // Default mapped photo for Mercedes E-Class Coupe (white / factory)
    expect(resolveVehiclePhoto('2018 Mercedes-Benz E400 Coupe')).toBe(`/vehicles/2018_mercedes_benz_e400_coupe_white.png?v=${v}`)
    // Custom color mapped photo for Mercedes E-Class Coupe
    expect(resolveVehiclePhoto('2018 Mercedes-Benz E400 Coupe', null, '#1e293b')).toBe(`/vehicles/2018_mercedes_benz_e400_coupe_obsidian.png?v=${v}`)
    expect(resolveVehiclePhoto('2018 Mercedes-Benz E400 Coupe', null, '#dc2626')).toBe(`/vehicles/2018_mercedes_benz_e400_coupe_red.png?v=${v}`)
    expect(resolveVehiclePhoto('2018 Mercedes-Benz E400 Coupe', null, '#1d4ed8')).toBe(`/vehicles/2018_mercedes_benz_e400_coupe_blue.png?v=${v}`)
    // Unmapped vehicle returns null
    expect(resolveVehiclePhoto('2019 Honda Civic EX')).toBe(null)
  })

  it('accurately categorizes top popular vehicles from the validation dataset', () => {
    // Trucks
    expect(inferVehicleArchetype('Ford F-Series')).toBe('truck')
    expect(inferVehicleArchetype('Chevrolet Silverado')).toBe('truck')
    expect(inferVehicleArchetype('Toyota Tacoma')).toBe('truck')
    expect(inferVehicleArchetype('GMC Sierra')).toBe('truck')

    // SUVs
    expect(inferVehicleArchetype('Toyota RAV4')).toBe('suv')
    expect(inferVehicleArchetype('Honda CR-V')).toBe('suv')
    expect(inferVehicleArchetype('Nissan Rogue')).toBe('suv')
    expect(inferVehicleArchetype('Hyundai Tucson')).toBe('suv')
    expect(inferVehicleArchetype('Hyundai Kona')).toBe('suv')
    expect(inferVehicleArchetype('Jeep Wrangler')).toBe('suv')

    // Sedans
    expect(inferVehicleArchetype('Toyota Camry')).toBe('sedan')
    expect(inferVehicleArchetype('Honda Accord')).toBe('sedan')
    expect(inferVehicleArchetype('Nissan Altima')).toBe('sedan')
    expect(inferVehicleArchetype('BMW 3 Series')).toBe('sedan')
  })
})
