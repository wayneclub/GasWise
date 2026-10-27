import { useState } from 'react'
import type { SmartResult } from '../../api/types'
import { Button, LinkButton } from '../../components/ui'
import { useI18n } from '../../i18n'
import { age, fuelKey, perGallon, sourceLabel } from '../../lib/format'
import { navigationUrl } from '../../lib/navigation'
import type { NavApp } from '../../lib/prefs'
import type { StationSummary } from './StationDetails'

function fallbackStations(result: SmartResult) {
  const stations = new Map<string, StationSummary>()
  const ranked = new Set(result.ranking?.results.map(row => row.station.canonical_id ?? `${row.station.source}:${row.station.id}`))
  for (const station of result.snapshot.inventory ?? []) {
    stations.set(`google_places:${station.place_id}`, { ...station, source: 'google_maps_web' })
  }
  for (const station of result.snapshot.stations) {
    const key = station.canonical_id ?? `${station.source}:${station.id}`
    const old = stations.get(key)
    if (!old?.price_per_gallon || Date.parse(station.price_updated_at ?? '') > Date.parse(old.price_updated_at ?? '')) {
      stations.set(key, { ...old, ...station })
    }
  }
  return [...stations].filter(([key]) => !ranked.has(key))
}

export function SearchFallback({ result, completing, radius, navApp, onRadius, onRetry }: {
  result: SmartResult; completing: boolean; radius: number; navApp: NavApp
  onRadius: (miles: number) => void; onRetry: () => void
}) {
  const { t } = useI18n()
  const [visible, setVisible] = useState(10)
  const records = fallbackStations(result)
  const failures = result.snapshot.source_statuses.filter(source => source.status === 'unavailable')
  const available = result.snapshot.source_statuses
    .filter(source => source.status === 'ok' && source.quote_count > 0)
    .map(source => sourceLabel(source.source))
  const hasRanked = !!result.ranking?.results.length
  const now = Date.parse(result.ranking?.generated_at ?? result.snapshot.collected_at)
  const isStale = (station: StationSummary) => station.price_updated_at
    ? now - Date.parse(station.price_updated_at) >= Math.min(result.snapshot.query.max_price_age_minutes ?? 4320, 4320) * 60000
    : !!station.fetched_at && now - Date.parse(station.fetched_at) >= 21600000
  const onlyStale = records.length > 0 && records.every(([, station]) => !!station.price_per_gallon && isStale(station))
  if (!records.length && !failures.length && hasRanked && !completing) return null
  const expansionChoices = [10, 20].filter(miles => miles > radius)
  return <section aria-label={t('fallback.title')} className="min-w-0 rounded-box border border-line bg-surface p-4 sm:p-5">
    <h2 className="text-lg font-semibold">{completing ? t('decide.searching') : hasRanked ? t('fallback.title') : failures.length ? t('fallback.failed') : onlyStale ? t('fallback.staleOnly') : t('fallback.empty')}</h2>
    <p role="status" className="mt-2 text-sm text-muted">{t('fallback.note')}</p>
    {failures.length > 0 && available.length > 0 ? <p className="mt-2 text-sm">{t('cache.partialSources', { sources: available.join(', ') })}</p> : null}
    {failures.map(source => <p key={source.source} className="mt-2 text-sm text-caution">{t('cache.sourceUnavailable', { source: sourceLabel(source.source) })}</p>)}
    {!completing && (expansionChoices.length || failures.length) ? <div className="mt-4 flex flex-wrap gap-2">
      {expansionChoices.map(miles => <Button key={miles} className="h-auto min-h-11 min-w-0 flex-1 whitespace-normal px-3 py-2 leading-snug" variant="secondary" onClick={() => onRadius(miles)}>{t('fallback.expand', { miles })}</Button>)}
      {failures.length ? <Button className="h-auto min-h-11 whitespace-normal px-3 py-2" variant="ghost" onClick={onRetry}>{t('state.retry')}</Button> : null}
    </div> : null}
    {records.length ? <><p className="mt-4 text-sm text-muted">{t('fallback.count', { count: records.length })}</p><div className="mt-2 divide-y divide-line">
      {records.slice(0, visible).map(([key, station]) => <article key={key} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-start gap-x-3 py-4">
        <div className="col-span-2 min-w-0">
        <h3 className="break-words text-base font-medium leading-snug">{station.name}</h3>
        <p className="mt-1 break-words text-sm leading-relaxed text-muted">{station.address}</p>
        {station.discovery_state === 'known' && !station.price_per_gallon ? <p className="mt-1 text-xs text-caution">{t('fallback.knownStation', { age: age(station.last_seen_at, t) })}</p> : null}
        </div>
        <div className="min-w-0 break-words">
        <p className="mt-2 text-sm">{station.price_per_gallon ? `${perGallon(station.price_per_gallon)} · ${t(isStale(station) ? 'fallback.stale' : 'fallback.unranked')}` : t('fallback.noPrice')}</p>
        {station.price_per_gallon && station.fuel_type ? <p className="mt-1 text-xs text-muted">{t(fuelKey(station.fuel_type))} · {t(station.payment_type === 'cash' ? 'prefs.cash' : station.payment_type === 'credit' ? 'prefs.card' : 'station.unknownPayment')}</p> : null}
        {station.price_per_gallon ? <p className="mt-1 text-xs text-muted">{t('age.updated', { age: age(station.price_updated_at, t) })}</p> : null}
        <p className="mt-1 text-xs text-muted">{sourceLabel(station.source ?? 'google_maps_web')} · {t(station.open_now === true ? 'hours.open' : station.open_now === false ? 'hours.closed' : 'hours.unknown')}</p>
        </div>
        <LinkButton variant="secondary" href={navigationUrl(navApp, station.location.lat, station.location.lng)} className="mt-2 self-center">{t('pick.navigate')}</LinkButton>
      </article>)}
    </div>{records.length > visible ? <Button className="mt-2 w-full whitespace-normal" variant="ghost" onClick={() => setVisible(n => n + 10)}>{t('station.more', { count: records.length - visible })}</Button> : null}</> : null}
  </section>
}
