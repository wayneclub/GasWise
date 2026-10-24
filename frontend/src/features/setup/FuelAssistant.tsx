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
  return (
    <section
      id="section-assistant"
      className="grid grid-cols-1 gap-6 border-b border-line py-8 first:pt-0 last:border-b-0 lg:grid-cols-[280px_1fr] lg:gap-10 lg:py-10"
      aria-label={t('assistant.title')}
    >
      <div className="flex flex-col gap-2 lg:pt-1">
        <h2 className="text-base font-semibold text-ink">{t('assistant.title')}</h2>
        <p className="text-[13px] leading-relaxed text-muted">{t('assistant.description')}</p>
        <p className="mt-2 text-xs leading-relaxed text-muted">{t('assistant.automaticHint')}</p>
      </div>
      <div className="liquid-panel rounded-box p-5 sm:p-6 flex flex-col gap-5 min-w-0">
        <div className="rounded-control bg-sunken p-4 flex flex-col gap-1.5">
          <p className="text-base font-semibold text-ink">{range}</p>
          <p className="text-xs text-muted">{t(`assistant.confidence.${estimate.confidence}`)}</p>
          <p className="mt-1 text-xs font-medium text-ink">{basis}</p>
        </div>

        <div>
          <button
            type="button"
            disabled={busy}
            onClick={() => void filled()}
            className="inline-flex h-11 items-center justify-center rounded-control bg-ink px-4 text-sm font-medium text-surface transition hover:opacity-90 active:scale-[0.98] disabled:opacity-50"
          >
            {t('assistant.justFilled')}
          </button>
          <p className="mt-2 text-xs text-muted">{t('assistant.refuelOptional')}</p>
        </div>

        <details className="rounded-control border border-line p-3.5 text-xs text-muted">
          <summary className="cursor-pointer font-medium text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent">
            {t('assistant.tune')}
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1">
              <span>{t('assistant.weeklyMiles')}</span>
              <input
                type="number"
                min="10"
                max="2000"
                value={settings.weeklyMiles}
                onChange={event => void save({ ...settings, weeklyMiles: Number(event.target.value) })}
                className="h-11 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span>{t('assistant.typicalGallons')}</span>
              <input
                type="number"
                min="1"
                max="30"
                value={settings.typicalGallons}
                onChange={event => void save({ ...settings, typicalGallons: Number(event.target.value) })}
                className="h-11 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent"
              />
            </label>
          </div>
        </details>

        {events.length ? (
          <details className="text-xs text-muted">
            <summary className="cursor-pointer font-medium text-muted hover:text-ink">
              {t('assistant.history', { count: events.length })}
            </summary>
            <ul className="mt-2.5 divide-y divide-line rounded-control border border-line bg-surface px-3">
              {events.slice(0, 6).map(event => (
                <li key={event.id} className="flex items-center justify-between py-2.5 text-xs">
                  <span>{new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(event.at))}</span>
                  <button type="button" onClick={() => void remove(event.id)} className="text-caution underline hover:opacity-80">
                    {t('assistant.delete')}
                  </button>
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>
    </section>
  )
}
