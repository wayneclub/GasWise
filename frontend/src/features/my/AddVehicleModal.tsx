import { CarIcon, SparkleIcon, XIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { Button } from '../../components/ui'
import { useI18n } from '../../i18n'
import type { SavedVehicle } from '../../lib/prefs'
import { getVehicleColorPresets } from '../../lib/vehicleStyle'
import { POPULAR_BRANDS, POPULAR_VEHICLES, type PopularVehiclePreset } from '../../lib/popularVehicles'
import { VehiclePicker } from '../setup/VehiclePicker'

interface AddVehicleModalProps {
  open: boolean
  onClose: () => void
  onAddCar: (car: SavedVehicle, chosenColor: string) => void
}

export function AddVehicleModal({ open, onClose, onAddCar }: AddVehicleModalProps) {
  const { t, locale } = useI18n()
  const isZh = locale?.startsWith('zh')
  const [selectedBrand, setSelectedBrand] = useState<string>('Toyota')
  const [addModalMake, setAddModalMake] = useState<string | null>('Toyota')
  const [newCarColor, setNewCarColor] = useState<string>('#4b5563')

  if (!open) return null

  const filteredPresets = selectedBrand === 'ALL'
    ? POPULAR_VEHICLES
    : POPULAR_VEHICLES.filter((v) => v.brand.toLowerCase() === selectedBrand.toLowerCase())

  const handleSelectPreset = (preset: PopularVehiclePreset) => {
    setAddModalMake(preset.label)
    setNewCarColor(preset.defaultColor)
    onAddCar(
      {
        id: preset.id,
        label: preset.label,
        fuelType: preset.fuelType,
        combinedMpg: preset.combinedMpg,
        year: preset.year,
        make: preset.make,
        model: preset.model,
        bodyStyle: preset.bodyStyle,
      },
      preset.defaultColor,
    )
  }

  return (
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
            onClick={onClose}
            className="grid size-8 place-items-center rounded-lg text-muted hover:bg-sunken hover:text-ink"
            aria-label={t('garage.cancel')}
          >
            <XIcon size={18} />
          </button>
        </div>

        {/* Popular Vehicle Quick Pick Section */}
        <div className="flex flex-col gap-2.5 rounded-xl border border-line bg-sunken/40 p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-ink">
              <SparkleIcon size={14} weight="fill" className="text-accent" />
              <span>{t('garage.popularCars')}</span>
            </div>
            <span className="text-[11px] text-muted">
              {isZh ? '點擊一鍵加入車庫' : 'Click to add instantly'}
            </span>
          </div>

          {/* Brand Filter Chips */}
          <div className="flex flex-wrap items-center gap-1">
            <button
              type="button"
              onClick={() => setSelectedBrand('ALL')}
              className={`rounded-md px-2 py-0.5 text-xs font-medium transition ${
                selectedBrand === 'ALL'
                  ? 'bg-accent text-white shadow-2xs'
                  : 'bg-surface text-muted hover:text-ink border border-line/60'
              }`}
            >
              {t('garage.allBrands')}
            </button>
            {POPULAR_BRANDS.map((brand) => {
              const active = selectedBrand.toLowerCase() === brand.toLowerCase()
              return (
                <button
                  key={brand}
                  type="button"
                  onClick={() => {
                    setSelectedBrand(brand)
                    setAddModalMake(brand)
                    const presets = getVehicleColorPresets(brand)
                    if (presets.length > 0) {
                      setNewCarColor(presets[0].hex)
                    }
                  }}
                  className={`rounded-md px-2 py-0.5 text-xs font-medium transition ${
                    active
                      ? 'bg-accent text-white shadow-2xs'
                      : 'bg-surface text-muted hover:text-ink border border-line/60'
                  }`}
                >
                  {brand}
                </button>
              )
            })}
          </div>

          {/* Quick Model Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 max-h-48 overflow-y-auto pr-1">
            {filteredPresets.map((preset) => (
              <button
                key={preset.id}
                type="button"
                onClick={() => handleSelectPreset(preset)}
                className="flex items-center justify-between gap-2 rounded-lg border border-line bg-surface p-2 text-left transition hover:border-accent hover:shadow-xs group"
              >
                <div className="min-w-0">
                  <div className="text-xs font-semibold text-ink group-hover:text-accent truncate">
                    {preset.label}
                  </div>
                  <div className="text-[10px] text-muted">
                    {preset.combinedMpg} MPG · {preset.fuelType}
                  </div>
                </div>
                <span className="shrink-0 size-4 rounded-full border border-line/80 shadow-2xs" style={{ backgroundColor: preset.defaultColor }} />
              </button>
            ))}
          </div>
        </div>

        {/* Optional initial color selector before adding */}
        <div className="rounded-xl border border-line bg-sunken/30 p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink">{t('garage.color')}</span>
            {(() => {
              const modalPresets = getVehicleColorPresets(addModalMake)
              const matched = modalPresets.find(
                (p) => p.hex.toLowerCase() === newCarColor.toLowerCase(),
              )
              const label = matched ? (isZh ? matched.labelZh : matched.name) : newCarColor
              return <span className="font-mono text-[11px] text-muted">{label}</span>
            })()}
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {getVehicleColorPresets(addModalMake).map((preset) => {
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

        {/* Or Search by text / VIN / plate */}
        <div className="py-1">
          <p className="text-xs text-muted mb-2 font-medium">
            {isZh ? '或是自行搜尋年份、車型或 VIN 車牌：' : 'Or search by year, model, or VIN / license plate:'}
          </p>
          <VehiclePicker
            vehicle={null}
            onSelectionChange={(draft) => {
              setAddModalMake(draft)
              const presets = getVehicleColorPresets(draft)
              if (presets.length > 0 && (newCarColor === '#1e293b' || newCarColor === '#f8fafc' || newCarColor === '#4b5563')) {
                setNewCarColor(presets[0].hex)
              }
            }}
            onChange={(car) => {
              if (car) {
                onAddCar(car, newCarColor)
              }
            }}
          />
        </div>

        <div className="flex justify-end border-t border-line pt-3">
          <Button
            variant="secondary"
            onClick={onClose}
            className="min-h-9 text-xs"
          >
            {t('garage.cancel')}
          </Button>
        </div>
      </div>
    </div>
  )
}
