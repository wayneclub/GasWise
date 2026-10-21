import { describe, expect, it } from 'vitest'

import { serviceWorkerUrl } from './serviceWorker'

describe('serviceWorkerUrl', () => {
  it('changes with the hashed application bundle and never exposes its origin', () => {
    const first = serviceWorkerUrl('https://gaswise.wayneclub.com/assets/index-first.js')
    const second = serviceWorkerUrl('https://gaswise.wayneclub.com/assets/index-second.js')

    expect(first).toBe('/sw.js?v=%2Fassets%2Findex-first.js')
    expect(second).not.toBe(first)
    expect(first).not.toContain('gaswise.wayneclub.com')
  })
})
