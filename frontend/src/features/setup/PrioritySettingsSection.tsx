import { Select } from '../../components/Select'
import { Field, Segmented, TextInput, Toggle } from '../../components/ui'
import { useI18n } from '../../i18n'
import type { Prefs } from '../../lib/prefs'
import { SettingsSection } from './SettingsSection'

interface PrioritySettingsSectionProps {
  prefs: Prefs
  update: (change: Partial<Prefs>) => void
  advanced?: boolean
}

export function PrioritySettingsSection({
  prefs,
  update,
  advanced = false,
}: PrioritySettingsSectionProps) {
  const { t } = useI18n()

  return (
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
          <Select
            label={t('board.radius')}
            value={String(prefs.searchRadiusMiles ?? 5)}
            onChange={(value) => update({ searchRadiusMiles: Number(value) })}
            options={[2, 5, 10, 20].map((value) => ({ value: String(value), label: `${value} mi` }))}
          />
        </Field>
      </div>

      <div className="flex flex-col gap-5 border-t border-line pt-5">
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
  )
}
