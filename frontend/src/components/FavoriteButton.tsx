import { HeartIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import type { Station } from '../api/types'
import { useI18n } from '../i18n'
import { favoriteKey, useFavorites } from '../lib/favorites'

export function FavoriteButton({
  station,
  size = 20,
  iconOnly = true,
  className = '',
}: {
  station: Partial<Station> & { id: string; name?: string }
  size?: number
  iconOnly?: boolean
  className?: string
}) {
  const { t } = useI18n()
  const { isFav, toggle } = useFavorites()
  const key = favoriteKey(station)
  const favorited = isFav(key)
  const [busy, setBusy] = useState(false)

  const handleToggle = async (e: React.MouseEvent) => {
    e.stopPropagation()
    e.preventDefault()
    if (busy) return
    setBusy(true)
    try {
      await toggle(station)
    } finally {
      setBusy(false)
    }
  }

  const label = t(favorited ? 'favorites.remove' : 'favorites.add')

  if (iconOnly) {
    return (
      <button
        type="button"
        disabled={busy}
        onClick={handleToggle}
        aria-label={label}
        aria-pressed={favorited}
        title={label}
        className={`grid size-9 place-items-center rounded-control transition active:scale-95 disabled:opacity-50 ${
          favorited
            ? 'text-rose-500 hover:text-rose-600 hover:bg-rose-500/10'
            : 'text-muted hover:text-ink hover:bg-sunken'
        } ${className}`}
      >
        <HeartIcon
          size={size}
          weight={favorited ? 'fill' : 'regular'}
          className={favorited ? 'scale-105 transition-transform' : ''}
        />
      </button>
    )
  }

  return (
    <button
      type="button"
      disabled={busy}
      onClick={handleToggle}
      aria-label={label}
      aria-pressed={favorited}
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-control px-4 text-sm font-medium transition active:scale-[0.98] disabled:opacity-50 ${
        favorited
          ? 'border border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-400 hover:bg-rose-500/20'
          : 'border border-line bg-surface text-ink hover:bg-sunken'
      } ${className}`}
    >
      <HeartIcon
        size={size}
        weight={favorited ? 'fill' : 'regular'}
        className={favorited ? 'text-rose-500' : 'text-muted'}
      />
      <span>{t(favorited ? 'favorites.badge' : 'favorites.add')}</span>
    </button>
  )
}
