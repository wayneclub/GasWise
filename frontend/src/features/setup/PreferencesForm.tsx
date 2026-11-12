import { useI18n } from '../../i18n'
import type { Prefs } from '../../lib/prefs'
import { CalculationSettingsSection } from './CalculationSettingsSection'
import { GeneralSettingsSection } from './GeneralSettingsSection'
import { LifeZones } from './LifeZones'
import { OnboardingVehicleSection } from './OnboardingVehicleSection'
import { PrioritySettingsSection } from './PrioritySettingsSection'
import { PrivacyProfile } from './PrivacyProfile'
import { SettingsSection } from './SettingsSection'
import { SmartAlerts } from './SmartAlerts'
import { TripForm } from './TripForm'

export function PreferencesForm({
  prefs,
  update,
  replace,
  advanced = false,
}: {
  prefs: Prefs
  update: (change: Partial<Prefs>) => void
  replace?: (prefs: Prefs) => void
  advanced?: boolean
}) {
  const { t } = useI18n()

  const navItems = [
    { id: 'section-general', label: t('prefs.general') },
    { id: 'section-priority', label: t('prefs.priority') },
    { id: 'section-calculation', label: t('prefs.gallons') },
    { id: 'section-route', label: t('route.mode') },
    { id: 'section-lifezones', label: t('lifezones.title') },
    { id: 'smart-alerts', label: t('alerts.title') },
    { id: 'section-privacy', label: t('privacy.title') },
  ]

  return (
    <div className="flex min-w-0 flex-col">
      {advanced ? (
        <nav
          aria-label="Settings sections"
          className="mb-4 flex flex-wrap items-center gap-1.5 rounded-control border border-line bg-surface p-1.5"
        >
          {navItems.map((item) => (
            <a
              key={item.id}
              href={`#${item.id}`}
              onClick={(event) => {
                event.preventDefault()
                const el = document.getElementById(item.id)
                if (el) {
                  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
                  el.focus?.()
                }
              }}
              className="inline-flex h-8 items-center rounded-[10px] px-2.5 text-xs font-medium text-muted transition hover:bg-sunken hover:text-ink"
            >
              {item.label}
            </a>
          ))}
        </nav>
      ) : null}

      {/* Onboarding only: Initial vehicle setup */}
      {!advanced ? (
        <OnboardingVehicleSection prefs={prefs} update={update} />
      ) : null}

      {/* 1. Language & Navigation */}
      {advanced ? (
        <GeneralSettingsSection prefs={prefs} update={update} />
      ) : null}

      {/* 2. Ranking Priority & Stations */}
      <PrioritySettingsSection prefs={prefs} update={update} advanced={advanced} />

      {/* 3. Fuel & Calculation */}
      <CalculationSettingsSection prefs={prefs} update={update} />

      {/* 4. Route & Navigation (Advanced) */}
      {advanced ? (
        <SettingsSection
          id="section-route"
          title={t('route.mode')}
          description={t('route.hint')}
        >
          <TripForm prefs={prefs} update={update} />
        </SettingsSection>
      ) : null}

      {/* 5. Life Zones (Advanced) */}
      {advanced ? <LifeZones prefs={prefs} /> : null}

      {/* 6. Smart Fuel Alerts (Advanced) */}
      {advanced ? <SmartAlerts /> : null}

      {/* 7. Privacy Profile & Backup (Advanced & replace) */}
      {advanced && replace ? <PrivacyProfile prefs={prefs} replace={replace} /> : null}
    </div>
  )
}
