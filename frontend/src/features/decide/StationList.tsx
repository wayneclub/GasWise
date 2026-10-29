import { CaretDownIcon, ClockIcon, CoinsIcon, GasPumpIcon, InfoIcon } from '@phosphor-icons/react'
import { useId, useState } from 'react'
import type { RankedStation } from '../../api/types'
import { CopyAddress } from '../../components/CopyAddress'
import { Select } from '../../components/Select'
import { Button } from '../../components/ui'
import { useI18n } from '../../i18n'
import { age, comparisonPrice, minutes, perGallon, usd } from '../../lib/format'
import type { NavApp } from '../../lib/prefs'
import { googleStationUrl } from '../../lib/stationLinks'
import { StationSources } from './SourcePill'
import { StationDetails, StationRating, TopTierBadge } from './StationDetails'
import './StationList.css'

type Sort = 'cost' | 'time' | 'price'

/** Compare displayed amounts so visible values and their differences reconcile. */
function displayed(value: string | number | null | undefined, decimals: number): number | null {
  if (value == null || String(value).trim() === '' || !Number.isFinite(Number(value)) || Number(value) < 0) return null
  return Math.round(Number(Number(value).toFixed(decimals)) * 10 ** decimals)
}
function minimum(values: (number | null)[]) {
  const valid = values.filter((value): value is number => value !== null)
  return valid.length ? Math.min(...valid) : null
}

