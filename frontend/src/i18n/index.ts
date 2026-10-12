import { createContext, useContext } from 'react'
import { en, type MessageKey } from './en'
import { es } from './es'
import { zhTW } from './zh-TW'

export type Locale = 'en' | 'zh-TW' | 'es'
export type Vars = Record<string, string | number>
export type Translate = (key: MessageKey, vars?: Vars) => string
export type { MessageKey }

export const LOCALES: { value: Locale; label: string }[] = [
  { value: 'en', label: 'English' },
  { value: 'zh-TW', label: '繁體中文' },
  { value: 'es', label: 'Español' },
]

const CATALOGS: Record<Locale, Record<MessageKey, string>> = { en, 'zh-TW': zhTW, es }

export function detectLocale(languages: readonly string[] = navigator.languages ?? [navigator.language]): Locale {
  for (const language of languages) {
    const lower = language.toLowerCase()
    if (lower.startsWith('zh')) return 'zh-TW'
    if (lower.startsWith('es')) return 'es'
    if (lower.startsWith('en')) return 'en'
  }
  return 'en'
}

export function translator(locale: Locale): Translate {
  const catalog = CATALOGS[locale]
  return (key, vars) => {
    const template = catalog[key] ?? en[key]
    return vars ? template.replace(/\{(\w+)\}/g, (match, name) => (name in vars ? String(vars[name]) : match)) : template
  }
}

export const I18nContext = createContext<{ locale: Locale; t: Translate }>({ locale: 'en', t: translator('en') })

export function useI18n() {
  return useContext(I18nContext)
}
