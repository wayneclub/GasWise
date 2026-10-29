import { useEffect, useId, useRef, useState } from 'react'
import { api } from '../../api/client'
import { Button, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n'
import type { Origin } from '../../lib/session'

export interface RecentLocation {
  id: string
  label: string
  location: Origin
}

const RECENT_KEY = 'gaswise.recent_locations'

function loadRecents(): RecentLocation[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.slice(0, 5) : []
  } catch {
    return []
  }
}

function persistRecent(item: RecentLocation) {
  try {
    const list = loadRecents().filter(
      (r) => r.label !== item.label && !(Math.abs(r.location.lat - item.location.lat) < 0.001 && Math.abs(r.location.lng - item.location.lng) < 0.001)
    )
    list.unshift(item)
    localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, 5)))
  } catch {}
}

const QUICK_PRESETS = [
  { label: 'Downtown LA', query: 'Downtown LA' },
  { label: 'Irvine', query: 'Irvine, CA' },
  { label: 'Pasadena', query: 'Pasadena, CA' },
  { label: 'San Diego', query: 'San Diego, CA' },
]

export function LocationSearch({ onChoose }: { onChoose: (location: Origin, label: string) => void }) {
  const id = useId()
  const { t, locale } = useI18n()
  const [text, setText] = useState('')
  const [items, setItems] = useState<{ id: string; label: string; location: Origin }[]>([])
  const [recents, setRecents] = useState<RecentLocation[]>(() => loadRecents())
  const [status, setStatus] = useState<'idle' | 'pending' | 'empty' | 'unsupported' | 'error'>('idle')
  const controller = useRef<AbortController | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  const executeSearch = async (queryText: string) => {
    if (queryText.trim().length < 2) return
    controller.current?.abort()
    const abort = new AbortController()
    controller.current = abort
    setStatus('pending')
    setItems([])
    try {
      const result = await api.resolveLocation(queryText.trim(), locale, abort.signal)
      if (abort.signal.aborted) return
      setStatus(result.candidates.length ? 'idle' : result.reason === 'unsupported_area' ? 'unsupported' : 'empty')
      if (result.candidates.length === 1) {
        const [item] = result.candidates
        persistRecent(item)
        setRecents(loadRecents())
        onChoose(item.location, item.label)
      } else setItems(result.candidates)
    } catch {
      if (!abort.signal.aborted) setStatus('error')
    }
  }

  const handleSelect = (item: RecentLocation) => {
    persistRecent(item)
    setRecents(loadRecents())
    setItems([])
    onChoose(item.location, item.label)
  }

  const clearRecents = () => {
    try {
      localStorage.removeItem(RECENT_KEY)
    } catch {}
    setRecents([])
  }

  return (
    <form
      className="flex flex-col gap-3 text-left"
      onSubmit={(event) => {
        event.preventDefault()
        void executeSearch(text)
      }}
    >
      <label className="text-sm font-medium" htmlFor={id}>
        {t('location.label')}
      </label>
      <div className="flex gap-2">
        <TextInput
          id={id}
          value={text}
          maxLength={200}
          placeholder={t('location.placeholder')}
          onChange={(e) => {
            controller.current?.abort()
            setText(e.target.value)
            setItems([])
            setStatus('idle')
          }}
        />
        <Button type="submit" disabled={status === 'pending' || text.trim().length < 2}>
          {t(status === 'pending' ? 'vehicle.finding' : 'vehicle.find')}
        </Button>
      </div>

      {/* Recent searches & quick presets */}
      {items.length === 0 && text.trim().length === 0 ? (
        <div className="flex flex-col gap-2 pt-1">
          {recents.length > 0 ? (
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between text-xs text-muted">
                <span>{t('location.recent')}</span>
                <button
                  type="button"
                  className="underline hover:text-ink"
                  onClick={clearRecents}
                >
                  {t('location.clearRecent')}
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {recents.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="inline-flex max-w-full items-center gap-1 rounded-full border border-line bg-surface px-2.5 py-1 text-xs text-ink transition hover:border-accent hover:bg-sunken"
                    onClick={() => handleSelect(item)}
                  >
                    <span aria-hidden="true" className="shrink-0 text-muted">🕒</span>
                    <span className="truncate">{item.label}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
              <span className="shrink-0">💡</span>
              {QUICK_PRESETS.map((preset) => (
                <button
                  key={preset.query}
                  type="button"
                  className="rounded-full border border-line bg-surface px-2.5 py-0.5 text-xs text-muted transition hover:border-accent hover:text-ink"
                  onClick={() => {
                    setText(preset.query)
                    void executeSearch(preset.query)
                  }}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          )}
        </div>
      ) : null}

      <p className="text-xs leading-relaxed text-muted">
        {t('location.hint')}{' '}
        <a href="https://maps.google.com/" target="_blank" rel="noreferrer" className="underline">
          Google Maps
        </a>
      </p>

      {status === 'error' || status === 'empty' || status === 'unsupported' ? (
        <p role="status" className="text-sm text-caution">
          {t(`location.${status}`)}
        </p>
      ) : null}

      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          className="rounded-control border border-line bg-surface p-3 text-left text-sm hover:border-accent"
          onClick={() => handleSelect(item)}
        >
          {item.label}
        </button>
      ))}
    </form>
  )
}
