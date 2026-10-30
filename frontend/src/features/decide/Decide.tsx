import { CaretDownIcon, GasPumpIcon } from '@phosphor-icons/react'
import { SourcePill } from './SourcePill'
import { SharedCacheStatus } from './SharedCacheStatus'
import { SearchContext } from './SearchContext'
import { useEffect, useRef, useState } from 'react'
import { Segmented, Stepper } from '../../components/ui'
import { Select } from '../../components/Select'
import { type MessageKey, useI18n } from '../../i18n'
import { age, fuelKey, gallons, sourceLabel } from '../../lib/format'
import { effectiveFuel, type Prefs } from '../../lib/prefs'
import { assess, PRIORITY_STRATEGY, picks, tradeoff } from '../../lib/recommend'
import { messageId } from '../../lib/errorMessages'
import { useFuelSession } from '../../lib/session'
import { LocationSearch } from '../setup/LocationSearch'
import { calculateArbitrage, estimateDistanceMiles, loadLifeZones, saveLifeZone, type ArbitrageOpportunity } from '../../lib/lifeZones'
import { HeroPick } from './PickCards'
import { ErrorState, PickSkeleton } from './States'
import { SearchFallback } from './SearchFallback'
import { NearbyStations } from './NearbyStations'
import { StationList } from './StationList'
import { Leaderboards } from './Leaderboards'

const DOWNTOWN_LA = { lat: 34.0522, lng: -118.2437 }

