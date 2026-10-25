import { Field, Segmented, TextInput } from '../../components/ui'
import { Select } from '../../components/Select'
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
        <Select label={t('vehicle.stateLabel')} value={identity.value.state}
          triggerClassName="gap-1 px-2" panelWidth={160}
          options={US_STATES.map(value => ({ value, label: value }))}
          onChange={state => onChange({ kind: 'plate', value: { ...identity.value, state } })} />
      </Field>
      <Field label={t('vehicle.plateLabel')}>
        <TextInput aria-label={t('vehicle.plateLabel')} autoComplete="off" maxLength={12} value={identity.value.plate}
          onChange={(e) => onChange({ kind: 'plate', value: { ...identity.value, plate: e.target.value.toUpperCase().replace(/[ -]/g, '') } })} />
      </Field>
    </div>}
    <p className="text-xs leading-relaxed text-muted">{t('vehicle.identityPrivacy')}</p>
  </div>
}
