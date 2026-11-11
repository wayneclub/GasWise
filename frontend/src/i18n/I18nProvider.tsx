import { type ReactNode, useEffect, useMemo, useState } from 'react'
import {
  I18nContext,
  type Locale,
  getLoadedCatalog,
  isCatalogLoaded,
  loadCatalog,
} from './index'

export function I18nProvider({ locale, children }: { locale: Locale; children: ReactNode }) {
  const [activeCatalogLocale, setActiveCatalogLocale] = useState<Locale>(() =>
    isCatalogLoaded(locale) ? locale : 'en'
  )

  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  useEffect(() => {
    if (isCatalogLoaded(locale)) {
      setActiveCatalogLocale(locale)
      return
    }
    let cancelled = false
    void loadCatalog(locale).then(() => {
      if (!cancelled) {
        setActiveCatalogLocale(locale)
      }
    })
    return () => {
      cancelled = true
    }
  }, [locale])

  const value = useMemo(() => {
    const catalog = getLoadedCatalog(activeCatalogLocale === locale ? locale : 'en')
    const t = (key: any, vars?: any) => {
      const template = catalog[key] ?? getLoadedCatalog('en')[key]
      return vars ? template.replace(/\{(\w+)\}/g, (match: string, name: string) => (name in vars ? String(vars[name]) : match)) : template
    }
    return { locale, t }
  }, [locale, activeCatalogLocale])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}
