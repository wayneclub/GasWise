import type { FuelType } from '../api/types'

export interface PopularVehiclePreset {
  id: number
  brand: string
  label: string
  year: number
  make: string
  model: string
  bodyStyle: string
  fuelType: FuelType
  combinedMpg: string
  defaultColor: string
}

export const POPULAR_VEHICLES: PopularVehiclePreset[] = [
  // --- Toyota ---
  {
    id: 48910,
    brand: 'Toyota',
    label: '2024 Toyota RAV4',
    year: 2024,
    make: 'Toyota',
    model: 'RAV4',
    bodyStyle: 'suv',
    fuelType: 'regular',
    combinedMpg: '30',
    defaultColor: '#4b5563', // Magnetic Gray
  },
  {
    id: 48034,
    brand: 'Toyota',
    label: '2024 Toyota Camry',
    year: 2024,
    make: 'Toyota',
    model: 'Camry',
    bodyStyle: 'sedan',
    fuelType: 'regular',
    combinedMpg: '32',
    defaultColor: '#cbd5e1', // Celestial Silver
  },
  {
    id: 48872,
    brand: 'Toyota',
    label: '2024 Toyota Tacoma',
    year: 2024,
    make: 'Toyota',
    model: 'Tacoma',
    bodyStyle: 'truck',
    fuelType: 'regular',
    combinedMpg: '23',
    defaultColor: '#4b5563', // Magnetic Gray
  },
  {
    id: 48495,
    brand: 'Toyota',
    label: '2024 Toyota Corolla',
    year: 2024,
    make: 'Toyota',
    model: 'Corolla',
    bodyStyle: 'sedan',
    fuelType: 'regular',
    combinedMpg: '35',
    defaultColor: '#f8fafc', // Wind Chill Pearl
  },
  {
    id: 48510,
    brand: 'Toyota',
    label: '2024 Toyota Prius',
    year: 2024,
    make: 'Toyota',
    model: 'Prius',
    bodyStyle: 'hatchback',
    fuelType: 'regular',
    combinedMpg: '57',
    defaultColor: '#eab308', // Cutting Edge Yellow / Pearl
  },

  // --- Ford ---
  {
    id: 48884,
    brand: 'Ford',
    label: '2024 Ford F-150',
    year: 2024,
    make: 'Ford',
    model: 'F-150',
    bodyStyle: 'truck',
    fuelType: 'regular',
    combinedMpg: '22',
    defaultColor: '#f8fafc', // Oxford White
  },
  {
    id: 48118,
    brand: 'Ford',
    label: '2024 Ford Mustang',
    year: 2024,
    make: 'Ford',
    model: 'Mustang',
    bodyStyle: 'coupe',
    fuelType: 'premium',
    combinedMpg: '26',
    defaultColor: '#dc2626', // Race Red
  },
  {
    id: 48874,
    brand: 'Ford',
    label: '2024 Ford Explorer',
    year: 2024,
    make: 'Ford',
    model: 'Explorer',
    bodyStyle: 'suv',
    fuelType: 'regular',
    combinedMpg: '24',
    defaultColor: '#111827', // Agate Black
  },
  {
    id: 49053,
    brand: 'Ford',
    label: '2024 Ford Bronco',
    year: 2024,
    make: 'Ford',
    model: 'Bronco',
    bodyStyle: 'suv',
    fuelType: 'regular',
    combinedMpg: '20',
    defaultColor: '#38bdf8', // Grabber Blue / Area 51
  },

  // --- Kia ---
  {
    id: 48199,
    brand: 'Kia',
    label: '2024 Kia Sportage',
    year: 2024,
    make: 'Kia',
    model: 'Sportage',
    bodyStyle: 'suv',
    fuelType: 'regular',
    combinedMpg: '28',
    defaultColor: '#475569', // Gravity Gray
  },
  {
    id: 48089,
    brand: 'Kia',
    label: '2024 Kia Telluride',
    year: 2024,
    make: 'Kia',
    model: 'Telluride',
    bodyStyle: 'suv',
    fuelType: 'regular',
    combinedMpg: '22',
    defaultColor: '#3b4c3d', // Dark Moss
  },
  {
    id: 47781,
    brand: 'Kia',
    label: '2024 Kia K5',
    year: 2024,
    make: 'Kia',
    model: 'K5',
    bodyStyle: 'sedan',
    fuelType: 'regular',
    combinedMpg: '31',
    defaultColor: '#0f172a', // Ebony Black
  },

  // --- Nissan ---
  {
    id: 48117,
    brand: 'Nissan',
    label: '2024 Nissan Rogue',
    year: 2024,
    make: 'Nissan',
    model: 'Rogue',
    bodyStyle: 'suv',
    fuelType: 'regular',
    combinedMpg: '33',
    defaultColor: '#f8fafc', // Glacier White
  },
  {
    id: 48621,
    brand: 'Nissan',
    label: '2024 Nissan Altima',
    year: 2024,
    make: 'Nissan',
    model: 'Altima',
    bodyStyle: 'sedan',
    fuelType: 'regular',
    combinedMpg: '32',
    defaultColor: '#cbd5e1', // Brilliant Silver
  },
  {
    id: 47956,
    brand: 'Nissan',
    label: '2024 Nissan Sentra',
    year: 2024,
    make: 'Nissan',
    model: 'Sentra',
    bodyStyle: 'sedan',
    fuelType: 'regular',
    combinedMpg: '34',
    defaultColor: '#4b5563', // Gun Metallic
  },

  // --- Honda ---
  {
    id: 48017,
    brand: 'Honda',
    label: '2024 Honda CR-V',
    year: 2024,
    make: 'Honda',
    model: 'CR-V',
    bodyStyle: 'suv',
    fuelType: 'regular',
    combinedMpg: '30',
    defaultColor: '#94a3b8', // Lunar Silver
  },
  {
    id: 48504,
    brand: 'Honda',
    label: '2024 Honda Civic',
    year: 2024,
    make: 'Honda',
    model: 'Civic',
    bodyStyle: 'sedan',
    fuelType: 'regular',
    combinedMpg: '36',
    defaultColor: '#f8fafc', // Platinum White
  },

  // --- Tesla ---
  {
    id: 47782,
    brand: 'Tesla',
    label: '2024 Tesla Model Y',
    year: 2024,
    make: 'Tesla',
    model: 'Model Y',
    bodyStyle: 'suv',
    fuelType: 'regular',
    combinedMpg: '122',
    defaultColor: '#f8fafc', // Pearl White
  },
  {
    id: 47753,
    brand: 'Tesla',
    label: '2024 Tesla Model 3',
    year: 2024,
    make: 'Tesla',
    model: 'Model 3',
    bodyStyle: 'sedan',
    fuelType: 'regular',
    combinedMpg: '132',
    defaultColor: '#475569', // Stealth Grey
  },

  // --- BMW ---
  {
    id: 43560,
    brand: 'BMW',
    label: '2019 BMW M4 Coupe',
    year: 2019,
    make: 'BMW',
    model: 'M4 Coupe',
    bodyStyle: 'coupe',
    fuelType: 'premium',
    combinedMpg: '19',
    defaultColor: '#5c9dc0', // Yas Marina Blue
  },
  {
    id: 48540,
    brand: 'BMW',
    label: '2024 BMW 330i',
    year: 2024,
    make: 'BMW',
    model: '330i',
    bodyStyle: 'sedan',
    fuelType: 'premium',
    combinedMpg: '30',
    defaultColor: '#1d4ed8', // Portimao Blue
  },

  // --- Mercedes-Benz ---
  {
    id: 41234,
    brand: 'Mercedes-Benz',
    label: '2018 Mercedes-Benz E400 Coupe',
    year: 2018,
    make: 'Mercedes-Benz',
    model: 'E400 Coupe',
    bodyStyle: 'coupe',
    fuelType: 'premium',
    combinedMpg: '22',
    defaultColor: '#1a1f2c', // Obsidian Black
  },
  {
    id: 48500,
    brand: 'Mercedes-Benz',
    label: '2024 Mercedes-Benz C300',
    year: 2024,
    make: 'Mercedes-Benz',
    model: 'C300',
    bodyStyle: 'sedan',
    fuelType: 'premium',
    combinedMpg: '30',
    defaultColor: '#525a65', // Selenite Grey
  },
]

export const POPULAR_BRANDS = [
  'Toyota',
  'Ford',
  'Kia',
  'Nissan',
  'Honda',
  'Tesla',
  'BMW',
  'Mercedes-Benz',
] as const
