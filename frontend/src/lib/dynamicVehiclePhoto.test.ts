import { describe, expect, it, vi, beforeEach } from 'vitest'
import { cleanVehicleQuery, fetchDynamicVehiclePhoto } from './dynamicVehiclePhoto'

describe('dynamicVehiclePhoto', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('cleans vehicle queries to extract search keywords cleanly', () => {
    expect(cleanVehicleQuery('2024 Mazda CX-30 Turbo Premium AWD')).toBe('2024 Mazda CX-30')
    expect(cleanVehicleQuery('2023 Genesis GV70 2.5T AWD')).toBe('2023 Genesis GV70 2.5T')
    expect(cleanVehicleQuery('2021 Volvo XC90 T6 Momentum 4dr')).toBe('2021 Volvo XC90 T6 Momentum')
    expect(cleanVehicleQuery('')).toBe('')
    expect(cleanVehicleQuery(null)).toBe('')
  })

  it('fetches photo from Wikipedia API and caches the result', async () => {
    const mockResponse = {
      query: {
        pages: {
          '12345': {
            pageid: 12345,
            title: 'Genesis GV70',
            thumbnail: {
              source: 'https://thumb.wikimedia.org/wikipedia/commons/thumb/test_gv70.jpg',
              width: 800,
              height: 500,
            },
          },
        },
      },
    }

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as Response)

    const url = await fetchDynamicVehiclePhoto('2023 Genesis GV70')
    expect(url).toBe('https://thumb.wikimedia.org/wikipedia/commons/thumb/test_gv70.jpg')
    expect(fetchSpy).toHaveBeenCalledTimes(1)

    // Second call should hit the cache without calling fetch again
    const cachedUrl = await fetchDynamicVehiclePhoto('2023 Genesis GV70')
    expect(cachedUrl).toBe('https://thumb.wikimedia.org/wikipedia/commons/thumb/test_gv70.jpg')
    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })

  it('handles API errors gracefully and returns null without throwing', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new Error('Network offline'))
    const result = await fetchDynamicVehiclePhoto('Nonexistent Brand Car 9999')
    expect(result).toBeNull()
  })
})
