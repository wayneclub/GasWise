import { CarIcon, XIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { Button } from '../../components/ui'
import { useI18n } from '../../i18n'
import type { SavedVehicle } from '../../lib/prefs'
import { getVehicleColorPresets } from '../../lib/vehicleStyle'
import { VehiclePicker } from '../setup/VehiclePicker'

interface AddVehicleModalProps {
  open: boolean
  onClose: () => void
  onAddCar: (car: SavedVehicle, chosenColor: string) => void
}

export function AddVehicleModal({ open, onClose, onAddCar }: AddVehicleModalProps) {
  const { t, locale } = useI18n()
  const isZh = locale?.startsWith('zh')
  const [addModalMake, setAddModalMake] = useState<string | null>(null)
  const [newCarColor, setNewCarColor] = useState<string>('#1e293b')

  if (!open) return null

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

        <div className="py-2">
          <VehiclePicker
            vehicle={null}
            onSelectionChange={(draft) => {
              setAddModalMake(draft)
              const presets = getVehicleColorPresets(draft)
              if (presets.length > 0 && (newCarColor === '#1e293b' || newCarColor === '#f8fafc')) {
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
