/// <reference types="node" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { IDBFactory } from 'fake-indexeddb'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MyPage } from './MyPage'
import { saveFavorite, loadFavorites } from '../../lib/favorites'
import { DEFAULT_PREFS } from '../../lib/prefs'

describe('MyPage', () => {
  beforeEach(() => {
    vi.stubGlobal('indexedDB', new IDBFactory())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders empty state when there are no favorite stations', () => {
    const onNavigate = vi.fn()
    render(<MyPage prefs={DEFAULT_PREFS} onNavigateToFuel={onNavigate} />)

    expect(screen.getByText('No favorite stations yet')).toBeInTheDocument()
    const searchBtn = screen.getByRole('button', { name: 'Find Gas Stations' })
    fireEvent.click(searchBtn)
    expect(onNavigate).toHaveBeenCalled()
  })

  it('renders favorite stations and price analytics with stats, bars, notes and deletion', async () => {
    await saveFavorite({
      id: 'google:shell_downtown',
      stationId: 'shell_downtown',
      name: 'Shell Downtown',
      source: 'google',
      address: '100 Main St, Los Angeles, CA',
      location: { lat: 34.05, lng: -118.25 },
      lastObservedPrice: '4.89',
      fuelType: 'regular',
      topTierBrand: 'Shell',
      addedAt: '2026-10-30T00:00:00Z',
    })

    await saveFavorite({
      id: 'google:costco_la',
      stationId: 'costco_la',
      name: 'Costco Wholesale',
      source: 'google',
      address: '2207 E Olympic Blvd, Los Angeles, CA',
      location: { lat: 34.02, lng: -118.22 },
      lastObservedPrice: '4.29',
      fuelType: 'regular',
      addedAt: '2026-10-30T01:00:00Z',
      notes: 'Best prices on weekends',
    })

    await saveFavorite({
      id: 'google:chevron_express',
      stationId: 'chevron_express',
      name: 'Chevron Express',
      source: 'google',
      address: '800 Figueroa St, Los Angeles, CA',
      location: { lat: 34.04, lng: -118.26 },
      lastObservedPrice: '5.19',
      fuelType: 'regular',
      topTierBrand: 'Chevron',
      addedAt: '2026-10-30T02:00:00Z',
    })

    render(
      <MyPage
        prefs={{ ...DEFAULT_PREFS, gallons: 10 }}
        onNavigateToFuel={() => {}}
      />,
    )

    // Wait for favorites to load
    await waitFor(() => {
      expect(screen.getByText('Favorite Stations Price Analysis')).toBeInTheDocument()
    })

    // Stat cards assertions
    // Lowest price is 4.29 (Costco)
    expect(screen.getAllByText('$4.29').length).toBeGreaterThan(0)
    // Spread is 5.19 - 4.29 = 0.90
    expect(screen.getByText('$0.90')).toBeInTheDocument()
    // Max savings = 0.90 * 10 = $9.00
    expect(screen.getByText('$9.00')).toBeInTheDocument()

    // Price visualization sections
    expect(screen.getByText('Price Distribution Spectrum')).toBeInTheDocument()
    expect(screen.getByText(/Full Tank Cost Comparison/)).toBeInTheDocument()
    expect(screen.getByText('Baseline')).toBeInTheDocument()

    // Smart Recommendations and Multi-Station Price Trend History
    expect(screen.getByText('Smart Recommendations & Fuel Advisor')).toBeInTheDocument()
    expect(screen.getByText('Favorite Stations Price Trend History')).toBeInTheDocument()
    expect(screen.getByText('Annual Savings Potential')).toBeInTheDocument()

    // Station list items
    expect(screen.getAllByText('Costco Wholesale').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Shell Downtown').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Chevron Express').length).toBeGreaterThan(0)
    expect(screen.getByText('Best prices on weekends')).toBeInTheDocument()

    // Edit notes
    const editBtns = screen.getAllByText('Edit')
    fireEvent.click(editBtns[0])
    const noteInput = screen.getByDisplayValue('Best prices on weekends')
    fireEvent.change(noteInput, { target: { value: 'Free tire air available' } })
    fireEvent.click(screen.getByText('Save notes'))

    await waitFor(async () => {
      const stored = await loadFavorites()
      const costco = stored.find((s) => s.id === 'google:costco_la')
      expect(costco?.notes).toBe('Free tire air available')
    })

    // Delete one station
    const deleteBtn = screen.getByRole('button', {
      name: 'Remove from favorites Chevron Express',
    })
    fireEvent.click(deleteBtn)

    await waitFor(() => {
      expect(screen.queryByText('Chevron Express')).not.toBeInTheDocument()
    })
  })

  it('allows user to add, edit and delete refuel records in MyPage', async () => {
    vi.spyOn(window, 'confirm').mockImplementation(() => true)

    render(
      <MyPage
        prefs={{ ...DEFAULT_PREFS, vehicle: { id: 1, label: '2020 Honda Civic', fuelType: 'regular', combinedMpg: '32' } }}
        onNavigateToFuel={() => {}}
      />,
    )

    // Check Assistant card is present
    expect(await screen.findByText('Fuel timing assistant')).toBeInTheDocument()
    expect(screen.getByText('Refueling Records (0)')).toBeInTheDocument()

    // 1. Quick refuel button
    const quickBtn = screen.getByRole('button', { name: 'I just refuelled' })
    fireEvent.click(quickBtn)

    await waitFor(() => {
      expect(screen.getByText('Refueling Records (1)')).toBeInTheDocument()
    })

    // 2. Add detailed refuel record
    const addBtns = screen.getAllByRole('button', { name: 'Add Refuel Record' })
    fireEvent.click(addBtns[0])

    expect(screen.getByRole('dialog')).toBeInTheDocument()

    // Fill form
    const stationInput = screen.getByPlaceholderText('Costco, Chevron, Shell...')
    fireEvent.change(stationInput, { target: { value: 'Shell Pasadena' } })

    const priceInput = screen.getByPlaceholderText('3.899')
    fireEvent.change(priceInput, { target: { value: '4.50' } })

    const gallonsInput = screen.getByPlaceholderText('10')
    fireEvent.change(gallonsInput, { target: { value: '12' } })

    const saveBtn = screen.getByRole('button', { name: 'Save' })
    fireEvent.click(saveBtn)

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(screen.getByText('Refueling Records (2)')).toBeInTheDocument()
      expect(screen.getByText('Shell Pasadena')).toBeInTheDocument()
      expect(screen.getByText('$4.50/gal')).toBeInTheDocument()
      expect(screen.getByText('12 gal')).toBeInTheDocument()
      expect(screen.getByText('$54.00')).toBeInTheDocument()
    })

    // 3. Edit record
    const editBtn = screen.getByRole('button', { name: /Edit Shell Pasadena/i })
    fireEvent.click(editBtn)

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    const editStationInput = screen.getByDisplayValue('Shell Pasadena')
    fireEvent.change(editStationInput, { target: { value: 'Shell Pasadena North' } })
    const editGallonsInput = screen.getByDisplayValue('12')
    fireEvent.change(editGallonsInput, { target: { value: '14' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(screen.getByText('Shell Pasadena North')).toBeInTheDocument()
      expect(screen.getByText('14 gal')).toBeInTheDocument()
    })

    // 4. Delete record
    const deleteBtn = screen.getByRole('button', { name: /Delete Shell Pasadena North/i })
    fireEvent.click(deleteBtn)

    await waitFor(() => {
      expect(screen.queryByText('Shell Pasadena North')).not.toBeInTheDocument()
      expect(screen.getByText('Refueling Records (1)')).toBeInTheDocument()
    })
  })

  it('renders garage management, displays clean archetype thumbnails, and switches active car', async () => {
    const update = vi.fn()
    const car1 = {
      id: 101,
      label: '2018 Mercedes-Benz E400 Coupe',
      fuelType: 'premium' as const,
      combinedMpg: '22',
    }
    const car2 = {
      id: 102,
      label: '2021 Toyota RAV4 Hybrid',
      fuelType: 'regular' as const,
      combinedMpg: '40',
    }

    render(
      <MyPage
        prefs={{
          ...DEFAULT_PREFS,
          vehicle: car1,
          garage: [car1, car2],
        }}
        update={update}
        onNavigateToFuel={() => {}}
      />,
    )

    // Garage header
    expect(screen.getByText('My Garage')).toBeInTheDocument()

    // Both cars rendered with labels
    expect(screen.getByText('2018 Mercedes-Benz E400 Coupe')).toBeInTheDocument()
    expect(screen.getByText('2021 Toyota RAV4 Hybrid')).toBeInTheDocument()

    // Clean thumbnails infer archetypes: Coupe and SUV
    expect(screen.getByText('Coupe')).toBeInTheDocument()
    expect(screen.getByText('SUV')).toBeInTheDocument()

    // Car 1 is active, Car 2 has switch button
    expect(screen.getByText('Currently Active')).toBeInTheDocument()
    const switchBtn = screen.getByRole('button', { name: 'Switch to this car' })
    fireEvent.click(switchBtn)

    expect(update).toHaveBeenCalledWith(
      expect.objectContaining({
        vehicle: car2,
        fuelType: 'regular',
        mpg: '40',
      }),
    )

    // Remove car
    const removeBtns = screen.getAllByRole('button', { name: 'Remove vehicle' })
    fireEvent.click(removeBtns[1]) // click remove on car2

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Are you sure you want to remove this vehicle from your garage?')).toBeInTheDocument()
    const confirmRemoveBtn = screen.getAllByRole('button', { name: 'Remove vehicle' })
    fireEvent.click(confirmRemoveBtn[confirmRemoveBtn.length - 1])

    expect(update).toHaveBeenCalledWith(
      expect.objectContaining({
        garage: [car1],
      }),
    )
  })

  it('allows user to customize vehicle colors in garage', async () => {
    const update = vi.fn()
    const car = {
      id: 201,
      label: '2018 Mercedes-Benz E400 Coupe',
      fuelType: 'premium' as const,
      combinedMpg: '22',
      color: '#1e293b',
    }

    render(
      <MyPage
        prefs={{
          ...DEFAULT_PREFS,
          vehicle: car,
          garage: [car],
        }}
        update={update}
        onNavigateToFuel={() => {}}
      />,
    )

    // Open color customization
    const colorBtn = screen.getByRole('button', { name: 'Vehicle Color' })
    fireEvent.click(colorBtn)

    // Pick Soul Red
    const redBtn = screen.getByRole('button', { name: 'Soul Red' })
    fireEvent.click(redBtn)

    expect(update).toHaveBeenCalledWith(
      expect.objectContaining({
        garage: [expect.objectContaining({ color: '#dc2626' })],
        vehicle: expect.objectContaining({ color: '#dc2626' }),
      }),
    )
  })

  it('renders integrated life zones, personal driving & payment preferences and privacy vault in MyPage', async () => {
    const update = vi.fn()
    const replace = vi.fn()

    render(
      <MyPage
        prefs={DEFAULT_PREFS}
        update={update}
        replace={replace}
        onNavigateToFuel={() => {}}
      />,
    )

    // Life zones section
    expect(screen.getByText('Life Zones & Commute')).toBeInTheDocument()

    // Personal Driving & Payment Preferences section
    expect(screen.getByText('Driving & Payment Defaults')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Google Maps' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Apple Maps' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Waze' })).toBeInTheDocument()

    // Quick cashback preset button click
    const presetBtn = screen.getByRole('button', { name: 'Costco (4%)' })
    fireEvent.click(presetBtn)
    expect(update).toHaveBeenCalledWith({ creditCashbackPercent: '4' })

    // Privacy vault backup & reset section
    expect(screen.getByRole('button', { name: 'Export encrypted backup' })).toBeInTheDocument()
  })
})
