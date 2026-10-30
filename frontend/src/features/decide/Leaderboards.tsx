import { CopyAddress } from '../../components/CopyAddress'
import { FavoriteButton } from '../../components/FavoriteButton'
import { CaretDownIcon, CaretRightIcon, InfoIcon, NavigationArrowIcon } from '@phosphor-icons/react'
import {googleStationUrl} from '../../lib/stationLinks'
import { StationSources } from './SourcePill'
import {useState} from 'react'
import type {RankedStation, SmartResult, StrategyKey} from '../../api/types'
import {Segmented} from '../../components/ui'
import {useI18n} from '../../i18n'
import {age, comparisonPrice, minutes, perGallon, usd} from '../../lib/format'
import {navigationUrl} from '../../lib/navigation'
import type {NavApp} from '../../lib/prefs'
import {StationDetails, StationRating, TopTierBadge} from './StationDetails'
import {RegionalPrice} from './RegionalPrice'

export function Leaderboards({result, primary, onStrategyChange, navApp, tripMode}: {result:SmartResult; primary:StrategyKey; onStrategyChange?:(strategy:StrategyKey)=>void; navApp:NavApp; tripMode:'round_trip'|'on_route'}) {
  const {t} = useI18n()
  const [category,setCategory] = useState<StrategyKey|null>(null)
  const [selected,setSelected] = useState<RankedStation|null>(null)
  const current = onStrategyChange ? primary : category ?? primary
  const rows = result.ranking?.leaderboards?.[current] ?? []
  return <section className="min-w-0 rounded-box border border-line bg-surface p-4 sm:p-5" aria-label={t('board.title')}>
    <h2 className="mb-3 text-sm font-semibold">{t('board.title')}</h2>
    <Segmented label={t('board.title')} value={current} options={[
      {value:'cheapest_overall',label:t('board.money')},
      {value:'best_value',label:t('board.balanced')},
      {value:'fastest_stop',label:t('board.time')},
    ]} onChange={onStrategyChange ?? setCategory}/>
    {current==='best_value' ? <details className="group mt-2 text-xs text-muted"><summary className="flex min-h-11 cursor-pointer list-none items-center gap-1.5"><InfoIcon size={15} aria-hidden="true" className="shrink-0" /><span>{t('fill.timeValue')} · ${result.snapshot.query.time_value_per_hour ?? '15'}/h</span><CaretDownIcon size={14} aria-hidden="true" className="ml-auto shrink-0 group-open:rotate-180" /></summary><p className="pb-2">{t('board.costGuide')}</p></details> : null}
    <ol className="mt-4 flex flex-col gap-3">
      {rows.map((row,index) => {
        const station = row.station
        const isFirst = index === 0
        return (
          <li
            key={row.price_comparison?.station_key ?? station.id}
            className={`rounded-control border p-3.5 sm:p-4 transition-all duration-200 ${
              isFirst
                ? 'border-accent/40 bg-accent-soft/25 ring-1 ring-accent/15'
                : 'border-line bg-canvas/35 hover:bg-canvas/60'
            }`}
          >
            {/* Header: Rank + Station Name + Badges | Price Summary */}
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2">
                <span
                  className={`num flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                    isFirst
                      ? 'bg-accent text-surface shadow-2xs'
                      : 'bg-sunken text-muted'
                  }`}
                >
                  {index + 1}
                </span>
                <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                  <a
                    href={googleStationUrl(station)}
                    target="_blank"
                    rel="noreferrer"
                    className="truncate text-[15px] sm:text-base font-bold text-ink underline decoration-line underline-offset-4 hover:text-accent hover:decoration-accent transition"
                  >
                    {station.name}
                  </a>
                  {station.top_tier_brand ? <TopTierBadge brand={station.top_tier_brand} /> : null}
                  {station.id ? <FavoriteButton station={station} size={15} className="!size-7 shrink-0 text-muted" /> : null}
                </div>
              </div>

              <div className="num shrink-0 text-right">
                <p className="text-[15px] sm:text-base font-bold text-ink">
                  {current === 'fastest_stop'
                    ? minutes(row.extra_travel_minutes, t)
                    : usd(
                        current === 'best_value'
                          ? row.price_comparison?.comparable_cost_max ?? row.generalized_trip_cost
                          : row.actual_fuel_cost
                      )}
                </p>
                <p className="text-[10px] font-medium text-muted">
                  {t(
                    current === 'best_value'
                      ? 'board.withTime'
                      : current === 'fastest_stop'
                      ? 'board.driveTime'
                      : 'board.fuelCost'
                  )}
                </p>
                <p className="mt-0.5 text-[11px] font-medium text-muted">
                  {perGallon(comparisonPrice(station))}/gal
                </p>
              </div>
            </div>

            {/* Middle Details: Address, Rating, Travel & Sources, Regional Benchmark */}
            <div className="mt-2.5 flex flex-col gap-1 pl-8">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
                <CopyAddress
                  address={station.address}
                  display={station.address?.split(',')[0]}
                  className="text-xs text-muted"
                />
                <StationRating station={station} />
              </div>

              <div className="mt-0.5 flex flex-wrap items-center gap-2">
                <StationSources source={station.source} row={row} />
                <span className="text-xs text-muted">
                  {t(tripMode === 'round_trip' ? 'pick.roundTrip' : 'route.extraTime', {
                    time: minutes(row.extra_travel_minutes, t),
                  })}{' '}
                  · {t('age.updated', { age: age(station.price_updated_at, t) })}
                </span>
              </div>

              <RegionalPrice row={row} />
              {row.route.source === 'straight_line_estimate' ? (
                <p className="text-[11px] text-caution">{t('coverage.estimated_route')}</p>
              ) : null}
            </div>

            {/* Action Bar: View Details + Navigate */}
            <div className="mt-3.5 flex items-center gap-2 border-t border-line/60 pt-3">
              <button
                type="button"
                onClick={() => setSelected(row)}
                aria-label={`${t('station.view')} ${station.name}`}
                className="inline-flex min-h-10 flex-1 items-center justify-center gap-1.5 rounded-control border border-line bg-surface px-3 py-2 text-xs font-semibold text-ink shadow-2xs hover:bg-sunken hover:border-line-strong active:scale-[0.98] transition focus-visible:ring-2 focus-visible:ring-accent"
              >
                <span>{t('station.view')}</span>
                <CaretRightIcon size={14} className="text-muted" aria-hidden="true" />
              </button>
              <a
                href={navigationUrl(navApp, station.location.lat, station.location.lng)}
                target="_blank"
                rel="noreferrer"
                aria-label={`${t('pick.navigate')} ${station.name}`}
                className="inline-flex min-h-10 flex-1 items-center justify-center gap-1.5 rounded-control bg-ink px-3 py-2 text-xs font-semibold text-surface shadow-2xs hover:opacity-90 active:scale-[0.98] transition focus-visible:ring-2 focus-visible:ring-accent"
              >
                <NavigationArrowIcon size={14} weight="fill" aria-hidden="true" />
                <span>{t('pick.navigate')}</span>
              </a>
            </div>
          </li>
        )
      })}
    </ol>
    {!rows.length?<p className="mt-3 text-xs text-muted">{t('board.none')}</p>:null}
    {rows.find(r=>r.regional_benchmark)?.regional_benchmark ? (()=>{
      const benchmark = rows.find(r=>r.regional_benchmark)!.regional_benchmark!
      return <details className="mt-2 border-t border-line pt-2 text-[11px] text-faint"><summary className="cursor-pointer">{t('board.date',{scope:t(benchmark.scope==='metro'?'board.metro':'board.state'),date:benchmark.price_as_of})} · ${Number(benchmark.price_per_gallon).toFixed(2)}/gal</summary><p>{t('board.context')}</p><a href={benchmark.source_url} target="_blank" rel="noreferrer" className="underline">AAA · {benchmark.region}</a></details>
    })() : null}
    {selected?<StationDetails station={selected.station} row={selected} open onClose={()=>setSelected(null)} navApp={navApp} tripMode={tripMode}/>:null}
  </section>
}
