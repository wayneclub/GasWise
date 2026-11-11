import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { GarageVehicleSwitcher } from './GarageVehicleSwitcher'
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

describe('GarageVehicleSwitcher', () => {
  it('renders vehicles and allows switching', () => {
    const onSelect = vi.fn()
    const onManage = vi.fn()

    render(
      <I18nProvider locale="en">
        <VehicleIdentityContext.Provider
          value={{
            identity: null,
            setIdentity: () => {},
            getVehicleIdentity: (id) =>
              id === 101 ? { kind: 'vin', value: { vin: 'WBS3R9C55K1234567' } } : null,
            setVehicleIdentity: () => {},
            identities: {},
          }}
        >
          <GarageVehicleSwitcher
            garage={[car1, car2]}
            activeVehicleId={101}
            onSelectVehicle={onSelect}
            onManageGarage={onManage}
            showIdentity
          />
        </VehicleIdentityContext.Provider>
      </I18nProvider>,
    )

    // Check titles and specs
    expect(screen.getByText('2019 BMW M4 Coupe')).toBeInTheDocument()
    expect(screen.getByText('2018 Mercedes-Benz E400 Coupe')).toBeInTheDocument()
    expect(screen.getByText(/19 MPG/)).toBeInTheDocument()
    expect(screen.getByText(/22 MPG/)).toBeInTheDocument()

    // Check identity display
    expect(screen.getByText(/VIN · •••••4567/)).toBeInTheDocument()
    expect(screen.getByText(/No VIN or plate linked/)).toBeInTheDocument()

    // Click car2
    const car2Btn = screen.getByRole('button', { name: /2018 Mercedes-Benz E400 Coupe/ })
    fireEvent.click(car2Btn)
    expect(onSelect).toHaveBeenCalledWith(car2)

    // Click manage garage
    const editBtn = screen.getByRole('button', { name: /Edit/i })
    fireEvent.click(editBtn)
    expect(onManage).toHaveBeenCalled()
  })

  it('renders nothing when garage is empty', () => {
    const { container } = render(
      <I18nProvider locale="en">
        <GarageVehicleSwitcher garage={[]} onSelectVehicle={() => {}} />
      </I18nProvider>,
    )
    expect(container.firstChild).toBeNull()
  })
})
