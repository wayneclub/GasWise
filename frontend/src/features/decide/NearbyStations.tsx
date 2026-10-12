import { useState } from 'react'
import type { SmartResult } from '../../api/types'
import { Button } from '../../components/ui'
import { useI18n } from '../../i18n'
import { comparisonPrice, perGallon, sourceLabel } from '../../lib/format'
import type { NavApp } from '../../lib/prefs'
import { reasonKey } from '../../lib/stationStatus'
import { ExcludedStations } from './ExcludedStations'
import { StationDetails, StationRating, TopTierBadge, type StationSummary } from './StationDetails'

export function NearbyStations({ result, navApp, onExpandRoutes, allowUnknownPayment, onUnknownPayment }: { allowUnknownPayment?: boolean; onUnknownPayment?: (value: boolean) => void; result: SmartResult; navApp: NavApp; onExpandRoutes?: () => void }) {
  const { t } = useI18n()
  const [visible, setVisible] = useState(8)
  const [selected, setSelected] = useState<string | null>(null)
  const rows = result.ranking?.results ?? []
  const stations = new Map<string, StationSummary>()
  for (const s of result.snapshot.inventory ?? []) stations.set(`google_places:${s.place_id}`, { ...s, canonical_id: `google_places:${s.place_id}` })
  const coverage = result.coverage
  for (const [index, s] of result.snapshot.stations.entries()) {
    const key = s.canonical_id ?? `${s.source}:${s.id}`
    if (coverage?.quote_indices && coverage.quote_indices[key] !== index) continue
    const old = stations.get(key)
    if (!old?.price_per_gallon || (s.payment_type !== 'unknown' && old.payment_type === 'unknown')) stations.set(key, { ...old, ...s })
  }
  for (const row of rows) stations.set(row.station.canonical_id ?? `${row.station.source}:${row.station.id}`, row.station)
  const excluded = [...stations].filter(([,s]) => s.open_now !== true || ['temporarily_closed', 'permanently_closed'].includes(s.business_status ?? ''))
  for (const [key, candidate] of stations) if (candidate.open_now !== true || ['temporarily_closed', 'permanently_closed'].includes(candidate.business_status ?? '')) stations.delete(key)
  const station = selected ? stations.get(selected) : undefined
  const row = rows.find((r) => (r.station.canonical_id ?? `${r.station.source}:${r.station.id}`) === selected)
  return <section className="flex flex-col gap-3">
    <h2 className="text-base font-semibold">{t('station.all', { count: stations.size })}</h2>
    <p className="text-xs leading-relaxed text-muted">{t('station.allNote')}</p>
    {coverage ? <div className="rounded-control bg-sunken p-3 text-sm text-muted">
      <dl className="grid grid-cols-4 gap-2 text-center">{(['found', 'priced', 'eligible', 'routed'] as const).map((key) => <div key={key}><dd className={key === 'routed' ? 'num text-xl font-semibold text-accent' : 'num text-xl font-semibold text-ink'}>{key === 'found' ? coverage.discovered : coverage[key]}</dd><dt className="mt-1 text-[11px]">{t(key === 'routed' ? 'coverage.compared' : `coverage.${key}`)}</dt></div>)}</dl>
      <details className="mt-2"><summary className="cursor-pointer font-medium text-ink">{t('coverage.why')}</summary>
        {onUnknownPayment ? <label className="mt-3 flex cursor-pointer items-center gap-2 text-xs"><input type="checkbox" checked={allowUnknownPayment ?? false} onChange={(event) => onUnknownPayment(event.target.checked)}/>{t('prefs.unconfirmed')}</label> : null}
        <ul className="mt-2 space-y-1">{Object.entries(coverage.exclusions).map(([reason, count]) => <li key={reason}>{t(reasonKey(reason))}: {count}</li>)}</ul>
      </details>
    </div> : null}
    {coverage && coverage.eligible > coverage.routed && (result.snapshot.routes?.length ?? 0) < 100 && onExpandRoutes ? <Button variant="secondary" onClick={onExpandRoutes}>{t('coverage.moreRoutes')}</Button> : null}
    <ExcludedStations records={excluded} result={result} />
    <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2 lg:grid-cols-1">
      {[...stations].slice(0, visible).map(([key, s]) => <article key={key} className="rounded-box border border-line bg-surface p-4">
        <div className="flex items-start justify-between gap-3"><div className="flex min-w-0 flex-wrap items-center gap-1.5"><h3 className="font-medium">{s.name}</h3>{s.top_tier_brand ? <TopTierBadge brand={s.top_tier_brand} /> : null}</div><span className="shrink-0 text-sm num">{s.price_per_gallon ? perGallon(comparisonPrice({ ...s, price_per_gallon: s.price_per_gallon })) : t('coverage.noPrice')}</span></div>
        {s.comparison_price_per_gallon ? <span className="text-[10px] text-caution">{t('payment.estimated')}</span> : null}
        <p className="mt-1 truncate text-xs text-muted">{s.address}</p><p className="mt-1 text-xs text-faint">{s.source ? sourceLabel(s.source) : s.rating_source ?? 'Google Maps'}</p>
        <div className="mt-2"><StationRating station={s} /></div>
        {s.price_per_gallon ? <p className="mt-1 text-xs text-muted">{t(s.payment_type === 'cash' ? 'prefs.cash' : s.payment_type === 'credit' ? 'prefs.card' : 'station.unknownPayment')}</p> : null}
        <p className="mt-2 text-xs text-muted">{t(reasonKey(coverage?.station_statuses[key] ?? 'routed'))}</p>
        <Button variant="ghost" className="mt-2 h-8 px-0 text-sm" aria-label={`${t('station.view')} ${s.name}`} onClick={() => setSelected(key)}>{t('station.view')}</Button>
      </article>)}
    </div>
    {stations.size > visible ? <Button variant="secondary" onClick={() => setVisible((count) => count + 12)}>{t('station.more', { count: stations.size - visible })}</Button> : null}
    {station ? <StationDetails open onClose={() => setSelected(null)} station={station} row={row} navApp={navApp} status={coverage?.station_statuses[selected!]} tripMode={result.snapshot.query.trip_mode} /> : null}
  </section>
}
