import type { FavoriteStation } from '../../lib/favorites'

export interface StationPalette {
  stroke: string
  bg: string
  text: string
  badge: string
}

export const STATION_PALETTE: StationPalette[] = [
  { stroke: '#10b981', bg: 'bg-emerald-500', text: 'text-emerald-600 dark:text-emerald-400', badge: 'bg-emerald-500/10 border-emerald-500/30' },
  { stroke: '#0ea5e9', bg: 'bg-sky-500', text: 'text-sky-600 dark:text-sky-400', badge: 'bg-sky-500/10 border-sky-500/30' },
  { stroke: '#8b5cf6', bg: 'bg-violet-500', text: 'text-violet-600 dark:text-violet-400', badge: 'bg-violet-500/10 border-violet-500/30' },
  { stroke: '#f59e0b', bg: 'bg-amber-500', text: 'text-amber-600 dark:text-amber-400', badge: 'bg-amber-500/10 border-amber-500/30' },
  { stroke: '#ec4899', bg: 'bg-rose-500', text: 'text-rose-600 dark:text-rose-400', badge: 'bg-rose-500/10 border-rose-500/30' },
]

export interface PlottedCoordinate {
  x: number
  y: number
  price: number
  time: number
}

export interface PlottedLine {
  station: FavoriteStation
  palette: StationPalette
  coordinates: PlottedCoordinate[]
  pathData: string
}

export interface ComputedChartData {
  series: Array<{
    station: FavoriteStation
    palette: StationPalette
    points: Array<{ time: number; price: number }>
    lastPrice?: number
    delta: number
    hidden: boolean
  }>
  visibleSeries: Array<{
    station: FavoriteStation
    palette: StationPalette
    points: Array<{ time: number; price: number }>
    lastPrice?: number
    delta: number
    hidden: boolean
  }>
  hasData: boolean
  minPrice?: number
  maxPrice?: number
  gridLines?: Array<{ price: number; y: number }>
  dateTicks?: Array<{ time: number; x: number; label: string }>
  plottedLines?: PlottedLine[]
  svgWidth?: number
  svgHeight?: number
}
