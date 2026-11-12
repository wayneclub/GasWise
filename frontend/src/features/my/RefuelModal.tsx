import { CalendarBlankIcon, GasPumpIcon, XIcon } from '@phosphor-icons/react'
import { Button, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n'
import { useFavorites } from '../../lib/favorites'

interface RefuelModalProps {
  isOpen: boolean
  isEditing: boolean
  draftAt: string
  draftStation: string
  draftPrice: string
  draftGallons: string
  draftCost: string
  draftNotes: string
  onClose: () => void
  onSave: () => Promise<void>
  onChangeAt: (val: string) => void
  onChangeStation: (val: string) => void
  onChangeAddress: (val: string) => void
  onChangePriceOrGallons: (price: string, gallons: string) => void
  onChangeCost: (val: string) => void
  onChangeNotes: (val: string) => void
}

export function RefuelModal({
  isOpen,
  isEditing,
  draftAt,
  draftStation,
  draftPrice,
  draftGallons,
  draftCost,
  draftNotes,
  onClose,
  onSave,
  onChangeAt,
  onChangeStation,
  onChangeAddress,
  onChangePriceOrGallons,
  onChangeCost,
  onChangeNotes,
}: RefuelModalProps) {
  const { t } = useI18n()
  const { favorites } = useFavorites()

  if (!isOpen) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="refuel-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs"
    >
      <div className="relative w-full max-w-md rounded-box border border-line bg-surface p-5 sm:p-6 shadow-xl flex flex-col gap-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-line pb-3">
          <h3 id="refuel-modal-title" className="text-base font-bold text-ink">
            {isEditing ? t('refuel.editRecord') : t('refuel.addRecord')}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="grid size-8 place-items-center rounded-control text-muted hover:text-ink"
            aria-label="Close"
          >
            <XIcon size={18} />
          </button>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault()
            void onSave()
          }}
          className="flex flex-col gap-3.5 text-xs"
        >
          <label className="flex flex-col gap-1">
            <span className="font-medium text-ink flex items-center gap-1">
              <CalendarBlankIcon size={14} />
              {t('refuel.date')}
            </span>
            <input
              type="datetime-local"
              required
              value={draftAt}
              onChange={(e) => onChangeAt(e.target.value)}
              className="h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="font-medium text-ink flex items-center gap-1">
              <GasPumpIcon size={14} />
              {t('refuel.station')}
            </span>
            <TextInput
              value={draftStation}
              onChange={(e) => onChangeStation(e.target.value)}
              placeholder="Costco, Chevron, Shell..."
              className="text-sm"
            />
          </label>

          {/* Quick-pick favorites as chips */}
          {favorites.length > 0 ? (
            <div className="flex flex-wrap items-center gap-1.5 -mt-1.5">
              <span className="text-[11px] text-muted">{t('favorites.title')}:</span>
              {favorites.slice(0, 4).map((fav) => (
                <button
                  key={fav.id}
                  type="button"
                  onClick={() => {
                    onChangeStation(fav.name)
                    if (fav.address) onChangeAddress(fav.address)
                    if (fav.lastObservedPrice) {
                      onChangePriceOrGallons(String(fav.lastObservedPrice), draftGallons)
                    }
                  }}
                  className="rounded-full border border-line bg-sunken/60 px-2 py-0.5 text-[11px] text-ink hover:border-accent hover:text-accent transition"
                >
                  {fav.name}
                </button>
              ))}
            </div>
          ) : null}

          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="font-medium text-ink">{t('refuel.price')}</span>
              <input
                type="number"
                step="0.001"
                min="0"
                placeholder="3.899"
                value={draftPrice}
                onChange={(e) => onChangePriceOrGallons(e.target.value, draftGallons)}
                className="h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent"
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="font-medium text-ink">{t('refuel.gallons')}</span>
              <input
                type="number"
                step="0.01"
                min="0"
                placeholder="10"
                value={draftGallons}
                onChange={(e) => onChangePriceOrGallons(draftPrice, e.target.value)}
                className="h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent"
              />
            </label>
          </div>

          <label className="flex flex-col gap-1">
            <span className="font-medium text-ink">{t('refuel.totalCost')}</span>
            <input
              type="number"
              step="0.01"
              min="0"
              placeholder="38.99"
              value={draftCost}
              onChange={(e) => onChangeCost(e.target.value)}
              className="h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="font-medium text-ink">{t('refuel.notes')}</span>
            <TextInput
              value={draftNotes}
              onChange={(e) => onChangeNotes(e.target.value)}
              placeholder={t('refuel.notes')}
              className="text-sm"
            />
          </label>

          <div className="mt-2 flex items-center justify-end gap-2 border-t border-line pt-3">
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              className="h-9 px-4 text-xs"
            >
              {t('refuel.cancel')}
            </Button>
            <Button
              type="submit"
              variant="primary"
              className="h-9 px-5 text-xs font-semibold"
            >
              {t('refuel.save')}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
