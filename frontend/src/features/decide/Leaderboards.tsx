import { CopyAddress } from '../../components/CopyAddress'
import {googleStationUrl} from '../../lib/stationLinks'
import { StationSources } from './SourcePill'
import {useState} from 'react'
import type {RankedStation, SmartResult, StrategyKey} from '../../api/types'
import {Segmented} from '../../components/ui'
import {useI18n} from '../../i18n'
import {age, comparisonPrice, minutes, perGallon, usd} from '../../lib/format'
import type {NavApp} from '../../lib/prefs'
import {StationDetails, StationRating, TopTierBadge} from './StationDetails'
import {RegionalPrice} from './RegionalPrice'

export function Leaderboards({result, primary, onStrategyChange, navApp, tripMode}: {result:SmartResult; primary:StrategyKey; onStrategyChange?:(strategy:StrategyKey)=>void; navApp:NavApp; tripMode:'round_trip'|'on_route'}) {
  const {t} = useI18n()
  const [category,setCategory] = useState<StrategyKey|null>(null)
  const [selected,setSelected] = useState<RankedStation|null>(null)
  const current = onStrategyChange ? primary : category ?? primary
  const rows = result.ranking?.leaderboards?.[current] ?? []
  return <section className="min-w-0 rounded-box bg-surface p-4 sm:p-5" aria-label={t('board.title')}>
    <h2 className="mb-3 text-sm font-semibold">{t('board.title')}</h2>
    <Segmented label={t('board.title')} value={current} options={[
      {value:'cheapest_overall',label:t('board.money')},
      {value:'best_value',label:t('board.balanced')},
      {value:'fastest_stop',label:t('board.time')},
    ]} onChange={onStrategyChange ?? setCategory}/>
    {current==='best_value' ? <p className="mt-2 text-xs text-muted">{t('board.costGuide')}<span className="mt-1 block">{t('board.value')} · ${result.snapshot.query.time_value_per_hour ?? '15'}</span></p> : null}
    <ol className="mt-3 divide-y divide-line">
      {rows.map((row,index) => <li key={row.price_comparison?.station_key ?? row.station.id} className="grid min-w-0 grid-cols-[1.75rem_minmax(0,1fr)] items-start gap-3 py-3">
        <span className={`num flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${index===0?'bg-accent-soft text-accent':'bg-sunken text-muted'}`}>{index+1}</span>
        <div className="min-w-0">
          <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-2">
            <div className="flex min-w-0 flex-wrap items-center gap-1.5"><a href={googleStationUrl(row.station)} target="_blank" rel="noreferrer" className="text-left text-sm font-semibold underline decoration-line underline-offset-4">{row.station.name}</a><button type="button" className="text-xs text-muted underline" onClick={()=>setSelected(row)}>{t('station.view')}</button>{row.station.top_tier_brand ? <TopTierBadge brand={row.station.top_tier_brand}/> : null}</div>
            <div className="num text-right text-sm"><p className="font-semibold">{current==='fastest_stop' ? minutes(row.extra_travel_minutes,t) : usd(current==='best_value' ? row.price_comparison?.comparable_cost_max ?? row.generalized_trip_cost : row.actual_fuel_cost)}</p><p className="mt-0.5 max-w-32 text-[10px] leading-snug text-muted">{t(current==='best_value' ? 'board.withTime' : current==='fastest_stop' ? 'board.driveTime' : 'board.fuelCost')}</p><p className="mt-1 text-[11px] text-muted">{perGallon(comparisonPrice(row.station))}/gal</p></div>
          </div>
          <CopyAddress address={row.station.address} display={row.station.address?.split(',')[0]} className="w-full text-[11px] text-muted" />
          <StationRating station={row.station}/>
          <div className="mt-1 flex flex-wrap items-center gap-2"><StationSources source={row.station.source} row={row}/><span className="text-xs text-muted">{t(tripMode==='round_trip'?'pick.roundTrip':'route.extraTime',{time:minutes(row.extra_travel_minutes,t)})} · {t('age.updated',{age:age(row.station.price_updated_at,t)})}</span></div>
          <RegionalPrice row={row}/>
          {row.route.source==='straight_line_estimate'?<p className="mt-1 text-[11px] text-caution">{t('coverage.estimated_route')}</p>:null}
        </div>
      </li>)}
    </ol>
    {!rows.length?<p className="mt-3 text-xs text-muted">{t('board.none')}</p>:null}
    {rows.find(r=>r.regional_benchmark)?.regional_benchmark ? (()=>{
      const benchmark = rows.find(r=>r.regional_benchmark)!.regional_benchmark!
      return <details className="mt-2 border-t border-line pt-2 text-[11px] text-faint"><summary className="cursor-pointer">{t('board.date',{scope:t(benchmark.scope==='metro'?'board.metro':'board.state'),date:benchmark.price_as_of})} · ${Number(benchmark.price_per_gallon).toFixed(2)}/gal</summary><p>{t('board.context')}</p><a href={benchmark.source_url} target="_blank" rel="noreferrer" className="underline">AAA · {benchmark.region}</a></details>
    })() : null}
    {selected?<StationDetails station={selected.station} row={selected} open onClose={()=>setSelected(null)} navApp={navApp} tripMode={tripMode}/>:null}
  </section>
}
