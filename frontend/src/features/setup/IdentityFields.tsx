import { Field, Segmented, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n'
import type { VehicleIdentity } from '../../lib/vehicleIdentity'

import { US_STATES, emptyIdentity } from '../../lib/identity'
export function IdentityFields({ identity, onChange, showMode = true }: {
  identity: VehicleIdentity; onChange: (value: VehicleIdentity) => void; showMode?: boolean
}) {
  const { t } = useI18n()
  return <div className="flex flex-col gap-3">
    {showMode ? <Segmented label={t('prefs.car')} value={identity.kind}
      options={[{ value: 'plate', label: t('vehicle.byPlate') }, { value: 'vin', label: t('vehicle.byVin') }]}
      onChange={(kind) => onChange(kind === 'vin' ? { kind, value: { vin: '' } } : emptyIdentity())} /> : null}
    {identity.kind === 'vin' ? <Field label={t('vehicle.vinLabel')}>
      <TextInput aria-label={t('vehicle.vinLabel')} autoComplete="off" maxLength={17} value={identity.value.vin}
        onChange={(e) => onChange({ kind: 'vin', value: { vin: e.target.value.toUpperCase().replace(/\s/g, '') } })} />
    </Field> : <div className="grid grid-cols-[5rem_minmax(0,1fr)] gap-3">
      <Field label={t('vehicle.stateLabel')}>
        <select aria-label={t('vehicle.stateLabel')} className="h-11 rounded-control border border-line bg-surface px-2 text-sm"
          value={identity.value.state} onChange={(e) => onChange({ kind: 'plate', value: { ...identity.value, state: e.target.value } })}>
          {US_STATES.map((state) => <option key={state}>{state}</option>)}
        </select>
      </Field>
      <Field label={t('vehicle.plateLabel')}>
        <TextInput aria-label={t('vehicle.plateLabel')} autoComplete="off" maxLength={12} value={identity.value.plate}
          onChange={(e) => onChange({ kind: 'plate', value: { ...identity.value, plate: e.target.value.toUpperCase().replace(/[ -]/g, '') } })} />
      </Field>
    </div>}
    <p className="text-xs leading-relaxed text-muted">{t('vehicle.identityPrivacy')}</p>
  </div>
}
