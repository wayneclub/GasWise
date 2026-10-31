import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SearchContext } from './SearchContext'
import { DEFAULT_PREFS, type SavedVehicle } from '../../lib/prefs'
import { I18nProvider } from '../../i18n/I18nProvider'

const car1: SavedVehicle = {
  id: 101,
  year: 2018,
  make: 'Mercedes-Benz',
  model: 'E400 Coupe',
  label: '2018 Mercedes-Benz E400 Coupe',
  fuelType: 'premium',
  combinedMpg: '22',
  color: '#0f172a',
}

const car2: SavedVehicle = {
  id: 102,
  year: 2021,
  make: 'Tesla',
  model: 'Model 3',
  label: '2021 Tesla Model 3',
  fuelType: 'regular',
  combinedMpg: '132',
  color: '#dc2626',
}

describe('SearchContext', () => {
  it('renders garage switcher and allows switching vehicles directly', () => {
    const onSelectCar = vi.fn()
    const onEditCar = vi.fn()

    render(
      <I18nProvider locale="en">
        <SearchContext
          prefs={{
            ...DEFAULT_PREFS,
            vehicle: car1,
            garage: [car1, car2],
          }}
          label="Downtown LA"
          source="manual"
          permission="granted"
          locating={false}
          searching={false}
          onLocate={() => {}}
          onChange={() => {}}
          onRefresh={() => {}}
          onEditCar={onEditCar}
          onSelectCar={onSelectCar}
        />
      </I18nProvider>,
    )

    // Expand vehicle panel
    const expandBtn = screen.getByRole('button', { name: /2018 Mercedes-Benz E400 Coupe.*Details/ })
    fireEvent.click(expandBtn)

    // Verify both cars from garage are displayed
    expect(screen.getByText('2018 Mercedes-Benz E400 Coupe')).toBeInTheDocument()
    expect(screen.getByText('2021 Tesla Model 3')).toBeInTheDocument()

    // Click on the second car to switch to it
    const teslaBtn = screen.getByRole('button', { name: /2021 Tesla Model 3/ })
    fireEvent.click(teslaBtn)
    expect(onSelectCar).toHaveBeenCalledWith(car2)

    // Click "Edit vehicle" button
    const editBtn = screen.getAllByRole('button', { name: 'Edit vehicle' })[0]
    fireEvent.click(editBtn)
    expect(onEditCar).toHaveBeenCalled()
  })
})
