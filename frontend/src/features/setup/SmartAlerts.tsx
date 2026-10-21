import { useEffect, useState } from 'react'
import { useI18n } from '../../i18n'
import { alertCredential, disableSmartAlerts, enableSmartAlerts, smartAlertsSupported } from '../../lib/smartAlerts'
import { api } from '../../api/client'

export function SmartAlerts() {
  const { t, locale } = useI18n()
  const [enabled, setEnabled] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<'ready' | 'error' | null>(null)
  const [items, setItems] = useState<{ id: number; title: string; body: string; created_at: string }[]>([])
  const supported = smartAlertsSupported()
  useEffect(() => { void alertCredential().then(async value => {
    setEnabled(Boolean(value))
    if (value) setItems((await api.alertInbox(value)).items)
  }).catch(() => setNotice('error')) }, [])

  async function toggle() {
    setBusy(true); setNotice(null)
    try {
      if (enabled) { await disableSmartAlerts(); setItems([]) } else await enableSmartAlerts(locale)
      setEnabled(!enabled); setNotice('ready')
    } catch { setNotice('error') } finally { setBusy(false) }
  }

  return <section id="smart-alerts" tabIndex={-1} className="flex min-w-0 scroll-mt-24 flex-col gap-4 liquid-panel rounded-box p-4 outline-none sm:p-6 lg:col-span-2" aria-label={t('alerts.title')}>
    <div><h2 className="font-semibold">{t('alerts.title')}</h2><p className="mt-1 text-xs leading-relaxed text-muted">{t('alerts.description')}</p></div>
    <p className="text-xs leading-relaxed text-muted">{t('alerts.privacy')}</p>
    <div><button type="button" disabled={busy || !supported} onClick={() => void toggle()} className="rounded-control border border-line px-4 py-2 text-sm disabled:opacity-50">{t(enabled ? 'alerts.disable' : 'alerts.enable')}</button></div>
    {!supported ? <p role="status" className="text-xs text-caution">{t('alerts.unsupported')}</p> : null}
    {notice ? <p role="status" className={`text-xs ${notice === 'error' ? 'text-caution' : 'text-muted'}`}>{t(notice === 'error' ? 'alerts.error' : enabled ? 'alerts.enabled' : 'alerts.disabled')}</p> : null}
    {items.length ? <div className="border-t border-line pt-3"><h3 className="text-sm font-medium">{t('alerts.inbox')}</h3><ul className="mt-2 space-y-2">{items.slice(0, 5).map(item => <li key={item.id} className="rounded-control bg-sunken p-3"><p className="text-sm font-medium">{item.title}</p><p className="mt-1 text-xs text-muted">{item.body}</p></li>)}</ul></div> : null}
  </section>
}
