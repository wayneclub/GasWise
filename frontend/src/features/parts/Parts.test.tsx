import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Parts } from './Parts'
import { VehicleIdentityContext } from '../../lib/vehicleIdentity'
import { I18nProvider } from '../../i18n/I18nProvider'
import type { SavedVehicle } from '../../lib/prefs'

const car1: SavedVehicle = {
  id: 101,
  year: 2019,
  make: 'BMW',
  model: 'M4 Coupe',
  label: '2019 BMW M4 Coupe',
  fuelType: 'premium',
  combinedMpg: '19',
  color: '#2563eb',
}

const car2: SavedVehicle = {
  id: 102,
  year: 2018,
  make: 'Mercedes-Benz',
  model: 'E400 Coupe',
  label: '2018 Mercedes-Benz E400 Coupe',
  fuelType: 'premium',
  combinedMpg: '22',
  color: '#0f172a',
}

describe('Parts Vehicle Switching', () => {
  it('renders garage vehicle switcher when multiple cars exist in garage and switches car directly', () => {
    const onSelectVehicle = vi.fn()
    const onChooseCar = vi.fn()

    render(
      <I18nProvider locale="zh-TW">
        <VehicleIdentityContext.Provider
          value={{
            identity: null,
            setIdentity: () => {},
            getVehicleIdentity: () => null,
            setVehicleIdentity: () => {},
            identities: {},
          }}
        >
          <Parts
            vehicle={car1}
            garage={[car1, car2]}
            onSelectVehicle={onSelectVehicle}
            onChooseCar={onChooseCar}
          />
        </VehicleIdentityContext.Provider>
      </I18nProvider>,
    )

    // Should display the switcher with both vehicles
    expect(screen.getByText('我的車庫')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /2019 BMW M4 Coupe/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /2018 Mercedes-Benz E400 Coupe/ })).toBeInTheDocument()

    // Click on Mercedes E400 to switch
    const e400Btn = screen.getByRole('button', { name: /2018 Mercedes-Benz E400 Coupe/ })
    fireEvent.click(e400Btn)
    expect(onSelectVehicle).toHaveBeenCalledWith(car2)
  })

  it('renders switcher inside edit details when identity is configured', () => {
    const onSelectVehicle = vi.fn()

    render(
      <I18nProvider locale="zh-TW">
        <VehicleIdentityContext.Provider
          value={{
            identity: { kind: 'vin', value: { vin: 'WBS3R9C55K1234567' } },
            setIdentity: () => {},
            getVehicleIdentity: (id) =>
              id === 101 ? { kind: 'vin', value: { vin: 'WBS3R9C55K1234567' } } : null,
            setVehicleIdentity: () => {},
            identities: {},
          }}
        >
          <Parts
            vehicle={car1}
            garage={[car1, car2]}
            onSelectVehicle={onSelectVehicle}
            onChooseCar={() => {}}
          />
        </VehicleIdentityContext.Provider>
      </I18nProvider>,
    )

    // Should show parts search mode
    expect(screen.getByRole('heading', { name: '找適合這台車的零件' })).toBeInTheDocument()

    // Switcher should be present in the details section
    const e400Btn = screen.getByRole('button', { name: /2018 Mercedes-Benz E400 Coupe/ })
    fireEvent.click(e400Btn)
    expect(onSelectVehicle).toHaveBeenCalledWith(car2)
  })
})
