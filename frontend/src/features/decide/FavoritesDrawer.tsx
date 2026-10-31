import { HeartIcon, NavigationArrowIcon, NotePencilIcon, TrashIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { CopyAddress } from '../../components/CopyAddress'
import { Button, Sheet, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n'
import { fuelKey, perGallon } from '../../lib/format'
import { navigationUrl } from '../../lib/navigation'
import { recordStationRefuel } from '../../lib/fuelAssistant'
import type { NavApp } from '../../lib/prefs'
import { useFavorites, type FavoriteStation } from '../../lib/favorites'
import { TopTierBadge } from './StationDetails'

function FavoriteItem({
  station,
  navApp,
  onRemove,
  onUpdateNotes,
}: {
  station: FavoriteStation
  navApp: NavApp
  onRemove: (id: string) => void
  onUpdateNotes: (id: string, notes: string | null) => void
}) {
  const { t } = useI18n()
  const [editingNotes, setEditingNotes] = useState(false)
  const [notesText, setNotesText] = useState(station.notes ?? '')
  const navUrl = navigationUrl(navApp, station.location.lat, station.location.lng)

  const handleSaveNotes = () => {
    onUpdateNotes(station.id, notesText)
    setEditingNotes(false)
  }

  return (
    <article className="rounded-control border border-line bg-surface p-4 flex flex-col gap-2.5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <h3 className="font-semibold text-ink break-words">{station.name}</h3>
            {station.topTierBrand ? <TopTierBadge brand={station.topTierBrand} /> : null}
          </div>
          {station.address ? (
            <CopyAddress address={station.address} className="mt-1 w-full text-xs text-muted" />
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => onRemove(station.id)}
          aria-label={`${t('favorites.remove')} ${station.name}`}
          className="grid size-8 shrink-0 place-items-center rounded-control text-muted hover:text-caution hover:bg-caution-soft transition"
        >
          <TrashIcon size={16} />
        </button>
      </div>

      {station.lastObservedPrice ? (
        <div className="flex items-center gap-2 text-xs text-muted">
          <span className="font-medium text-ink num">
            {perGallon(String(station.lastObservedPrice))}
          </span>
          {station.fuelType ? (
            <span>· {t(fuelKey(station.fuelType as any))}</span>
          ) : null}
        </div>
      ) : null}

      {/* Notes section */}
      <div className="rounded-control bg-sunken/60 p-2 text-xs">
        {editingNotes ? (
          <div className="flex flex-col gap-2">
            <TextInput
              value={notesText}
              onChange={(e) => setNotesText(e.target.value)}
              placeholder={t('favorites.notesPlaceholder')}
              className="text-xs"
              autoFocus
            />
            <div className="flex items-center justify-end gap-2">
              <Button variant="ghost" className="h-7 px-2 text-xs" onClick={() => setEditingNotes(false)}>
                {t('favorites.cancel')}
              </Button>
              <Button variant="primary" className="h-7 px-3 text-xs" onClick={handleSaveNotes}>
                {t('favorites.saveNotes')}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex items-start justify-between gap-2">
            <p className="text-muted leading-relaxed italic break-words flex-1">
              {station.notes ? station.notes : <span className="opacity-60">{t('favorites.notesPlaceholder')}</span>}
            </p>
            <button
              type="button"
              onClick={() => {
                setNotesText(station.notes ?? '')
                setEditingNotes(true)
              }}
              className="inline-flex shrink-0 items-center gap-1 text-[11px] font-medium text-accent hover:underline"
            >
              <NotePencilIcon size={13} />
              <span>{station.notes ? t('favorites.editNotes') : t('favorites.notes')}</span>
            </button>
          </div>
        )}
      </div>

      <div className="flex items-center justify-end pt-1">
        <a
          href={navUrl}
          target="_blank"
          rel="noreferrer"
          onClick={() => {
            void recordStationRefuel(station, {
              fuelType: station.fuelType,
              note: t('refuel.navigatedNote'),
            })
          }}
          className="inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-control min-h-8 border border-line px-3 text-xs font-medium text-ink hover:bg-sunken transition active:scale-[0.98]"
        >
          <NavigationArrowIcon size={14} weight="fill" className="text-accent" />
          <span>{t('favorites.navigate')}</span>
        </a>
      </div>
    </article>
  )
}

export function FavoritesDrawer({
  open,
  onClose,
  navApp = 'google',
}: {
  open: boolean
  onClose: () => void
  navApp?: NavApp
}) {
  const { t } = useI18n()
  const { favorites, remove, updateNotes } = useFavorites()

  return (
    <Sheet open={open} onClose={onClose} title={t('favorites.title')}>
      <div className="flex flex-col gap-4">
        {favorites.length === 0 ? (
          <div className="py-8 text-center flex flex-col items-center gap-3">
            <span className="grid size-12 place-items-center rounded-2xl bg-rose-500/10 text-rose-500">
              <HeartIcon size={24} weight="duotone" />
            </span>
            <div className="flex flex-col gap-1 max-w-xs">
              <h3 className="font-semibold text-ink text-sm">{t('favorites.empty')}</h3>
              <p className="text-xs text-muted leading-relaxed">{t('favorites.emptyHint')}</p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3 max-h-[65vh] overflow-y-auto pr-1">
            <p className="text-xs text-muted">{t('favorites.description')}</p>
            {favorites.map((station) => (
              <FavoriteItem
                key={station.id}
                station={station}
                navApp={navApp}
                onRemove={remove}
                onUpdateNotes={updateNotes}
              />
            ))}
          </div>
        )}
      </div>
    </Sheet>
  )
}
