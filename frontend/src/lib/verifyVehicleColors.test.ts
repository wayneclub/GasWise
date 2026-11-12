import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import {
  resolveVehiclePhoto,
  inferVehicleSilhouette,
  MERCEDES_COLOR_PRESETS,
  TESLA_COLOR_PRESETS,
  BMW_M4_F82_COLOR_PRESETS,
  BMW_COLOR_PRESETS,
  TOYOTA_RAV4_COLOR_PRESETS,
  TOYOTA_COLOR_PRESETS,
  FORD_MUSTANG_COLOR_PRESETS,
  FORD_COLOR_PRESETS,
  PORSCHE_911_COLOR_PRESETS,
  PORSCHE_COLOR_PRESETS,
  HONDA_COLOR_PRESETS,
  CHEVROLET_COLOR_PRESETS,
  HYUNDAI_COLOR_PRESETS,
  KIA_COLOR_PRESETS,
  SUBARU_COLOR_PRESETS,
  NISSAN_COLOR_PRESETS,
  MAZDA_COLOR_PRESETS,
  JEEP_COLOR_PRESETS,
  AUDI_COLOR_PRESETS,
  LEXUS_COLOR_PRESETS,
  VOLVO_COLOR_PRESETS,
  UNIVERSAL_COLOR_PRESETS,
} from './vehicleStyle'

const PUBLIC_DIR = path.resolve(__dirname, '../../public')

