import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { api } from '../../api/client'
import { MultiStationPriceChart } from './MultiStationPriceChart'
import type { FavoriteStation } from '../../lib/favorites'

const mockStation1: FavoriteStation = {
  id: 'gasbuddy:101',
  stationId: '101',
  source: 'gasbuddy',
  name: 'Costco Wholesale',
  location: { lat: 34.05, lng: -118.25 },
  addedAt: '2026-10-25T10:00:00Z',
  lastObservedPrice: '4.29',
  topTierBrand: 'Costco',
}

const mockStation2: FavoriteStation = {
  id: 'waze:202',
  stationId: '202',
  source: 'waze',
  name: 'Chevron',
  location: { lat: 34.06, lng: -118.26 },
  addedAt: '2026-10-26T10:00:00Z',
  lastObservedPrice: '4.89',
  topTierBrand: 'Chevron',
}

describe('MultiStationPriceChart', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders loading state and displays multi-station continuous comparison chart upon success', async () => {
    vi.spyOn(api, 'priceHistory').mockImplementation(async (req) => {
      if (req.station_id === '101') {
        return {
          observations: [
            {
              observation_kind: 'report',
              source: 'gasbuddy',
              station_id: '101',
              payment_type: 'cash',
              condition: 'regular',
              price: '4.35',
              reported_at: '2026-10-10T10:00:00Z',
              observed_at: '2026-10-10T10:00:00Z',
              membership: null,
              octane: 87,
            },
            {
              observation_kind: 'report',
              source: 'gasbuddy',
              station_id: '101',
              payment_type: 'cash',
              condition: 'regular',
              price: '4.29',
              reported_at: '2026-10-25T10:00:00Z',
              observed_at: '2026-10-25T10:00:00Z',
              membership: null,
              octane: 87,
            },
          ],
          truncated: false,
          analysis: {
            price_band: {
              min_price: '4.29',
              max_price: '4.45',
              median_price: '4.35',
              current_price: '4.29',
              percentile: 15,
              band: 'near_low',
              is_cycle_low: true,
              is_cycle_high: false,
              advice: 'Great time to fill',
            },
            weekend_cycle: {
              day_of_week: 'Thursday',
              is_pre_weekend: true,
              pre_weekend_hike_risk: false,
              risk_level: 'low',
              trend: 'falling',
              message: 'Stable cycle',
            },
            observation_count: 2,
          },
        }
      }

      return {
        observations: [
          {
            observation_kind: 'report',
            source: 'waze',
            station_id: '202',
            payment_type: 'credit',
            condition: 'regular',
            price: '4.79',
            reported_at: '2026-10-10T10:00:00Z',
            observed_at: '2026-10-10T10:00:00Z',
            membership: null,
            octane: 87,
          },
          {
            observation_kind: 'report',
            source: 'waze',
            station_id: '202',
            payment_type: 'credit',
            condition: 'regular',
            price: '4.89',
            reported_at: '2026-10-25T10:00:00Z',
            observed_at: '2026-10-25T10:00:00Z',
            membership: null,
            octane: 87,
          },
        ],
        truncated: false,
        analysis: null,
      }
    })

    const onTrendAnalysis = vi.fn()
    render(
      <MultiStationPriceChart
        favorites={[mockStation1, mockStation2]}
        fuelType="regular"
        onTrendAnalysis={onTrendAnalysis}
      />
    )

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('Costco Wholesale')).toBeInTheDocument()
      expect(screen.getByText('Chevron')).toBeInTheDocument()
    })

    // Station badges with prices rendered
    expect(screen.getAllByText('$4.29').length).toBeGreaterThan(0)
    expect(screen.getAllByText('$4.89').length).toBeGreaterThan(0)

    // Verify SVG is rendered with role="img"
    const svgChart = screen.getByRole('img', { name: /走勢|Trend|推移|추이|tendencias/i })
    expect(svgChart).toBeInTheDocument()

    // Test station line toggle
    const costcoToggle = screen.getByText('Costco Wholesale').closest('button')!
    fireEvent.click(costcoToggle)
    expect(costcoToggle.className).toContain('line-through')

    // Click again to toggle back
    fireEvent.click(costcoToggle)
    expect(costcoToggle.className).not.toContain('line-through')

    // Verify trend callback was triggered
    expect(onTrendAnalysis).toHaveBeenCalled()
  })

  it('handles empty observations gracefully', async () => {
    vi.spyOn(api, 'priceHistory').mockResolvedValue({
      observations: [],
      truncated: false,
      analysis: null,
    })

    render(
      <MultiStationPriceChart
        favorites={[mockStation1]}
        fuelType="regular"
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/暫無足夠|No historical price|十分にありません|충분한 과거/i)).toBeInTheDocument()
    })
  })
})
