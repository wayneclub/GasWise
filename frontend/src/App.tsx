import { GasPumpIcon, GearSixIcon, WrenchIcon } from '@phosphor-icons/react'
import { PreferencesForm } from './features/setup/PreferencesForm'
import { useState } from 'react'
import { Decide } from './features/decide/Decide'
import { Parts } from './features/parts/Parts'
import { Setup } from './features/setup/Setup'
import { useBrowserLocale, useI18n } from './i18n'
import { I18nProvider } from './i18n/I18nProvider'
import { usePrefs, type Prefs } from './lib/prefs'
import { VehicleIdentityContext, useEncryptedVehicleIdentity } from './lib/vehicleIdentity'

function ServiceTabs({ prefs, update }: { prefs: Prefs; update: (change: Partial<Prefs>) => void }) {
  const { t } = useI18n()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [tab, setTab] = useState<'fuel' | 'parts'>('fuel')
  return <>
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex min-h-16 w-full max-w-5xl items-center gap-2 px-4 sm:gap-8">
        <div className="flex shrink-0 items-center gap-2 font-semibold tracking-tight"><GasPumpIcon size={22} weight="fill" className="text-accent" /><span>GasWise</span></div>
        <nav className="flex min-w-0 flex-1 items-center gap-1 self-stretch" role="tablist" aria-label="GasWise">
          {(['fuel', 'parts'] as const).map((key) => { const Icon = key === 'fuel' ? GasPumpIcon : WrenchIcon; return <button key={key} type="button" role="tab" id={`tab-${key}`} aria-controls={`panel-${key}`} aria-selected={!settingsOpen && tab === key}
            className={`relative flex min-h-14 min-w-0 flex-1 items-center justify-center gap-2 whitespace-normal sm:whitespace-nowrap px-2 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-accent sm:flex-none sm:px-5 ${!settingsOpen && tab === key ? 'text-accent after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:bg-accent' : 'text-muted hover:text-ink'}`}
            onKeyDown={(event) => { if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) { event.preventDefault(); const next = event.key === 'Home' ? 'fuel' : event.key === 'End' ? 'parts' : key === 'fuel' ? 'parts' : 'fuel'; setTab(next); setSettingsOpen(false); document.getElementById(`tab-${next}`)?.focus() } }}
            tabIndex={tab === key ? 0 : -1} onClick={() => { setTab(key); setSettingsOpen(false) }}><Icon size={18} className="hidden sm:block" />{t(`nav.${key}`)}</button> })}
        </nav>
        <button type="button" onClick={() => setSettingsOpen(true)} aria-label={t('decide.settings')} className="grid size-10 shrink-0 place-items-center rounded-control text-muted hover:bg-sunken hover:text-ink"><GearSixIcon size={20} /></button>
      </div>
    </header>
    <div role="tabpanel" id="panel-fuel" aria-labelledby="tab-fuel" hidden={settingsOpen || tab !== 'fuel'}><Decide active={!settingsOpen && tab === 'fuel'} prefs={prefs} update={update} onSettings={() => setSettingsOpen(true)} /></div>
    <div role="tabpanel" id="panel-parts" aria-labelledby="tab-parts" hidden={settingsOpen || tab !== 'parts'}><Parts key={prefs.vehicle?.id ?? 'manual'} vehicle={prefs.vehicle} onChooseCar={() => setSettingsOpen(true)} /></div>
    {settingsOpen ? <main aria-label={t('decide.settings')} className="mx-auto max-w-5xl px-4 py-6 lg:py-10"><div className="mb-6 flex items-center justify-between"><h1 className="text-2xl font-semibold">{t('decide.settings')}</h1><button type="button" onClick={() => setSettingsOpen(false)} className="rounded-control border border-line px-4 py-2 text-sm">{t('settings.back')}</button></div><PreferencesForm prefs={prefs} update={update} advanced /></main> : null}
  </>
}
export default function App() {
  const [prefs, update] = usePrefs()
  const browserLocale = useBrowserLocale()
  const identityState = useEncryptedVehicleIdentity()
  return <I18nProvider locale={prefs.locale ?? browserLocale}>
    <VehicleIdentityContext.Provider value={identityState}>
      {identityState.ready ? (prefs.onboarded ? <ServiceTabs prefs={prefs} update={update} /> : <Setup prefs={prefs} update={update} />) : <div role="status" className="p-6 text-center text-muted">GasWise</div>}
    </VehicleIdentityContext.Provider>
  </I18nProvider>
}
