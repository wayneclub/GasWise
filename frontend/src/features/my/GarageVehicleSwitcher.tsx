import { CarIcon, CheckCircleIcon, ShieldCheckIcon } from '@phosphor-icons/react'
import { useI18n } from '../../i18n'
import { fuelKey } from '../../lib/format'
import type { SavedVehicle } from '../../lib/prefs'
import { useVehicleIdentity } from '../../lib/vehicleIdentity'
import { VehicleThumbnail } from './VehicleThumbnail'

export interface GarageVehicleSwitcherProps {
  garage: SavedVehicle[]
  activeVehicleId?: number | null
  onSelectVehicle: (car: SavedVehicle) => void
  onManageGarage?: () => void
  showIdentity?: boolean
  showTitle?: boolean
  title?: string
  className?: string
}

export function GarageVehicleSwitcher({
  garage,
  activeVehicleId,
  onSelectVehicle,
  onManageGarage,
  showIdentity = false,
  showTitle = true,
  title,
  className = '',
}: GarageVehicleSwitcherProps) {
  const { t } = useI18n()
  const { getVehicleIdentity } = useVehicleIdentity()

  if (garage.length === 0) {
    return null
  }

  return (
    <div className={`flex flex-col gap-2.5 ${className}`}>
      {showTitle ? (
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-ink flex items-center gap-1.5">
            <CarIcon size={15} className="text-accent" />
            <span>{title ?? t('garage.title')}</span>
            {garage.length > 1 ? (
              <span className="text-[11px] font-normal text-muted">({garage.length})</span>
            ) : null}
          </span>
          {onManageGarage ? (
            <button
              type="button"
              onClick={onManageGarage}
              className="text-xs font-medium text-accent hover:underline flex items-center gap-1"
            >
              <span>{t('context.edit')}</span>
            </button>
          ) : null}
        </div>
      ) : null}

      {/* Responsive vehicle switcher grid */}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {garage.map((car) => {
          const isSelected = activeVehicleId === car.id
          const carIdentity = showIdentity ? getVehicleIdentity(car.id) : null

          return (
            <button
              key={car.id}
              type="button"
              onClick={() => onSelectVehicle(car)}
              aria-pressed={isSelected}
              className={`flex items-center gap-3 rounded-control border p-2 text-left transition ${
                isSelected
                  ? 'border-accent bg-accent/5 ring-1 ring-accent/30 shadow-2xs'
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
                  imageUrl={car.imageUrl}
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
                {showIdentity ? (
                  <div className="mt-1 flex items-center gap-1 text-[10px]">
                    {carIdentity ? (
                      <span className="inline-flex items-center gap-0.5 font-mono text-accent">
                        <ShieldCheckIcon size={11} weight="fill" />
                        <span>
                          {carIdentity.kind === 'vin'
                            ? `VIN · •••••${carIdentity.value.vin.slice(-4)}`
                            : `${carIdentity.value.state} · ••${carIdentity.value.plate.slice(-2)}`}
                        </span>
                      </span>
                    ) : (
                      <span className="text-muted/70">
                        {t('garage.noIdentity')}
                      </span>
                    )}
                  </div>
                ) : null}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
