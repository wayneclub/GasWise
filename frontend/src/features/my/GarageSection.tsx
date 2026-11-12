import { CarIcon, PlusIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { Button } from '../../components/ui'
import { useI18n } from '../../i18n'
import type { Prefs, SavedVehicle } from '../../lib/prefs'
import { useVehicleIdentity } from '../../lib/vehicleIdentity'
import { validIdentity } from '../../lib/identity'
import { getVehicleColorPresets } from '../../lib/vehicleStyle'
import { fetchDynamicVehiclePhoto } from '../../lib/dynamicVehiclePhoto'
import { compressImageFile } from '../../lib/imageCompression'
import { GarageVehicleCard } from './GarageVehicleCard'
import { AddVehicleModal } from './AddVehicleModal'
import { DeleteVehicleModal } from './DeleteVehicleModal'

interface GarageSectionProps {
  prefs: Prefs
  update: (change: Partial<Prefs>) => void
}

export function GarageSection({ prefs, update }: GarageSectionProps) {
  const { t } = useI18n()
  const { identity, setVehicleIdentity, storageStatus } = useVehicleIdentity()
  const [showAddModal, setShowAddModal] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [isSearchingPhoto, setIsSearchingPhoto] = useState<number | null>(null)

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

  const handleAutoFetchPhoto = async (carId: number, carLabel: string) => {
    setIsSearchingPhoto(carId)
    try {
      const photo = await fetchDynamicVehiclePhoto(carLabel)
      if (photo) {
        handlePhotoChange(carId, photo)
      }
    } finally {
      setIsSearchingPhoto(null)
    }
  }

  const handleAddCar = (newCar: SavedVehicle, chosenColor: string) => {
    const brandPresets = getVehicleColorPresets(newCar.label)
    const defaultColor = brandPresets[0]?.hex ?? '#f8fafc'
    const finalColor = newCar.color || (chosenColor !== '#1e293b' ? chosenColor : defaultColor)
    const carWithColor = { ...newCar, color: finalColor }
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
  }

  const handleFileUpload = async (carId: number, file: File) => {
    try {
      const compressed = await compressImageFile(file, 400, 0.85)
      handlePhotoChange(carId, compressed)
    } catch {
      // Ignore unreadable image
    }
  }

  return (
    <section aria-label={t('garage.title')} className="mt-8">
      {/* Section Header */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
        <div className="flex items-center gap-2">
          <div className="grid size-9 place-items-center rounded-xl bg-accent-soft text-accent">
            <CarIcon size={20} weight="duotone" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-ink sm:text-lg">{t('garage.title')}</h2>
              <span className="grid size-5 place-items-center rounded-full bg-accent-soft text-[11px] font-bold text-accent">
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
          {garageList.map((car) => (
            <GarageVehicleCard
              key={car.id}
              car={car}
              isActive={activeId === car.id}
              onSelect={() => handleSelectCar(car)}
              onDelete={() => setDeletingId(car.id)}
              onColorChange={(color) => handleColorChange(car.id, color)}
              onPhotoChange={(imageUrl) => handlePhotoChange(car.id, imageUrl)}
              onFileUpload={(file) => handleFileUpload(car.id, file)}
              onAutoFetchPhoto={() => handleAutoFetchPhoto(car.id, car.label)}
              isSearchingPhoto={isSearchingPhoto === car.id}
              storageStatus={storageStatus}
            />
          ))}
        </div>
      )}

      {/* Add Car Modal */}
      <AddVehicleModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        onAddCar={handleAddCar}
      />

      {/* Delete Confirmation Modal */}
      <DeleteVehicleModal
        open={deletingId !== null}
        onClose={() => setDeletingId(null)}
        onConfirm={() => {
          if (deletingId !== null) {
            handleDeleteCar(deletingId)
          }
        }}
      />
    </section>
  )
}
