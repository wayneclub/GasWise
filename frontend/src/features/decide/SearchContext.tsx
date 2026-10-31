import { ArrowClockwiseIcon, CarIcon, CheckCircleIcon, MapPinIcon, NavigationArrowIcon } from '@phosphor-icons/react'
import { type ReactNode, useState } from 'react'
import { Button } from '../../components/ui'
import { useI18n } from '../../i18n'
import { effectiveFuel, type Prefs, type SavedVehicle } from '../../lib/prefs'
import { fuelKey } from '../../lib/format'
import { VehicleThumbnail } from '../my/VehicleThumbnail'

export function SearchContext({
  prefs,
  label,
  source,
  permission,
  locating,
  searching,
  refreshing,
  onLocate,
  onChange,
  onSettings,
  onEditCar,
  onSelectCar,
  onRefresh,
  children,
}: {
  children?: ReactNode
  prefs: Prefs
  label: string | null
  source: 'device' | 'manual' | null
  permission: PermissionState | 'unknown'
  locating: boolean
  searching: boolean
  refreshing?: boolean
  onLocate: () => void
  onChange: () => void
  onSettings?: () => void
  onEditCar?: () => void
  onSelectCar?: (car: SavedVehicle) => void
  onRefresh: () => void
}) {
  const { t } = useI18n()
  const [expanded, setExpanded] = useState(false)
  const busy = locating || searching
  const garageList: SavedVehicle[] =
    prefs.garage && prefs.garage.length > 0
      ? prefs.garage
      : prefs.vehicle
        ? [prefs.vehicle]
        : []

  return (
    <section aria-label={t('context.title')} className="liquid-panel my-3 rounded-box">
      <div className="flex items-center gap-2 px-3 py-2">
        <button
          type="button"
          onClick={onChange}
          aria-label={t('location.change')}
          className="flex min-h-10 min-w-0 flex-1 items-center gap-2 text-left text-sm font-medium"
        >
          <MapPinIcon size={18} className="shrink-0 text-accent" />
          <span className="truncate">
            {source === 'device' ? t('context.device') : label ?? t('context.noLocation')}
          </span>
          {refreshing ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-accent-soft px-1.5 py-0.5 text-[10px] font-normal text-accent">
              <span className="size-1.5 animate-pulse rounded-full bg-accent" />
              {t('cache.updating')}
            </span>
          ) : null}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onLocate}
          aria-label={t('context.useGPS')}
          className="grid size-10 shrink-0 place-items-center rounded-control text-accent hover:bg-sunken disabled:opacity-40"
        >
          <NavigationArrowIcon size={19} />
        </button>
        <button
          type="button"
          disabled={busy || refreshing}
          onClick={onRefresh}
          aria-label={t('decide.refresh')}
          className="grid size-10 shrink-0 place-items-center rounded-control text-muted hover:bg-sunken disabled:opacity-40"
        >
          <ArrowClockwiseIcon size={19} className={refreshing ? 'animate-spin text-accent' : ''} />
        </button>
      </div>
      {children ? <div className="border-t border-line p-4">{children}</div> : null}
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 border-t border-line px-3 py-2 text-left text-xs text-muted"
      >
        <CarIcon size={16} className="shrink-0" />
        <span className="min-w-0 flex-1 truncate">
          {prefs.vehicle?.label ?? t('context.manualCar')} · {t(fuelKey(effectiveFuel(prefs)))} ·{' '}
          {t(
            prefs.payment === 'cash_or_credit'
              ? 'prefs.all'
              : prefs.payment === 'cash'
                ? 'prefs.cash'
                : 'prefs.card',
          )}
        </span>
        <span className="shrink-0 text-accent">{t(expanded ? 'context.collapse' : 'context.expand')}</span>
      </button>
      {!source || locating ? (
        <p role="status" className="px-3 pb-2 text-xs text-muted">
          {t(
            locating
              ? 'context.locating'
              : permission === 'denied'
                ? 'context.denied'
                : 'context.choose',
          )}
        </p>
      ) : null}
      {expanded ? (
        <div className="border-t border-line p-3 flex flex-col gap-3">
          <div className="flex items-center justify-between gap-2 text-xs text-muted">
            <span className="truncate">
              {locating
                ? t('context.locating')
                : source === 'manual'
                  ? t('context.manual')
                  : source === 'device'
                    ? t('context.deviceHint')
                    : permission === 'denied'
                      ? t('context.denied')
                      : t('context.choose')}
            </span>
            <button
              type="button"
              onClick={onChange}
              className="shrink-0 text-accent underline hover:opacity-80"
            >
              {t('location.change')}
            </button>
          </div>

          {garageList.length > 0 ? (
            <div className="flex flex-col gap-2 pt-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-ink flex items-center gap-1.5">
                  <CarIcon size={15} className="text-accent" />
                  <span>{t('garage.title')}</span>
                  {garageList.length > 1 ? (
                    <span className="text-[11px] font-normal text-muted">({garageList.length})</span>
                  ) : null}
                </span>
                <button
                  type="button"
                  onClick={onEditCar ?? onSettings}
                  className="text-xs font-medium text-accent hover:underline flex items-center gap-1"
                >
                  <span>{t('context.edit')}</span>
                </button>
              </div>

              {/* Garage vehicles quick switcher */}
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {garageList.map((car) => {
                  const isSelected = prefs.vehicle?.id === car.id
                  return (
                    <button
                      key={car.id}
                      type="button"
                      onClick={() => onSelectCar?.(car)}
                      className={`flex items-center gap-3 rounded-control border p-2 text-left transition ${
                        isSelected
                          ? 'border-accent bg-accent/5 ring-1 ring-accent/30'
                          : 'border-line bg-surface hover:border-accent/40 hover:bg-sunken'
                      }`}
                    >
                      <div className="shrink-0 w-16 h-9 flex items-center justify-center bg-canvas/60 rounded-md overflow-hidden border border-line/40">
                        <VehicleThumbnail
                          label={car.label}
                          bodyStyle={car.bodyStyle}
                          color={car.color}
                          size="sm"
                          showBadge={false}
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1">
                          <span className="truncate text-xs font-semibold text-ink">
                            {car.year} {car.make} {car.model}
                          </span>
                          {isSelected ? (
                            <span className="shrink-0 text-accent">
                              <CheckCircleIcon size={14} weight="fill" />
                            </span>
                          ) : null}
                        </div>
                        <div className="flex items-center gap-1.5 text-[11px] text-muted mt-0.5">
                          <span>{t(fuelKey(car.fuelType))}</span>
                          <span>·</span>
                          <span>{car.combinedMpg} MPG</span>
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          ) : (
            <p className="text-sm font-medium">{t('context.manualCar')}</p>
          )}

          <div className="flex items-center justify-between pt-2 border-t border-line/60">
            <Button variant="ghost" className="h-9 px-2.5 text-xs gap-1.5" onClick={onChange}>
              <MapPinIcon size={14} />
              {t('location.change')}
            </Button>
            <Button
              variant="secondary"
              className="h-9 px-3 text-xs gap-1.5 font-medium"
              onClick={onEditCar ?? onSettings}
            >
              <CarIcon size={14} />
              {t('context.edit')}
            </Button>
          </div>
        </div>
      ) : null}
    </section>
  )
}
