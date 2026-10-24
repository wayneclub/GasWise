import { ArrowClockwiseIcon, CarIcon, MapPinIcon, NavigationArrowIcon } from '@phosphor-icons/react'
import { type ReactNode, useState } from 'react'
import { Button } from '../../components/ui'
import { useI18n } from '../../i18n'
import { effectiveFuel, type Prefs } from '../../lib/prefs'
import { fuelKey } from '../../lib/format'

export function SearchContext({ prefs, label, source, permission, locating, searching, refreshing, onLocate, onChange, onSettings, onRefresh, children }: {
  children?: ReactNode; prefs: Prefs; label: string | null; source: 'device' | 'manual' | null; permission: PermissionState | 'unknown'; locating: boolean; searching: boolean; refreshing?: boolean
  onLocate: () => void; onChange: () => void; onSettings: () => void; onRefresh: () => void
}) {
  const { t } = useI18n()
  const [expanded, setExpanded] = useState(false)
  const busy = locating || searching
  return <section aria-label={t('context.title')} className="liquid-panel my-3 rounded-box">
    <div className="flex items-center gap-2 px-3 py-2">
      <button type="button" onClick={onChange} aria-label={t('location.change')} className="flex min-h-10 min-w-0 flex-1 items-center gap-2 text-left text-sm font-medium">
        <MapPinIcon size={18} className="shrink-0 text-accent"/>
        <span className="truncate">{source === 'device' ? t('context.device') : label ?? t('context.noLocation')}</span>
        {refreshing ? <span className="inline-flex items-center gap-1 rounded-full bg-accent-soft px-1.5 py-0.5 text-[10px] font-normal text-accent"><span className="size-1.5 animate-pulse rounded-full bg-accent" />{t('cache.updating')}</span> : null}
      </button>
      <button type="button" disabled={busy} onClick={onLocate} aria-label={t('context.useGPS')} className="grid size-10 shrink-0 place-items-center rounded-control text-accent hover:bg-sunken disabled:opacity-40"><NavigationArrowIcon size={19}/></button>
      <button type="button" disabled={busy || refreshing} onClick={onRefresh} aria-label={t('decide.refresh')} className="grid size-10 shrink-0 place-items-center rounded-control text-muted hover:bg-sunken disabled:opacity-40"><ArrowClockwiseIcon size={19} className={refreshing ? 'animate-spin text-accent' : ''}/></button>
    </div>
    {children ? <div className="border-t border-line p-4">{children}</div> : null}
    <button type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)} className="flex w-full items-center gap-2 border-t border-line px-3 py-2 text-left text-xs text-muted"><CarIcon size={16} className="shrink-0"/><span className="min-w-0 flex-1 truncate">{prefs.vehicle?.label ?? t('context.manualCar')} · {t(fuelKey(effectiveFuel(prefs)))} · {t(prefs.payment === 'cash_or_credit' ? 'prefs.all' : prefs.payment === 'cash' ? 'prefs.cash' : 'prefs.card')}</span><span className="shrink-0 text-accent">{t(expanded ? 'context.collapse' : 'context.expand')}</span></button>
    {!source || locating ? <p role="status" className="px-3 pb-2 text-xs text-muted">{t(locating ? 'context.locating' : permission === 'denied' ? 'context.denied' : 'context.choose')}</p> : null}
    {expanded ? <div className="border-t border-line p-3"><p className="text-sm">{prefs.vehicle?.label ?? t('context.manualCar')}</p><p className="mt-1 text-xs text-muted">{t(locating ? 'context.locating' : source === 'manual' ? 'context.manual' : source === 'device' ? 'context.deviceHint' : permission === 'denied' ? 'context.denied' : 'context.choose')}</p><div className="mt-2 flex gap-2"><Button variant="ghost" className="h-9 px-2 text-xs" onClick={onChange}>{t('location.change')}</Button><Button variant="ghost" className="h-9 px-2 text-xs" onClick={onSettings}>{t('context.edit')}</Button></div></div> : null}
  </section>
}