describe('Vehicle Image and Color Verification', () => {
  const brandTestSuites = [
    {
      name: 'Mercedes-Benz E-Class Coupe',
      vehicles: ['2018 Mercedes-Benz E400 Coupe', 'Mercedes E450 Coupe', 'Mercedes-Benz E350 Coupe'],
      presets: MERCEDES_COLOR_PRESETS,
      expectsStudioPhoto: true,
    },
    {
      name: 'Tesla Model 3',
      vehicles: ['2022 Tesla Model 3', 'Tesla Model 3 Long Range'],
      presets: TESLA_COLOR_PRESETS,
      expectsStudioPhoto: true,
    },
    {
      name: 'Tesla Model Y',
      vehicles: ['2023 Tesla Model Y', 'Tesla Model Y Performance'],
      presets: TESLA_COLOR_PRESETS,
      expectsStudioPhoto: true,
    },
    {
      name: 'BMW M4 Coupe',
      vehicles: ['2019 BMW M4 Coupe', 'BMW M4 Competition', 'BMW 430i Coupe'],
      presets: BMW_M4_F82_COLOR_PRESETS,
      expectsStudioPhoto: true,
    },
    {
      name: 'Toyota RAV4',
      vehicles: ['2021 Toyota RAV4', 'Toyota RAV4 Hybrid'],
      presets: TOYOTA_RAV4_COLOR_PRESETS,
      expectsStudioPhoto: true,
    },
    {
      name: 'Toyota Camry (Sedan)',
      vehicles: ['2022 Toyota Camry', 'Toyota Avalon'],
      presets: TOYOTA_COLOR_PRESETS,
      expectsStudioPhoto: true,
    },
    {
      name: 'Ford F-150 (Truck)',
      vehicles: ['2020 Ford F-150', 'Ford Raptor'],
      presets: FORD_COLOR_PRESETS,
      expectsStudioPhoto: true,
    },
    {
      name: 'Porsche 911 (Vector Silhouette)',
      vehicles: ['2021 Porsche 911 Carrera', 'Porsche Cayman'],
      presets: PORSCHE_911_COLOR_PRESETS,
      expectsStudioPhoto: false,
    },
    {
      name: 'Honda Civic & CR-V',
      vehicles: ['2022 Honda Civic', '2023 Honda CR-V'],
      presets: HONDA_COLOR_PRESETS,
      expectsStudioPhoto: false, // CR-V maps to crossover_suv photo/silhouette
    },
    {
      name: 'Ford Mustang (Muscle Coupe)',
      vehicles: ['2021 Ford Mustang GT'],
      presets: FORD_MUSTANG_COLOR_PRESETS,
      expectsStudioPhoto: false,
    },
    {
      name: 'Chevrolet Corvette & Silverado',
      vehicles: ['2022 Chevrolet Corvette', '2021 Chevrolet Silverado 1500'],
      presets: CHEVROLET_COLOR_PRESETS,
      expectsStudioPhoto: false,
    },
    {
      name: 'Hyundai Tucson & Elantra',
      vehicles: ['2022 Hyundai Tucson', '2023 Hyundai Elantra'],
      presets: HYUNDAI_COLOR_PRESETS,
      expectsStudioPhoto: false,
    },
    {
      name: 'Kia Telluride & Sportage',
      vehicles: ['2022 Kia Telluride', '2023 Kia Sportage'],
      presets: KIA_COLOR_PRESETS,
      expectsStudioPhoto: false,
    },
    {
      name: 'Subaru Outback & Forester',
      vehicles: ['2021 Subaru Outback', '2022 Subaru Forester'],
      presets: SUBARU_COLOR_PRESETS,
      expectsStudioPhoto: false,
    },
    {
      name: 'Nissan Rogue & Altima',
      vehicles: ['2021 Nissan Rogue', '2022 Nissan Altima'],
      presets: NISSAN_COLOR_PRESETS,
      expectsStudioPhoto: false,
    },
    {
      name: 'Mazda CX-5 & Mazda 3',
      vehicles: ['2022 Mazda CX-5', '2021 Mazda 3'],
      presets: MAZDA_COLOR_PRESETS,
      expectsStudioPhoto: false,
    },
    {
      name: 'Jeep Wrangler & Grand Cherokee',
      vehicles: ['2021 Jeep Wrangler', '2022 Jeep Grand Cherokee'],
      presets: JEEP_COLOR_PRESETS,
      expectsStudioPhoto: false,
    },
    {
      name: 'Audi A4 & Q5',
      vehicles: ['2021 Audi A4', '2022 Audi Q5'],
      presets: AUDI_COLOR_PRESETS,
      expectsStudioPhoto: false,
    },
    {
      name: 'Lexus RX 350 & ES 350',
      vehicles: ['2021 Lexus RX 350', '2022 Lexus ES 350'],
      presets: LEXUS_COLOR_PRESETS,
      expectsStudioPhoto: false,
    },
    {
      name: 'Volvo XC60 & V60',
      vehicles: ['2021 Volvo XC60', '2022 Volvo V60'],
      presets: VOLVO_COLOR_PRESETS,
      expectsStudioPhoto: false,
    },
  ]

  for (const suite of brandTestSuites) {
    it(`verifies all colors and models for ${suite.name} without 404 broken images`, () => {
      for (const car of suite.vehicles) {
        // Also test with null color
        const defaultPhoto = resolveVehiclePhoto(car, null, null)
        if (defaultPhoto && defaultPhoto.startsWith('/vehicles/')) {
          const cleanPath = defaultPhoto.split('?')[0].replace('/vehicles/', '')
          const diskPath = path.join(PUBLIC_DIR, 'vehicles', cleanPath)
          expect(fs.existsSync(diskPath), `Missing default photo on disk: ${diskPath}`).toBe(true)
          const stat = fs.statSync(diskPath)
          expect(stat.size, `Corrupt or empty photo file: ${diskPath}`).toBeGreaterThan(5000)
        }

        // Test every color preset
        for (const preset of suite.presets) {
          const photoUrl = resolveVehiclePhoto(car, null, preset.hex)
          if (photoUrl && photoUrl.startsWith('/vehicles/')) {
            const cleanPath = photoUrl.split('?')[0].replace('/vehicles/', '')
            const diskPath = path.join(PUBLIC_DIR, 'vehicles', cleanPath)
            expect(fs.existsSync(diskPath), `Missing photo for ${car} with color ${preset.name} (${preset.hex}): ${diskPath}`).toBe(true)
            const stat = fs.statSync(diskPath)
            expect(stat.size, `File too small/corrupt: ${diskPath}`).toBeGreaterThan(5000)
          } else {
            // If no photoUrl, must have a valid vector silhouette
            const silhouette = inferVehicleSilhouette(car)
            expect(silhouette).toBeDefined()
            expect(typeof silhouette).toBe('string')
          }
        }
      }
    })
  }
})
