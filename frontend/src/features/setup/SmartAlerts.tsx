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
  const isIos = typeof navigator !== 'undefined' && (/iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1))
  const isStandalone = typeof window !== 'undefined' && (Boolean((window.navigator as unknown as { standalone?: boolean }).standalone) || Boolean(window.matchMedia?.('(display-mode: standalone)')?.matches))
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

  return (
    <section
      id="smart-alerts"
      tabIndex={-1}
      className="grid grid-cols-1 gap-6 border-b border-line py-8 first:pt-0 last:border-b-0 lg:grid-cols-[280px_1fr] lg:gap-10 lg:py-10 scroll-mt-24 outline-none"
      aria-label={t('alerts.title')}
    >
      <div className="flex flex-col gap-2 lg:pt-1">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-ink">{t('alerts.title')}</h2>
          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${enabled ? 'bg-accent-soft text-accent' : 'bg-sunken text-muted'}`}>
            {enabled ? 'Active' : 'Off'}
          </span>
        </div>
        <p className="text-[13px] leading-relaxed text-muted">{t('alerts.description')}</p>
        <p className="mt-1 text-xs leading-relaxed text-muted">{t('alerts.privacy')}</p>
      </div>

      <div className="liquid-panel rounded-box p-5 sm:p-6 flex flex-col gap-5 min-w-0">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex flex-col gap-0.5">
            <span className="text-[15px] font-medium text-ink">{t('alerts.title')}</span>
            <span className="text-xs text-muted">{enabled ? t('alerts.enabled') : t('alerts.description')}</span>
          </div>
          <button
            type="button"
            disabled={busy || !supported}
            onClick={() => void toggle()}
            className={`inline-flex h-11 shrink-0 items-center justify-center rounded-control px-4 text-sm font-medium transition active:scale-[0.98] disabled:opacity-50 ${
              enabled
                ? 'border border-line bg-surface text-ink hover:bg-sunken'
                : 'bg-ink text-surface hover:opacity-90'
            }`}
          >
            {t(enabled ? 'alerts.disable' : 'alerts.enable')}
          </button>
        </div>

        {!supported ? <p role="status" className="text-xs text-caution">{t('alerts.unsupported')}</p> : null}
        {isIos && !isStandalone ? (
          <div className="rounded-control bg-amber-500/10 border border-amber-500/30 p-3.5 text-xs text-amber-800 dark:text-amber-200">
            <p className="font-semibold flex items-center gap-1.5">
              <span>📱 {t('alerts.iosPwaTipTitle')}</span>
            </p>
            <p className="mt-1 leading-relaxed opacity-90">{t('alerts.iosPwaTip')}</p>
          </div>
        ) : null}
        {notice ? <p role="status" className={`text-xs ${notice === 'error' ? 'text-caution' : 'text-muted'}`}>{t(notice === 'error' ? 'alerts.error' : enabled ? 'alerts.enabled' : 'alerts.disabled')}</p> : null}

        {items.length ? (
          <div className="border-t border-line pt-4">
            <h3 className="text-sm font-medium text-ink">{t('alerts.inbox')}</h3>
            <ul className="mt-3 space-y-2.5">
              {items.slice(0, 5).map(item => (
                <li key={item.id} className="rounded-control bg-sunken p-3.5">
                  <p className="text-sm font-medium text-ink">{item.title}</p>
                  <p className="mt-1 text-xs text-muted">{item.body}</p>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  )
}
