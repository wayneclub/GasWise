import { useEffect, useState } from 'react'
import { useI18n } from '../../i18n'
import { DEFAULT_FUEL_ASSISTANT_SETTINGS, deleteRefuel, estimateNeed, loadFuelAssistant, recordRefuel, saveFuelAssistantSettings, syncNeedEstimate, type FuelAssistantSettings, type NeedEstimate, type RefuelEvent } from '../../lib/fuelAssistant'
import type { Prefs } from '../../lib/prefs'

export function FuelAssistant({ prefs }: { prefs: Prefs }) {
  const { t, locale } = useI18n()
  const mpg = Number(prefs.vehicle?.combinedMpg ?? prefs.mpg ?? 0)
  const mpgBasis = prefs.vehicle ? 'epa_vehicle' as const : 'manual_mpg' as const
  const [settings, setSettings] = useState<FuelAssistantSettings>(DEFAULT_FUEL_ASSISTANT_SETTINGS)
  const [events, setEvents] = useState<RefuelEvent[]>([])
  const [estimate, setEstimate] = useState<NeedEstimate>(() => estimateNeed([], DEFAULT_FUEL_ASSISTANT_SETTINGS, mpg, new Date(), mpgBasis))
  const [busy, setBusy] = useState(false)
  async function refresh(nextSettings = settings) {
    const loaded = await loadFuelAssistant()
    setSettings(loaded.settings); setEvents(loaded.events)
    const next = estimateNeed(loaded.events, nextSettings === settings ? loaded.settings : nextSettings, mpg, new Date(), mpgBasis)
    setEstimate(next); await syncNeedEstimate(next)
  }
  useEffect(() => { void refresh().catch(() => {}) }, [mpg]) // eslint-disable-line react-hooks/exhaustive-deps
  async function filled() {
    setBusy(true)
    try { await recordRefuel(); await refresh() } finally { setBusy(false) }
  }
  async function save(next: FuelAssistantSettings) {
    setSettings(next); await saveFuelAssistantSettings(next)
    const value = estimateNeed(events, next, mpg, new Date(), mpgBasis); setEstimate(value); await syncNeedEstimate(value)
  }
  async function remove(id: string) { await deleteRefuel(id); await refresh() }
  const range = estimate.earliestDays == null ? t('assistant.unknown') : t('assistant.range', { start: estimate.earliestDays, end: estimate.latestDays ?? estimate.earliestDays })
  const basis = estimate.basis === 'refuel_cadence'
    ? t('assistant.basis.cadence', { count: estimate.observations })
    : estimate.basis === 'epa_vehicle' && prefs.vehicle
      ? t('assistant.basis.epa', { vehicle: prefs.vehicle.label, mpg })
      : estimate.basis === 'manual_mpg' && mpg > 0
        ? t('assistant.basis.manual', { mpg })
        : t('assistant.basis.learning')
  return <section className="flex min-w-0 flex-col gap-4 liquid-panel rounded-box p-4 sm:p-6 lg:col-span-2" aria-label={t('assistant.title')}>
    <div><h2 className="font-semibold">{t('assistant.title')}</h2><p className="mt-1 text-xs text-muted">{t('assistant.description')}</p></div>
    <div className="rounded-control bg-sunken p-3"><p className="font-medium">{range}</p><p className="mt-1 text-xs text-muted">{t(`assistant.confidence.${estimate.confidence}`)}</p><p className="mt-2 text-xs font-medium text-ink">{basis}</p></div>
    <p className="text-xs leading-relaxed text-muted">{t('assistant.automaticHint')}</p>
    <details className="rounded-control border border-line p-3 text-xs text-muted">
      <summary className="cursor-pointer font-medium text-ink">{t('assistant.tune')}</summary>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label>{t('assistant.weeklyMiles')}<input type="number" min="10" max="2000" value={settings.weeklyMiles} onChange={event => void save({ ...settings, weeklyMiles: Number(event.target.value) })} className="mt-1 h-11 w-full rounded-control border border-line bg-canvas px-3 text-sm text-ink" /></label>
        <label>{t('assistant.typicalGallons')}<input type="number" min="1" max="30" value={settings.typicalGallons} onChange={event => void save({ ...settings, typicalGallons: Number(event.target.value) })} className="mt-1 h-11 w-full rounded-control border border-line bg-canvas px-3 text-sm text-ink" /></label>
      </div>
    </details>
    <div><button type="button" disabled={busy} onClick={() => void filled()} className="rounded-control bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{t('assistant.justFilled')}</button><p className="mt-2 text-xs text-muted">{t('assistant.refuelOptional')}</p></div>
    {events.length ? <details><summary className="cursor-pointer text-xs text-muted">{t('assistant.history', { count: events.length })}</summary><ul className="mt-2 space-y-2">{events.slice(0, 6).map(event => <li key={event.id} className="flex items-center justify-between text-xs"><span>{new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(event.at))}</span><button type="button" onClick={() => void remove(event.id)} className="text-caution underline">{t('assistant.delete')}</button></li>)}</ul></details> : null}
  </section>
}
