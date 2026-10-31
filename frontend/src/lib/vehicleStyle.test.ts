import { describe, expect, it } from 'vitest'
import { inferVehicleArchetype } from './vehicleStyle'

describe('inferVehicleArchetype', () => {
  it('identifies coupes accurately', () => {
    expect(inferVehicleArchetype('2018 Mercedes-Benz E400 Coupe')).toBe('coupe')
    expect(inferVehicleArchetype('2020 Ford Mustang GT Coupe')).toBe('coupe')
    expect(inferVehicleArchetype('2016 Porsche Cayman')).toBe('coupe')
    expect(inferVehicleArchetype('2022 Subaru BRZ')).toBe('coupe')
  })

  it('identifies convertibles accurately', () => {
    expect(inferVehicleArchetype('2015 Mazda MX-5 Miata')).toBe('convertible')
    expect(inferVehicleArchetype('2019 Porsche 911 Cabriolet')).toBe('convertible')
    expect(inferVehicleArchetype('2021 BMW Z4 Roadster')).toBe('convertible')
  })

  it('identifies SUVs accurately', () => {
    expect(inferVehicleArchetype('2021 Toyota RAV4 Hybrid')).toBe('suv')
    expect(inferVehicleArchetype('2020 Honda CR-V EX-L')).toBe('suv')
    expect(inferVehicleArchetype('2022 Tesla Model Y')).toBe('suv')
    expect(inferVehicleArchetype('2019 Mercedes-Benz GLC 300')).toBe('suv')
  })

  it('identifies pickup trucks accurately', () => {
    expect(inferVehicleArchetype('2020 Ford F-150 SuperCrew')).toBe('truck')
    expect(inferVehicleArchetype('2021 Chevrolet Silverado 1500')).toBe('truck')
    expect(inferVehicleArchetype('2019 Toyota Tacoma Double Cab')).toBe('truck')
    expect(inferVehicleArchetype('Tesla Cybertruck')).toBe('truck')
  })

  it('identifies hatchbacks accurately', () => {
    expect(inferVehicleArchetype('2018 Volkswagen Golf GTI')).toBe('hatchback')
    expect(inferVehicleArchetype('2020 Toyota Prius Prime')).toBe('hatchback')
    expect(inferVehicleArchetype('2017 Honda Fit EX')).toBe('hatchback')
  })

  it('identifies station wagons accurately', () => {
    expect(inferVehicleArchetype('2020 Audi A4 Allroad')).toBe('wagon')
    expect(inferVehicleArchetype('2019 Volvo V60 Cross Country')).toBe('wagon')
    expect(inferVehicleArchetype('2015 BMW 328i Sports Wagon')).toBe('wagon')
  })

  it('identifies minivans accurately', () => {
    expect(inferVehicleArchetype('2022 Toyota Sienna XLE')).toBe('van')
    expect(inferVehicleArchetype('2021 Honda Odyssey Elite')).toBe('van')
    expect(inferVehicleArchetype('2020 Chrysler Pacifica')).toBe('van')
  })

  it('identifies sedans accurately and falls back safely', () => {
    expect(inferVehicleArchetype('2019 Honda Civic Sedan')).toBe('sedan')
    expect(inferVehicleArchetype('2021 Toyota Camry LE')).toBe('sedan')
    expect(inferVehicleArchetype('2022 Tesla Model 3 Long Range')).toBe('sedan')
    expect(inferVehicleArchetype('Unknown Car 2020')).toBe('sedan')
    expect(inferVehicleArchetype(null)).toBe('sedan')
  })
})
