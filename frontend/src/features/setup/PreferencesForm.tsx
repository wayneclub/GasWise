import type { FuelType } from '../../api/types'
import {useState} from 'react'
import { Field, Segmented, Stepper, TextInput, Toggle } from '../../components/ui'
import { LOCALES, useI18n } from '../../i18n'
import { gallons } from '../../lib/format'
import { NAV_APPS } from '../../lib/navigation'
import { useVehicleIdentity } from '../../lib/vehicleIdentity'
import type { Prefs } from '../../lib/prefs'
import { TripForm } from './TripForm'
import { VehiclePicker } from './VehiclePicker'

export function PreferencesForm({
  prefs,
  update,
  advanced = false,
}: {
  prefs: Prefs
  update: (change: Partial<Prefs>) => void
  advanced?: boolean
}) {
  const { identity, setIdentity, storageStatus, storageError } = useVehicleIdentity()
  const { t } = useI18n()
  const [identityReset,setIdentityReset]=useState(0)
  const fuels: { value: FuelType; label: string }[] = [
    { value: 'regular', label: t('fuel.regular') },
    { value: 'midgrade', label: t('fuel.midgradeShort') },
    { value: 'premium', label: t('fuel.premium') },
    { value: 'diesel', label: t('fuel.diesel') },
  ]
  return (
    <div className="grid min-w-0 gap-6 lg:grid-cols-2 lg:items-start">
      <section className="flex min-w-0 flex-col gap-6 rounded-box border border-line bg-surface p-4 sm:p-6" aria-label={t('prefs.car')}>
      <Field label={t('prefs.language')}>
        <select aria-label={t('prefs.language')} value={prefs.locale ?? 'auto'} onChange={(event) => update({ locale: event.target.value === 'auto' ? null : LOCALES.find((item) => item.value === event.target.value)!.value })} className="h-11 w-full rounded-control border border-line bg-canvas px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-accent">
          <option value="auto">{t('prefs.languageAuto')}</option>
          {LOCALES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
      </Field>

      <Field label={t('prefs.car')} hint={t('prefs.carHint')}>
        <VehiclePicker key={identityReset} vehicle={prefs.vehicle} onChange={(vehicle) => update({ vehicle })} />
        <p className="text-xs leading-relaxed text-muted">{identity ? t('vehicle.sharedReady') : t('vehicle.sharedMissing')}</p>
        {identity ? <p className="font-mono text-xs text-muted">{identity.kind === 'vin' ? `VIN · •••••••••••••${identity.value.vin.slice(-4)}` : `${identity.value.state} · •••${identity.value.plate.slice(-2)}`}</p> : null}
        <p className="text-xs text-muted">{t(storageStatus === 'encrypted' ? 'vehicle.encryptedLocal' : 'vehicle.sessionLocal')}</p>
        {identity || storageError ? <button type="button" onClick={()=>{setIdentity(null);setIdentityReset(n=>n+1)}} className="self-start text-xs text-accent underline">{t('vehicle.clearIdentity')}</button> : null}
        {storageError ? <p role="alert" className="text-xs text-caution">{t('vehicle.storageError')}</p> : null}
      </Field>

      {prefs.vehicle ? null : (
        <div className="grid gap-5 sm:grid-cols-[1fr_7rem]">
          <Field label={t('prefs.fuel')}>
            <Segmented label={t('prefs.fuel')} value={prefs.fuelType} options={fuels} onChange={(fuelType) => update({ fuelType })} />
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
      </section>
      <section className="flex min-w-0 flex-col gap-6 rounded-box border border-line bg-surface p-4 sm:p-6" aria-label={t('prefs.gallons')}>
      <Field label={t('prefs.gallons')} hint={t('prefs.gallonsHint')}>
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
        <div className="relative max-w-40">
          <TextInput type="number" inputMode="decimal" min={0} max={100} step="0.1" aria-label={t('prefs.cashback')} disabled={prefs.payment === 'cash'} value={prefs.creditCashbackPercent} className="num pr-9" onChange={(event) => {
            const value = event.target.value
            if (value === '' || Number.isFinite(Number(value))) update({ creditCashbackPercent: value === '' ? '' : String(Math.max(0, Math.min(100, Number(value)))) })
          }} />
          <span className="pointer-events-none absolute right-3 top-3 text-sm text-muted">%</span>
        </div>
      </Field>
      <details className="text-xs text-muted">
        <summary className="cursor-pointer font-medium">{t('prefs.cardFees')}</summary>
        <p className="mt-2 leading-relaxed">{t('prefs.cardFeesHint')}</p>
        <p className="mt-2"><a className="underline" target="_blank" rel="noreferrer" href="https://usa.visa.com/content/dam/VCOM/global/support-legal/documents/merchant-surcharging-qa-for-web.pdf">Visa</a> · <a className="underline" target="_blank" rel="noreferrer" href="https://oag.ca.gov/consumers/general/credit-card-surcharges">California DOJ</a></p>
      </details>

      <Field label={t('prefs.priority')} hint={t('prefs.priorityHint',{value:prefs.timeValuePerHour ?? 15})}>
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
      <div className="grid grid-cols-2 gap-3">
        <Field label={t('board.value')}>
          <TextInput type="number" min={0} max={500} step={5} aria-label={t('board.value')} value={prefs.timeValuePerHour ?? 15} onChange={e => update({timeValuePerHour:Math.min(500,Math.max(0,Number(e.target.value)))})} />
        </Field>
        <Field label={t('board.radius')}>
          <select aria-label={t('board.radius')} value={prefs.searchRadiusMiles ?? 5} onChange={e => update({searchRadiusMiles:Number(e.target.value)})} className="h-11 rounded-control border border-line bg-surface px-3">
            {[2,5,10,20].map(m=><option key={m} value={m}>{m} mi</option>)}
          </select>
        </Field>
      </div>


      <div className="flex flex-col gap-5 border-t border-line pt-6">
        <Toggle label={t('prefs.costco')} description={t('prefs.costcoHint')} checked={prefs.costco} onChange={(costco) => update({ costco })} />
        <Toggle label={t('prefs.preferTopTier')} description={t('prefs.preferTopTierHint')} checked={prefs.preferTopTier} onChange={(preferTopTier) => update({ preferTopTier })} />
        {advanced ? (
          <Toggle
            label={t('prefs.unconfirmed')}
            description={t('prefs.unconfirmedHint')}
            checked={prefs.allowUnknownPayment}
            onChange={(allowUnknownPayment) => update({ allowUnknownPayment })}
          />
        ) : null}
      </div>

      {advanced ? <TripForm prefs={prefs} update={update} /> : null}
      {advanced ? (
        <Field label={t('prefs.navApp')}>
          <Segmented label={t('prefs.navApp')} value={prefs.navApp} options={NAV_APPS} onChange={(navApp) => update({ navApp })} />
        </Field>
      ) : null}
      </section>
    </div>
  )
}
