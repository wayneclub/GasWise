import { SearchContext } from './SearchContext'
import { useEffect, useRef, useState } from 'react'
import { Button, Segmented, Sheet, Stepper } from '../../components/ui'
import { type MessageKey, useI18n } from '../../i18n'
import { age, gallons, sourceLabel } from '../../lib/format'
import { type Prefs } from '../../lib/prefs'
import { assess, PRIORITY_STRATEGY, picks, tradeoff } from '../../lib/recommend'
import { messageId } from '../../lib/errorMessages'
import { useFuelSession } from '../../lib/session'
import { LocationSearch } from '../setup/LocationSearch'
import { HeroPick } from './PickCards'
import { EmptyState, ErrorState, PickSkeleton } from './States'
import { NearbyStations } from './NearbyStations'
import { StationList } from './StationList'
import { Leaderboards } from './Leaderboards'

const DOWNTOWN_LA = { lat: 34.0522, lng: -118.2437 }

export function Decide({ prefs, update, onSettings, active = true }: { active?: boolean; prefs: Prefs; update: (change: Partial<Prefs>) => void; onSettings: () => void }) {
  const { t } = useI18n()
  const session = useFuelSession(prefs, active)
  const [locationOpen, setLocationOpen] = useState(false)
  const [locationLabel, setLocationLabel] = useState<string | null>(null)
  const { start } = session
  const started = useRef(false)

  // One search per visit. StrictMode remounts must not spend a second acquisition.
  useEffect(() => {
    let cancelled = false
    queueMicrotask(() => {
      if (cancelled || started.current) return
      started.current = true
      void start()
    })
    return () => { cancelled = true }
  }, [start])

  const { phase, result, error } = session
  const primary = PRIORITY_STRATEGY[prefs.preference]
  const cards = result ? picks(result, primary) : []
  const assessment = result ? assess(result, primary) : null
  const [hero] = cards
  const rows = result?.ranking?.results ?? []
  const sources = result?.snapshot.source_statuses.filter((s) => s.status === 'ok') ?? []

  return (
    <div className="mx-auto w-full max-w-md px-4 pb-12 lg:max-w-5xl">
      <SearchContext prefs={prefs} label={locationLabel} source={session.originKind} permission={session.locationPermission} locating={phase === 'locating'} searching={phase === 'searching'}
        onLocate={() => void start({ userInitiated: true })} onChange={() => setLocationOpen(true)} onSettings={onSettings} onRefresh={() => void session.refresh()} />

      <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] lg:items-start lg:gap-8">
        <div className="flex flex-col gap-4">
          <section aria-label={t('decide.yourFill')} className="flex flex-col gap-3">
            <div className="flex items-center justify-between gap-3"><h2 className="text-sm font-semibold">{t('decide.yourFill')}</h2>
              <Segmented label={t('prefs.payment')} value={prefs.payment} options={[{value:'cash_or_credit',label:t('prefs.all')},{value:'cash',label:t('prefs.cash')},{value:'credit',label:t('prefs.card')}]} onChange={(payment) => update({payment})} />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Stepper
                label={t('ui.gallons')}
                value={prefs.gallons}
                min={1}
                max={30}
                step={1}
                format={(value) => gallons(value, t)}
                onChange={(value) => update({ gallons: value })}
              />
              <div className="min-w-[14rem] flex-1">
                <Segmented
                  label={t('prefs.priority')}
                  value={prefs.preference}
                  options={[
                    { value: 'money', label: t('prefs.moneyShort') },
                    { value: 'balanced', label: t('prefs.balanced') },
                    { value: 'time', label: t('prefs.timeShort') },
                  ]}
                  onChange={(preference) => update({ preference })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs text-muted">
              <label className="flex flex-col gap-1.5">{t('board.radius')}
                <select aria-label={t('board.radius')} value={prefs.searchRadiusMiles ?? 5} onChange={e => update({searchRadiusMiles:Number(e.target.value)})} className="h-9 rounded-control border border-line bg-surface px-3 text-ink">
                  {[2,5,10,20].map(m => <option key={m} value={m}>{m} mi</option>)}
                </select>
              </label>
              <label className="flex flex-col gap-1.5">{t('board.value')}
                <input type="number" min={0} max={500} step={5} aria-label={t('board.value')} value={prefs.timeValuePerHour ?? 15} onChange={e => update({timeValuePerHour:Math.min(500,Math.max(0,Number(e.target.value)))})} className="num h-9 min-w-0 rounded-control border border-line bg-surface px-3 text-ink" />
              </label>
            </div>
          </section>

          {session.expired ? (
            <div className="flex items-center justify-between gap-3 rounded-control bg-caution-soft px-4 py-3 text-[14px] text-caution">
              <span>{t('decide.expired')}</span>
              <button type="button" className="shrink-0 font-medium underline underline-offset-2" onClick={() => void session.refresh()}>
                {t('decide.refresh')}
              </button>
            </div>
          ) : null}

          {session.refreshing ? <p role="status" className="text-xs text-accent">{t('cache.updating')}</p> : null}
          {phase === 'ready' && error ? (
            <p role="status" className="rounded-control bg-caution-soft px-4 py-3 text-[14px] text-caution">
              {error.kind === 'location' ? t('context.keptLocation') : t('cache.failed')}
            </p>
          ) : null}

          {phase === 'searching' || phase === 'idle' || (phase === 'locating' && !result) ? (
            <PickSkeleton label={phase === 'searching' ? t('decide.searching') : t('decide.locating')} />
          ) : phase === 'error' && error?.kind === 'location' ? (
            <section className="rounded-box border border-line bg-surface p-5">
              {error.code !== 'prompt' ? <><h3 className="text-sm font-semibold">{t(`error.${messageId(error)}.title` as MessageKey)}</h3><p className="mb-4 mt-2 text-sm leading-relaxed text-muted">{t(`error.${messageId(error)}.body` as MessageKey)}</p></> : null}
              <LocationSearch onChoose={(location, label) => { setLocationLabel(label); void start({ override: location }) }} />
              {import.meta.env.DEV ? <Button variant="ghost" className="mt-3 h-8 text-xs" onClick={() => { setLocationLabel(t('decide.demoLocation')); void start({ override: DOWNTOWN_LA }) }}>{t('decide.demoLocation')}</Button> : null}
            </section>
          ) : phase === 'error' && error ? (
            <ErrorState
              key={error.at}
              error={error}
              onRetry={() => void session.refresh()}
              onLocate={() => void start({ userInitiated: true })}
              onChooseLocation={(location, label) => { setLocationLabel(label); void start({ override: location }) }}
              onDemoLocation={import.meta.env.DEV ? () => void start({ override: DOWNTOWN_LA }) : undefined}
            />
          ) : result && assessment && hero ? (
            <div className={`transition-opacity ${session.reranking ? 'opacity-60' : ''}`} aria-busy={session.reranking}>
              <HeroPick
                pick={hero}
                assessment={assessment}
                rows={rows}
                gallons={Number(result.snapshot.query.gallons ?? prefs.gallons)}
                navApp={prefs.navApp}
                trade={tradeoff(hero, cards)}
                tripMode={prefs.tripMode}
              />
            </div>
          ) : result && assessment ? (
            <EmptyState
              reasons={assessment.reasons.map((reason) => t(reason.key, reason.vars))}
              canWiden={!prefs.allowUnknownPayment}
              onWiden={() => update({ allowUnknownPayment: true })}
              onSettings={onSettings}
            />
          ) : null}
        </div>

        {(phase === 'ready' || phase === 'locating') && result ? (
          <div className="flex flex-col gap-4">
            <Leaderboards result={result} primary={primary} navApp={prefs.navApp} tripMode={prefs.tripMode} />
            <StationList rows={rows} navApp={prefs.navApp} tripMode={prefs.tripMode} />
            <NearbyStations allowUnknownPayment={prefs.allowUnknownPayment} onUnknownPayment={(value) => update({ allowUnknownPayment: value })} result={result} navApp={prefs.navApp} onExpandRoutes={() => void session.expandRoutes()} />
            <footer className="px-1 text-[12px] leading-relaxed text-faint">
              <p>
                {t('decide.sources', {
                  sources: sources.length ? sources.map((s) => sourceLabel(s.source)).join(', ') : t('decide.noSource'),
                  age: age(result.snapshot.collected_at, t),
                })}
                {assessment ? ` ${t('decide.coverage', { usable: assessment.usable, total: assessment.total })}` : ''}
              </p>
              {result.snapshot.source_statuses.filter(s=>s.status==='unavailable').map(s=><p key={s.source} className="text-caution">{t('cache.sourceUnavailable',{source:sourceLabel(s.source)})}</p>)}
              {result.snapshot.warnings?.some(w => w.startsWith('AAA regional average unavailable')) ? <p className="text-caution">{t('cache.sourceUnavailable',{source:'AAA'})}</p> : null}
              <p className="mt-1">{t('cache.policy')}</p>
              {result.cache_hits ? <p>{t('cache.reused', { count: result.cache_hits })}</p> : null}
              <p className="mt-1">{t('decide.rerankNote')}</p>
            </footer>
          </div>
        ) : null}
      </div>

      <Sheet open={locationOpen} title={t('location.change')} onClose={() => setLocationOpen(false)}>
        <LocationSearch onChoose={(location, label) => { setLocationLabel(label); setLocationOpen(false); void start({ override: location }) }} />
      </Sheet>
    </div>
  )
}
