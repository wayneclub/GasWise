import { createContext, useContext, useEffect, useState } from 'react'
import { en, type MessageKey } from './en'
import { es } from './es'
import { ja } from './ja'
import { ko } from './ko'
import { zhTW } from './zh-TW'
import { zhCN } from './zh-CN'

export type Locale = 'en' | 'zh-TW' | 'zh-CN' | 'es' | 'ja' | 'ko'
export type Vars = Record<string, string | number>
export type Translate = (key: MessageKey, vars?: Vars) => string
export type { MessageKey }

export const LOCALES: { value: Locale; label: string }[] = [
  { value: 'en', label: 'English' },
  { value: 'zh-TW', label: '繁體中文' },
  { value: 'zh-CN', label: '简体中文' },
  { value: 'es', label: 'Español' },
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
]

const CATALOGS: Record<Locale, Record<MessageKey, string>> = { en, 'zh-TW': zhTW, 'zh-CN': zhCN, es, ja, ko }

export function detectLocale(languages: readonly string[] = navigator.languages ?? [navigator.language]): Locale {
  for (const language of languages) {
    const lower = language.toLowerCase()
    const [base, ...subtags] = lower.split('-')
    if (base === 'zh') {
      if (subtags.includes('hans')) return 'zh-CN'
      if (subtags.includes('hant') || subtags.some((tag) => ['tw', 'hk', 'mo'].includes(tag))) return 'zh-TW'
      return 'zh-CN'
    }
    if (base === 'es') return 'es'
    if (base === 'ja') return 'ja'
    if (base === 'ko') return 'ko'
    if (base === 'en') return 'en'
  }
  return 'en'
}

export function useBrowserLocale(): Locale {
  const [locale, setLocale] = useState(() => detectLocale())
  useEffect(() => {
    const changed = () => setLocale(detectLocale())
    window.addEventListener('languagechange', changed)
    return () => window.removeEventListener('languagechange', changed)
  }, [])
  return locale
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
