import { ChartLineUpIcon, WarningIcon } from '@phosphor-icons/react'
import { useEffect, useMemo, useState } from 'react'
import { api, type HistoryAnalysis, type PriceObservation } from '../../api/client'
import { Button } from '../../components/ui'
import { useI18n } from '../../i18n'
import { perGallon } from '../../lib/format'
import type { FavoriteStation } from '../../lib/favorites'
import {
  STATION_PALETTE,
  type ComputedChartData,
} from './priceChartMath'
import { MultiStationPriceLegend } from './MultiStationPriceLegend'
import {
  MultiStationPriceSvg,
  type HoveredChartPoint,
} from './MultiStationPriceSvg'

export interface TrendAnalysisSummary {
  trend: 'falling' | 'rising' | 'stable'
  delta: number
  preWeekendHikeRisk: boolean
  cycleLow: boolean
  cheapestObservedStationId?: string
}

interface MultiStationPriceChartProps {
  favorites: FavoriteStation[]
  fuelType?: 'regular' | 'midgrade' | 'premium' | 'diesel'
  onTrendAnalysis?: (summary: TrendAnalysisSummary) => void
}

const parseTimestamp = (row: PriceObservation) =>
  new Date(row.observation_kind === 'daily_check' ? row.observed_at : row.reported_at ?? row.observed_at).getTime()

