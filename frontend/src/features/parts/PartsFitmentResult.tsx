import type { PartsResult } from '../../api/types'
import { useI18n } from '../../i18n'
import { safeProductLink } from '../../lib/partsLinks'

interface PartsFitmentResultProps {
  result: PartsResult
  checkedName: string
  replacements: Record<string, string>[]
}

export function PartsFitmentResult({
  result,
  checkedName,
  replacements,
}: PartsFitmentResultProps) {
  const { t } = useI18n()

  return (
    <section aria-live="polite" className="mt-5 flex flex-col gap-4">
      {/* Fitment Banner */}
      <div
        className={`rounded-box border border-line p-5 ${
          result.fitment_confirmed ? 'bg-accent-soft' : 'bg-caution-soft'
        }`}
      >
        <h2 className="text-xl font-semibold">{t(`parts.${result.status}`)}</h2>
        <p className="mt-2 font-medium">
          {result.title ?? [result.brand, result.part_number].filter(Boolean).join(' ')}
        </p>
        <p className="mt-2 text-sm text-muted">{t('parts.resultVehicle', { name: checkedName })}</p>
        {safeProductLink(result.amazon_url) ? (
          <a
            href={safeProductLink(result.amazon_url)!}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-block text-sm underline"
          >
            {t('parts.openProduct')}
          </a>
        ) : null}
      </div>

      {/* Cross-Check Evidence */}
      <div className="rounded-box border border-line bg-surface p-5">
        <h3 className="font-semibold">{t('parts.evidence')}</h3>
        {(result.evidence ?? []).map((e, index) => (
          <details key={`${e.source}:${index}`} className="border-b border-line py-3 last:border-0">
            <summary className="cursor-pointer text-sm">
              <span className="font-medium">
                {e.source === 'autozone'
                  ? 'AutoZone'
                  : e.source === 'oreilly'
                    ? "O’Reilly"
                    : e.source === 'amazon'
                      ? 'Amazon'
                      : 'Manufacturer'}
              </span>{' '}
              · {t(e.status === 'incompatible' ? 'parts.incompatible' : `parts.${e.status}`)}
            </summary>
            <div className="mt-2 space-y-2 text-xs leading-relaxed text-muted">
              <p>{[e.brand, e.part_number].filter(Boolean).join(' ')}</p>
              <p>{e.detail}</p>
              {(e.conditions ?? []).map((condition) => (
                <p key={condition}>{condition}</p>
              ))}
              {safeProductLink(e.source_url) ? (
                <a
                  href={safeProductLink(e.source_url)!}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-block underline"
                >
                  {t('parts.openProduct')}
                </a>
              ) : null}
            </div>
          </details>
        ))}
      </div>

      {/* Alternative Recommendations */}
      <div className="rounded-box border border-line bg-surface p-5">
        <h3 className="font-semibold">{t('parts.alternatives')}</h3>
        <p className="mt-2 text-xs leading-relaxed text-muted">{t('parts.alternativesNote')}</p>
        {replacements.length ? (
          <ul className="mt-3 space-y-3">
            {replacements.map((c, index) => (
              <li key={`${c.part_number}:${index}`} className="rounded-control bg-sunken p-3 text-sm">
                <p className="font-medium">
                  {[c.brand, c.part_number, c.name ?? c.title].filter(Boolean).join(' · ')}
                </p>
                <p className="mt-1 text-xs text-muted">{c.source}</p>
                {safeProductLink(c.url ?? c.source_url) ? (
                  <a
                    href={safeProductLink(c.url ?? c.source_url)!}
                    className="mt-2 inline-block underline"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {t('parts.openProduct')}
                  </a>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-muted">{t('parts.noAlternatives')}</p>
        )}
      </div>

      {/* Restrictions & Notes */}
      {result.warnings?.length || result.reasons?.length ? (
        <details className="rounded-box border border-line bg-surface p-5">
          <summary className="cursor-pointer text-sm font-medium">{t('parts.restrictions')}</summary>
          <ul className="mt-3 space-y-2 text-xs leading-relaxed text-muted">
            {[...(result.reasons ?? []), ...(result.warnings ?? [])].map((warning, i) => (
              <li key={i}>{warning}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  )
}
