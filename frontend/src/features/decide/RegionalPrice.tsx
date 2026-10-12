import type { RankedStation } from '../../api/types'
import { useI18n } from '../../i18n'
import { comparisonPrice } from '../../lib/format'

export function RegionalPrice({row}: {row:RankedStation}) {
  const {t} = useI18n()
  const benchmark = row.regional_benchmark
  if (!benchmark) return null
  const difference = Number(comparisonPrice(row.station)) - Number(benchmark.price_per_gallon)
  return <div className="mt-1 text-[11px] leading-relaxed" title={t('board.context')}>
    <a className={difference <= 0 ? 'font-medium text-accent' : 'font-medium text-caution'} href={benchmark.source_url} target="_blank" rel="noreferrer">
      {difference <= 0 ? '↓' : '↑'} ${Math.abs(difference).toFixed(2)}/gal · {t('board.benchmark',{region:benchmark.region})}
    </a>
    <p className="text-faint">${Number(benchmark.price_per_gallon).toFixed(4)}/gal · {t('board.date',{scope:t(benchmark.scope === 'metro' ? 'board.metro' : 'board.state'),date:benchmark.price_as_of})}</p>
  </div>
}
