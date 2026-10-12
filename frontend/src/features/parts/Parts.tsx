import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { PartsResult, PartsSearchResult } from '../../api/types'
import { Button, Field, TextInput, Segmented } from '../../components/ui'
import { useI18n } from '../../i18n'
import type { SavedVehicle } from '../../lib/prefs'
import { useVehicleIdentity } from '../../lib/vehicleIdentity'
import { validIdentity } from '../../lib/identity'

import { safeProductLink, isAmazonProduct } from '../../lib/partsLinks'

export function Parts({ vehicle, onChooseCar }: { vehicle: SavedVehicle | null; onChooseCar: () => void }) {
  const { t } = useI18n()
  const { identity } = useVehicleIdentity()
  const [mode, setMode] = useState<'search' | 'product'>('search')
  const [keyword, setKeyword] = useState('oil filter')
  const [searchResult, setSearchResult] = useState<PartsSearchResult | null>(null)
  const [url, setUrl] = useState('')
  const [result, setResult] = useState<PartsResult | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(false)
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])
  const invalidate = () => { controller.current?.abort(); setPending(false); setResult(null); setSearchResult(null); setError(false) }
  async function search() {
    controller.current?.abort()
    const abort = new AbortController()
    controller.current = abort
    setPending(true); setError(false); setResult(null); setSearchResult(null)
    try {
      if (!identity) return
      const identityBody = identity.kind === 'vin' ? { vin: identity.value } : { plate: identity.value }
      if (mode === 'search') {
        const next = await api.partsSearch({ keyword: keyword.trim(), max_results: 6, ...identityBody }, abort.signal)
        if (!abort.signal.aborted) setSearchResult(next)
      } else {
        const next = await api.parts({ amazon_url: url.trim(), ...identityBody }, abort.signal)
        if (!abort.signal.aborted) setResult(next)
      }
    } catch { if (!abort.signal.aborted) setError(true) }
    finally { if (!abort.signal.aborted) setPending(false) }
  }
  useEffect(() => { controller.current?.abort(); queueMicrotask(() => { setPending(false); setResult(null); setSearchResult(null) }) }, [identity])
  const replacements = (result?.evidence ?? []).flatMap((e) => (e.replacement_candidates ?? []).map((c): Record<string, string> => ({ ...c, source: e.source })))
  const decoded = searchResult?.vehicle ?? result?.vehicle
  const checkedName = decoded ? [decoded.year, decoded.make, decoded.model, decoded.trim, decoded.engine_liters ? `${Number(decoded.engine_liters).toFixed(1)}L` : ''].filter(Boolean).join(' ') : ''
  return <main className="mx-auto w-full max-w-2xl px-4 pb-12 pt-6">
    <h1 className="text-2xl font-semibold tracking-tight">{t('parts.title')}</h1>
    <p className="mt-2 text-sm leading-relaxed text-muted">{t(mode === 'search' ? 'parts.searchLead' : 'parts.productLead')}</p>
    <div className="mt-5"><Segmented label={t('parts.title')} value={mode} options={[{ value: 'search', label: t('parts.searchMode') }, { value: 'product', label: t('parts.checkMode') }]} onChange={(value) => { invalidate(); setMode(value) }} /></div>
    <details open={!result && !searchResult} className="mt-5 rounded-box border border-line bg-surface p-5">
      <summary className="cursor-pointer text-sm font-medium">{t('parts.edit')}</summary>
      <div className="mt-4">
      {vehicle ? <p className="text-sm font-medium">{t('parts.car', { name: vehicle.label })}</p> : <Button variant="ghost" onClick={onChooseCar}>{t('parts.back')}</Button>}
      <p className="mt-2 text-xs leading-relaxed text-muted">{t('parts.identityNeeded')}</p>
      <form className="mt-5 flex flex-col gap-5" onSubmit={(event) => { event.preventDefault(); if ((identity && validIdentity(identity)) && (mode === 'search' ? keyword.trim().length >= 2 : isAmazonProduct(url.trim()))) void search() }}>
        <div className="rounded-control bg-sunken p-3"><p className="text-sm">{identity ? t('vehicle.sharedReady') : t('vehicle.sharedMissing')}</p><Button variant="ghost" onClick={onChooseCar}>{t('vehicle.openSettings')}</Button></div>
        {mode === 'search' ? <Field label={t('parts.keyword')}>
          <TextInput aria-label={t('parts.keyword')} value={keyword} maxLength={100} onChange={(e) => { invalidate(); setKeyword(e.target.value) }} />
          <div className="flex flex-wrap gap-2">{([{ value: 'oil filter', label: 'parts.oilFilter' }, { value: 'engine air filter', label: 'parts.airFilter' }, { value: 'cabin air filter', label: 'parts.cabinFilter' }, { value: 'brake pads', label: 'parts.brakePads' }] as const).map((choice) => <Button key={choice.value} variant="ghost" className={`h-8 px-2 text-xs ${keyword === choice.value ? 'bg-sunken text-ink' : ''}`} onClick={() => { invalidate(); setKeyword(choice.value) }}>{t(choice.label)}</Button>)}</div>
        </Field> : <Field label={t('parts.url')}><TextInput type="url" aria-label={t('parts.url')} value={url} placeholder="https://www.amazon.com/dp/…" onChange={(e) => { invalidate(); setUrl(e.target.value) }} /></Field>}
        <Button type="submit" className="h-auto min-h-11 py-2" style={{ whiteSpace: 'normal' }} disabled={pending || !(identity && validIdentity(identity)) || (mode === 'search' ? keyword.trim().length < 2 : !isAmazonProduct(url.trim()))}>{pending ? t(mode === 'search' ? 'parts.finding' : 'parts.pending') : t(mode === 'search' ? 'parts.find' : 'parts.submit')}</Button>
      </form>
      </div>
    </details>
    {error ? <p role="alert" className="mt-4 rounded-control bg-caution-soft p-4 text-sm text-caution">{t('parts.error')}</p> : null}
    {searchResult ? <section aria-live="polite" className="mt-5 space-y-4">
      <div className="rounded-box border border-line bg-surface p-5">
        <h2 className="font-semibold">{t('parts.searchSummary', { verified: searchResult.items.filter((item) => item.status === 'compatible').length, count: searchResult.items.length })}</h2>
        <p className="mt-2 text-sm text-muted">{t('parts.resultVehicle', { name: checkedName })}</p>
        <p className="mt-2 text-xs text-muted">{t('parts.bounded')}</p>
      </div>
      {!searchResult.items.length ? <p className="rounded-control bg-caution-soft p-4 text-sm text-caution">{t(searchResult.source_status === 'unavailable' || searchResult.source_status === 'not_configured' ? 'parts.sourceUnavailable' : 'parts.emptySearch')}</p> : null}
      {searchResult.items.map((item) => <article key={item.product_url} className="rounded-box border border-line bg-surface p-5">
        <p className={`text-sm font-semibold ${item.status === 'compatible' ? 'text-accent' : 'text-caution'}`}>{t(`parts.${item.status}`)}</p>
        <h3 className="mt-2 text-base font-medium">{item.name}</h3>
        <p className="mt-1 text-sm text-muted">{item.brand} · {item.part_number}</p>
        <details className="mt-3 text-xs leading-relaxed text-muted"><summary className="cursor-pointer">AutoZone · {t('parts.evidence')}</summary><p className="mt-2">{item.evidence.detail}</p>{(item.evidence.conditions ?? []).map((c) => <p key={c}>{c}</p>)}</details>
        {safeProductLink(item.product_url) ? <a className="mt-3 inline-block text-sm underline" href={safeProductLink(item.product_url)!} target="_blank" rel="noreferrer">{t('parts.openProduct')}</a> : null}
      </article>)}
    </section> : null}
    {result ? <section aria-live="polite" className="mt-5 flex flex-col gap-4">
      <div className={`rounded-box border border-line p-5 ${result.fitment_confirmed ? 'bg-accent-soft' : 'bg-caution-soft'}`}>
        <h2 className="text-xl font-semibold">{t(`parts.${result.status}`)}</h2>
        <p className="mt-2 font-medium">{result.title ?? [result.brand, result.part_number].filter(Boolean).join(' ')}</p>
        <p className="mt-2 text-sm text-muted">{t('parts.resultVehicle', { name: checkedName })}</p>
        {safeProductLink(result.amazon_url) ? <a href={safeProductLink(result.amazon_url)!} target="_blank" rel="noreferrer" className="mt-3 inline-block text-sm underline">{t('parts.openProduct')}</a> : null}
      </div>
      <div className="rounded-box border border-line bg-surface p-5">
        <h3 className="font-semibold">{t('parts.evidence')}</h3>
        {(result.evidence ?? []).map((e, index) => <details key={`${e.source}:${index}`} className="border-b border-line py-3 last:border-0">
          <summary className="cursor-pointer text-sm"><span className="font-medium">{e.source === 'autozone' ? 'AutoZone' : e.source === 'oreilly' ? "O’Reilly" : e.source === 'amazon' ? 'Amazon' : 'Manufacturer'}</span> · {t(e.status === 'incompatible' ? 'parts.incompatible' : `parts.${e.status}`)}</summary>
          <div className="mt-2 space-y-2 text-xs leading-relaxed text-muted">
            <p>{[e.brand, e.part_number].filter(Boolean).join(' ')}</p><p>{e.detail}</p>
            {(e.conditions ?? []).map((condition) => <p key={condition}>{condition}</p>)}
            {safeProductLink(e.source_url) ? <a href={safeProductLink(e.source_url)!} target="_blank" rel="noreferrer" className="inline-block underline">{t('parts.openProduct')}</a> : null}
          </div>
        </details>)}
      </div>
      <div className="rounded-box border border-line bg-surface p-5">
        <h3 className="font-semibold">{t('parts.alternatives')}</h3>
        <p className="mt-2 text-xs leading-relaxed text-muted">{t('parts.alternativesNote')}</p>
        {replacements.length ? <ul className="mt-3 space-y-3">{replacements.map((c, index) => <li key={`${c.part_number}:${index}`} className="rounded-control bg-sunken p-3 text-sm"><p className="font-medium">{[c.brand, c.part_number, c.name ?? c.title].filter(Boolean).join(' · ')}</p><p className="mt-1 text-xs text-muted">{c.source}</p>{safeProductLink(c.url ?? c.source_url) ? <a href={safeProductLink(c.url ?? c.source_url)!} className="mt-2 inline-block underline" target="_blank" rel="noreferrer">{t('parts.openProduct')}</a> : null}</li>)}</ul> : <p className="mt-3 text-sm text-muted">{t('parts.noAlternatives')}</p>}
      </div>
      {result.warnings?.length || result.reasons?.length ? <details className="rounded-box border border-line bg-surface p-5"><summary className="cursor-pointer text-sm font-medium">{t('parts.restrictions')}</summary><ul className="mt-3 space-y-2 text-xs leading-relaxed text-muted">{[...(result.reasons ?? []), ...(result.warnings ?? [])].map((warning, i) => <li key={i}>{warning}</li>)}</ul></details> : null}
    </section> : null}
  </main>
}
