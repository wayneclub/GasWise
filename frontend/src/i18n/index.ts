import { createContext, useContext, useEffect, useState } from 'react'
import { en, type MessageKey } from './en'

export type Locale = 'en' | 'zh-TW' | 'zh-CN' | 'es' | 'ja' | 'ko'
export type Vars = Record<string, string | number>
export type Translate = (key: MessageKey, vars?: Vars) => string
export type { MessageKey }
export type Catalog = Record<MessageKey, string>

export const LOCALES: { value: Locale; label: string }[] = [
  { value: 'en', label: 'English' },
  { value: 'zh-TW', label: '繁體中文' },
  { value: 'zh-CN', label: '简体中文' },
  { value: 'es', label: 'Español' },
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
]

const CATALOGS: Partial<Record<Locale, Catalog>> = { en }
const LOADING_PROMISES: Partial<Record<Locale, Promise<Catalog>>> = {}

const LOADERS: Record<Exclude<Locale, 'en'>, () => Promise<any>> = {
  'zh-TW': () => import('./zh-TW'),
  'zh-CN': () => import('./zh-CN'),
  es: () => import('./es'),
  ja: () => import('./ja'),
  ko: () => import('./ko'),
}

function extractCatalog(locale: Locale, mod: any): Catalog {
  if (locale === 'zh-TW') return mod.zhTW ?? mod.default
  if (locale === 'zh-CN') return mod.zhCN ?? mod.default
  if (locale === 'es') return mod.es ?? mod.default
  if (locale === 'ja') return mod.ja ?? mod.default
  if (locale === 'ko') return mod.ko ?? mod.default
  return mod.default ?? mod
}

export function registerCatalog(locale: Locale, catalog: Catalog): void {
  CATALOGS[locale] = catalog
}

export function isCatalogLoaded(locale: Locale): boolean {
  return locale === 'en' || Boolean(CATALOGS[locale])
}

export function getLoadedCatalog(locale: Locale): Catalog {
  return CATALOGS[locale] ?? en
}

export async function loadCatalog(locale: Locale): Promise<Catalog> {
  if (locale === 'en') return en
  if (CATALOGS[locale]) return CATALOGS[locale]!

  if (!LOADING_PROMISES[locale]) {
    const loader = LOADERS[locale]
    if (!loader) return en
    LOADING_PROMISES[locale] = loader()
      .then((mod) => {
        const catalog = extractCatalog(locale, mod)
        CATALOGS[locale] = catalog
        delete LOADING_PROMISES[locale]
        return catalog
      })
      .catch((err) => {
        delete LOADING_PROMISES[locale]
        console.warn(`[i18n] Failed to load ${locale} catalog:`, err)
        return en
      })
  }
  return LOADING_PROMISES[locale]!
}

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
  if (locale !== 'en' && !CATALOGS[locale]) {
    void loadCatalog(locale)
  }
  const catalog = CATALOGS[locale] ?? en
  return (key, vars) => {
    const template = catalog[key] ?? en[key]
    return vars ? template.replace(/\{(\w+)\}/g, (match, name) => (name in vars ? String(vars[name]) : match)) : template
  }
}

export const I18nContext = createContext<{ locale: Locale; t: Translate }>({ locale: 'en', t: translator('en') })

export function useI18n() {
  return useContext(I18nContext)
}
