import type { SmartResult } from '../../api/types'
import { useI18n } from '../../i18n'
import { age, perGallon, sourceLabel } from '../../lib/format'
import { reasonKey } from '../../lib/stationStatus'
import type { StationSummary } from './StationDetails'

/** Keep discovery failures visible without presenting them as navigable recommendations. */
export function ExcludedStations({ records, result }: {
  records: [string, StationSummary][]
  result: SmartResult
}) {
  const {t} = useI18n()
  const unlocated = result.snapshot.unlocated_gasbuddy ?? []
  const unmapped = [...new Map(unlocated.map(q => [q.id,q])).values()]
  if (!records.length && !unmapped.length) return null
  return <details className="rounded-box border border-line bg-surface p-4">
    <summary className="cursor-pointer text-sm font-medium">{t('coverage.excludedStations', {count:records.length + unmapped.length})}</summary>
    <div className="mt-3 space-y-3">
      {records.map(([key,station]) => {
        const quotes = result.snapshot.stations.filter(q => (q.canonical_id ?? `${q.source}:${q.id}`) === key && q.source === station.source)
        const sourceName = typeof station.details?.location_source_name === 'string' ? station.details.location_source_name : null
        return <article key={key} className="border-t border-line pt-3 text-xs">
          <h3 className="font-medium text-ink">{station.name}</h3>
          <p className="text-muted">{station.address}</p>
          <p className="mt-1 text-caution">{t(reasonKey(result.coverage?.station_statuses[key] ?? 'opening_status_unknown'))}</p>
          {sourceName && sourceName !== station.name ? <p className="text-muted">Google Maps · {sourceName}</p> : null}
          {quotes.length ? <><p className="mt-1 text-muted">{sourceLabel(station.source ?? '')} · {t('age.updated', {age:age(station.price_updated_at,t)})}</p>
            <div className="mt-1 flex flex-wrap gap-3">{quotes.map(q=><span key={`${q.id}:${q.payment_type}`}>{t(q.payment_type==='cash'?'prefs.cash':q.payment_type==='credit'?'prefs.card':'station.unknownPayment')} {perGallon(q.price_per_gallon)}</span>)}</div></> : null}
        </article>
      })}
      {unmapped.map(station => <article key={station.id} className="border-t border-line pt-3 text-xs">
        <h3 className="font-medium text-ink">{station.name}</h3>
        <p className="text-muted">{station.address}</p>
        <p className="mt-1 text-caution">{t('coverage.unlocated')}</p>
        <p className="mt-1 text-muted">GasBuddy · {t('age.updated', {age:age(station.price_updated_at,t)})}</p>
        <div className="mt-1 flex flex-wrap gap-3">{unlocated.filter(q=>q.id===station.id).map(q=><span key={q.payment_type}>{t(q.payment_type==='cash'?'prefs.cash':'prefs.card')} {perGallon(q.price_per_gallon)}</span>)}</div>
        <a href={station.source_url} target="_blank" rel="noreferrer" className="mt-1 inline-block underline">GasBuddy ↗</a>
      </article>)}
    </div>
  </details>
}
