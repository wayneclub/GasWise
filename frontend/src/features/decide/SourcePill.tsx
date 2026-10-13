import {stationSourceUrl} from '../../lib/stationLinks'
import type {RankedStation} from '../../api/types'
import {useI18n} from '../../i18n'
import {sourceLabel} from '../../lib/format'

/** Quote provenance, never inferred from the station rating provider. */
export function SourcePill({source,unavailable=false,href}:{source:string;unavailable?:boolean;href?:string}) {
  const {t}=useI18n()
  const label=sourceLabel(source) || t('decide.noSource')
  const description=t(unavailable?'cache.sourceUnavailable':'station.source',{source:label})
  const Tag=href ? 'a' : 'span'
  return <Tag href={href} target={href ? '_blank' : undefined} rel={href ? 'noreferrer' : undefined} title={description} aria-label={description} className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 text-[10px] font-medium ${unavailable?'border-caution/20 bg-caution-soft text-caution':'border-line bg-sunken/60 text-muted'}`}><span aria-hidden="true" className={`size-1.5 rounded-full ${unavailable?'bg-caution':'bg-accent'}`}/>{label}{unavailable?' !':''}</Tag>
}

/** Show the selected quote and every source actually referenced for this station. */
export function StationSources({source,row,selectedOnly=false}:{source:string;row?:RankedStation|null;selectedOnly?:boolean}) {
  const {t}=useI18n()
  const sources=[...new Set([source,...(selectedOnly ? [] : row?.price_comparison?.evidence.map(e=>e.source) ?? [])].filter(Boolean))]
  return <span className="inline-flex flex-wrap items-center gap-1.5">{sources.map(value=><span key={value} title={t(value===source?'station.selectedSource':'station.referenceSource',{source:sourceLabel(value)})}><SourcePill source={value} href={row ? stationSourceUrl(value,value===source ? row.station.id : row.price_comparison?.evidence.find(e=>e.source===value)?.provider_station_id ?? '',row.station) : undefined}/>{value===source && sources.length>1 ? <span className="ml-1 text-[10px] text-muted">{t('station.selectedQuote')}</span> : null}</span>)}</span>
}