export function Decide({ prefs, update, onSettings, active = true }: { active?: boolean; prefs: Prefs; update: (change: Partial<Prefs>) => void; onSettings: () => void }) {
  const { t } = useI18n()
  const session = useFuelSession(prefs, active)
  const [fillOpen, setFillOpen] = useState(false)
  const [locationOpen, setLocationOpen] = useState(false)
  const [arbitrage, setArbitrage] = useState<ArbitrageOpportunity | null>(null)
  const { start } = session
  const started = useRef(!!session.origin)

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

  // Observe and evaluate life-zones arbitrage opportunity
  useEffect(() => {
    if (!result || !session.origin) return
    let active = true
    void (async () => {
      const zones = await loadLifeZones()
      if (!zones.length || !active) return
      const topStation = result.ranking?.results?.[0]?.station
      const bestPriceStr = topStation?.comparison_price_per_gallon ?? topStation?.price_per_gallon
      const bestPrice = bestPriceStr ? Number(bestPriceStr) : undefined
      if (bestPrice && session.origin) {
        const match = zones.find(z => estimateDistanceMiles(z.origin, session.origin!) < 3.0)
        if (match && match.lastObservedPrice !== bestPrice) {
          await saveLifeZone({ ...match, lastObservedPrice: bestPrice })
        }
      }
      const home = zones.find(z => z.kind === 'home')
      const work = zones.find(z => z.kind === 'work')
      if (home && work && active) {
        const mpg = Number(prefs.vehicle?.combinedMpg ?? prefs.mpg ?? 25)
        const opp = calculateArbitrage(home, work, prefs.gallons, mpg)
        setArbitrage(opp && opp.isBeneficial ? opp : null)
      }
    })()
    return () => { active = false }
  }, [result, session.origin, prefs.gallons, prefs.mpg, prefs.vehicle])
  const primary = PRIORITY_STRATEGY[prefs.preference]
  const cards = result ? picks(result, primary) : []
  const assessment = result ? assess(result, primary) : null
  const [hero] = cards
  const rows = result?.ranking?.results ?? []
  const sources = result?.snapshot.source_statuses.filter((s) => s.status === 'ok') ?? []

  return (
    <div className="mx-auto w-full max-w-md px-4 pb-12 sm:max-w-2xl sm:px-6 lg:max-w-5xl">
      {!session.origin ? <div className="experience-intro pt-7 pb-2">
        <span className="mb-3 grid size-12 place-items-center rounded-2xl bg-accent-soft text-accent"><GasPumpIcon size={26} weight="duotone" /></span>
        <h1 className="text-3xl font-semibold tracking-tight">{t('experience.locationTitle')}</h1>
      </div> : null}
      {hero ? <h1 className="sr-only">{t('experience.ready')}</h1> : null}
      <SearchContext prefs={prefs} label={session.originLabel} source={session.originKind} permission={session.locationPermission} locating={phase === 'locating'} searching={phase === 'searching'} refreshing={session.refreshing}
        onLocate={() => void start({ userInitiated: true })} onChange={() => setLocationOpen(open => !open)} onSettings={onSettings} onRefresh={() => void session.refresh()}>
        {locationOpen || !session.origin ? <>
          {error?.kind === 'location' && !['prompt', 'permission_pending'].includes(error.code) ? <div role="status" className="mb-3"><h3 className="text-sm font-semibold">{t(`error.${messageId(error)}.title` as MessageKey)}</h3><p className="mt-1 text-sm text-muted">{t(`error.${messageId(error)}.body` as MessageKey)}</p></div> : null}
          <LocationSearch onChoose={(location, label) => { setLocationOpen(false); void start({ override: location, label }) }} />
        </> : null}
      </SearchContext>

      {arbitrage && arbitrage.isBeneficial ? (
        <div className="mb-4 rounded-control border border-accent/40 bg-accent-soft/30 p-3.5 flex items-start gap-3 text-sm">
          <span className="text-xl shrink-0" aria-hidden="true">💡</span>
          <div className="flex-1 min-w-0">
            <span className="font-semibold text-accent block text-sm">{t('lifezones.arbitrageTitle')}</span>
            <p className="text-xs text-ink mt-0.5 leading-relaxed">
              {t('lifezones.arbitrageHint', {
                zone: arbitrage.toZone.name,
                diff: `$${arbitrage.priceDiff.toFixed(2)}`,
                detour: arbitrage.detourMiles.toString(),
                amount: `$${arbitrage.netSavings.toFixed(2)}`,
              })}
            </p>
          </div>
        </div>
      ) : null}

      <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] lg:items-start lg:gap-8">
        <div className="flex flex-col gap-4">
          <section aria-label={t('decide.yourFill')} className="fill-panel rounded-box border border-line bg-surface">
            {hero ? <button type="button" aria-expanded={fillOpen} aria-controls="fill-controls" onClick={() => setFillOpen(!fillOpen)} className="flex min-h-14 w-full items-center gap-3 rounded-box px-4 py-3 text-left focus-visible:outline-accent">
              <GasPumpIcon size={20} className="shrink-0 text-accent" />
              <span className="min-w-0 flex-1"><span className="block text-xs text-muted">{t('decide.yourFill')}</span><span className="block text-sm font-medium">{t(fuelKey(effectiveFuel(prefs)))} · {gallons(prefs.gallons,t)} · {t(prefs.payment === 'cash_or_credit' ? 'prefs.all' : prefs.payment === 'cash' ? 'prefs.cash' : 'prefs.card')}</span></span>
              <span className="sr-only">{t('experience.editFill')}</span><CaretDownIcon size={16} className={`shrink-0 text-muted transition ${fillOpen ? 'rotate-180' : ''}`} />
            </button> : null}
            <div id="fill-controls" hidden={!!hero && !fillOpen} className={`p-4 ${hero ? 'border-t border-line' : ''}`}>
            <div className="grid grid-cols-1 items-center min-[420px]:grid-cols-[4.5rem_minmax(0,1fr)] gap-x-3 gap-y-3">
              <h2 className="text-sm font-semibold">{t('decide.yourFill')}</h2>
              <Stepper label={t('ui.gallons')} value={prefs.gallons} min={1} max={30} step={1} format={(value)=>gallons(value,t)} onChange={(gallons)=>update({gallons})} className="w-full" />
              <span className="text-xs font-medium text-muted">{t('prefs.payment')}</span>
              <Segmented label={t('prefs.payment')} value={prefs.payment} options={[{value:'cash_or_credit',label:t('prefs.all')},{value:'cash',label:t('prefs.cash')},{value:'credit',label:t('prefs.card')}]} onChange={(payment) => update({payment})} />

            </div>
            <details className="mt-4 border-t border-line pt-3 text-xs text-muted">
              <summary className="cursor-pointer py-1">{t('board.radius')} {prefs.searchRadiusMiles ?? 5} mi · {t('fill.timeValue')} ${prefs.timeValuePerHour ?? 15}/h</summary>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <div className="flex min-w-0 flex-col gap-1.5"><span>{t('board.radius')}</span>
                  <Select label={t('board.radius')} value={String(prefs.searchRadiusMiles ?? 5)} onChange={value=>update({searchRadiusMiles:Number(value)})}
                    options={[2,5,10,20].map(value=>({value:String(value),label:`${value} mi`}))} />
                </div>
                <label className="flex flex-col gap-1.5">{t('board.value')}
                  <input type="number" min={0} max={500} step={5} aria-label={t('board.value')} value={prefs.timeValuePerHour ?? 15} onChange={e=>update({timeValuePerHour:Math.min(500,Math.max(0,Number(e.target.value)))})} className="num h-11 min-w-0 rounded-control border border-line bg-surface px-3 text-ink" />
                </label>
              </div>
            </details>
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
            null
          ) : phase === 'error' && error ? (
            <ErrorState
              key={error.at}
              error={error}
              onRetry={() => void session.refresh()}
              onLocate={() => void start({ userInitiated: true })}
              onChooseLocation={(location, label) => { void start({ override: location, label }) }}
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
          ) : null}
          {result && phase === 'ready' ? <SearchFallback result={result} completing={session.completing} radius={prefs.searchRadiusMiles ?? 5} navApp={prefs.navApp} onRadius={searchRadiusMiles => update({ searchRadiusMiles })} onRetry={() => void session.refresh()} /> : null}
        </div>

        {(phase === 'ready' || phase === 'locating') && result ? (
          <div className="contents">
            <div className="min-w-0">
            <Leaderboards result={result} primary={primary} onStrategyChange={strategy=>update({preference:strategy==='cheapest_overall'?'money':strategy==='fastest_stop'?'time':'balanced'})} navApp={prefs.navApp} tripMode={prefs.tripMode} />
            </div>
            <div className="min-w-0 lg:col-span-2">
            <StationList rows={rows} navApp={prefs.navApp} tripMode={prefs.tripMode} />
            </div>
            <div className="flex min-w-0 flex-col gap-4 lg:col-span-2">
            <NearbyStations allowUnknownPayment={prefs.allowUnknownPayment} onUnknownPayment={(value) => update({ allowUnknownPayment: value })} result={result} navApp={prefs.navApp} onExpandRoutes={() => void session.expandRoutes()} />
            <footer className="px-1 text-[12px] leading-relaxed text-faint"><div className="mb-2 flex flex-wrap items-center gap-2">{result.snapshot.source_statuses.map(s=><SourcePill key={s.source} source={s.source} unavailable={s.status!=='ok'}/>)}<span>{age(result.snapshot.collected_at,t)}</span></div><details><summary className="cursor-pointer">{t('coverage.why')}</summary>
              <p>
                {t('decide.sources', {
                  sources: sources.length ? sources.map((s) => sourceLabel(s.source)).join(', ') : t('decide.noSource'),
                  age: age(result.snapshot.collected_at, t),
                })}
                {assessment ? ` ${t('decide.coverage', { usable: assessment.usable, total: assessment.total })}` : ''}
              </p>
              {result.snapshot.source_statuses.filter(s=>s.status==='unavailable').map(s=><p key={s.source} className="text-caution">{t('cache.sourceUnavailable',{source:sourceLabel(s.source)})}</p>)}
              {result.snapshot.warnings?.some(w => w.startsWith('AAA regional average unavailable')) ? <p className="text-caution">{t('cache.sourceUnavailable',{source:'AAA'})}</p> : null}
              <SharedCacheStatus caches={result.snapshot.source_cache}/>
              <p className="mt-1">{t('cache.policy')}</p>
              {result.cache_hits ? <p>{t('cache.reused', { count: result.cache_hits })}</p> : null}
            </details></footer>
            </div>
          </div>
        ) : null}
      </div>


    </div>
  )
}
