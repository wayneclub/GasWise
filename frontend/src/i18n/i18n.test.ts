import { describe, expect, it } from 'vitest'
import { en } from './en'
import { es } from './es'
import { detectLocale, translator } from './index'
import { zhTW } from './zh-TW'
import { zhCN } from './zh-CN'

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort()

describe('i18n', () => {
  it('detects the browser language with an English fallback', () => {
    expect(detectLocale(['zh-TW', 'en'])).toBe('zh-TW')
    expect(detectLocale(['zh-Hant-HK'])).toBe('zh-TW')
    expect(detectLocale(['zh-CN'])).toBe('zh-CN')
    expect(detectLocale(['zh-SG'])).toBe('zh-CN')
    expect(detectLocale(['zh-Hans-TW'])).toBe('zh-CN')
    expect(detectLocale(['zh-Hant-CN'])).toBe('zh-TW')
    expect(detectLocale(['zh-HK'])).toBe('zh-TW')
    expect(detectLocale(['zh'])).toBe('zh-CN')
    expect(detectLocale(['fr-FR', 'zh-CN', 'en-US'])).toBe('zh-CN')
    expect(detectLocale(['es-MX'])).toBe('es')
    expect(detectLocale(['fr-FR', 'en-US'])).toBe('en')
    expect(detectLocale(['ja-JP'])).toBe('en')
  })

  it('keeps every placeholder in every translation', () => {
    for (const catalog of [zhTW, zhCN, es]) {
      for (const key of Object.keys(en) as (keyof typeof en)[]) {
        expect(placeholders(catalog[key]), key).toEqual(placeholders(en[key]))
      }
    }
  })

  it('interpolates variables', () => {
    expect(translator('es')('pick.save', { amount: '$2.05', name: 'Chevron' })).toBe('Ahorras $2.05 frente a Chevron')
    expect(translator('zh-TW')('pick.save', { amount: '$2.05', name: 'Chevron' })).toBe('比 Chevron 省 $2.05')
    expect(translator('zh-CN')('pick.save', { amount: '$2.05', name: 'Chevron' })).toBe('比 Chevron 省 $2.05')
  })

  it('never uses em or en dashes in visible copy', () => {
    for (const catalog of [en, zhTW, zhCN, es]) {
      for (const text of Object.values(catalog)) expect(text).not.toMatch(/[–—]/)
    }
  })
})
