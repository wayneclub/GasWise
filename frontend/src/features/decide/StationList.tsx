import { SourcePill } from './SourcePill'
import { RegionalPrice } from './RegionalPrice'
import { CaretDownIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import type { RankedStation } from '../../api/types'
import { useI18n } from '../../i18n'
import type { NavApp } from '../../lib/prefs'
import { StationDetails, StationRating, TopTierBadge } from './StationDetails'
import { age, comparisonPrice, minutes, perGallon, usd } from '../../lib/format'


export function StationList({ rows, navApp = 'google', tripMode = 'round_trip' }: { rows: RankedStation[]; navApp?: NavApp; tripMode?: 'round_trip' | 'on_route' }) {
  const { t } = useI18n()
  const [selected, setSelected] = useState<RankedStation | null>(null)
  const [open, setOpen] = useState(false)
  if (rows.length < 2) return null
  return (
    <section className="rounded-box border border-line bg-surface shadow-raised">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-5 py-4 text-left"
      >
        <span className="num text-[15px] font-medium">{t('list.compare', { count: rows.length })}</span>
        <CaretDownIcon size={16} className={`text-muted transition ${open ? 'rotate-180' : ''}`} />
      </button>
      {open ? (
        <table className="w-full border-t border-line text-[14px]">
          <thead className="bg-sunken/50 text-xs text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">{t('list.station')}</th>
              <th className="px-3 py-2 font-medium">{t('list.price')}</th>
              <th className="px-3 py-2 font-medium">{t('list.total')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.station.source}:${row.station.id}`} className="align-top">
                <td className="py-3 pl-5 pr-2">
                  <div className="flex flex-wrap items-center gap-1.5"><button type="button" onClick={() => setSelected(row)} className="font-medium underline decoration-line underline-offset-4" aria-label={`${t('station.view')} ${row.station.name}`}>{row.station.name}</button>{row.station.top_tier_brand ? <TopTierBadge brand={row.station.top_tier_brand} /> : null}</div><StationRating station={row.station} /><RegionalPrice row={row}/>
                  {row?.route.source === "straight_line_estimate" ? <p className="text-xs text-caution">{t("coverage.estimated_route")}</p> : null}
                  <SourcePill source={row.station.source}/><p className="num mt-1 text-[12px] text-muted">
                    {t(tripMode==='on_route'?'route.extraTime':'pick.roundTrip',{time:minutes(row.extra_travel_minutes,t)})} · {t('age.updated',{age:age(row.station.price_updated_at,t)})}
                  </p>
                </td>
                <td className="num py-3 pr-2 text-right">{perGallon(comparisonPrice(row.station))}{row.station.comparison_price_per_gallon ? <span className="mt-1 block text-[10px] text-caution">{t('payment.estimated')}</span> : null}</td>
                <td className="num py-3 pr-5 text-right font-medium">{usd(row.actual_fuel_cost)}<div className="mt-2 h-1.5 w-full min-w-12 overflow-hidden rounded-full bg-sunken" aria-hidden="true"><div className="h-full rounded-full bg-accent/50" style={{ width: `${Math.min(100, 100 * Number(row.actual_fuel_cost) / Math.max(...rows.map((r) => Number(r.actual_fuel_cost))))}%` }}/></div></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {selected ? <StationDetails station={selected.station} row={selected} open onClose={() => setSelected(null)} navApp={navApp} tripMode={tripMode} /> : null}
    </section>
  )
}
