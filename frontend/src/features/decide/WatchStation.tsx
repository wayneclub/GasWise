import { useEffect, useMemo, useState } from 'react'
import type { Station } from '../../api/types'
import { useI18n } from '../../i18n'
import { alertCredential, alertWatchKey, isAlertWatched, updateAlertWatch } from '../../lib/smartAlerts'

export function WatchStation({ station }: { station: Partial<Station> }) {
  const { t } = useI18n()
  const [enabled, setEnabled] = useState(false)
  const [available, setAvailable] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  const watch = useMemo(() => station.id && station.source && station.fuel_type ? {
    enabled: true,
    canonical_id: station.canonical_id ?? null,
    source: station.source,
    station_id: station.id,
    station_name: station.name ?? station.id,
    fuel_type: station.fuel_type,
    payment_type: station.payment_type ?? 'unknown' as const,
    membership_required: station.membership_required ?? null,
    octane: station.octane ?? null,
    currency: 'USD' as const,
    unit: 'US_gallon' as const,
    expected_gallons: 10,
    threshold_cents: 10,
  } : null, [station])
  useEffect(() => {
    if (!watch) return
    void Promise.all([alertCredential(), isAlertWatched(alertWatchKey(watch))]).then(([credential, watched]) => {
      setAvailable(Boolean(credential)); setEnabled(watched)
    }).catch(() => setError(true))
  }, [watch])
  if (!watch) return null
  async function toggle() {
    if (!watch) return
    setBusy(true); setError(false)
    try { await updateAlertWatch({ ...watch, enabled: !enabled }); setEnabled(!enabled) }
    catch { setError(true) } finally { setBusy(false) }
  }
  return <div className="rounded-control border border-line bg-surface p-3">
    <button type="button" disabled={busy || !available} onClick={() => void toggle()} className="text-sm font-medium text-accent disabled:text-muted">{t(enabled ? 'alerts.unwatch' : 'alerts.watch')}</button>
    <p className="mt-1 text-xs text-muted">{t(available ? 'alerts.watchHint' : 'alerts.enableFirst')}</p>
    {error ? <p role="status" className="mt-1 text-xs text-caution">{t('alerts.watchError')}</p> : null}
  </div>
}