export function StationList({ rows, navApp = 'google', tripMode = 'round_trip' }: { rows: RankedStation[]; navApp?: NavApp; tripMode?: 'round_trip' | 'on_route' }) {
  const { t } = useI18n()
  const id = useId()
  const [selected, setSelected] = useState<RankedStation | null>(null)
  const [open, setOpen] = useState(true)
  const [sort, setSort] = useState<Sort>('cost')
  const [visible, setVisible] = useState(5)
  if (rows.length < 2) return null
  const entries = rows.map((row, index) => ({ row, index, cost: displayed(row.actual_fuel_cost, 2), time: displayed(row.extra_travel_minutes, 3), price: displayed(comparisonPrice(row.station), 3) }))
  const lowest = minimum(entries.map(entry => entry.cost))
  const quickest = minimum(entries.map(entry => entry.time))
  const lowestPrice = minimum(entries.map(entry => entry.price))
  const ordered = [...entries].sort((a, b) => (a[sort] ?? Infinity) - (b[sort] ?? Infinity) || a.index - b.index)
  const timeLabel = t(tripMode === 'on_route' ? 'comparison.detourTime' : 'comparison.roundTrip')
  return <section aria-label={t('list.compare', { count: rows.length })} className="station-comparison min-w-0 rounded-box border border-line bg-surface">
    <h2><button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}
      className="flex min-h-14 w-full items-center justify-between gap-3 px-4 py-3 text-left text-base font-semibold sm:px-5">
      <span>{t('list.compare', { count: rows.length })}</span><CaretDownIcon size={18} aria-hidden="true" className={`shrink-0 text-muted ${open ? 'rotate-180' : ''}`} />
    </button></h2>
    {open ? <div id={id}>
      <div className="flex flex-col gap-3 px-4 pb-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
        <p className="flex min-w-0 items-start gap-1.5 text-xs leading-relaxed text-muted"><InfoIcon size={16} aria-hidden="true" className="mt-0.5 shrink-0" /><span>{t('comparison.basis')}</span></p>
        <Select<Sort> label={t('comparison.sort')} value={sort} onChange={next => { setSort(next); setVisible(5) }} className="w-full shrink-0 sm:w-48" options={[
          { value: 'cost', label: t('comparison.sortCost'), icon: <CoinsIcon size={19} /> },
          { value: 'time', label: t('comparison.sortTime'), icon: <ClockIcon size={19} /> },
          { value: 'price', label: t('comparison.sortPrice'), icon: <GasPumpIcon size={19} /> },
        ]} />
      </div>
      <table role="table" className="comparison-table" aria-label={t('list.compare', { count: rows.length })}>
        <thead role="rowgroup"><tr role="row"><th role="columnheader" scope="col">{t('list.station')}</th><th role="columnheader" scope="col">{t('list.total')}</th><th role="columnheader" scope="col">{timeLabel}</th><th role="columnheader" scope="col">{t('list.price')}</th></tr></thead>
        <tbody role="rowgroup">
          {ordered.slice(0, visible).map(({ row, index, cost, time, price }) => <tr role="row" key={`${row.price_comparison?.station_key ?? `${row.station.source}:${row.station.id}`}:${index}`}>
            <td role="cell" className="comparison-identity">
              <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
                <a href={googleStationUrl(row.station)} target="_blank" rel="noreferrer" className="break-words text-base font-semibold underline decoration-line underline-offset-4">{row.station.name}</a>
                {row.station.top_tier_brand ? <TopTierBadge brand={row.station.top_tier_brand} /> : null}
                <button type="button" onClick={() => setSelected(row)} aria-label={`${t('station.view')} ${row.station.name}`} className="ml-auto min-h-11 shrink-0 rounded-control px-2 text-xs text-muted underline hover:bg-sunken focus-visible:outline-accent">{t('station.view')}</button>
              </div>
              <CopyAddress address={row.station.address} display={row.station.address?.split(',')[0]} className="w-full text-xs text-muted" />
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">{row.station.rating != null ? <StationRating station={row.station} /> : null}{row.station.membership_required ? <span className="text-xs text-caution">{t('station.member', { name: row.station.membership_required })}</span> : null}</div>
              <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1"><StationSources source={row.station.source} row={row} selectedOnly /><span className="text-xs text-muted">{t('age.updated', { age: age(row.station.price_updated_at, t) })}</span></div>
              {row.break_even && row.break_even.reference_station_id !== row.station.id ? (() => {
                const s = Number(row.break_even.fuel_savings_at_requested_gallons)
                if (s >= 0.05) {
                  return (
                    <div className="mt-1.5 flex items-center">
                      <span className="inline-flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-xs font-semibold text-accent" title={row.break_even.reference_station_name ? `vs ${row.break_even.reference_station_name}` : undefined}>
                        {t('badge.netSave', { amount: usd(s) })}
                      </span>
                    </div>
                  )
                }
                if (s <= -0.05) {
                  return (
                    <div className="mt-1.5 flex items-center">
                      <span className="inline-flex items-center gap-1 rounded-full bg-caution-soft px-2 py-0.5 text-xs font-semibold text-caution" title={row.break_even.reference_station_name ? `vs ${row.break_even.reference_station_name}` : undefined}>
                        {t('badge.detourLoss', { amount: usd(Math.abs(s)) })}
                      </span>
                    </div>
                  )
                }
                return null
              })() : null}
              {row.route.source === 'straight_line_estimate' ? <p className="mt-1 text-xs text-caution">{t('coverage.estimated_route')}</p> : null}
            </td>
            <td role="cell" className="comparison-metric">
              <span className="comparison-mobile-label"><CoinsIcon size={14} aria-hidden="true" />{t('list.total')}</span>
              <span className={`comparison-value ${cost !== null && cost === lowest ? 'text-accent' : ''}`}>{cost === null ? '-' : usd(cost / 100)}</span>
              <span className={`comparison-difference ${cost !== null && cost === lowest ? 'text-accent' : 'text-muted'}`}>{cost === null || lowest === null ? '-' : cost === lowest ? t('comparison.lowestCost') : t('comparison.costDelta', { amount: usd((cost - lowest) / 100) })}</span>
            </td>
            <td role="cell" className="comparison-metric">
              <span className="comparison-mobile-label"><ClockIcon size={14} aria-hidden="true" />{timeLabel}</span>
              <span className={`comparison-value ${time !== null && time === quickest ? 'text-accent' : ''}`}>{time === null ? '-' : minutes(time / 1000, t)}</span>
              <span className={`comparison-difference ${time !== null && time === quickest ? 'text-accent' : 'text-muted'}`}>{time === null || quickest === null ? '-' : time === quickest ? t('comparison.quickest') : t('comparison.timeDelta', { time: minutes((time - quickest) / 1000, t) })}</span>
            </td>
            <td role="cell" className="comparison-metric">
              <span className="comparison-mobile-label"><GasPumpIcon size={14} aria-hidden="true" />{t('list.price')}</span>
              <span className={`comparison-value ${price !== null && price === lowestPrice ? 'text-accent' : ''}`}>{price === null ? '-' : perGallon(comparisonPrice(row.station))}</span>
              <div className="comparison-price-conditions">
              {price !== null && price === lowestPrice ? <span className="comparison-difference text-accent">{t('comparison.lowestPrice')}</span> : null}
              <span className="comparison-difference text-muted">{t(row.station.payment_type === 'cash' ? 'prefs.cash' : row.station.payment_type === 'credit' ? 'prefs.card' : 'station.unknownPayment')}</span>
              {row.station.comparison_price_per_gallon ? <span className="comparison-difference text-caution">{t('payment.estimated')}</span> : null}
              </div>
            </td>
          </tr>)}
        </tbody>
      </table>
      {ordered.length > visible ? <div className="px-4 pb-4 sm:px-5"><Button variant="secondary" className="w-full whitespace-normal" onClick={() => setVisible(count => count + 5)}>{t('station.more', { count: ordered.length - visible })}</Button></div> : null}
    </div> : null}
    {selected ? <StationDetails station={selected.station} row={selected} open onClose={() => setSelected(null)} navApp={navApp} tripMode={tripMode} /> : null}
  </section>
}
