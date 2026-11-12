import { EyeIcon, EyeSlashIcon, TrendDownIcon, TrendUpIcon } from '@phosphor-icons/react'
import { useI18n } from '../../i18n'
import { perGallon } from '../../lib/format'
import type { ComputedChartData } from './priceChartMath'

interface MultiStationPriceLegendProps {
  series: ComputedChartData['series']
  onToggleStation: (id: string) => void
}

export function MultiStationPriceLegend({
  series,
  onToggleStation,
}: MultiStationPriceLegendProps) {
  const { t } = useI18n()

  if (series.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-2">
      {series.map((s) => {
        const isHidden = s.hidden
        return (
          <button
            key={s.station.id}
            type="button"
            onClick={() => onToggleStation(s.station.id)}
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
                {s.delta > 0 ? '+' : '-'}${Math.abs(s.delta).toFixed(2)}
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
  )
}
