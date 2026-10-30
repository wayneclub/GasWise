import { HeartIcon, NavigationArrowIcon, NotePencilIcon, TrashIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { CopyAddress } from '../../components/CopyAddress'
import { Button, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n'
import { fuelKey, perGallon } from '../../lib/format'
import { navigationUrl } from '../../lib/navigation'
import type { NavApp } from '../../lib/prefs'
import { useFavorites, type FavoriteStation } from '../../lib/favorites'
import { TopTierBadge } from '../decide/StationDetails'

export function FavoriteStationsSection({ navApp = 'google' }: { navApp?: NavApp }) {
  const { t } = useI18n()
  const { favorites, remove, updateNotes } = useFavorites()
  const [editingId, setEditingId] = useState<string | null>(null)
  const [noteInput, setNoteInput] = useState('')

  const startEditNote = (station: FavoriteStation) => {
    setEditingId(station.id)
    setNoteInput(station.notes ?? '')
  }

  const saveNote = async (id: string) => {
    await updateNotes(id, noteInput)
    setEditingId(null)
  }

  return (
    <section
      id="section-favorites"
      aria-label={t('favorites.title')}
      className="grid grid-cols-1 gap-6 border-b border-line py-8 first:pt-0 last:border-b-0 lg:grid-cols-[280px_1fr] lg:gap-10 lg:py-10"
    >
      <div className="flex flex-col gap-2 lg:pt-1">
        <div className="flex items-center gap-2">
          <HeartIcon size={18} weight="fill" className="text-rose-500" />
          <h2 className="text-base font-semibold text-ink">{t('favorites.title')}</h2>
        </div>
        <p className="text-[13px] leading-relaxed text-muted">{t('favorites.description')}</p>
        <div className="mt-2 text-xs text-muted">
          {t('favorites.count', { count: favorites.length })}
        </div>
      </div>

      <div className="liquid-panel rounded-box p-5 sm:p-6 flex flex-col gap-4 min-w-0">
        {favorites.length === 0 ? (
          <div className="py-6 text-center flex flex-col items-center gap-2">
            <span className="grid size-10 place-items-center rounded-xl bg-rose-500/10 text-rose-500">
              <HeartIcon size={20} weight="duotone" />
            </span>
            <p className="text-sm font-medium text-ink">{t('favorites.empty')}</p>
            <p className="text-xs text-muted max-w-sm">{t('favorites.emptyHint')}</p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {favorites.map((station) => {
              const navUrl = navigationUrl(navApp, station.location.lat, station.location.lng)
              return (
                <article
                  key={station.id}
                  className="rounded-control border border-line bg-surface p-4 flex flex-col gap-2.5"
                >
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
                      onClick={() => remove(station.id)}
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
                      {station.fuelType ? <span>· {t(fuelKey(station.fuelType as any))}</span> : null}
                    </div>
                  ) : null}

                  {/* Notes */}
                  <div className="rounded-control bg-sunken/60 p-2 text-xs">
                    {editingId === station.id ? (
                      <div className="flex flex-col gap-2">
                        <TextInput
                          value={noteInput}
                          onChange={(e) => setNoteInput(e.target.value)}
                          placeholder={t('favorites.notesPlaceholder')}
                          className="text-xs"
                          autoFocus
                        />
                        <div className="flex items-center justify-end gap-2">
                          <Button variant="ghost" className="h-7 px-2 text-xs" onClick={() => setEditingId(null)}>
                            {t('favorites.cancel')}
                          </Button>
                          <Button variant="primary" className="h-7 px-3 text-xs" onClick={() => saveNote(station.id)}>
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
                          onClick={() => startEditNote(station)}
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
                      className="inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-control min-h-8 border border-line px-3 text-xs font-medium text-ink hover:bg-sunken transition active:scale-[0.98]"
                    >
                      <NavigationArrowIcon size={14} weight="fill" className="text-accent" />
                      <span>{t('favorites.navigate')}</span>
                    </a>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </div>
    </section>
  )
}
