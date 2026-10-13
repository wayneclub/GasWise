import { SourcePill } from './SourcePill'
import {useState} from 'react'
import type {RankedStation, SmartResult, StrategyKey} from '../../api/types'
import {Segmented} from '../../components/ui'
import {useI18n} from '../../i18n'
import {age, comparisonPrice, minutes, perGallon, usd} from '../../lib/format'
import type {NavApp} from '../../lib/prefs'
import {StationDetails, StationRating, TopTierBadge} from './StationDetails'
import {RegionalPrice} from './RegionalPrice'

export function Leaderboards({result, primary, navApp, tripMode}: {result:SmartResult; primary:StrategyKey; navApp:NavApp; tripMode:'round_trip'|'on_route'}) {
  const {t} = useI18n()
  const [category,setCategory] = useState<StrategyKey|null>(null)
  const [selected,setSelected] = useState<RankedStation|null>(null)
  const current = category ?? primary
  const rows = result.ranking?.leaderboards?.[current] ?? []
  return <section className="min-w-0 rounded-box border border-line bg-surface p-4 shadow-raised" aria-label={t('board.title')}>
    <h2 className="mb-3 text-sm font-semibold">{t('board.title')}</h2>
    <Segmented label={t('board.title')} value={current} options={[
      {value:'cheapest_overall',label:t('board.money')},
      {value:'best_value',label:t('board.balanced')},
      {value:'fastest_stop',label:t('board.time')},
    ]} onChange={setCategory}/>
    {current==='best_value' ? <p className="mt-2 text-xs text-muted">{t('board.value')} · ${result.snapshot.query.time_value_per_hour ?? '15'}</p> : null}
    <ol className="mt-3 divide-y divide-line">
      {rows.map((row,index) => <li key={row.price_comparison?.station_key ?? row.station.id} className="grid min-w-0 grid-cols-[1.75rem_minmax(0,1fr)] items-start gap-3 py-3">
        <span className={`num flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${index===0?'bg-accent-soft text-accent':'bg-sunken text-muted'}`}>{index+1}</span>
        <div className="min-w-0">
          <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-2">
            <div className="flex min-w-0 flex-wrap items-center gap-1.5"><button type="button" className="text-left text-sm font-semibold underline decoration-line underline-offset-4" onClick={()=>setSelected(row)}>{row.station.name}</button>{row.station.top_tier_brand ? <TopTierBadge brand={row.station.top_tier_brand}/> : null}</div>
            <div className="num text-right text-sm"><p className="font-semibold">{usd(row.actual_fuel_cost)}</p><p className="mt-1 text-[11px] text-muted">{perGallon(comparisonPrice(row.station))}/gal</p></div>
          </div>
          {row.station.address ? <p className="mt-0.5 truncate text-[11px] text-muted" title={row.station.address}>{row.station.address.split(',')[0]}</p> : null}
          <StationRating station={row.station}/>
          <div className="mt-1 flex flex-wrap items-center gap-2"><SourcePill source={row.station.source}/><span className="text-xs text-muted">{minutes(row.extra_travel_minutes,t)} · {age(row.station.price_updated_at,t)}</span></div>
          <RegionalPrice row={row}/>
          {current==='best_value'?<p className="num mt-1 text-[10px] text-muted">{t('board.score')} {usd(row.price_comparison?.comparable_cost_max ?? row.generalized_trip_cost)}</p>:null}
        </div>
      </li>)}
    </ol>
    {!rows.length?<p className="mt-3 text-xs text-muted">{t('board.none')}</p>:null}
    {rows.some(r=>r.regional_benchmark)?<p className="mt-2 border-t border-line pt-2 text-[10px] text-faint">{t('board.context')}</p>:null}
    {selected?<StationDetails station={selected.station} row={selected} open onClose={()=>setSelected(null)} navApp={navApp} tripMode={tripMode}/>:null}
  </section>
}
