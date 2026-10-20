self.addEventListener('push', event => {
  let data = {}
  try { data = event.data?.json() ?? {} } catch {}
  const title = typeof data.title === 'string' ? data.title : 'GasWise'
  const options = {
    body: typeof data.body === 'string' ? data.body : '',
    tag: typeof data.tag === 'string' ? data.tag : 'gaswise-smart-alert',
    data: { url: typeof data.url === 'string' && data.url.startsWith('/') ? data.url : '/' },
    icon: '/favicon.svg',
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', event => {
  event.notification.close()
  const target = new URL(event.notification.data?.url || '/', self.location.origin).href
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    const existing = windows.find(client => new URL(client.url).origin === self.location.origin)
    if (existing) { await existing.navigate(target); return existing.focus() }
    return self.clients.openWindow(target)
  })())
})
