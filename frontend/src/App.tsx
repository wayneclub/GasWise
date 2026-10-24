import { BellIcon, GasPumpIcon, GearSixIcon, GlobeIcon, WrenchIcon } from '@phosphor-icons/react'
import { PreferencesForm } from './features/setup/PreferencesForm'
import { useEffect, useState } from 'react'
import { Decide } from './features/decide/Decide'
import { Parts } from './features/parts/Parts'
import { Setup } from './features/setup/Setup'
import { LOCALES, useBrowserLocale, useI18n } from './i18n'
import { I18nProvider } from './i18n/I18nProvider'
import { usePrefs, type Prefs } from './lib/prefs'
import { VehicleIdentityContext, useEncryptedVehicleIdentity } from './lib/vehicleIdentity'
import { getLocalProfile } from './lib/localProfile'

function ServiceTabs({ prefs, update, replace }: { prefs: Prefs; update: (change: Partial<Prefs>) => void; replace: (prefs: Prefs) => void }) {
  const { t } = useI18n()
  const [settingsView, setSettingsView] = useState<'all' | 'alerts' | null>(null)
  const settingsOpen = settingsView !== null
  const [tab, setTab] = useState<'fuel' | 'parts'>('fuel')
  useEffect(() => {
    if (settingsView !== 'alerts') return
    const frame = requestAnimationFrame(() => {
      const alerts = document.getElementById('smart-alerts')
      alerts?.scrollIntoView?.({ block: 'start' })
      alerts?.focus({ preventScroll: true })
    })
    return () => cancelAnimationFrame(frame)
  }, [settingsView])
  return <>
    <header className="liquid-nav">
      <div className="mx-auto flex min-h-16 w-full max-w-5xl flex-wrap items-center gap-x-2 px-4 pt-2 sm:flex-nowrap sm:gap-4 sm:pt-0">
        <div className="flex shrink-0 items-center gap-2 font-semibold tracking-tight"><GasPumpIcon size={22} weight="fill" className="text-accent" /><span>GasWise</span></div>
        <nav className="order-last flex min-w-0 basis-full flex-1 items-center gap-1 self-stretch sm:order-none sm:basis-auto" role="tablist" aria-label="GasWise">
          {(['fuel', 'parts'] as const).map((key) => { const Icon = key === 'fuel' ? GasPumpIcon : WrenchIcon; return <button key={key} type="button" role="tab" id={`tab-${key}`} aria-controls={`panel-${key}`} aria-selected={!settingsOpen && tab === key}
            className={`liquid-tab relative flex min-h-14 min-w-0 flex-1 items-center justify-center gap-2 whitespace-normal sm:whitespace-nowrap px-2 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-accent sm:flex-none sm:px-5 ${!settingsOpen && tab === key ? 'text-accent' : 'text-muted hover:text-ink'}`}
            onKeyDown={(event) => { if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) { event.preventDefault(); const next = event.key === 'Home' ? 'fuel' : event.key === 'End' ? 'parts' : key === 'fuel' ? 'parts' : 'fuel'; setTab(next); setSettingsView(null); document.getElementById(`tab-${next}`)?.focus() } }}
            tabIndex={tab === key ? 0 : -1} onClick={() => { setTab(key); setSettingsView(null) }}><Icon size={18} className="hidden sm:block" />{t(`nav.${key}`)}</button> })}
        </nav>
        <label className="relative ml-auto flex shrink-0 items-center">
          <GlobeIcon size={18} aria-hidden="true" className="pointer-events-none absolute left-2 text-muted" />
          <select aria-label={t('prefs.language')} value={prefs.locale ?? 'auto'} onChange={(event) => update({ locale: LOCALES.find((item) => item.value === event.target.value)?.value ?? null })} className="h-11 w-28 rounded-control border border-line bg-canvas pl-8 pr-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-accent sm:w-36">
            <option value="auto">{t('prefs.languageAuto')}</option>
            {LOCALES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        <button type="button" onClick={() => setSettingsView('alerts')} aria-label={t('alerts.title')} aria-pressed={settingsView === 'alerts'} className={`grid size-10 shrink-0 place-items-center rounded-control hover:bg-sunken ${settingsView === 'alerts' ? 'text-accent' : 'text-muted hover:text-ink'}`}><BellIcon size={20} /></button>
        <button type="button" onClick={() => setSettingsView('all')} aria-label={t('decide.settings')} className="grid size-10 shrink-0 place-items-center rounded-control text-muted hover:bg-sunken hover:text-ink"><GearSixIcon size={20} /></button>
      </div>
    </header>
    <div role="tabpanel" id="panel-fuel" aria-labelledby="tab-fuel" hidden={settingsOpen || tab !== 'fuel'}><Decide active={!settingsOpen && tab === 'fuel'} prefs={prefs} update={update} onSettings={() => setSettingsView('all')} /></div>
    <div role="tabpanel" id="panel-parts" aria-labelledby="tab-parts" hidden={settingsOpen || tab !== 'parts'}><Parts key={prefs.vehicle?.id ?? 'manual'} vehicle={prefs.vehicle} onChooseCar={() => setSettingsView('all')} /></div>
    {settingsOpen ? (
      <main aria-label={t('decide.settings')} className="mx-auto max-w-5xl px-4 py-6 sm:py-8 lg:py-10">
        <div className="mb-6 flex items-center justify-between border-b border-line pb-5">
          <div className="flex flex-col gap-0.5">
            <h1 className="text-2xl font-semibold tracking-tight text-ink">{t('decide.settings')}</h1>
            <p className="text-xs sm:text-sm text-muted">{t('setup.lead')}</p>
          </div>
          <button
            type="button"
            onClick={() => setSettingsView(null)}
            className="inline-flex h-10 items-center justify-center rounded-control border border-line bg-surface px-4 text-sm font-medium text-ink hover:bg-sunken active:scale-[0.98]"
          >
            {t('settings.back')}
          </button>
        </div>
        <PreferencesForm prefs={prefs} update={update} replace={replace} advanced />
      </main>
    ) : null}
  </>
}
export default function App() {
  const [prefs, update, replace] = usePrefs()
  const browserLocale = useBrowserLocale()
  const identityState = useEncryptedVehicleIdentity()
  useEffect(() => { void getLocalProfile().catch(() => {}) }, [])
  return <I18nProvider locale={prefs.locale ?? browserLocale}>
    <VehicleIdentityContext.Provider value={identityState}>
      {identityState.ready ? (prefs.onboarded ? <ServiceTabs prefs={prefs} update={update} replace={replace} /> : <Setup prefs={prefs} update={update} />) : <div role="status" className="p-6 text-center text-muted">GasWise</div>}
    </VehicleIdentityContext.Provider>
  </I18nProvider>
}
