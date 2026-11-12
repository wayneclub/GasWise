import { GearSixIcon } from '@phosphor-icons/react'
import { Field, Segmented, TextInput, Toggle } from '../../components/ui'
import { useI18n } from '../../i18n'
import { NAV_APPS } from '../../lib/navigation'
import type { Prefs } from '../../lib/prefs'
import { useFavorites } from '../../lib/favorites'
import { RefuelLog } from './RefuelLog'
import { GarageSection } from './GarageSection'
import { FavoriteStationsOverview } from './FavoriteStationsOverview'
import { LifeZones } from '../setup/LifeZones'
import { PrivacyProfile } from '../setup/PrivacyProfile'

export function MyPage({
  prefs,
  update = () => {},
  replace,
  onNavigateToFuel,
}: {
  prefs: Prefs
  update?: (change: Partial<Prefs>) => void
  replace?: (prefs: Prefs) => void
  onNavigateToFuel: () => void
}) {
  const { t } = useI18n()
  const { favorites, remove, updateNotes } = useFavorites()

  return (
    <main
      aria-label={t('favorites.myTitle')}
      className="mx-auto w-full max-w-md px-4 pb-20 pt-6 sm:max-w-2xl sm:px-6 lg:max-w-5xl"
    >
      {/* 1. Vehicle Garage Command Hub */}
      <div className="mb-8">
        <GarageSection prefs={prefs} update={update} />
      </div>

      {/* 2. Intelligent Fuel Timing & Refuel Records */}
      <div className="mb-8">
        <RefuelLog prefs={prefs} />
      </div>

      {/* 3. Favorite Stations & Fuel Price Analytics Overview */}
      <FavoriteStationsOverview
        prefs={prefs}
        favorites={favorites}
        remove={remove}
        updateNotes={updateNotes}
        onNavigateToFuel={onNavigateToFuel}
      />

      {/* 4. Commute & Life Zones Arbitrage */}
      <div className="mt-8">
        <LifeZones prefs={prefs} />
      </div>

      {/* 5. Personal Driving & Payment Preferences */}
      <section
        aria-label={t('my.personalPrefsTitle')}
        className="mt-8 rounded-box border border-line bg-surface p-5 sm:p-6 shadow-sm flex flex-col gap-6"
      >
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3">
          <div className="flex items-center gap-2">
            <GearSixIcon size={22} weight="bold" className="text-accent" />
            <h2 className="text-base font-bold text-ink sm:text-lg">
              {t('my.personalPrefsTitle')}
            </h2>
          </div>
          <span className="text-xs text-muted">{t('my.personalPrefsSubtitle')}</span>
        </div>

        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          {/* Navigation App */}
          <Field label={t('prefs.navApp')}>
            <Segmented
              label={t('prefs.navApp')}
              value={prefs.navApp}
              options={NAV_APPS}
              onChange={(navApp) => update({ navApp })}
            />
          </Field>

          {/* Costco Membership */}
          <div className="flex flex-col justify-center">
            <Toggle
              label={t('prefs.costco')}
              description={t('prefs.costcoHint')}
              checked={prefs.costco}
              onChange={(costco) => update({ costco })}
            />
          </div>
        </div>

        {/* Credit Card Cashback */}
        <div className="border-t border-line pt-5 flex flex-col gap-3">
          <Field
            label={t('prefs.cashback')}
            hint={t(prefs.payment === 'cash' ? 'prefs.cashbackCash' : 'prefs.cashbackHint')}
          >
            <div className="relative max-w-44">
              <TextInput
                type="number"
                inputMode="decimal"
                min={0}
                max={100}
                step="0.1"
                aria-label={t('prefs.cashback')}
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
              <span className="pointer-events-none absolute right-3.5 top-3 text-sm text-muted">
                %
              </span>
            </div>
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
          </Field>
        </div>
      </section>

      {/* 6. Privacy Vault & Data Backup */}
      {replace ? (
        <div className="mt-8">
          <PrivacyProfile prefs={prefs} replace={replace} />
        </div>
      ) : null}
    </main>
  )
}
