import {
  CarBatteryIcon,
  DiscIcon,
  DropIcon,
  FunnelIcon,
  GaugeIcon,
  HeadlightsIcon,
  LightningIcon,
  SparkleIcon,
  ThermometerIcon,
  WavesIcon,
  WindIcon,
  WrenchIcon,
} from '@phosphor-icons/react'
import type { MessageKey } from '../../i18n'

export type PartCategory = 'all' | 'maintenance' | 'brakes' | 'electrical' | 'chassis'

export interface PartChoice {
  value: string
  label: MessageKey
  icon: typeof FunnelIcon
  category: 'maintenance' | 'brakes' | 'electrical' | 'chassis'
}

export const PART_CHOICES: readonly PartChoice[] = [
  { value: 'oil filter', label: 'parts.oilFilter', icon: FunnelIcon, category: 'maintenance' },
  { value: 'engine air filter', label: 'parts.airFilter', icon: WindIcon, category: 'maintenance' },
  { value: 'cabin air filter', label: 'parts.cabinFilter', icon: WindIcon, category: 'maintenance' },
  { value: 'wiper blades', label: 'parts.wiperBlades', icon: WavesIcon, category: 'maintenance' },
  { value: 'spark plug', label: 'parts.sparkPlugs', icon: SparkleIcon, category: 'maintenance' },
  { value: 'fuel filter', label: 'parts.fuelFilter', icon: FunnelIcon, category: 'maintenance' },
  { value: 'brake pads', label: 'parts.brakePads', icon: DiscIcon, category: 'brakes' },
  { value: 'brake rotor', label: 'parts.brakeRotors', icon: DiscIcon, category: 'brakes' },
  { value: 'brake caliper', label: 'parts.brakeCaliper', icon: DiscIcon, category: 'brakes' },
  { value: 'battery', label: 'parts.battery', icon: CarBatteryIcon, category: 'electrical' },
  { value: 'alternator', label: 'parts.alternator', icon: LightningIcon, category: 'electrical' },
  { value: 'starter', label: 'parts.starter', icon: LightningIcon, category: 'electrical' },
  { value: 'ignition coil', label: 'parts.ignitionCoil', icon: LightningIcon, category: 'electrical' },
  { value: 'headlight bulb', label: 'parts.headlightBulb', icon: HeadlightsIcon, category: 'electrical' },
  { value: 'serpentine belt', label: 'parts.serpentineBelt', icon: WavesIcon, category: 'chassis' },
  { value: 'water pump', label: 'parts.waterPump', icon: DropIcon, category: 'chassis' },
  { value: 'coolant thermostat', label: 'parts.thermostat', icon: ThermometerIcon, category: 'chassis' },
  { value: 'shock absorber', label: 'parts.shockAbsorber', icon: WrenchIcon, category: 'chassis' },
  { value: 'control arm', label: 'parts.controlArm', icon: WrenchIcon, category: 'chassis' },
  { value: 'wheel hub assembly', label: 'parts.wheelBearing', icon: DiscIcon, category: 'chassis' },
  { value: 'oxygen sensor', label: 'parts.oxygenSensor', icon: GaugeIcon, category: 'chassis' },
]

export const CATEGORIES: readonly { id: PartCategory; label: MessageKey }[] = [
  { id: 'all', label: 'parts.catAll' },
  { id: 'maintenance', label: 'parts.catMaintenance' },
  { id: 'brakes', label: 'parts.catBrakes' },
  { id: 'electrical', label: 'parts.catElectrical' },
  { id: 'chassis', label: 'parts.catChassis' },
]
