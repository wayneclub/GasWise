import type { FuelType } from '../../api/types'
import { useState } from 'react'
import { Field, Segmented, Stepper, TextInput, Toggle } from '../../components/ui'
import { useI18n } from '../../i18n'
import { LanguagePicker } from '../../components/LanguagePicker'
import { Select } from '../../components/Select'
import { gallons } from '../../lib/format'
import { NAV_APPS } from '../../lib/navigation'
import { useVehicleIdentity } from '../../lib/vehicleIdentity'
import type { Prefs } from '../../lib/prefs'
import { TripForm } from './TripForm'
import { VehiclePicker } from './VehiclePicker'
import { PrivacyProfile } from './PrivacyProfile'
import { SmartAlerts } from './SmartAlerts'
import { FuelAssistant } from './FuelAssistant'
import { LifeZones } from './LifeZones'
import { FavoriteStationsSection } from './FavoriteStationsSection'

function SettingsSection({
  id,
  title,
  description,
  badge,
  aside,
  children,
}: {
  id?: string
  title: string
  description?: string
  badge?: React.ReactNode
  aside?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section
      id={id}
      aria-label={title}
      className="grid grid-cols-1 gap-6 border-b border-line py-8 first:pt-0 last:border-b-0 lg:grid-cols-[280px_1fr] lg:gap-10 lg:py-10"
    >
      <div className="flex flex-col gap-2 lg:pt-1">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-ink">{title}</h2>
          {badge}
        </div>
        {description ? <p className="text-[13px] leading-relaxed text-muted">{description}</p> : null}
        {aside ? <div className="mt-2 text-xs text-muted">{aside}</div> : null}
      </div>
      <div className="liquid-panel rounded-box p-5 sm:p-6 flex flex-col gap-6 min-w-0">
        {children}
      </div>
    </section>
  )
}

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
  const { identity, setIdentity, storageStatus, storageError } = useVehicleIdentity()
  const { t } = useI18n()
  const [identityReset, setIdentityReset] = useState(0)
  const fuels: { value: FuelType; label: string }[] = [
    { value: 'regular', label: t('fuel.regular') },
    { value: 'midgrade', label: t('fuel.midgradeShort') },
    { value: 'premium', label: t('fuel.premium') },
    { value: 'diesel', label: t('fuel.diesel') },
  ]

  const navItems = [
    { id: 'section-vehicle', label: t('prefs.car') },
    { id: 'section-calculation', label: t('prefs.gallons') },
    { id: 'section-priority', label: t('prefs.priority') },
    { id: 'section-stations', label: t('prefs.costco') },
    { id: 'section-route', label: t('route.mode') },
    { id: 'section-lifezones', label: t('lifezones.title') },
    { id: 'section-assistant', label: t('assistant.title') },
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

      {/* 1. Vehicle & Language */}
      <SettingsSection
        id="section-vehicle"
        title={t('prefs.car')}
        description={t('prefs.carHint')}
        aside={
          <p className="text-xs text-muted">
            {t(storageStatus === 'encrypted' ? 'vehicle.encryptedLocal' : 'vehicle.sessionLocal')}
          </p>
        }
      >
        <Field label={t('prefs.language')}>
          <LanguagePicker value={prefs.locale} onChange={locale => update({ locale })} />
        </Field>

        <Field label={t('prefs.car')}>
          <VehiclePicker key={identityReset} vehicle={prefs.vehicle} onChange={(vehicle) => update({ vehicle })} />
          <p className="text-xs leading-relaxed text-muted">
            {identity ? t('vehicle.sharedReady') : t('vehicle.sharedMissing')}
          </p>
          {identity ? (
            <p className="num font-mono text-xs text-muted">
              {identity.kind === 'vin'
                ? `VIN · •••••••••••••${identity.value.vin.slice(-4)}`
                : `${identity.value.state} · •••${identity.value.plate.slice(-2)}`}
            </p>
          ) : null}
          {identity || storageError ? (
            <button
              type="button"
              onClick={() => {
                setIdentity(null)
                setIdentityReset((n) => n + 1)
              }}
              className="self-start text-xs text-accent underline hover:opacity-80"
            >
              {t('vehicle.clearIdentity')}
            </button>
          ) : null}
          {storageError ? (
            <p role="alert" className="text-xs text-caution">
              {t('vehicle.storageError')}
            </p>
          ) : null}
        </Field>

        {prefs.vehicle ? null : (
          <div className="grid gap-5 sm:grid-cols-[1fr_7rem]">
            <Field label={t('prefs.fuel')}>
              <Segmented
                label={t('prefs.fuel')}
                value={prefs.fuelType}
                options={fuels}
                onChange={(fuelType) => update({ fuelType })}
              />
            </Field>
            <Field label={t('prefs.mpg')}>
              <TextInput
                inputMode="decimal"
                aria-label={t('prefs.mpgLabel')}
                value={prefs.mpg ?? ''}
                onChange={(event) => {
                  const value = event.target.value.replace(/[^\d.]/g, '')
                  update({ mpg: value && Number(value) > 0 ? String(Math.min(Number(value), 200)) : null })
                }}
                className="num max-w-32 sm:max-w-none"
              />
            </Field>
          </div>
        )}
      </SettingsSection>

      {/* 2. Fuel & Calculation */}
      <SettingsSection
        id="section-calculation"
        title={t('prefs.gallons')}
        description={t('prefs.gallonsHint')}
      >
        <Field label={t('prefs.gallons')}>
          <Stepper
            label={t('ui.gallons')}
            value={prefs.gallons}
            min={1}
            max={30}
            step={1}
            format={(value) => gallons(value, t)}
            onChange={(value) => update({ gallons: value })}
          />
        </Field>

        <Field label={t('prefs.payment')} hint={prefs.payment === 'cash_or_credit' ? t('prefs.allHint') : undefined}>
          <Segmented
            label={t('prefs.payment')}
            value={prefs.payment}
            options={[
              { value: 'cash_or_credit', label: t('prefs.all') },
              { value: 'credit', label: t('prefs.card') },
              { value: 'cash', label: t('prefs.cash') },
            ]}
            onChange={(payment) => update({ payment })}
          />
        </Field>

        <Field label={t('prefs.cashback')} hint={t(prefs.payment === 'cash' ? 'prefs.cashbackCash' : 'prefs.cashbackHint')}>
          <div className="relative max-w-44">
            <TextInput
              type="number"
              inputMode="decimal"
              min={0}
              max={100}
              step="0.1"
              aria-label={t('prefs.cashback')}
              disabled={prefs.payment === 'cash'}
              value={prefs.creditCashbackPercent}
              className="num pr-9"
              onChange={(event) => {
                const value = event.target.value
                if (value === '' || Number.isFinite(Number(value))) {
                  update({
                    creditCashbackPercent:
                      value === '' ? '' : String(Math.max(0, Math.min(100, Number(value)))),
                  })
                }
              }}
            />
            <span className={`pointer-events-none absolute right-3.5 top-3 text-sm ${prefs.payment === 'cash' ? 'text-faint' : 'text-muted'}`}>
              %
            </span>
          </div>
          {prefs.payment !== 'cash' ? (
            <div className="mt-2.5 flex flex-wrap gap-1.5 text-xs">
              {[
                { label: 'Costco (4%)', val: '4' },
                { label: 'Citi / Amex (5%)', val: '5' },
                { label: 'Amex BCE (3%)', val: '3' },
                { label: '2%', val: '2' },
                { label: '1.5%', val: '1.5' },
                { label: '0%', val: '0' },
              ].map(({ label, val }) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => update({ creditCashbackPercent: val })}
                  className={`rounded border px-2 py-0.5 transition-colors ${
                    prefs.creditCashbackPercent === val
                      ? 'border-accent bg-accent/10 font-medium text-accent'
                      : 'border-line text-muted hover:border-ink hover:text-ink'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          ) : null}
        </Field>

        <details className="rounded-control border border-line p-3 text-xs text-muted">
          <summary className="cursor-pointer font-medium text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent">
            {t('prefs.cardFees')}
          </summary>
          <p className="mt-2 leading-relaxed">{t('prefs.cardFeesHint')}</p>
          <p className="mt-2">
            <a
              className="underline hover:text-ink"
              target="_blank"
              rel="noreferrer"
              href="https://usa.visa.com/content/dam/VCOM/global/support-legal/documents/merchant-surcharging-qa-for-web.pdf"
            >
              Visa
            </a>{' '}
            ·{' '}
            <a
              className="underline hover:text-ink"
              target="_blank"
              rel="noreferrer"
              href="https://oag.ca.gov/consumers/general/credit-card-surcharges"
            >
              California DOJ
            </a>
          </p>
        </details>
      </SettingsSection>

      {/* 3. Ranking Priority & Radius */}
      <SettingsSection
        id="section-priority"
        title={t('prefs.priority')}
        description={t('prefs.priorityHint', { value: prefs.timeValuePerHour ?? 15 })}
      >
        <Field label={t('prefs.priority')}>
          <Segmented
            label={t('prefs.priority')}
            value={prefs.preference}
            options={[
              { value: 'money', label: t('prefs.money') },
              { value: 'balanced', label: t('prefs.balanced') },
              { value: 'time', label: t('prefs.time') },
            ]}
            onChange={(preference) => update({ preference })}
          />
        </Field>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label={t('board.value')}>
            <TextInput
              type="number"
              min={0}
              max={500}
              step={5}
              aria-label={t('board.value')}
              value={prefs.timeValuePerHour ?? 15}
              onChange={(e) =>
                update({
                  timeValuePerHour: Math.min(500, Math.max(0, Number(e.target.value))),
                })
              }
            />
          </Field>
          <Field label={t('board.radius')}>
            <Select label={t('board.radius')} value={String(prefs.searchRadiusMiles ?? 5)}
              onChange={value => update({ searchRadiusMiles: Number(value) })}
              options={[2, 5, 10, 20].map(value => ({ value: String(value), label: `${value} mi` }))} />
          </Field>
        </div>
      </SettingsSection>

      {/* 4. Station Preferences */}
      <SettingsSection
        id="section-stations"
        title={t('prefs.costco')}
      >
        <div className="flex flex-col gap-5">
          <Toggle
            label={t('prefs.costco')}
            description={t('prefs.costcoHint')}
            checked={prefs.costco}
            onChange={(costco) => update({ costco })}
          />
          <div className="border-t border-line pt-5">
            <Toggle
              label={t('prefs.preferTopTier')}
              description={t('prefs.preferTopTierHint')}
              checked={prefs.preferTopTier}
              onChange={(preferTopTier) => update({ preferTopTier })}
            />
          </div>
          {advanced ? (
            <div className="border-t border-line pt-5">
              <Toggle
                label={t('prefs.unconfirmed')}
                description={t('prefs.unconfirmedHint')}
                checked={prefs.allowUnknownPayment}
                onChange={(allowUnknownPayment) => update({ allowUnknownPayment })}
              />
            </div>
          ) : null}
        </div>
      </SettingsSection>

      {/* 5. Route & Navigation (Advanced) */}
      {advanced ? (
        <SettingsSection
          id="section-route"
          title={t('route.mode')}
          description={t('route.hint')}
        >
          <TripForm prefs={prefs} update={update} />
          <div className="border-t border-line pt-5">
            <Field label={t('prefs.navApp')}>
              <Segmented
                label={t('prefs.navApp')}
                value={prefs.navApp}
                options={NAV_APPS}
                onChange={(navApp) => update({ navApp })}
              />
            </Field>
          </div>
        </SettingsSection>
      ) : null}

      {/* 6. Life Zones (Advanced) */}
      {advanced ? <LifeZones prefs={prefs} /> : null}

      {/* 7. Fuel Timing Assistant (Advanced) */}
      {advanced ? <FuelAssistant prefs={prefs} /> : null}

      {/* 8. Smart Fuel Alerts (Advanced) */}
      {advanced ? <SmartAlerts /> : null}

      {/* 9. Favorite Stations (Advanced) */}
      {advanced ? <FavoriteStationsSection navApp={prefs.navApp} /> : null}

      {/* 10. Privacy Profile & Danger Zone (Advanced & replace) */}
      {advanced && replace ? <PrivacyProfile prefs={prefs} replace={replace} /> : null}
    </div>
  )
}
