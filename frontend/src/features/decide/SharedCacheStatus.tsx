import type { SmartSnapshot } from '../../api/types'
import { useI18n } from '../../i18n'
import { age, sourceLabel } from '../../lib/format'

const SOURCE = { maps: 'google_maps_web', gasbuddy: 'gasbuddy_web', waze: 'waze' } as Record<string, string>

export function SharedCacheStatus({ caches }: { caches: SmartSnapshot['source_cache'] }) {
  const { t } = useI18n()
  return <>{Object.entries(caches ?? {}).map(([source, cache]) => <p key={source} className={cache.state === 'stale' ? 'text-caution' : ''}>
    {t(cache.state === 'stale' ? 'cache.sharedStale' : 'cache.sharedFresh', {
      source: sourceLabel(SOURCE[source] ?? source), age: age(cache.checked_at, t),
    })}
  </p>)}</>
}
