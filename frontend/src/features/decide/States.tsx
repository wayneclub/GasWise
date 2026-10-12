import { messageId } from '../../lib/errorMessages'
import { ArrowClockwiseIcon, MapPinIcon, NavigationArrowIcon, WarningIcon } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { Button } from '../../components/ui'
import { type MessageKey, useI18n } from '../../i18n'
import { LocationSearch } from '../setup/LocationSearch'
import type { Origin } from '../../lib/session'
import type { SessionError } from '../../lib/session'

export function PickSkeleton({ label }: { label: string }) {
  return (
    <section aria-busy="true" aria-label={label} className="rounded-box border border-line bg-surface p-5 shadow-raised">
      <div className="flex items-center justify-between">
        <div className="skeleton h-4 w-28" />
        <div className="skeleton h-6 w-24 rounded-full" />
      </div>
      <div className="skeleton mt-4 h-7 w-44" />
      <div className="skeleton mt-2 h-4 w-60" />
      <div className="skeleton mt-6 h-10 w-36" />
      <div className="mt-5 grid grid-cols-2 gap-3 border-t border-line pt-4">
        <div className="skeleton h-4" />
        <div className="skeleton h-4" />
      </div>
      <div className="skeleton mt-6 h-12 w-full rounded-control" />
      <p className="mt-4 text-center text-[13px] text-muted" aria-live="polite">
        {label}
      </p>
    </section>
  )
}


export function ErrorState({
  error,
  onRetry,
  onLocate,
  onDemoLocation,
  onChooseLocation,
}: {
  error: SessionError
  onRetry: () => void
  onLocate: () => void
  onDemoLocation?: () => void
  onChooseLocation?: (location: Origin, label: string) => void
}) {
  const { t } = useI18n()
  // The parent keys this component per failure, so the countdown restarts for each error.
  const [wait, setWait] = useState(error.retryAfterSeconds ?? 0)
  useEffect(() => {
    if (wait <= 0) return
    const timer = window.setTimeout(() => setWait(wait - 1), 1000)
    return () => window.clearTimeout(timer)
  }, [wait])
  const id = messageId(error)
  const askingForLocation = error.kind === 'location' && error.code !== 'unsupported'
  const Icon = error.kind === 'location' ? MapPinIcon : WarningIcon
  return (
    <section role={error.code === 'prompt' ? undefined : 'alert'} className="rounded-box border border-line bg-surface px-5 py-8 text-center shadow-raised">
      <span className="mx-auto grid size-11 place-items-center rounded-full bg-sunken text-muted">
        <Icon size={22} />
      </span>
      <h2 className="mt-4 text-[18px] font-semibold">{t(`error.${id}.title` as MessageKey)}</h2>
      <p className="mx-auto mt-1 max-w-[34ch] text-[14px] leading-relaxed text-muted">{t(`error.${id}.body` as MessageKey)}</p>
      <div className="mt-6 flex flex-col items-center gap-2">
        {askingForLocation ? (
          <Button onClick={onLocate}>
            <NavigationArrowIcon size={17} weight="fill" />
            {t('state.allowLocation')}
          </Button>
        ) : (
          <Button onClick={onRetry} disabled={wait > 0}>
            <ArrowClockwiseIcon size={17} />
            {wait > 0 ? t('state.retryIn', { n: wait }) : t('state.retry')}
          </Button>
        )}
        {onDemoLocation && error.kind === 'location' ? (
          <Button variant="ghost" onClick={onDemoLocation}>
            {t('decide.demoLocation')}
          </Button>
        ) : null}
      </div>
      {error.kind === 'location' && onChooseLocation ? <div className="mt-6 border-t border-line pt-5"><LocationSearch onChoose={onChooseLocation} /></div> : null}
      {error.kind === 'location' ? <p className="mx-auto mt-4 max-w-[36ch] text-[12px] text-faint">{t('app.locationPrivacy')}</p> : null}
    </section>
  )
}

export function EmptyState({
  reasons,
  canWiden,
  onWiden,
  onSettings,
}: {
  reasons: string[]
  canWiden: boolean
  onWiden: () => void
  onSettings: () => void
}) {
  const { t } = useI18n()
  return (
    <section className="rounded-box border border-line bg-surface px-5 py-8 text-center shadow-raised">
      <h2 className="text-[18px] font-semibold">{t('empty.title')}</h2>
      <p className="mx-auto mt-1 max-w-[36ch] text-[14px] leading-relaxed text-muted">{reasons[0] ?? t('empty.fallback')}</p>
      <div className="mt-6 flex flex-col items-center gap-2">
        {canWiden ? <Button onClick={onWiden}>{t('empty.widen')}</Button> : null}
        <Button variant="ghost" onClick={onSettings}>
          {t('empty.review')}
        </Button>
      </div>
      {canWiden ? <p className="mx-auto mt-4 max-w-[38ch] text-[12px] leading-snug text-faint">{t('empty.widenNote')}</p> : null}
    </section>
  )
}
