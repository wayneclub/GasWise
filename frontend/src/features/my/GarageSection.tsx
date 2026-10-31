import {
  CarIcon,
  CheckCircleIcon,
  PaletteIcon,
  PlusIcon,
  ShieldCheckIcon,
  TrashIcon,
  XIcon,
} from '@phosphor-icons/react'
import { useState } from 'react'
import { Button } from '../../components/ui'
import { useI18n } from '../../i18n'
import { fuelKey } from '../../lib/format'
import type { Prefs, SavedVehicle } from '../../lib/prefs'
import { useVehicleIdentity } from '../../lib/vehicleIdentity'
import { VehicleThumbnail } from './VehicleThumbnail'
import { VehiclePicker } from '../setup/VehiclePicker'
import { VEHICLE_COLOR_PRESETS } from '../../lib/vehicleStyle'

interface GarageSectionProps {
  prefs: Prefs
  update: (change: Partial<Prefs>) => void
}

export function GarageSection({ prefs, update }: GarageSectionProps) {
  const { t } = useI18n()
  const { identity, storageStatus } = useVehicleIdentity()
  const [showAddModal, setShowAddModal] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [editingColorId, setEditingColorId] = useState<number | null>(null)
  const [newCarColor, setNewCarColor] = useState<string>('#1e293b')

  // Ensure garage list has at least prefs.vehicle if garage is empty
  const garageList: SavedVehicle[] =
    prefs.garage && prefs.garage.length > 0
      ? prefs.garage
      : prefs.vehicle
        ? [prefs.vehicle]
        : []

  const activeId = prefs.vehicle?.id ?? null

  const handleSelectCar = (car: SavedVehicle) => {
    update({
      vehicle: car,
      fuelType: car.fuelType,
      mpg: car.combinedMpg,
    })
  }

  const handleAddCar = (newCar: SavedVehicle | null) => {
    if (!newCar) return
    const carWithColor = { ...newCar, color: newCar.color || newCarColor }
    const exists = garageList.some((v) => v.id === carWithColor.id)
    const updatedGarage = exists
      ? garageList.map((v) => (v.id === carWithColor.id ? carWithColor : v))
      : [carWithColor, ...garageList]

    update({
      garage: updatedGarage,
      vehicle: carWithColor,
      fuelType: carWithColor.fuelType,
      mpg: carWithColor.combinedMpg,
    })
    setShowAddModal(false)
  }

  const handleDeleteCar = (carId: number) => {
    const updatedGarage = garageList.filter((v) => v.id !== carId)
    const nextActive =
      activeId === carId ? updatedGarage[0] ?? null : prefs.vehicle

    update({
      garage: updatedGarage,
      vehicle: nextActive,
      fuelType: nextActive ? nextActive.fuelType : prefs.fuelType,
      mpg: nextActive ? nextActive.combinedMpg : prefs.mpg,
    })
    setDeletingId(null)
  }

  const handleColorChange = (carId: number, color: string) => {
    const updatedGarage = garageList.map((v) =>
      v.id === carId ? { ...v, color } : v,
    )
    const nextActive =
      activeId === carId && prefs.vehicle
        ? { ...prefs.vehicle, color }
        : prefs.vehicle

    update({
      garage: updatedGarage,
      vehicle: nextActive,
    })
  }

  return (
    <section id="garage-section" aria-label={t('garage.title')} className="rounded-box border border-line bg-surface p-5 sm:p-6 shadow-sm flex flex-col gap-5">
      {/* Garage Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
        <div className="flex items-center gap-2.5">
          <div className="grid size-9 place-items-center rounded-xl bg-accent-soft text-accent">
            <CarIcon size={20} weight="fill" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-ink sm:text-lg">{t('garage.title')}</h2>
              <span className="rounded-full bg-sunken px-2 py-0.5 text-xs font-semibold text-muted num">
                {garageList.length}
              </span>
            </div>
            <p className="text-xs text-muted mt-0.5">{t('garage.subtitle')}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            onClick={() => setShowAddModal(true)}
            className="min-h-9 gap-1.5 px-3.5 text-xs font-semibold shadow-xs"
          >
            <PlusIcon size={14} weight="bold" />
            <span>{t('garage.addCar')}</span>
          </Button>
        </div>
      </div>

      {/* Vehicle Grid / Cards */}
      {garageList.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-line bg-sunken/40 p-8 text-center sm:p-10">
          <div className="mx-auto mb-3 grid size-12 place-items-center rounded-2xl bg-accent-soft text-accent">
            <CarIcon size={24} weight="duotone" />
          </div>
          <h3 className="text-sm font-semibold text-ink">{t('garage.empty')}</h3>
          <p className="mx-auto mt-1 max-w-sm text-xs text-muted leading-relaxed">
            {t('garage.emptyHint')}
          </p>
          <div className="mt-4 flex justify-center">
            <Button
              variant="secondary"
              onClick={() => setShowAddModal(true)}
              className="min-h-9 gap-1.5 px-4 text-xs font-medium"
            >
              <PlusIcon size={14} weight="bold" />
              <span>{t('garage.addCar')}</span>
            </Button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {garageList.map((car) => {
            const isActive = activeId === car.id
            const currentColor = car.color || '#1e293b'
            return (
              <div
                key={car.id}
                className={`group relative flex flex-col justify-between rounded-2xl border p-4 transition-all ${
                  isActive
                    ? 'border-accent/40 bg-accent-soft/30 shadow-sm ring-1 ring-accent/30'
                    : 'border-line bg-surface hover:border-line/80 hover:bg-sunken/30'
                }`}
              >
                {/* Active Indicator & Top Actions */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    {isActive ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-[11px] font-semibold text-white shadow-xs">
                        <CheckCircleIcon size={13} weight="fill" />
                        <span>{t('garage.activeBadge')}</span>
                      </span>
                    ) : null}
                  </div>

                  <button
                    type="button"
                    onClick={() => setDeletingId(car.id)}
                    aria-label={t('garage.remove')}
                    title={t('garage.remove')}
                    className="rounded-lg p-1 text-muted transition hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-950/40"
                  >
                    <TrashIcon size={15} />
                  </button>
                </div>

                {/* Car Thumbnail & Spec Section */}
                <div className="my-2 flex items-center gap-4">
                  {/* Clean Vector Silhouette Thumbnail with Dynamic Color */}
                  <VehicleThumbnail
                    label={car.label}
                    bodyStyle={car.bodyStyle}
                    color={currentColor}
                    size="md"
                    showBadge
                    active={isActive}
                    className="shrink-0"
                  />

                  {/* Vehicle Details */}
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-sm font-bold text-ink sm:text-[15px]" title={car.label}>
                      {car.label}
                    </h3>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted">
                      <span className="inline-flex items-center rounded-md bg-sunken px-2 py-0.5 font-medium text-ink">
                        {t(fuelKey(car.fuelType))}
                      </span>
                      <span className="inline-flex items-center rounded-md bg-sunken px-2 py-0.5 font-medium num text-ink">
                        {car.combinedMpg} MPG
                      </span>
                    </div>

                    {/* Shared Identity Badge if associated */}
                    {isActive && identity ? (
                      <p className="mt-2 font-mono text-[11px] text-muted truncate">
                        {identity.kind === 'vin'
                          ? `VIN · •••••••••••••${identity.value.vin.slice(-4)}`
                          : `${identity.value.state} · •••${identity.value.plate.slice(-2)}`}
                      </p>
                    ) : null}
                  </div>
                </div>

                {/* Color Customization Swatch Bar */}
                <div className="my-1 flex flex-col gap-1.5 rounded-xl bg-sunken/40 p-2 text-xs">
                  <div className="flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => setEditingColorId(editingColorId === car.id ? null : car.id)}
                      className="inline-flex items-center gap-1.5 rounded-lg px-1.5 py-0.5 text-[11px] font-medium text-muted transition hover:bg-surface hover:text-ink"
                      aria-label={t('garage.color')}
                    >
                      <span
                        className="size-3.5 rounded-full border border-line shadow-2xs shrink-0"
                        style={{ backgroundColor: currentColor }}
                      />
                      <PaletteIcon size={13} className="text-muted" />
                      <span>{t('garage.color')}</span>
                    </button>

                    <label className="relative flex cursor-pointer items-center gap-1 text-[11px] font-mono text-muted hover:text-ink">
                      <span>{currentColor}</span>
                      <input
                        type="color"
                        value={currentColor}
                        onChange={(e) => handleColorChange(car.id, e.target.value)}
                        className="sr-only"
                        aria-label={t('garage.customColor')}
                      />
                    </label>
                  </div>

                  {editingColorId === car.id ? (
                    <div className="flex flex-wrap items-center gap-1.5 pt-1 border-t border-line/40">
                      {VEHICLE_COLOR_PRESETS.map((preset) => {
                        const isSelected = currentColor.toLowerCase() === preset.hex.toLowerCase()
                        return (
                          <button
                            key={preset.id}
                            type="button"
                            onClick={() => handleColorChange(car.id, preset.hex)}
                            title={preset.name}
                            aria-label={preset.name}
                            className={`size-5 rounded-full border transition-transform hover:scale-115 ${
                              isSelected ? 'ring-2 ring-accent ring-offset-1 scale-110 border-transparent' : 'border-line/70'
                            }`}
                            style={{ backgroundColor: preset.hex }}
                          />
                        )
                      })}
                      {/* Native Custom Color Input Button */}
                      <label
                        title={t('garage.customColor')}
                        className="grid size-5 cursor-pointer place-items-center rounded-full border border-dashed border-line hover:border-ink hover:scale-115 transition-transform"
                      >
                        <PlusIcon size={10} className="text-muted" />
                        <input
                          type="color"
                          value={currentColor}
                          onChange={(e) => handleColorChange(car.id, e.target.value)}
                          className="sr-only"
                          aria-label={t('garage.customColor')}
                        />
                      </label>
                    </div>
                  ) : null}
                </div>

                {/* Bottom Actions */}
                <div className="mt-2 flex items-center justify-between border-t border-line/60 pt-3">
                  <span className="inline-flex items-center gap-1 text-[11px] text-muted">
                    <ShieldCheckIcon size={13} weight="fill" className="text-accent" />
                    <span>{t(storageStatus === 'encrypted' ? 'vehicle.encryptedLocal' : 'vehicle.sessionLocal')}</span>
                  </span>

                  {!isActive ? (
                    <Button
                      variant="secondary"
                      onClick={() => handleSelectCar(car)}
                      className="min-h-8 text-xs font-semibold px-3 text-accent border-accent/40 hover:bg-accent-soft"
                    >
                      {t('garage.switchTo')}
                    </Button>
                  ) : (
                    <span className="text-xs font-semibold text-accent">
                      ✓ {t('garage.active')}
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Add Car Modal */}
      {showAddModal ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="add-vehicle-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
        >
          <div className="w-full max-w-lg rounded-box border border-line bg-surface p-5 shadow-2xl flex flex-col gap-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div className="flex items-center gap-2">
                <CarIcon size={20} weight="fill" className="text-accent" />
                <h3 id="add-vehicle-title" className="text-base font-bold text-ink">
                  {t('garage.addNewPrompt')}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="grid size-8 place-items-center rounded-lg text-muted hover:bg-sunken hover:text-ink"
                aria-label={t('garage.cancel')}
              >
                <XIcon size={18} />
              </button>
            </div>

            {/* Optional initial color selector before adding */}
            <div className="rounded-xl border border-line bg-sunken/30 p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-ink">{t('garage.color')}</span>
                <span className="font-mono text-[11px] text-muted">{newCarColor}</span>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {VEHICLE_COLOR_PRESETS.map((preset) => {
                  const isSelected = newCarColor.toLowerCase() === preset.hex.toLowerCase()
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => setNewCarColor(preset.hex)}
                      title={preset.name}
                      aria-label={preset.name}
                      className={`size-6 rounded-full border transition-transform hover:scale-115 ${
                        isSelected ? 'ring-2 ring-accent ring-offset-1 scale-110 border-transparent' : 'border-line/70'
                      }`}
                      style={{ backgroundColor: preset.hex }}
                    />
                  )
                })}
                <label
                  title={t('garage.customColor')}
                  className="grid size-6 cursor-pointer place-items-center rounded-full border border-dashed border-line hover:border-ink hover:scale-115 transition-transform"
                >
                  <PlusIcon size={12} className="text-muted" />
                  <input
                    type="color"
                    value={newCarColor}
                    onChange={(e) => setNewCarColor(e.target.value)}
                    className="sr-only"
                    aria-label={t('garage.customColor')}
                  />
                </label>
              </div>
            </div>

            <div className="py-2">
              <VehiclePicker
                vehicle={null}
                onChange={(car) => {
                  if (car) {
                    handleAddCar(car)
                  }
                }}
              />
            </div>

            <div className="flex justify-end border-t border-line pt-3">
              <Button
                variant="secondary"
                onClick={() => setShowAddModal(false)}
                className="min-h-9 text-xs"
              >
                {t('garage.cancel')}
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Delete Confirmation Modal */}
      {deletingId !== null ? (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
        >
          <div className="w-full max-w-sm rounded-box border border-line bg-surface p-5 shadow-2xl flex flex-col gap-4">
            <h3 className="text-sm font-bold text-ink">{t('garage.remove')}</h3>
            <p className="text-xs text-muted leading-relaxed">{t('garage.confirmRemove')}</p>
            <div className="flex justify-end gap-2 pt-2 border-t border-line">
              <Button
                variant="secondary"
                onClick={() => setDeletingId(null)}
                className="min-h-9 text-xs"
              >
                {t('garage.cancel')}
              </Button>
              <Button
                variant="primary"
                onClick={() => handleDeleteCar(deletingId)}
                className="min-h-9 text-xs bg-rose-600 hover:bg-rose-700 text-white"
              >
                {t('garage.remove')}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  )
}
