import { GlobeIcon } from '@phosphor-icons/react'
import { LOCALES, useI18n, type Locale } from '../i18n'
import { Select } from './Select'

// Flags are visual locale cues; native language names remain the accessible labels.
const FLAGS: Record<Locale, string> = { en: '🇺🇸', 'zh-TW': '🇹🇼', 'zh-CN': '🇨🇳', es: '🇪🇸', ja: '🇯🇵', ko: '🇰🇷' }

export function LanguagePicker({ value, onChange, compact = false, className = '' }: {
  value: Locale | null | undefined; onChange: (value: Locale | null) => void; compact?: boolean; className?: string
}) {
  const { t } = useI18n()
  return <Select label={t('prefs.language')} value={value ?? 'auto'}
    options={[{ value: 'auto' as const, label: t('prefs.languageAuto'), icon: <GlobeIcon size={20} /> }, ...LOCALES.map(locale => ({ ...locale, icon: FLAGS[locale.value] }))]}
    onChange={next => onChange(next === 'auto' ? null : next)}
    iconOnly={compact} triggerIcon={<GlobeIcon size={21} />} align={compact ? 'end' : 'start'} className={className} />
}
