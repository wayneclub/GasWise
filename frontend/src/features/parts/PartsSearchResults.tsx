import type { PartsSearchResult } from '../../api/types'
import { useI18n } from '../../i18n'
import { safeProductLink } from '../../lib/partsLinks'

interface PartsSearchResultsProps {
  result: PartsSearchResult
  checkedName: string
}

export function PartsSearchResults({ result, checkedName }: PartsSearchResultsProps) {
  const { t } = useI18n()
  const compatibleCount = result.items.filter((item) => item.status === 'compatible').length

  return (
    <section aria-live="polite" className="mt-5 space-y-4">
      <div className="rounded-box border border-line bg-surface p-5">
        <h2 className="font-semibold">
          {t('parts.searchSummary', { verified: compatibleCount, count: result.items.length })}
        </h2>
        <p className="mt-2 text-sm text-muted">{t('parts.resultVehicle', { name: checkedName })}</p>
        <p className="mt-2 text-xs text-muted">{t('parts.bounded')}</p>
      </div>

      {!result.items.length ? (
        <p className="rounded-control bg-caution-soft p-4 text-sm text-caution">
          {t(
            result.source_status === 'unavailable' || result.source_status === 'not_configured'
              ? 'parts.sourceUnavailable'
              : 'parts.emptySearch',
          )}
        </p>
      ) : null}

      {result.items.map((item) => (
        <article key={item.product_url} className="rounded-box border border-line bg-surface p-5">
          <p className={`text-sm font-semibold ${item.status === 'compatible' ? 'text-accent' : 'text-caution'}`}>
            {t(`parts.${item.status}`)}
          </p>
          <h3 className="mt-2 text-base font-medium">{item.name}</h3>
          <p className="mt-1 text-sm text-muted">
            {item.brand} · {item.part_number}
          </p>
          <details className="mt-3 text-xs leading-relaxed text-muted">
            <summary className="cursor-pointer">AutoZone · {t('parts.evidence')}</summary>
            <p className="mt-2">{item.evidence.detail}</p>
            {(item.evidence.conditions ?? []).map((c) => (
              <p key={c}>{c}</p>
            ))}
          </details>
          {safeProductLink(item.product_url) ? (
            <a
              className="mt-3 inline-block text-sm underline"
              href={safeProductLink(item.product_url)!}
              target="_blank"
              rel="noreferrer"
            >
              {t('parts.openProduct')}
            </a>
          ) : null}
        </article>
      ))}
    </section>
  )
}
