import { IDBFactory } from 'fake-indexeddb'
import { beforeEach, expect, it, vi } from 'vitest'

const subscription = {
  toJSON: () => ({ endpoint: 'https://push.example.test/one', keys: { p256dh: 'public', auth: 'secret' } }),
  unsubscribe: vi.fn(async () => true),
}
const pushManager = { getSubscription: vi.fn(async () => null), subscribe: vi.fn(async () => subscription) }

beforeEach(() => {
  vi.resetModules()
  vi.stubGlobal('indexedDB', new IDBFactory())
  vi.stubGlobal('PushManager', class {})
  vi.stubGlobal('Notification', { requestPermission: vi.fn(async () => 'granted') })
  Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: { ready: Promise.resolve({ pushManager }) } })
  pushManager.getSubscription.mockResolvedValue(null)
  pushManager.subscribe.mockResolvedValue(subscription)
  subscription.unsubscribe.mockClear()
})

it('persists only opaque installation credentials and can revoke them', async () => {
  const responses = [
    { enabled: true, vapid_public_key: 'YWFh' },
    { installation_id: 'installation-id-opaque', installation_token: 'token-that-is-long-enough-to-remain-secret' },
    { status: 'updated' }, { status: 'queued' }, { status: 'disabled' },
  ]
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(responses.shift()), { status: 200, headers: { 'Content-Type': 'application/json' } })))
  const alerts = await import('./smartAlerts')
  await alerts.enableSmartAlerts('en')
  expect(await alerts.alertCredential()).toEqual({ installation_id: 'installation-id-opaque', installation_token: 'token-that-is-long-enough-to-remain-secret' })
  pushManager.getSubscription.mockResolvedValue(subscription as never)
  await alerts.disableSmartAlerts()
  expect(await alerts.alertCredential()).toBeNull()
  expect(subscription.unsubscribe).toHaveBeenCalled()
})

it('compensates when local credential persistence fails after server creation', async () => {
  const responses = [
    { enabled: true, vapid_public_key: 'YWFh' },
    { installation_id: 'installation-id-opaque', installation_token: 'token-that-is-long-enough-to-remain-secret' },
    { status: 'disabled' },
  ]
  const fetch = vi.fn(async () => new Response(JSON.stringify(responses.shift()), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetch)
  const alerts = await import('./smartAlerts')
  vi.spyOn(indexedDB, 'open').mockImplementation(() => { throw new Error('storage failed') })
  await expect(alerts.enableSmartAlerts('en')).rejects.toThrow('storage failed')
  expect(fetch).toHaveBeenCalledTimes(3)
  expect(subscription.unsubscribe).toHaveBeenCalled()
})
