import { api, type AlertAuth, type AlertWatch } from '../api/client'

const DATABASE = 'gaswise-alerts-v1'
const STORE = 'credentials'
const WATCHES = 'watches'
const SLOT = 'current'

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 2)
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE)) request.result.createObjectStore(STORE)
      if (!request.result.objectStoreNames.contains(WATCHES)) request.result.createObjectStore(WATCHES)
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = request.onblocked = () => reject(new Error('alert_storage_unavailable'))
  })
}

async function credential(value?: AlertAuth | null): Promise<AlertAuth | null> {
  const db = await open()
  try {
    return await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE, value === undefined ? 'readonly' : 'readwrite')
      const store = transaction.objectStore(STORE)
      if (value === undefined) {
        const request = store.get(SLOT)
        request.onsuccess = () => resolve(request.result ?? null)
        request.onerror = () => reject(new Error('alert_storage_unavailable'))
      } else {
        if (value) store.put(value, SLOT); else store.delete(SLOT)
        transaction.oncomplete = () => resolve(value ?? null)
        transaction.onerror = transaction.onabort = () => reject(new Error('alert_storage_unavailable'))
      }
    })
  } finally { db.close() }
}

function applicationServerKey(value: string): Uint8Array<ArrayBuffer> {
  const decoded = atob(value.replaceAll('-', '+').replaceAll('_', '/') + '='.repeat((4 - value.length % 4) % 4))
  return Uint8Array.from(decoded, char => char.charCodeAt(0))
}

async function watchRecord(key: string, value?: boolean | null): Promise<boolean> {
  const db = await open()
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(WATCHES, value === undefined ? 'readonly' : 'readwrite')
      const store = tx.objectStore(WATCHES)
      if (value === undefined) {
        const request = store.get(key)
        request.onsuccess = () => resolve(Boolean(request.result))
        request.onerror = () => reject(new Error('alert_storage_unavailable'))
      } else {
        if (value) store.put(true, key); else store.delete(key)
        tx.oncomplete = () => resolve(Boolean(value))
        tx.onerror = tx.onabort = () => reject(new Error('alert_storage_unavailable'))
      }
    })
  } finally { db.close() }
}

export function alertWatchKey(watch: Pick<AlertWatch, 'source' | 'station_id' | 'fuel_type' | 'payment_type' | 'membership_required' | 'octane'>): string {
  return [watch.source, watch.station_id, watch.fuel_type, watch.payment_type,
    watch.membership_required ?? '', watch.octane ?? ''].join(':')
}

export async function isAlertWatched(key: string): Promise<boolean> { return watchRecord(key) }

export async function updateAlertWatch(watch: AlertWatch): Promise<void> {
  const current = await credential()
  if (!current) throw new Error('alerts_not_enabled')
  await api.updateAlertWatch({ ...current, ...watch })
  await watchRecord(alertWatchKey(watch), watch.enabled)
}

export function smartAlertsSupported(): boolean {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window && typeof indexedDB !== 'undefined'
}

export async function alertCredential(): Promise<AlertAuth | null> {
  if (!smartAlertsSupported()) return null
  return credential()
}

export async function enableSmartAlerts(locale: string): Promise<void> {
  if (!smartAlertsSupported()) throw new Error('unsupported')
  const config = await api.alertConfig()
  if (!config.enabled || !config.vapid_public_key) throw new Error('unavailable')

  if (typeof Notification !== 'undefined' && Notification.permission === 'denied') {
    throw new Error('permission_denied')
  }
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') throw new Error('permission_denied')

  if (typeof navigator.serviceWorker.getRegistration === 'function') {
    const reg = await navigator.serviceWorker.getRegistration('/').catch(() => null)
    if (!reg && typeof navigator.serviceWorker.register === 'function') {
      await navigator.serviceWorker.register('/sw.js', { scope: '/', updateViaCache: 'none' }).catch(() => {})
    }
  }
  const registration = await navigator.serviceWorker.ready

  const previous = await registration.pushManager.getSubscription()
  const subscription = previous ?? await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: applicationServerKey(config.vapid_public_key),
  })

  const subJson = subscription.toJSON()
  if (!subJson.keys?.p256dh || !subJson.keys?.auth) {
    if (typeof subscription.getKey === 'function') {
      const p256dhKey = subscription.getKey('p256dh')
      const authKey = subscription.getKey('auth')
      if (p256dhKey && authKey) {
        const toB64 = (buf: ArrayBuffer) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
        subJson.keys = {
          p256dh: toB64(p256dhKey),
          auth: toB64(authKey),
        }
      }
    }
  }

  let created: AlertAuth | null = null
  try {
    created = await api.createAlertInstallation({
      subscription: subJson as unknown as PushSubscriptionJSON,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
      locale,
    })
    await credential(created)
    await api.updateAlertNeed({ ...created, state: 'unknown', confidence: 'low', ttl_hours: 24 })
    await api.testAlert({ ...created, locale })
  } catch (error) {
    if (created) await api.disableAlerts(created).catch(() => ({ status: 'cleanup_deferred' }))
    if (!previous) await subscription.unsubscribe().catch(() => false)
    throw error
  }
}

export async function disableSmartAlerts(): Promise<void> {
  const current = await credential()
  if (current) await api.disableAlerts(current)
  const registration = 'serviceWorker' in navigator ? await navigator.serviceWorker.ready : null
  const subscription = await registration?.pushManager.getSubscription()
  await subscription?.unsubscribe()
  await credential(null)
  const db = await open()
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(WATCHES, 'readwrite')
      tx.objectStore(WATCHES).clear()
      tx.oncomplete = () => resolve()
      tx.onerror = tx.onabort = () => reject(new Error('alert_storage_unavailable'))
    })
  } finally { db.close() }
}

export async function clearSmartAlertStorage(): Promise<void> {
  await disableSmartAlerts()
}
