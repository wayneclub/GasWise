import { readFileSync } from 'node:fs'
import { JSDOM } from 'jsdom'
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

const source = readFileSync(new URL('./public/analytics.js', import.meta.url), 'utf8')

describe('GA4 bootstrap', () => {
  it('does not send development or preview traffic', () => {
    const dom = new JSDOM('<head></head>', { url: 'http://localhost:4173/', runScripts: 'outside-only' })
    dom.window.eval(source)
    assert.equal(dom.window.document.querySelector('script'), null)
    assert.equal(dom.window.dataLayer, undefined)
    dom.window.close()
  })

  it('initializes once and strips queries and fragments from page and referrer URLs', () => {
    const dom = new JSDOM('<head></head>', {
      url: 'https://gaswise.wayneclub.com/?vin=private#plate=private',
      referrer: 'https://example.com/start?address=private#private',
      runScripts: 'outside-only',
    })
    dom.window.eval(source)
    dom.window.eval(source)
    const commands = JSON.parse(JSON.stringify(dom.window.dataLayer.map((item) => Array.from(item))))
    assert.equal(commands.length, 3)
    assert.deepEqual(commands[0], ['consent', 'default', {
      ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied',
    }])
    assert.deepEqual(commands[2], ['config', 'G-C9VZE31GQK', {
      page_location: 'https://gaswise.wayneclub.com/',
      page_referrer: 'https://example.com/start',
      cookie_domain: 'gaswise.wayneclub.com', cookie_prefix: 'gaswise',
      allow_google_signals: false, allow_ad_personalization_signals: false,
    }])
    assert.ok(!JSON.stringify(commands).includes('private'))
    const scripts = dom.window.document.querySelectorAll('script')
    assert.equal(scripts.length, 1)
    assert.equal(scripts[0].src, 'https://www.googletagmanager.com/gtag/js?id=G-C9VZE31GQK')
    assert.equal(scripts[0].async, true)
    dom.window.close()
  })
})
