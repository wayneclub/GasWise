import { ClockIcon, NotePencilIcon, TrashIcon } from '@phosphor-icons/react'
import { useI18n } from '../../i18n'
import { fuelKey, perGallon, usd } from '../../lib/format'
import type { RefuelEvent } from '../../lib/fuelAssistant'

interface RefuelRecordCardProps {
  event: RefuelEvent
  onEdit: (event: RefuelEvent) => void
  onDelete: (id: string) => void
}

export function RefuelRecordCard({ event, onEdit, onDelete }: RefuelRecordCardProps) {
  const { t, locale } = useI18n()
  const d = new Date(event.at)
  const formattedDate = new Intl.DateTimeFormat(locale, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(d)

  return (
    <article className="rounded-control border border-line/80 bg-surface p-4 flex flex-col gap-2.5 shadow-2xs hover:border-line transition">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-bold text-ink text-sm sm:text-base break-words">
              {event.stationName || t('refuel.manualRecord')}
            </h3>
            {event.fuelType ? (
              <span className="rounded-full bg-sunken border border-line/60 px-2 py-0.5 text-[10px] font-medium text-muted">
                {t(fuelKey(event.fuelType as any))}
              </span>
            ) : null}
          </div>
          <p className="mt-0.5 text-xs text-muted flex items-center gap-1.5">
            <ClockIcon size={12} className="shrink-0" />
            <span>{formattedDate}</span>
          </p>
          {event.stationAddress ? (
            <p className="mt-0.5 text-xs text-faint truncate">{event.stationAddress}</p>
          ) : null}
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={() => onEdit(event)}
            aria-label={`${t('refuel.edit')} ${event.stationName ?? formattedDate}`}
            className="grid size-8 place-items-center rounded-control text-muted hover:text-ink hover:bg-sunken transition"
            title={t('refuel.edit')}
          >
            <NotePencilIcon size={16} />
          </button>
          <button
            type="button"
            onClick={() => onDelete(event.id)}
            aria-label={`${t('refuel.delete')} ${event.stationName ?? formattedDate}`}
            className="grid size-8 place-items-center rounded-control text-muted hover:text-caution hover:bg-caution-soft transition"
            title={t('refuel.delete')}
          >
            <TrashIcon size={16} />
          </button>
        </div>
      </div>

      {/* Badges for price, gallons, cost */}
      {event.pricePerGallon != null || event.gallons != null || event.cost != null ? (
        <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-line/50 text-xs">
          {event.pricePerGallon != null ? (
            <span className="rounded-md bg-sunken px-2 py-0.5 font-semibold text-ink num">
              {perGallon(String(event.pricePerGallon))}/gal
            </span>
          ) : null}
          {event.gallons != null ? (
            <span className="rounded-md bg-sunken px-2 py-0.5 font-medium text-muted num">
              {event.gallons} gal
            </span>
          ) : null}
          {event.cost != null ? (
            <span className="rounded-md bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 font-bold text-emerald-600 dark:text-emerald-400 num ml-auto">
              {usd(event.cost)}
            </span>
          ) : null}
        </div>
      ) : null}

      {event.notes ? (
        <p className="text-xs text-muted italic bg-sunken/50 rounded p-1.5 break-words">
          {event.notes}
        </p>
      ) : null}
    </article>
  )
}
