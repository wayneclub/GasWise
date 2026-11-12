import { useState } from 'react'
import type { FuelType } from '../../api/types'
import { LanguagePicker } from '../../components/LanguagePicker'
import { Field, Segmented, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n'
import type { Prefs } from '../../lib/prefs'
import { useVehicleIdentity } from '../../lib/vehicleIdentity'
import { SettingsSection } from './SettingsSection'
import { VehiclePicker } from './VehiclePicker'

interface OnboardingVehicleSectionProps {
  prefs: Prefs
  update: (change: Partial<Prefs>) => void
}

export function OnboardingVehicleSection({ prefs, update }: OnboardingVehicleSectionProps) {
  const { identity, setIdentity, storageStatus, storageError } = useVehicleIdentity()
  const { t } = useI18n()
  const [identityReset, setIdentityReset] = useState(0)

  const fuels: { value: FuelType; label: string }[] = [
    { value: 'regular', label: t('fuel.regular') },
    { value: 'midgrade', label: t('fuel.midgradeShort') },
    { value: 'premium', label: t('fuel.premium') },
    { value: 'diesel', label: t('fuel.diesel') },
  ]

  return (
    <SettingsSection
      id="section-onboarding-vehicle"
      title={t('prefs.car')}
      description={t('prefs.carHint')}
      aside={
        <p className="text-xs text-muted">
          {t(storageStatus === 'encrypted' ? 'vehicle.encryptedLocal' : 'vehicle.sessionLocal')}
        </p>
      }
    >
      <Field label={t('prefs.language')}>
        <LanguagePicker value={prefs.locale} onChange={(locale) => update({ locale })} />
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
  )
}
