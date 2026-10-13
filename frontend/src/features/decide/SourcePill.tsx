import {useI18n} from '../../i18n'
import {sourceLabel} from '../../lib/format'

/** Quote provenance, never inferred from the station rating provider. */
export function SourcePill({source,unavailable=false}:{source:string;unavailable?:boolean}) {
  const {t}=useI18n()
  const label=sourceLabel(source) || t('decide.noSource')
  const description=t(unavailable?'cache.sourceUnavailable':'station.source',{source:label})
  return <span title={description} aria-label={description} className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 text-[10px] font-medium ${unavailable?'border-caution/20 bg-caution-soft text-caution':'border-line bg-sunken/60 text-muted'}`}><span aria-hidden="true" className={`size-1.5 rounded-full ${unavailable?'bg-caution':'bg-accent'}`}/>{label}{unavailable?' !':''}</span>
}
