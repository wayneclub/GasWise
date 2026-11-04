import {
  CameraIcon,
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
import { useVehicleIdentity, type VehicleIdentity } from '../../lib/vehicleIdentity'
import { IdentityFields } from '../setup/IdentityFields'
import { validIdentity } from '../../lib/identity'
import { VehicleThumbnail } from './VehicleThumbnail'
import { VehiclePicker } from '../setup/VehiclePicker'
import { resolveVehiclePhoto, getVehicleColorPresets } from '../../lib/vehicleStyle'

interface GarageSectionProps {
  prefs: Prefs
  update: (change: Partial<Prefs>) => void
}

export function GarageSection({ prefs, update }: GarageSectionProps) {
  const { t, locale } = useI18n()
  const isZh = locale?.startsWith('zh')
  const { identity, getVehicleIdentity, setVehicleIdentity, storageStatus } = useVehicleIdentity()
  const [showAddModal, setShowAddModal] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [editingColorId, setEditingColorId] = useState<number | null>(null)
  const [editingPhotoId, setEditingPhotoId] = useState<number | null>(null)
  const [editingIdentityId, setEditingIdentityId] = useState<number | null>(null)
  const [tempIdentity, setTempIdentity] = useState<VehicleIdentity>({ kind: 'vin', value: { vin: '' } })
  const [photoInputUrl, setPhotoInputUrl] = useState<string>('')
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

    if (identity && validIdentity(identity)) {
      setVehicleIdentity(carWithColor.id, identity)
    }

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

  const handlePhotoChange = (carId: number, imageUrl?: string) => {
    const updatedGarage = garageList.map((v) =>
      v.id === carId ? { ...v, imageUrl } : v,
    )
    const nextActive =
      activeId === carId && prefs.vehicle
        ? { ...prefs.vehicle, imageUrl }
        : prefs.vehicle

    update({
      garage: updatedGarage,
      vehicle: nextActive,
    })
    setEditingPhotoId(null)
    setPhotoInputUrl('')
  }

  const handleFileUpload = (carId: number, file: File) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const src = e.target?.result as string
      if (!src) return
      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
        const maxW = 400
        const scale = Math.min(1, maxW / img.width)
        canvas.width = Math.round(img.width * scale)
        canvas.height = Math.round(img.height * scale)
        const ctx = canvas.getContext('2d')
        ctx?.drawImage(img, 0, 0, canvas.width, canvas.height)
        const compressed = canvas.toDataURL('image/webp', 0.85)
        handlePhotoChange(carId, compressed)
      }
      img.src = src
    }
    reader.readAsDataURL(file)
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
                  {/* Clean Vector Silhouette Thumbnail or Authentic Photo */}
                  <VehicleThumbnail
                    label={car.label}
                    bodyStyle={car.bodyStyle}
                    color={currentColor}
                    imageUrl={car.imageUrl}
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

                    {/* Per-Vehicle Identity Badge & Quick Trigger */}
                    {(() => {
                      const carIdentity = getVehicleIdentity(car.id)
                      return (
                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          {carIdentity ? (
                            <span className="inline-flex items-center gap-1 rounded-md bg-accent-soft/30 px-2 py-0.5 font-mono text-[11px] font-medium text-accent">
                              <ShieldCheckIcon size={12} weight="fill" />
                              <span>
                                {carIdentity.kind === 'vin'
                                  ? `VIN · •••••••••••••${carIdentity.value.vin.slice(-4)}`
                                  : `${carIdentity.value.state} · •••${carIdentity.value.plate.slice(-2)}`}
                              </span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 rounded-md bg-sunken px-2 py-0.5 text-[11px] text-muted">
                              <span>{t('garage.noIdentity')}</span>
                            </span>
                          )}
                          <button
                            type="button"
                            onClick={() => {
                              if (editingIdentityId === car.id) {
                                setEditingIdentityId(null)
                              } else {
                                setEditingIdentityId(car.id)
                                setEditingColorId(null)
                                setEditingPhotoId(null)
                                setTempIdentity(carIdentity ?? { kind: 'vin', value: { vin: '' } })
                              }
                            }}
                            className="text-[11px] font-medium text-accent hover:underline ml-auto"
                          >
                            {carIdentity ? t('garage.editIdentity') : `+ ${t('garage.setIdentity')}`}
                          </button>
                        </div>
                      )
                    })()}
                  </div>
                </div>

                {/* Appearance Customization Bar: Color & Authentic Photo */}
                <div className="my-1 flex flex-col gap-1.5 rounded-xl bg-sunken/40 p-2 text-xs">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setEditingColorId(editingColorId === car.id ? null : car.id)
                          setEditingPhotoId(null)
                        }}
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

                      <button
                        type="button"
                        onClick={() => {
                          setEditingPhotoId(editingPhotoId === car.id ? null : car.id)
                          setEditingColorId(null)
                          setPhotoInputUrl(car.imageUrl || '')
                        }}
                        className={`inline-flex items-center gap-1.5 rounded-lg px-1.5 py-0.5 text-[11px] font-medium transition ${
                          car.imageUrl
                            ? 'bg-accent/10 text-accent font-semibold'
                            : 'text-muted hover:bg-surface hover:text-ink'
                        }`}
                        aria-label={t('garage.photo')}
                      >
                        <CameraIcon size={13} />
                        <span>{t('garage.photo')}</span>
                        {car.imageUrl ? <span className="size-1.5 rounded-full bg-accent" /> : null}
                      </button>
                    </div>

                    {(() => {
                      const carPresets = getVehicleColorPresets(car.label)
                      const matchedPreset = carPresets.find(
                        (p) => p.hex.toLowerCase() === currentColor.toLowerCase(),
                      )
                      const displayName = matchedPreset ? (isZh ? matchedPreset.labelZh : matchedPreset.name) : currentColor
                      return (
                        <button
                          type="button"
                          onClick={() => {
                            setEditingColorId(editingColorId === car.id ? null : car.id)
                            setEditingPhotoId(null)
                          }}
                          className="flex items-center gap-1.5 rounded-md px-1.5 py-0.5 text-[11px] font-medium text-muted hover:bg-surface hover:text-ink transition"
                          title={displayName}
                        >
                          <span
                            className="size-2.5 rounded-full border border-line shrink-0"
                            style={{ backgroundColor: currentColor }}
                          />
                          <span>{displayName}</span>
                        </button>
                      )
                    })()}
                  </div>

                  {/* Photo Customization Panel */}
                  {editingPhotoId === car.id ? (
                    <div className="flex flex-col gap-2 pt-2 border-t border-line/40">
                      <div className="flex items-center gap-1.5">
                        <input
                          type="url"
                          value={photoInputUrl}
                          onChange={(e) => setPhotoInputUrl(e.target.value)}
                          placeholder={t('garage.photoUrlPlaceholder')}
                          className="flex-1 min-w-0 rounded-lg border border-line bg-surface px-2 py-1 text-xs text-ink placeholder:text-muted/60 focus:border-accent focus:outline-none"
                        />
                        <Button
                          variant="secondary"
                          onClick={() => handlePhotoChange(car.id, photoInputUrl.trim() || undefined)}
                          className="min-h-7 text-xs px-2.5 shrink-0"
                        >
                          {t('garage.savePhoto')}
                        </Button>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 text-[11px]">
                        {/* File Upload Trigger */}
                        <label className="inline-flex cursor-pointer items-center gap-1 rounded-md bg-surface px-2 py-1 text-muted border border-line hover:text-ink hover:border-ink/40 transition">
                          <PlusIcon size={11} />
                          <span>{t('garage.uploadPhoto')}</span>
                          <input
                            type="file"
                            accept="image/*"
                            onChange={(e) => {
                              const f = e.target.files?.[0]
                              if (f) handleFileUpload(car.id, f)
                            }}
                            className="sr-only"
                          />
                        </label>

                        {/* Built-in Studio Photo Shortcut */}
                        {resolveVehiclePhoto(car.label) ? (
                          <button
                            type="button"
                            onClick={() => handlePhotoChange(car.id, resolveVehiclePhoto(car.label)!)}
                            className="inline-flex items-center gap-1 rounded-md bg-accent-soft/40 px-2 py-1 text-accent hover:bg-accent-soft transition font-medium"
                          >
                            <span>✓ {t('garage.useStudioPhoto')}</span>
                          </button>
                        ) : null}

                        {/* Clear Photo / Revert to Vector */}
                        {car.imageUrl ? (
                          <button
                            type="button"
                            onClick={() => handlePhotoChange(car.id, undefined)}
                            className="inline-flex items-center gap-1 text-rose-500 hover:underline ml-auto"
                          >
                            <span>{t('garage.clearPhoto')}</span>
                          </button>
                        ) : null}
                      </div>
                    </div>
                  ) : null}

                  {editingColorId === car.id ? (
                    <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-line/40">
                      <div className="flex flex-wrap items-center gap-1.5">
                        {getVehicleColorPresets(car.label).map((preset) => {
                          const isSelected = currentColor.toLowerCase() === preset.hex.toLowerCase()
                          return (
                            <button
                              key={preset.id}
                              type="button"
                              onClick={() => handleColorChange(car.id, preset.hex)}
                              title={isZh ? preset.labelZh : preset.name}
                              aria-label={isZh ? preset.labelZh : preset.name}
                              className={`size-5 rounded-full border transition-transform hover:scale-115 ${
                                isSelected ? 'ring-2 ring-accent ring-offset-1 scale-110 border-transparent' : 'border-line/70'
                              }`}
                              style={{ backgroundColor: preset.hex }}
                            />
                          )
                        })}
                      </div>

                      {/* Reset to Factory Original Color */}
                      {currentColor.toLowerCase() !== '#ffffff' && currentColor.toLowerCase() !== '#f8fafc' ? (
                        <button
                          type="button"
                          onClick={() => handleColorChange(car.id, '#f8fafc')}
                          className="ml-auto inline-flex items-center gap-1 text-[11px] text-muted hover:text-ink hover:underline"
                        >
                          <span>{t('garage.resetColor')}</span>
                        </button>
                      ) : null}
                    </div>
                  ) : null}

                  {/* Identity Configuration Panel */}
                  {editingIdentityId === car.id ? (
                    <div className="flex flex-col gap-2.5 pt-2 border-t border-line/40">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-ink flex items-center gap-1">
                          <ShieldCheckIcon size={13} weight="fill" className="text-accent" />
                          <span>{t('garage.identity')}</span>
                        </span>
                        <span className="text-[11px] text-muted">{t('vehicle.encryptedLocal')}</span>
                      </div>
                      <div className="rounded-lg bg-surface p-2.5 border border-line/70">
                        <IdentityFields
                          identity={tempIdentity}
                          onChange={(val) => setTempIdentity(val)}
                          showMode={true}
                        />
                        <div className="mt-3 flex items-center justify-between pt-2 border-t border-line/40">
                          {getVehicleIdentity(car.id) ? (
                            <button
                              type="button"
                              onClick={() => {
                                setVehicleIdentity(car.id, null)
                                setEditingIdentityId(null)
                              }}
                              className="text-xs text-rose-500 hover:underline"
                            >
                              {t('garage.clearIdentity')}
                            </button>
                          ) : (
                            <span />
                          )}
                          <div className="flex items-center gap-2">
                            <Button
                              variant="ghost"
                              onClick={() => setEditingIdentityId(null)}
                              className="min-h-7 text-xs px-2.5"
                            >
                              {t('garage.cancel')}
                            </Button>
                            <Button
                              variant="secondary"
                              disabled={!validIdentity(tempIdentity)}
                              onClick={() => {
                                if (validIdentity(tempIdentity)) {
                                  setVehicleIdentity(car.id, tempIdentity)
                                  setEditingIdentityId(null)
                                }
                              }}
                              className="min-h-7 text-xs px-3 font-semibold text-accent border-accent/40 hover:bg-accent-soft"
                            >
                              {t('garage.saveIdentity')}
                            </Button>
                          </div>
                        </div>
                      </div>
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
                {(() => {
                  const modalPresets = getVehicleColorPresets(null)
                  const matched = modalPresets.find(
                    (p) => p.hex.toLowerCase() === newCarColor.toLowerCase(),
                  )
                  const label = matched ? (isZh ? matched.labelZh : matched.name) : newCarColor
                  return <span className="font-mono text-[11px] text-muted">{label}</span>
                })()}
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {getVehicleColorPresets(null).map((preset) => {
                  const isSelected = newCarColor.toLowerCase() === preset.hex.toLowerCase()
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => setNewCarColor(preset.hex)}
                      title={isZh ? preset.labelZh : preset.name}
                      aria-label={isZh ? preset.labelZh : preset.name}
                      className={`size-6 rounded-full border transition-transform hover:scale-115 ${
                        isSelected ? 'ring-2 ring-accent ring-offset-1 scale-110 border-transparent' : 'border-line/70'
                      }`}
                      style={{ backgroundColor: preset.hex }}
                    />
                  )
                })}
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
