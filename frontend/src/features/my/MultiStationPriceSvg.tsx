import { useI18n } from '../../i18n'
import { perGallon } from '../../lib/format'
import type { ComputedChartData } from './priceChartMath'

export interface HoveredChartPoint {
  stationName: string
  color: string
  time: number
  price: number
  x: number
  y: number
}

interface MultiStationPriceSvgProps {
  chartData: ComputedChartData
  hoveredPoint: HoveredChartPoint | null
  onHoverPoint: (pt: HoveredChartPoint) => void
  formatFullDate: (time: number) => string
}

export function MultiStationPriceSvg({
  chartData,
  hoveredPoint,
  onHoverPoint,
  formatFullDate,
}: MultiStationPriceSvgProps) {
  const { t } = useI18n()

  if (!chartData.hasData || !chartData.svgWidth || !chartData.svgHeight) return null

  return (
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
                    onHoverPoint({
                      stationName: pl.station.name,
                      color: pl.palette.stroke,
                      time: coord.time,
                      price: coord.price,
                      x: coord.x,
                      y: coord.y,
                    })
                  }
                  onClick={() =>
                    onHoverPoint({
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
  )
}
