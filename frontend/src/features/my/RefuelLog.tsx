import {
  CalendarBlankIcon,
  ClockIcon,
  GasPumpIcon,
  NotePencilIcon,
  PlusIcon,
  SparkleIcon,
  TrashIcon,
  XIcon,
} from '@phosphor-icons/react'
import { useCallback, useEffect, useState } from 'react'
import { Button, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n'
import { fuelKey, perGallon, usd } from '../../lib/format'
import {
  DEFAULT_FUEL_ASSISTANT_SETTINGS,
  deleteRefuel,
  estimateNeed,
  loadFuelAssistant,
  recordRefuel,
  saveFuelAssistantSettings,
  syncNeedEstimate,
  updateRefuel,
  onRefuelRecorded,
  type FuelAssistantSettings,
  type NeedEstimate,
  type RefuelEvent,
} from '../../lib/fuelAssistant'
import type { Prefs } from '../../lib/prefs'
import { useFavorites } from '../../lib/favorites'

function toDatetimeLocal(isoOrDate: string | Date): string {
  const d = typeof isoOrDate === 'string' ? new Date(isoOrDate) : isoOrDate
  if (isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  const YYYY = d.getFullYear()
  const MM = pad(d.getMonth() + 1)
  const DD = pad(d.getDate())
  const hh = pad(d.getHours())
  const mm = pad(d.getMinutes())
  return `${YYYY}-${MM}-${DD}T${hh}:${mm}`
}

export function RefuelLog({ prefs }: { prefs: Prefs }) {
  const { t, locale } = useI18n()
  const { favorites } = useFavorites()
  const mpg = Number(prefs.vehicle?.combinedMpg ?? prefs.mpg ?? 0)
  const mpgBasis = prefs.vehicle ? ('epa_vehicle' as const) : ('manual_mpg' as const)

  const [settings, setSettings] = useState<FuelAssistantSettings>(DEFAULT_FUEL_ASSISTANT_SETTINGS)
  const [events, setEvents] = useState<RefuelEvent[]>([])
  const [estimate, setEstimate] = useState<NeedEstimate>(() =>
    estimateNeed([], DEFAULT_FUEL_ASSISTANT_SETTINGS, mpg, new Date(), mpgBasis),
  )
  const [busy, setBusy] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)

  // Form draft state
  const [draftAt, setDraftAt] = useState('')
  const [draftStation, setDraftStation] = useState('')
  const [draftAddress, setDraftAddress] = useState('')
  const [draftFuelType, setDraftFuelType] = useState<string>(prefs.fuelType ?? 'regular')
  const [draftPrice, setDraftPrice] = useState('')
  const [draftGallons, setDraftGallons] = useState('')
  const [draftCost, setDraftCost] = useState('')
  const [draftNotes, setDraftNotes] = useState('')

  const refresh = useCallback(
    async (now = new Date(), nextSettings = settings) => {
      const loaded = await loadFuelAssistant()
      setSettings(loaded.settings)
      setEvents(loaded.events)
      const next = estimateNeed(
        loaded.events,
        nextSettings === settings ? loaded.settings : nextSettings,
        mpg,
        now,
        mpgBasis,
      )
      setEstimate(next)
      await syncNeedEstimate(next)
    },
    [settings, mpg, mpgBasis],
  )

  useEffect(() => {
    let cancelled = false
    void loadFuelAssistant()
      .then(async (loaded) => {
        if (cancelled) return
        const next = estimateNeed(loaded.events, loaded.settings, mpg, new Date(), mpgBasis)
        setSettings(loaded.settings)
        setEvents(loaded.events)
        setEstimate(next)
        await syncNeedEstimate(next)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [mpg, mpgBasis])

  useEffect(() => {
    return onRefuelRecorded(() => {
      void refresh()
    })
  }, [refresh])

  async function handleQuickRefuel(now = new Date()) {
    setBusy(true)
    try {
      await recordRefuel(now, {
        fuelType: prefs.fuelType,
        gallons: prefs.gallons || settings.typicalGallons,
      })
      await refresh(now)
    } finally {
      setBusy(false)
    }
  }

  async function handleSaveSettings(next: FuelAssistantSettings, now = new Date()) {
    setSettings(next)
    await saveFuelAssistantSettings(next)
    const value = estimateNeed(events, next, mpg, now, mpgBasis)
    setEstimate(value)
    await syncNeedEstimate(value)
  }

  function openCreateModal() {
    setEditingId(null)
    setDraftAt(toDatetimeLocal(new Date()))
    setDraftStation('')
    setDraftAddress('')
    setDraftFuelType(prefs.fuelType ?? 'regular')
    setDraftPrice('')
    setDraftGallons(String(prefs.gallons || settings.typicalGallons || 10))
    setDraftCost('')
    setDraftNotes('')
    setModalOpen(true)
  }

  function openEditModal(event: RefuelEvent) {
    setEditingId(event.id)
    setDraftAt(toDatetimeLocal(event.at))
    setDraftStation(event.stationName ?? '')
    setDraftAddress(event.stationAddress ?? '')
    setDraftFuelType(event.fuelType ?? prefs.fuelType ?? 'regular')
    setDraftPrice(event.pricePerGallon != null ? String(event.pricePerGallon) : '')
    setDraftGallons(event.gallons != null ? String(event.gallons) : '')
    setDraftCost(event.cost != null ? String(event.cost) : '')
    setDraftNotes(event.notes ?? '')
    setModalOpen(true)
  }

  function handlePriceOrGallonsChange(nextPrice: string, nextGallons: string) {
    setDraftPrice(nextPrice)
    setDraftGallons(nextGallons)
    const p = parseFloat(nextPrice)
    const g = parseFloat(nextGallons)
    if (!isNaN(p) && !isNaN(g) && p > 0 && g > 0) {
      setDraftCost((p * g).toFixed(2))
    }
  }

  async function handleSaveModal() {
    const atDate = draftAt ? new Date(draftAt) : new Date()
    const validAt = isNaN(atDate.getTime()) ? new Date().toISOString() : atDate.toISOString()
    const numericPrice = draftPrice ? parseFloat(draftPrice) : undefined
    const numericGallons = draftGallons ? parseFloat(draftGallons) : undefined
    const numericCost = draftCost ? parseFloat(draftCost) : (numericPrice && numericGallons ? Number((numericPrice * numericGallons).toFixed(2)) : undefined)

    if (editingId) {
      await updateRefuel(editingId, {
        at: validAt,
        stationName: draftStation.trim() || undefined,
        stationAddress: draftAddress.trim() || undefined,
        fuelType: draftFuelType,
        pricePerGallon: numericPrice != null && !isNaN(numericPrice) ? numericPrice : undefined,
        gallons: numericGallons != null && !isNaN(numericGallons) ? numericGallons : undefined,
        cost: numericCost != null && !isNaN(numericCost) ? numericCost : undefined,
        notes: draftNotes.trim() || undefined,
      })
    } else {
      await recordRefuel(validAt, {
        stationName: draftStation.trim() || undefined,
        stationAddress: draftAddress.trim() || undefined,
        fuelType: draftFuelType,
        pricePerGallon: numericPrice != null && !isNaN(numericPrice) ? numericPrice : undefined,
        gallons: numericGallons != null && !isNaN(numericGallons) ? numericGallons : undefined,
        cost: numericCost != null && !isNaN(numericCost) ? numericCost : undefined,
        notes: draftNotes.trim() || undefined,
      })
    }

    setModalOpen(false)
    await refresh(new Date())
  }

  async function handleDelete(id: string) {
    if (window.confirm(t('refuel.confirmDelete'))) {
      await deleteRefuel(id)
      await refresh(new Date())
    }
  }

  const range =
    estimate.earliestDays == null
      ? t('assistant.unknown')
      : t('assistant.range', {
          start: estimate.earliestDays,
          end: estimate.latestDays ?? estimate.earliestDays,
        })
  const basis =
    estimate.basis === 'refuel_cadence'
      ? t('assistant.basis.cadence', { count: estimate.observations })
      : estimate.basis === 'epa_vehicle' && prefs.vehicle
      ? t('assistant.basis.epa', { vehicle: prefs.vehicle.label, mpg })
      : estimate.basis === 'manual_mpg' && mpg > 0
      ? t('assistant.basis.manual', { mpg })
      : t('assistant.basis.learning')

  return (
    <section aria-label={t('refuel.logTitle')} className="flex flex-col gap-6">
      {/* 1. Intelligent Fuel Timing Assistant card */}
      <div className="rounded-box border border-line bg-surface p-5 sm:p-6 shadow-sm flex flex-col gap-5">
        <div className="flex flex-col gap-1 border-b border-line pb-4">
          <div className="flex items-center gap-2">
            <SparkleIcon size={20} weight="fill" className="text-accent" />
            <h2 className="text-base font-bold text-ink sm:text-lg">{t('assistant.title')}</h2>
          </div>
          <p className="text-xs text-muted leading-relaxed">{t('assistant.description')}</p>
        </div>

        {/* Prediction summary pill */}
        <div className="rounded-control bg-sunken/80 border border-line/60 p-4 flex flex-col gap-1.5">
          <p className="text-base font-bold text-ink sm:text-lg">{range}</p>
          <p className="text-xs text-muted">{t(`assistant.confidence.${estimate.confidence}`)}</p>
          <p className="mt-1 text-xs font-medium text-accent">{basis}</p>
        </div>

        {/* Quick action buttons */}
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={busy}
            onClick={() => void handleQuickRefuel(new Date())}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-control bg-ink px-4 text-sm font-semibold text-surface transition hover:opacity-90 active:scale-[0.98] disabled:opacity-50 shadow-sm"
          >
            <GasPumpIcon size={18} weight="fill" />
            <span>{t('assistant.justFilled')}</span>
          </button>

          <Button
            variant="secondary"
            onClick={openCreateModal}
            className="min-h-11 gap-2 px-4 text-sm font-semibold shadow-xs"
          >
            <PlusIcon size={16} weight="bold" />
            <span>{t('refuel.addRecord')}</span>
          </Button>
        </div>

        <p className="text-xs text-muted">{t('assistant.refuelOptional')}</p>

        {/* Fine-tune parameters collapsible */}
        <details className="rounded-control border border-line p-3.5 text-xs text-muted">
          <summary className="cursor-pointer font-medium text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent">
            {t('assistant.tune')}
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1">
              <span>{t('assistant.weeklyMiles')}</span>
              <input
                type="number"
                min="10"
                max="2000"
                value={settings.weeklyMiles}
                onChange={(event) =>
                  void handleSaveSettings({ ...settings, weeklyMiles: Number(event.target.value) }, new Date())
                }
                className="h-11 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span>{t('assistant.typicalGallons')}</span>
              <input
                type="number"
                min="1"
                max="30"
                value={settings.typicalGallons}
                onChange={(event) =>
                  void handleSaveSettings({ ...settings, typicalGallons: Number(event.target.value) }, new Date())
                }
                className="h-11 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent"
              />
            </label>
          </div>
        </details>
      </div>

      {/* 2. Refuel History Section */}
      <div className="rounded-box border border-line bg-surface p-5 sm:p-6 shadow-sm flex flex-col gap-4">
        <div className="flex items-center justify-between border-b border-line pb-3">
          <div className="flex items-center gap-2">
            <GasPumpIcon size={20} weight="duotone" className="text-accent" />
            <h2 className="text-base font-bold text-ink sm:text-lg">
              {t('refuel.logTitle')} ({events.length})
            </h2>
          </div>
          <Button
            variant="ghost"
            onClick={openCreateModal}
            className="h-8 gap-1.5 px-2.5 text-xs font-semibold text-accent"
          >
            <PlusIcon size={14} weight="bold" />
            <span>{t('refuel.addRecord')}</span>
          </Button>
        </div>

        {events.length === 0 ? (
          <div className="rounded-control border border-dashed border-line bg-sunken/40 p-6 text-center text-xs text-muted leading-relaxed">
            <p className="font-semibold text-ink text-sm">{t('refuel.empty')}</p>
            <p className="mt-1 max-w-md mx-auto">{t('refuel.emptyHint')}</p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {events.map((event) => {
              const d = new Date(event.at)
              const formattedDate = new Intl.DateTimeFormat(locale, {
                dateStyle: 'medium',
                timeStyle: 'short',
              }).format(d)

              return (
                <article
                  key={event.id}
                  className="rounded-control border border-line/80 bg-surface p-4 flex flex-col gap-2.5 shadow-2xs hover:border-line transition"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-bold text-ink text-sm sm:text-base break-words">
                          {event.stationName || t('refuel.manualRecord')}
                        </h3>
                        {event.fuelType ? (
                          <span className="rounded-full bg-sunken border border-line/60 px-2 py-0.5 text-[10px] font-medium text-muted">
                            {t(fuelKey(event.fuelType as any))}
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-0.5 text-xs text-muted flex items-center gap-1.5">
                        <ClockIcon size={12} className="shrink-0" />
                        <span>{formattedDate}</span>
                      </p>
                      {event.stationAddress ? (
                        <p className="mt-0.5 text-xs text-faint truncate">{event.stationAddress}</p>
                      ) : null}
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        type="button"
                        onClick={() => openEditModal(event)}
                        aria-label={`${t('refuel.edit')} ${event.stationName ?? formattedDate}`}
                        className="grid size-8 place-items-center rounded-control text-muted hover:text-ink hover:bg-sunken transition"
                        title={t('refuel.edit')}
                      >
                        <NotePencilIcon size={16} />
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleDelete(event.id)}
                        aria-label={`${t('refuel.delete')} ${event.stationName ?? formattedDate}`}
                        className="grid size-8 place-items-center rounded-control text-muted hover:text-caution hover:bg-caution-soft transition"
                        title={t('refuel.delete')}
                      >
                        <TrashIcon size={16} />
                      </button>
                    </div>
                  </div>

                  {/* Badges for price, gallons, cost */}
                  {(event.pricePerGallon != null || event.gallons != null || event.cost != null) ? (
                    <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-line/50 text-xs">
                      {event.pricePerGallon != null ? (
                        <span className="rounded-md bg-sunken px-2 py-0.5 font-semibold text-ink num">
                          {perGallon(String(event.pricePerGallon))}/gal
                        </span>
                      ) : null}
                      {event.gallons != null ? (
                        <span className="rounded-md bg-sunken px-2 py-0.5 font-medium text-muted num">
                          {event.gallons} gal
                        </span>
                      ) : null}
                      {event.cost != null ? (
                        <span className="rounded-md bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 font-bold text-emerald-600 dark:text-emerald-400 num ml-auto">
                          {usd(event.cost)}
                        </span>
                      ) : null}
                    </div>
                  ) : null}

                  {event.notes ? (
                    <p className="text-xs text-muted italic bg-sunken/50 rounded p-1.5 break-words">
                      {event.notes}
                    </p>
                  ) : null}
                </article>
              )
            })}
          </div>
        )}
      </div>

      {/* 3. Add / Edit Modal Dialog */}
      {modalOpen ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="refuel-modal-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs"
        >
          <div className="relative w-full max-w-md rounded-box border border-line bg-surface p-5 sm:p-6 shadow-xl flex flex-col gap-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <h3 id="refuel-modal-title" className="text-base font-bold text-ink">
                {editingId ? t('refuel.editRecord') : t('refuel.addRecord')}
              </h3>
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="grid size-8 place-items-center rounded-control text-muted hover:text-ink"
                aria-label="Close"
              >
                <XIcon size={18} />
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault()
                void handleSaveModal()
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
                  onChange={(e) => setDraftAt(e.target.value)}
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
                  onChange={(e) => setDraftStation(e.target.value)}
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
                        setDraftStation(fav.name)
                        if (fav.address) setDraftAddress(fav.address)
                        if (fav.lastObservedPrice) {
                          handlePriceOrGallonsChange(String(fav.lastObservedPrice), draftGallons)
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
                    onChange={(e) => handlePriceOrGallonsChange(e.target.value, draftGallons)}
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
                    onChange={(e) => handlePriceOrGallonsChange(draftPrice, e.target.value)}
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
                  onChange={(e) => setDraftCost(e.target.value)}
                  className="h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent"
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="font-medium text-ink">{t('refuel.notes')}</span>
                <TextInput
                  value={draftNotes}
                  onChange={(e) => setDraftNotes(e.target.value)}
                  placeholder={t('refuel.notes')}
                  className="text-sm"
                />
              </label>

              <div className="mt-2 flex items-center justify-end gap-2 border-t border-line pt-3">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setModalOpen(false)}
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
      ) : null}
    </section>
  )
}
