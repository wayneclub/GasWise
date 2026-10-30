import {
  ChartLineUpIcon,
  EyeIcon,
  EyeSlashIcon,
  TrendDownIcon,
  TrendUpIcon,
  WarningIcon,
} from '@phosphor-icons/react'
import { useEffect, useMemo, useState } from 'react'
import { api, type HistoryAnalysis, type PriceObservation } from '../../api/client'
import { Button } from '../../components/ui'
import { useI18n } from '../../i18n'
import { perGallon } from '../../lib/format'
import type { FavoriteStation } from '../../lib/favorites'

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

const STATION_PALETTE = [
  { stroke: '#10b981', bg: 'bg-emerald-500', text: 'text-emerald-600 dark:text-emerald-400', badge: 'bg-emerald-500/10 border-emerald-500/30' },
  { stroke: '#0ea5e9', bg: 'bg-sky-500', text: 'text-sky-600 dark:text-sky-400', badge: 'bg-sky-500/10 border-sky-500/30' },
  { stroke: '#8b5cf6', bg: 'bg-violet-500', text: 'text-violet-600 dark:text-violet-400', badge: 'bg-violet-500/10 border-violet-500/30' },
  { stroke: '#f59e0b', bg: 'bg-amber-500', text: 'text-amber-600 dark:text-amber-400', badge: 'bg-amber-500/10 border-amber-500/30' },
  { stroke: '#ec4899', bg: 'bg-rose-500', text: 'text-rose-600 dark:text-rose-400', badge: 'bg-rose-500/10 border-rose-500/30' },
]

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
  const [hoveredPoint, setHoveredPoint] = useState<{
    stationName: string
    color: string
    time: number
    price: number
    x: number
    y: number
  } | null>(null)
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
      } catch (err: any) {
        if (err?.name === 'AbortError') throw err
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

        // Compute overall trend analysis to pass to parent advisor
        if (onTrendAnalysis) {
          let totalDelta = 0
          let deltaCount = 0
          let preWeekendRisk = false
          let cycleLowCount = 0

          for (const item of results) {
            if (item.analysis?.weekend_cycle?.pre_weekend_hike_risk) {
              preWeekendRisk = true
            }
            if (item.analysis?.price_band?.band === 'near_low' || item.analysis?.price_band?.is_cycle_low) {
              cycleLowCount++
            }
            const valid = (item.observations ?? [])
              .filter((o) => Number.isFinite(Number(o.price)) && Number(o.price) > 0)
              .sort((a, b) => parseTimestamp(a) - parseTimestamp(b))
            if (valid.length >= 2) {
              const firstP = Number(valid[0].price)
              const lastP = Number(valid[valid.length - 1].price)
              totalDelta += lastP - firstP
              deltaCount++
            }
          }

          const avgDelta = deltaCount > 0 ? totalDelta / deltaCount : 0
          const trend = avgDelta < -0.04 ? 'falling' : avgDelta > 0.04 ? 'rising' : 'stable'
          onTrendAnalysis({
            trend,
            delta: avgDelta,
            preWeekendHikeRisk: preWeekendRisk,
            cycleLow: cycleLowCount > 0,
          })
        }
      })
      .catch((_err) => {
        if (controller.signal.aborted) return
        setError(true)
        setLoading(false)
      })

    return () => controller.abort()
  }, [eligibleStations, fuelType, days, retryCount, onTrendAnalysis])

  // Process data for the SVG chart
  const chartData = useMemo(() => {
    const series = stationHistories.map((item, idx) => {
      const palette = STATION_PALETTE[idx % STATION_PALETTE.length]
      const validObs = (item.observations ?? [])
        .map((obs) => {
          const t = parseTimestamp(obs)
          const p = Number(obs.price)
          return { time: t, price: p, raw: obs }
        })
        .filter((d) => Number.isFinite(d.time) && Number.isFinite(d.price) && d.price > 0)
        .sort((a, b) => a.time - b.time)

      const first = validObs[0]
      const last = validObs[validObs.length - 1]
      const delta = first && last && validObs.length > 1 ? last.price - first.price : 0

      return {
        station: item.station,
        palette,
        points: validObs,
        firstPrice: first?.price ?? null,
        lastPrice: last?.price ?? null,
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
      {chartData.series.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          {chartData.series.map((s) => {
            const isHidden = s.hidden
            return (
              <button
                key={s.station.id}
                type="button"
                onClick={() => toggleStation(s.station.id)}
                title={t('favorites.historyStationToggle')}
                className={`flex items-center gap-2 rounded-control border px-3 py-1.5 text-xs transition-all ${
                  isHidden
                    ? 'border-line/60 bg-sunken/40 text-muted/60 opacity-50 line-through'
                    : `${s.palette.badge} bg-surface text-ink shadow-sm`
                }`}
              >
                <span
                  className="size-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: isHidden ? '#9ca3af' : s.palette.stroke }}
                />
                <span className="font-semibold truncate max-w-[130px] sm:max-w-[180px]">
                  {s.station.name}
                </span>
                {s.lastPrice ? (
                  <span className="num font-bold text-ink">
                    {perGallon(s.lastPrice.toFixed(2))}
                  </span>
                ) : null}
                {s.delta !== 0 ? (
                  <span
                    className={`num text-[11px] font-semibold flex items-center ${
                      s.delta < 0
                        ? 'text-emerald-600 dark:text-emerald-400'
                        : 'text-amber-600 dark:text-amber-400'
                    }`}
                  >
                    {s.delta < 0 ? (
                      <TrendDownIcon size={12} weight="bold" className="mr-0.5 inline" />
                    ) : (
                      <TrendUpIcon size={12} weight="bold" className="mr-0.5 inline" />
                    )}
                    {s.delta > 0 ? `+` : `-`}${Math.abs(s.delta).toFixed(2)}
                  </span>
                ) : null}
                {isHidden ? (
                  <EyeSlashIcon size={14} className="text-muted ml-0.5 shrink-0" />
                ) : (
                  <EyeIcon size={14} className="text-muted/70 ml-0.5 shrink-0" />
                )}
              </button>
            )
          })}
        </div>
      ) : null}

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
          <div className="w-full overflow-hidden">
            <svg
              viewBox={`0 0 ${chartData.svgWidth} ${chartData.svgHeight}`}
              role="img"
              aria-label={t('favorites.historyCompareTitle')}
              className="w-full h-auto text-ink font-sans select-none overflow-visible"
            >
              {/* Horizontal Gridlines & Price Ticks */}
              {chartData.gridLines?.map((grid, i) => (
                <g key={i}>
                  <line
                    x1="46"
                    y1={grid.y}
                    x2="500"
                    y2={grid.y}
                    stroke="currentColor"
                    strokeOpacity="0.12"
                    strokeDasharray="4 4"
                  />
                  <text
                    x="42"
                    y={grid.y + 3.5}
                    textAnchor="end"
                    fontSize="10"
                    fill="currentColor"
                    opacity="0.65"
                    className="num"
                  >
                    ${grid.price.toFixed(2)}
                  </text>
                </g>
              ))}

              {/* Vertical Date Ticks along Bottom */}
              {chartData.dateTicks?.map((tick, i) => (
                <g key={i}>
                  <line
                    x1={tick.x}
                    y1={chartData.svgHeight! - 34}
                    x2={tick.x}
                    y2={chartData.svgHeight! - 30}
                    stroke="currentColor"
                    strokeOpacity="0.3"
                  />
                  <text
                    x={tick.x}
                    y={chartData.svgHeight! - 18}
                    textAnchor="middle"
                    fontSize="10"
                    fill="currentColor"
                    opacity="0.6"
                  >
                    {tick.label}
                  </text>
                </g>
              ))}

              {/* Station Continuous Polylines */}
              {chartData.plottedLines?.map((pl) => (
                <g key={pl.station.id}>
                  {/* Glowing backdrop shadow line for depth */}
                  <path
                    d={pl.pathData}
                    fill="none"
                    stroke={pl.palette.stroke}
                    strokeWidth="4"
                    strokeOpacity="0.15"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  {/* Main Line */}
                  <path
                    d={pl.pathData}
                    fill="none"
                    stroke={pl.palette.stroke}
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />

                  {/* Observation Dot Markers */}
                  {pl.coordinates.map((coord, ci) => {
                    const isHovered =
                      hoveredPoint?.stationName === pl.station.name &&
                      hoveredPoint?.time === coord.time
                    return (
                      <circle
                        key={ci}
                        cx={coord.x}
                        cy={coord.y}
                        r={isHovered ? 6 : 3.5}
                        fill={pl.palette.stroke}
                        stroke="#ffffff"
                        strokeWidth={isHovered ? 2 : 1}
                        className="cursor-pointer transition-all duration-150"
                        onMouseEnter={() =>
                          setHoveredPoint({
                            stationName: pl.station.name,
                            color: pl.palette.stroke,
                            time: coord.time,
                            price: coord.price,
                            x: coord.x,
                            y: coord.y,
                          })
                        }
                        onClick={() =>
                          setHoveredPoint({
                            stationName: pl.station.name,
                            color: pl.palette.stroke,
                            time: coord.time,
                            price: coord.price,
                            x: coord.x,
                            y: coord.y,
                          })
                        }
                      >
                        <title>
                          {pl.station.name}: {perGallon(String(coord.price))} ({formatFullDate(coord.time)})
                        </title>
                      </circle>
                    )
                  })}
                </g>
              ))}
            </svg>
          </div>

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