export function MultiStationPriceChart({
  favorites,
  fuelType = 'regular',
  onTrendAnalysis,
}: MultiStationPriceChartProps) {
  const { t, locale } = useI18n()
  const [days, setDays] = useState<7 | 30 | 90>(30)
  const [hiddenStationIds, setHiddenStationIds] = useState<Set<string>>(new Set())
  const [hoveredPoint, setHoveredPoint] = useState<HoveredChartPoint | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const [stationHistories, setStationHistories] = useState<
    Array<{
      station: FavoriteStation
      observations: PriceObservation[]
      analysis?: HistoryAnalysis | null
    }>
  >([])

  // Eligible stations for history lookup (limit to 5 for optimal chart clarity)
  const eligibleStations = useMemo(() => {
    return favorites
      .filter((s) => s.stationId || s.canonicalId || s.id)
      .slice(0, 5)
  }, [favorites])

  useEffect(() => {
    if (eligibleStations.length === 0) return

    const controller = new AbortController()
    queueMicrotask(() => {
      if (!controller.signal.aborted) {
        setLoading(true)
        setError(false)
      }
    })

    const fetchPromises = eligibleStations.map(async (station) => {
      const source = station.source || (station.id.includes(':') ? station.id.split(':')[0] : 'gasbuddy')
      const stationId = station.stationId || (station.id.includes(':') ? station.id.split(':')[1] : station.id)
      try {
        const res = await api.priceHistory(
          {
            canonical_id: station.canonicalId ?? undefined,
            source,
            station_id: stationId,
            fuel_type: (station.fuelType as any) || fuelType,
            days,
          },
          controller.signal,
        )
        return {
          station,
          observations: res.observations ?? [],
          analysis: res.analysis,
        }
      } catch {
        return {
          station,
          observations: [],
          analysis: null,
        }
      }
    })

    Promise.all(fetchPromises)
      .then((results) => {
        if (controller.signal.aborted) return
        setStationHistories(results)
        setLoading(false)

        // Calculate macro trend analysis
        const analyses = results.map((r) => r.analysis).filter(Boolean) as HistoryAnalysis[]
        if (analyses.length > 0 && onTrendAnalysis) {
          const fallingCount = analyses.filter((a) => a.trend === 'falling').length
          const risingCount = analyses.filter((a) => a.trend === 'rising').length
          const avgDelta = analyses.reduce((acc, a) => acc + (a.delta ?? 0), 0) / analyses.length
          const anyHikeRisk = analyses.some((a) => a.pre_weekend_hike_risk)
          const anyCycleLow = analyses.some((a) => a.cycle_low)

          const validLastPrices = results
            .map((r) => {
              const pts = r.observations
                .map((o) => ({
                  time: parseTimestamp(o),
                  price: typeof o.price === 'number' ? o.price : parseFloat(String(o.price)),
                }))
                .filter((p) => !isNaN(p.price) && p.price > 0)
                .sort((a, b) => a.time - b.time)
              return {
                stationId: r.station.id,
                lastPrice: pts[pts.length - 1]?.price,
              }
            })
            .filter((x): x is { stationId: string; lastPrice: number } => typeof x.lastPrice === 'number')

          validLastPrices.sort((a, b) => a.lastPrice - b.lastPrice)
          const cheapestId = validLastPrices[0]?.stationId

          onTrendAnalysis({
            trend: fallingCount > risingCount ? 'falling' : risingCount > fallingCount ? 'rising' : 'stable',
            delta: avgDelta,
            preWeekendHikeRisk: anyHikeRisk,
            cycleLow: anyCycleLow,
            cheapestObservedStationId: cheapestId,
          })
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setError(true)
          setLoading(false)
        }
      })

    return () => {
      controller.abort()
    }
  }, [eligibleStations, days, fuelType, retryCount, onTrendAnalysis])

  // Process data for multi-line SVG plotting
  const chartData: ComputedChartData = useMemo(() => {
    const series = stationHistories.map((item, idx) => {
      const palette = STATION_PALETTE[idx % STATION_PALETTE.length]
      const points = (item.observations ?? [])
        .map((o) => ({
          time: parseTimestamp(o),
          price: typeof o.price === 'number' ? o.price : parseFloat(String(o.price)),
        }))
        .filter((p) => !isNaN(p.price) && p.price > 0)
        .sort((a, b) => a.time - b.time)

      const lastPrice = points[points.length - 1]?.price
      const firstPrice = points[0]?.price
      const delta = lastPrice != null && firstPrice != null ? lastPrice - firstPrice : 0

      return {
        station: item.station,
        palette,
        points,
        lastPrice,
        delta,
        hidden: hiddenStationIds.has(item.station.id),
      }
    })

    const visibleSeries = series.filter((s) => !s.hidden && s.points.length > 0)
    const allVisiblePoints = visibleSeries.flatMap((s) => s.points)

    if (allVisiblePoints.length === 0) {
      return { series, visibleSeries, hasData: false }
    }

    const times = allVisiblePoints.map((p) => p.time)
    const prices = allVisiblePoints.map((p) => p.price)

    let minTime = Math.min(...times)
    let maxTime = Math.max(...times)
    if (minTime === maxTime) {
      minTime -= 24 * 60 * 60 * 1000
      maxTime += 24 * 60 * 60 * 1000
    }

    let minPrice = Math.min(...prices)
    let maxPrice = Math.max(...prices)
    if (minPrice === maxPrice) {
      minPrice -= 0.2
      maxPrice += 0.2
    }

    // Add 10% breathing room on Y axis
    const pad = Math.max(0.08, (maxPrice - minPrice) * 0.12)
    const yMin = Math.max(0, minPrice - pad)
    const yMax = maxPrice + pad

    // SVG coordinate mapping
    const svgWidth = 520
    const svgHeight = 220
    const marginLeft = 46
    const marginRight = 20
    const marginTop = 20
    const marginBottom = 34
    const plotWidth = svgWidth - marginLeft - marginRight
    const plotHeight = svgHeight - marginTop - marginBottom

    const getX = (t: number) => marginLeft + ((t - minTime) / (maxTime - minTime)) * plotWidth
    const getY = (p: number) => marginTop + plotHeight - ((p - yMin) / (yMax - yMin)) * plotHeight

    // Horizontal grid line levels
    const gridSteps = 4
    const gridLines = Array.from({ length: gridSteps + 1 }, (_, i) => {
      const price = yMin + ((yMax - yMin) / gridSteps) * i
      return { price, y: getY(price) }
    })

    // X-axis date ticks (4 evenly spaced)
    const dateTicks = Array.from({ length: 4 }, (_, i) => {
      const time = minTime + ((maxTime - minTime) / 3) * i
      return {
        time,
        x: getX(time),
        label: new Intl.DateTimeFormat(locale, { month: 'numeric', day: 'numeric' }).format(new Date(time)),
      }
    })

    // Plotted line paths
    const plottedLines = visibleSeries.map((s) => {
      const coordinates = s.points.map((p) => ({
        x: getX(p.time),
        y: getY(p.price),
        price: p.price,
        time: p.time,
      }))

      const pathData = coordinates
        .map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt.x.toFixed(1)},${pt.y.toFixed(1)}`)
        .join(' ')

      return {
        station: s.station,
        palette: s.palette,
        coordinates,
        pathData,
      }
    })

    return {
      series,
      visibleSeries,
      hasData: true,
      minPrice,
      maxPrice,
      gridLines,
      dateTicks,
      plottedLines,
      svgWidth,
      svgHeight,
    }
  }, [stationHistories, hiddenStationIds, locale])

  const toggleStation = (id: string) => {
    setHiddenStationIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const formatFullDate = (time: number) =>
    new Intl.DateTimeFormat(locale, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(time))

  return (
    <section
      aria-label={t('favorites.historyCompareTitle')}
      className="rounded-box border border-line bg-surface p-5 sm:p-6 shadow-sm flex flex-col gap-5"
    >
      {/* Header and Controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-line pb-4">
        <div>
          <div className="flex items-center gap-2">
            <ChartLineUpIcon size={22} weight="bold" className="text-accent" />
            <h2 className="text-base font-bold text-ink sm:text-lg">
              {t('favorites.historyCompareTitle')}
            </h2>
          </div>
          <p className="mt-0.5 text-xs text-muted">
            {t('favorites.historyCompareSubtitle')}
          </p>
        </div>

        {/* Days Filter */}
        <div className="flex items-center gap-1.5 self-start sm:self-auto">
          {([7, 30, 90] as const).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={days === v}
              onClick={() => {
                setDays(v)
                setHoveredPoint(null)
              }}
              className={`rounded-control px-3 py-1.5 text-xs font-semibold transition-colors ${
                days === v
                  ? 'bg-accent text-white shadow-sm'
                  : 'bg-sunken text-muted hover:text-ink'
              }`}
            >
              {v === 7
                ? t('favorites.historyDays7')
                : v === 30
                ? t('favorites.historyDays30')
                : t('favorites.historyDays90')}
            </button>
          ))}
        </div>
      </div>

      {/* Station Badges & Toggle Pill Legend */}
      <MultiStationPriceLegend
        series={chartData.series}
        onToggleStation={toggleStation}
      />

      {/* Multi-Station Notice if only 1 station */}
      {eligibleStations.length === 1 ? (
        <div className="rounded-control bg-accent-soft/30 border border-accent/30 p-2.5 text-xs text-ink">
          💡 {t('favorites.historyMultiStationNotice')}
        </div>
      ) : null}

      {/* Main Chart Area */}
      {loading ? (
        <div className="h-56 w-full flex flex-col items-center justify-center rounded-control bg-sunken/40 border border-line gap-3 text-muted text-xs">
          <div className="size-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          <span>{t('favorites.historyLoading')}</span>
        </div>
      ) : error ? (
        <div className="h-44 w-full flex flex-col items-center justify-center rounded-control bg-sunken p-4 text-center gap-2">
          <WarningIcon size={24} className="text-caution" />
          <p className="text-xs text-muted">{t('favorites.historyError')}</p>
          <Button
            variant="secondary"
            onClick={() => setRetryCount((c) => c + 1)}
            className="text-xs"
          >
            {t('history.retry')}
          </Button>
        </div>
      ) : !chartData.hasData ? (
        <div className="h-44 w-full flex flex-col items-center justify-center rounded-control bg-sunken/50 border border-dashed border-line p-6 text-center text-xs text-muted">
          <ChartLineUpIcon size={28} className="text-muted/60 mb-2" />
          <p>{t('favorites.historyEmpty')}</p>
        </div>
      ) : (
        <div className="relative">
          {/* Responsive SVG Chart */}
          <MultiStationPriceSvg
            chartData={chartData}
            hoveredPoint={hoveredPoint}
            onHoverPoint={setHoveredPoint}
            formatFullDate={formatFullDate}
          />

          {/* Floating Tooltip Box when Point is Hovered/Tapped */}
          {hoveredPoint ? (
            <div
              className="mt-2 flex items-center justify-between gap-3 rounded-control border border-line bg-surface p-2.5 text-xs shadow-md"
              style={{ borderLeftColor: hoveredPoint.color, borderLeftWidth: 4 }}
            >
              <div className="flex items-center gap-2">
                <span
                  className="size-2 rounded-full shrink-0"
                  style={{ backgroundColor: hoveredPoint.color }}
                />
                <span className="font-bold text-ink truncate max-w-[160px] sm:max-w-none">
                  {hoveredPoint.stationName}
                </span>
                <span className="text-muted text-[11px]">
                  ({formatFullDate(hoveredPoint.time)})
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="num font-bold text-ink text-sm">
                  {perGallon(hoveredPoint.price.toFixed(2))}
                </span>
                <button
                  type="button"
                  onClick={() => setHoveredPoint(null)}
                  className="text-muted hover:text-ink text-xs px-1"
                >
                  ✕
                </button>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </section>
  )
}
