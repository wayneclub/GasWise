import { useEffect, useState } from 'react'
import { api, type PriceHistory as HistoryData, type PriceObservation } from '../../api/client'
import { Button } from '../../components/ui'
import { Select } from '../../components/Select'
import { useI18n } from '../../i18n'
import { fuelKey, perGallon, sourceLabel } from '../../lib/format'
import type { StationSummary } from './StationDetails'

const timestamp = (row: PriceObservation) => new Date(row.observation_kind === 'daily_check' ? row.observed_at : row.reported_at ?? row.observed_at).getTime()
const seriesKey = (row: PriceObservation) => JSON.stringify([row.source, row.station_id, row.payment_type, row.condition])

export function PriceHistory({ station }: { station: StationSummary }) {
  const { t, locale } = useI18n()
  const [expanded, setExpanded] = useState(false)
  const [days, setDays] = useState<7 | 30 | 90>(30)
  const [response, setResponse] = useState<{ key: string; data: HistoryData } | null>(null)
  const [failed, setFailed] = useState('')
  const [retry, setRetry] = useState(0)
  const [selected, setSelected] = useState('')
  const requestKey = JSON.stringify([station.canonical_id, station.id, station.source, station.fuel_type, days, retry])
  const data = response?.key === requestKey ? response.data : null
  const error = failed === requestKey
  useEffect(() => {
    if (!expanded || !station.id || !station.source || !station.fuel_type) return
    const controller = new AbortController()
    api.priceHistory({ canonical_id: station.canonical_id, source: station.source, station_id: station.id, fuel_type: station.fuel_type, days }, controller.signal)
      .then((value) => { if (!controller.signal.aborted) setResponse({ key: requestKey, data: value }) })
      .catch(() => { if (!controller.signal.aborted) setFailed(requestKey) })
    return () => controller.abort()
  }, [expanded, days, requestKey, station.canonical_id, station.id, station.source, station.fuel_type])
  if (!station.id || !station.source || !station.fuel_type) return null
  const groups = new Map<string, PriceObservation[]>()
  for (const observation of data?.observations ?? []) {
    if (!Number.isFinite(Number(observation.price)) || Number(observation.price) <= 0 || !Number.isFinite(timestamp(observation))) continue
    const key = seriesKey(observation)
    groups.set(key, [...(groups.get(key) ?? []), observation])
  }
  const key = groups.has(selected) ? selected : groups.keys().next().value
  const rows = (key ? groups.get(key) ?? [] : []).toSorted((a, b) => timestamp(a) - timestamp(b))
  const prices = rows.map((r) => Number(r.price))
  const low = Math.min(...prices), high = Math.max(...prices)
  const delta = prices.length > 1 ? prices[prices.length - 1] - prices[0] : null
  const formatDate = (value: number | string) => new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
  const date = (row: PriceObservation) => formatDate(timestamp(row))
  const label = (row: PriceObservation) => [sourceLabel(row.source), t(row.payment_type === 'cash' ? 'prefs.cash' : row.payment_type === 'credit' ? 'prefs.card' : 'station.unknownPayment'), row.membership ? t('station.member', { name: row.membership }) : '', row.octane != null ? `${row.octane} AKI` : ''].filter(Boolean).join(' · ')
  const first = rows[0], last = rows[rows.length - 1]
  const span = last && first ? timestamp(last) - timestamp(first) : 0
  const x = (row: PriceObservation) => 35 + (span ? (timestamp(row) - timestamp(first)) / span : 0.5) * 280
  const y = (price: number) => 105 - (high === low ? 0.5 : (price - low) / (high - low)) * 70
  return <section className="rounded-control border border-line bg-surface">
    <button type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)} className="flex min-h-11 w-full items-center justify-between gap-2 p-4 text-left text-sm font-semibold">
      <span>{t('history.title')}</span><span className="text-xs text-muted">{t(expanded ? 'history.hide' : 'history.show')} {expanded ? '−' : '+'}</span>
    </button>
    {expanded ? <div className="space-y-3 border-t border-line p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-xs text-muted">{t(fuelKey(station.fuel_type))} · USD/gal</span><div className="flex gap-1">{([7, 30, 90] as const).map((value) => <button key={value} type="button" aria-pressed={days === value} onClick={() => { setDays(value); setSelected('') }} className={`min-h-11 rounded-control px-3 text-xs ${days === value ? 'bg-accent-soft font-semibold text-accent' : 'bg-sunken text-muted'}`}>{t('history.days', { days: value })}</button>)}</div></div>
      <p className="text-xs leading-relaxed text-muted">{t('history.note')}</p>
      {error ? <div role="status"><p className="text-sm text-muted">{t('history.error')}</p><Button variant="secondary" className="mt-2" onClick={() => setRetry(retry + 1)}>{t('history.retry')}</Button></div> : !data ? <p role="status" className="text-sm text-muted">{t('history.loading')}</p> : !rows.length ? <p role="status" className="rounded-control bg-sunken p-3 text-sm text-muted">{t('history.empty')}</p> : <>
        <div className="text-xs text-muted"><p className="mb-1">{t('history.series')}</p><Select label={t('history.series')} value={key ?? ''} onChange={setSelected}
          options={[...groups].map(([value, observations]) => ({ value, label: label(observations[0]) }))} /></div>
        <dl className="grid grid-cols-3 gap-2 rounded-control bg-sunken p-3 text-center">{[['history.low', perGallon(String(low))], ['history.high', perGallon(String(high))], ['history.change', delta == null ? '—' : `${delta > 0 ? '+' : delta < 0 ? '−' : ''}${perGallon(String(Math.abs(delta)))}`]].map(([title, value]) => <div key={title}><dt className="text-[11px] text-muted">{t(title as 'history.low')}</dt><dd className="num mt-1 text-sm font-semibold">{value}</dd></div>)}</dl>
        {data.analysis?.price_band?.band ? (
          <div className={`rounded-control p-3 text-xs flex items-center justify-between gap-2 ${
            data.analysis.price_band.band === 'near_low'
              ? 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
              : data.analysis.price_band.band === 'near_high'
              ? 'bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800'
              : 'bg-sunken text-muted'
          }`}>
            <div>
              <div className="font-semibold flex items-center gap-1.5">
                <span>{data.analysis.price_band.band === 'near_low' ? '✨ 近期低位' : data.analysis.price_band.band === 'near_high' ? '⚠️ 近期偏高' : '📊 常態區間'}</span>
                {data.analysis.price_band.percentile != null && (
                  <span className="text-[11px] opacity-80">(前 {data.analysis.price_band.percentile}% 百分位)</span>
                )}
              </div>
              <p className="mt-0.5 leading-snug">{data.analysis.price_band.advice}</p>
            </div>
          </div>
        ) : null}
        {data.analysis?.weekend_cycle?.pre_weekend_hike_risk ? (
          <div className="rounded-control bg-amber-500/10 border border-amber-500/30 p-2.5 text-xs text-amber-700 dark:text-amber-300 flex items-start gap-2">
            <span className="text-base leading-none">⛽</span>
            <div>
              <span className="font-semibold">週末調漲避險提醒</span>
              <p className="mt-0.5 leading-snug opacity-90">{data.analysis.weekend_cycle.message}</p>
            </div>
          </div>
        ) : null}
        {rows.length > 1 ? <div><svg viewBox="0 0 350 140" role="img" aria-label={t('history.chart')} className="w-full text-accent"><path d="M35 20V115H315" fill="none" stroke="currentColor" opacity="0.2"/><path d={rows.map((r, i) => `${i ? 'L' : 'M'}${x(r)},${y(Number(r.price))}`).join(' ')} fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="4 4"/>{rows.map((r, i) => <circle key={i} cx={x(r)} cy={y(Number(r.price))} r="3" fill="currentColor"><title>{date(r)}: {perGallon(r.price)}</title></circle>)}<text x="5" y="25" fontSize="10" fill="currentColor">{perGallon(String(high))}</text><text x="5" y="132" fontSize="10" fill="currentColor">{perGallon(String(low))}</text></svg><div className="flex justify-between text-[10px] text-muted"><span>{date(first)}</span><span>{date(last)}</span></div></div> : <p className="text-xs text-muted">{t('history.single')}</p>}
        <details><summary className="min-h-11 cursor-pointer py-3 text-xs font-medium">{t('history.records', { count: rows.length })}</summary><div className="max-h-60 overflow-auto"><table className="w-full text-xs"><thead><tr className="text-left text-muted"><th className="py-2 font-normal">{t('history.time')}</th><th className="py-2 text-right font-normal">USD/gal</th></tr></thead><tbody>{rows.toReversed().map((r, i) => <tr key={i} className="border-t border-line"><td className="py-2">{date(r)}{r.observation_kind === 'daily_check' && r.reported_at ? <span className="block text-xs text-muted">{t('history.reported', { time: formatDate(r.reported_at) })}</span> : null}{!r.reported_at ? <span className="block text-[10px] text-muted">{t('history.observed')}</span> : null}</td><td className="num text-right">{perGallon(r.price)}</td></tr>)}</tbody></table></div></details>
      </>}
      {data?.truncated ? <p className="text-xs text-caution">{t('history.truncated')}</p> : null}
    </div> : null}
  </section>
}
