import {
  CameraIcon,
  CheckCircleIcon,
  PaletteIcon,
  PlusIcon,
  ShieldCheckIcon,
  TrashIcon,
} from '@phosphor-icons/react'
import { useState } from 'react'
import { Button } from '../../components/ui'
import { useI18n } from '../../i18n'
import { fuelKey } from '../../lib/format'
import type { SavedVehicle } from '../../lib/prefs'
import { useVehicleIdentity, type VehicleIdentity } from '../../lib/vehicleIdentity'
import { IdentityFields } from '../setup/IdentityFields'
import { validIdentity } from '../../lib/identity'
import { VehicleThumbnail } from './VehicleThumbnail'
import { resolveVehiclePhoto, getVehicleColorPresets } from '../../lib/vehicleStyle'

export interface GarageVehicleCardProps {
  car: SavedVehicle
  isActive: boolean
  onSelect: () => void
  onDelete: () => void
  onColorChange: (color: string) => void
  onPhotoChange: (imageUrl?: string) => void
  onFileUpload: (file: File) => void
  onAutoFetchPhoto: () => void
  isSearchingPhoto: boolean
  storageStatus?: 'encrypted' | 'session'
}

export function GarageVehicleCard({
  car,
  isActive,
  onSelect,
  onDelete,
  onColorChange,
  onPhotoChange,
  onFileUpload,
  onAutoFetchPhoto,
  isSearchingPhoto,
  storageStatus = 'session',
}: GarageVehicleCardProps) {
  const { t, locale } = useI18n()
  const isZh = locale?.startsWith('zh')
  const { getVehicleIdentity, setVehicleIdentity } = useVehicleIdentity()
  const carIdentity = getVehicleIdentity(car.id)

  const [editingColor, setEditingColor] = useState(false)
  const [editingPhoto, setEditingPhoto] = useState(false)
  const [editingIdentity, setEditingIdentity] = useState(false)
  const [tempIdentity, setTempIdentity] = useState<VehicleIdentity>({ kind: 'vin', value: { vin: '' } })
  const [photoInputUrl, setPhotoInputUrl] = useState<string>('')

  const currentColor = car.color || '#1e293b'

  return (
    <div
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
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400 border border-emerald-500/20 shadow-xs">
              <CheckCircleIcon size={13} weight="fill" />
              <span>{t('garage.activeBadge')}</span>
            </span>
          ) : null}
        </div>

        <button
          type="button"
          onClick={onDelete}
          aria-label={t('garage.remove')}
          title={t('garage.remove')}
          className="rounded-lg p-1 text-muted transition hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-950/40"
        >
          <TrashIcon size={15} />
        </button>
      </div>

      {/* Car Thumbnail & Spec Section */}
      <div className="my-2 flex items-center gap-4">
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
                if (editingIdentity) {
                  setEditingIdentity(false)
                } else {
                  setEditingIdentity(true)
                  setEditingColor(false)
                  setEditingPhoto(false)
                  setTempIdentity(carIdentity ?? { kind: 'vin', value: { vin: '' } })
                }
              }}
              className="text-[11px] font-medium text-accent hover:underline ml-auto"
            >
              {carIdentity ? t('garage.editIdentity') : `+ ${t('garage.setIdentity')}`}
            </button>
          </div>
        </div>
      </div>

      {/* Appearance Customization Bar: Color & Authentic Photo */}
      <div className="my-1.5 flex flex-col gap-2 rounded-xl bg-sunken/40 p-2.5 text-xs border border-line/40">
        <div className="flex items-center justify-between gap-2">
          {/* Display Mode Segmented Control */}
          <div className="inline-flex items-center rounded-lg bg-surface p-0.5 border border-line/60 shadow-2xs">
            <button
              type="button"
              onClick={() => {
                if (car.imageUrl) {
                  onPhotoChange(undefined)
                }
                setEditingColor(true)
                setEditingPhoto(false)
              }}
              className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium transition ${
                !car.imageUrl && !editingPhoto
                  ? 'bg-accent text-white shadow-2xs font-semibold'
                  : 'text-muted hover:text-ink'
              }`}
              aria-label={t('garage.color')}
            >
              <PaletteIcon size={13} />
              <span>{t('garage.color')}</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setEditingPhoto((prev) => !prev)
                setEditingColor(false)
                setPhotoInputUrl(car.imageUrl || '')
              }}
              className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium transition ${
                car.imageUrl || editingPhoto
                  ? 'bg-accent text-white shadow-2xs font-semibold'
                  : 'text-muted hover:text-ink'
              }`}
              aria-label={t('garage.photo')}
            >
              <CameraIcon size={13} />
              <span>{t('garage.photo')}</span>
              {car.imageUrl ? <span className="size-1.5 rounded-full bg-emerald-400" /> : null}
            </button>
          </div>

          {/* Active State / Color Name Pill */}
          {(() => {
            const carPresets = getVehicleColorPresets(car.label)
            const matchedPreset = carPresets.find(
              (p) => p.hex.toLowerCase() === currentColor.toLowerCase(),
            )
            const displayName = matchedPreset ? (isZh ? matchedPreset.labelZh : matchedPreset.name) : currentColor
            if (car.imageUrl) {
              return (
                <span className="inline-flex items-center gap-1 rounded-md bg-accent-soft/40 px-2 py-0.5 text-[11px] font-medium text-accent">
                  <CameraIcon size={12} />
                  <span>{t('garage.customPhotoActive')}</span>
                </span>
              )
            }
            return (
              <div
                className="flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-medium text-ink bg-surface/80 border border-line/40 shadow-2xs"
                title={displayName}
              >
                <span
                  className="size-2.5 rounded-full border border-line shrink-0"
                  style={{ backgroundColor: currentColor }}
                />
                <span className="truncate max-w-[140px]">{displayName}</span>
              </div>
            )
          })()}
        </div>

        {/* Photo Customization Panel */}
        {editingPhoto || (car.imageUrl && !editingColor) ? (
          <div className="flex flex-col gap-2 pt-2 border-t border-line/40">
            <div className="flex items-center gap-1.5">
              <input
                type="url"
                value={photoInputUrl}
                onChange={(e) => setPhotoInputUrl(e.target.value)}
                placeholder={t('garage.photoUrlPlaceholder')}
                className="flex-1 min-w-0 rounded-lg border border-line bg-surface px-2.5 py-1 text-xs text-ink placeholder:text-muted/60 focus:border-accent focus:outline-none"
              />
              <Button
                variant="secondary"
                onClick={() => onPhotoChange(photoInputUrl.trim() || undefined)}
                className="min-h-7 text-xs px-2.5 shrink-0"
              >
                {t('garage.savePhoto')}
              </Button>
            </div>

            <div className="flex flex-wrap items-center gap-2 text-[11px]">
              {/* File Upload Trigger */}
              <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md bg-surface px-2.5 py-1 text-ink border border-line hover:border-accent hover:text-accent transition shadow-2xs font-medium">
                <PlusIcon size={12} />
                <span>{t('garage.uploadPhoto')}</span>
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) onFileUpload(f)
                  }}
                  className="sr-only"
                />
              </label>

              {/* Built-in Studio Photo Shortcut */}
              {resolveVehiclePhoto(car.label, null, car.color) ? (
                <button
                  type="button"
                  onClick={() => onPhotoChange(undefined)}
                  className="inline-flex items-center gap-1 rounded-md bg-accent-soft/40 px-2.5 py-1 text-accent hover:bg-accent-soft transition font-medium"
                >
                  <span>✓ {t('garage.useStudioPhoto')}</span>
                </button>
              ) : (
                <button
                  type="button"
                  disabled={isSearchingPhoto}
                  onClick={onAutoFetchPhoto}
                  className="inline-flex items-center gap-1.5 rounded-md bg-accent-soft/40 px-2.5 py-1 text-accent hover:bg-accent-soft transition font-medium disabled:opacity-50"
                >
                  <span>{isSearchingPhoto ? '...' : `🌐 ${t('garage.autoFetchPhoto')}`}</span>
                </button>
              )}

              {/* Clear Photo / Revert to Studio */}
              {car.imageUrl ? (
                <button
                  type="button"
                  onClick={() => onPhotoChange(undefined)}
                  className="inline-flex items-center gap-1 text-rose-500 hover:underline ml-auto"
                >
                  <span>✕ {t('garage.clearPhoto')}</span>
                </button>
              ) : null}
            </div>
          </div>
        ) : null}

        {/* Factory Color Swatches */}
        {!car.imageUrl && (editingColor || !editingPhoto) ? (
          <div className="flex flex-wrap items-center gap-2 pt-1.5 border-t border-line/40">
            <div className="flex flex-wrap items-center gap-1.5">
              {getVehicleColorPresets(car.label).map((preset) => {
                const isSelected = currentColor.toLowerCase() === preset.hex.toLowerCase()
                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => {
                      onColorChange(preset.hex)
                      if (car.imageUrl) {
                        onPhotoChange(undefined)
                      }
                    }}
                    title={isZh ? preset.labelZh : preset.name}
                    aria-label={isZh ? preset.labelZh : preset.name}
                    className={`size-5 rounded-full border transition-all hover:scale-120 ${
                      isSelected
                        ? 'ring-2 ring-accent ring-offset-2 ring-offset-surface scale-110 border-transparent shadow-xs'
                        : 'border-line/70 hover:border-ink/60'
                    }`}
                    style={{ backgroundColor: preset.hex }}
                  />
                )
              })}
            </div>

            {/* Reset to Factory Original Color */}
            {currentColor.toLowerCase() !== '#ffffff' &&
             currentColor.toLowerCase() !== '#f8fafc' &&
             currentColor.toLowerCase() !== '#faf9fb' ? (
              <button
                type="button"
                onClick={() => onColorChange('#faf9fb')}
                className="ml-auto inline-flex items-center gap-1 text-[11px] text-muted hover:text-ink hover:underline"
              >
                <span>{t('garage.resetColor')}</span>
              </button>
            ) : null}
          </div>
        ) : null}

        {/* Identity Configuration Panel */}
        {editingIdentity ? (
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
                {carIdentity ? (
                  <button
                    type="button"
                    onClick={() => {
                      setVehicleIdentity(car.id, null)
                      setEditingIdentity(false)
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
                    onClick={() => setEditingIdentity(false)}
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
                        setEditingIdentity(false)
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
            onClick={onSelect}
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
}
