import { describe, expect, it } from 'vitest'
import { translator } from '../i18n'
import { age, gallons, minutes, perGallon, usd } from './format'

const en = translator('en')
const zh = translator('zh-TW')

describe('format', () => {
  it('keeps tenth-of-a-cent pump prices and drops trailing zeros', () => {
    expect(perGallon('5.799')).toBe('$5.799')
    expect(perGallon('6.390')).toBe('$6.39')
  })

  it('formats money and negative differences', () => {
    expect(usd('62.25')).toBe('$62.25')
    expect(usd('-1.5')).toBe('-$1.50')
    expect(usd(null)).toBe('-')
  })

  it('rounds drive time per locale', () => {
    expect(minutes('0.4', en)).toBe('<1 min')
    expect(minutes('23.17', en)).toBe('23 min')
    expect(minutes(95, en)).toBe('1 h 35 min')
    expect(minutes(95, zh)).toBe('1 小時 35 分鐘')
    expect(gallons(10, zh)).toBe('10 加侖')
  })

  it('describes price age, and says when it is unknown', () => {
    const now = new Date('2026-10-11T12:00:00Z')
    expect(age('2026-10-11T11:48:00Z', en, now)).toBe('12 min ago')
    expect(age('2026-10-08T12:00:00Z', en, now)).toBe('3 days ago')
    expect(age(null, en, now)).toBe('update time unknown')
    expect(zh('age.updated', { age: age('2026-10-11T11:48:00Z', zh, now) })).toBe('12 分鐘前更新')
  })
})
