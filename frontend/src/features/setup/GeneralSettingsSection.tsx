import { LanguagePicker } from '../../components/LanguagePicker'
import { Field, Segmented } from '../../components/ui'
import { useI18n } from '../../i18n'
import { NAV_APPS } from '../../lib/navigation'
import type { Prefs } from '../../lib/prefs'
import { SettingsSection } from './SettingsSection'

interface GeneralSettingsSectionProps {
  prefs: Prefs
  update: (change: Partial<Prefs>) => void
}

export function GeneralSettingsSection({ prefs, update }: GeneralSettingsSectionProps) {
  const { t } = useI18n()

  return (
    <SettingsSection
      id="section-general"
      title={t('prefs.general')}
      description={t('prefs.generalHint')}
    >
      <Field label={t('prefs.language')}>
        <LanguagePicker value={prefs.locale} onChange={(locale) => update({ locale })} />
      </Field>

      <Field label={t('prefs.navApp')}>
        <Segmented
          label={t('prefs.navApp')}
          value={prefs.navApp}
          options={NAV_APPS}
          onChange={(navApp) => update({ navApp })}
        />
      </Field>
    </SettingsSection>
  )
}
