import { GasPumpIcon, PlusIcon } from '@phosphor-icons/react'
import { useCallback, useEffect, useState } from 'react'
import { Button } from '../../components/ui'
import { useI18n } from '../../i18n'
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
import { FuelTimingAssistantCard } from './FuelTimingAssistantCard'
import { RefuelModal } from './RefuelModal'
import { RefuelRecordCard } from './RefuelRecordCard'

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
  const { t } = useI18n()
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
      void refresh(new Date())
    })
  }, [refresh])

  async function handleQuickRefuel(now = new Date()) {
    setBusy(true)
    try {
      await recordRefuel(now, {
        fuelType: prefs.fuelType,
        source: 'manual',
      })
      await refresh(now)
    } finally {
      setBusy(false)
    }
  }

  async function handleSaveSettings(next: FuelAssistantSettings, now = new Date()) {
    setSettings(next)
    await saveFuelAssistantSettings(next)
    await refresh(now, next)
  }

  function openCreateModal() {
    setEditingId(null)
    setDraftAt(toDatetimeLocal(new Date()))
    setDraftStation('')
    setDraftAddress('')
    setDraftFuelType(prefs.fuelType ?? 'regular')
    setDraftPrice('')
    setDraftGallons('')
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
    const atIso = draftAt ? new Date(draftAt).toISOString() : new Date().toISOString()
    const p = parseFloat(draftPrice)
    const g = parseFloat(draftGallons)
    const c = parseFloat(draftCost)

    const payload = {
      at: atIso,
      stationName: draftStation.trim() || undefined,
      stationAddress: draftAddress.trim() || undefined,
      fuelType: draftFuelType || undefined,
      pricePerGallon: !isNaN(p) && p > 0 ? p : undefined,
      gallons: !isNaN(g) && g > 0 ? g : undefined,
      cost: !isNaN(c) && c > 0 ? c : undefined,
      notes: draftNotes.trim() || undefined,
      source: 'manual' as const,
    }

    if (editingId) {
      await updateRefuel(editingId, payload)
    } else {
      await recordRefuel(new Date(atIso), payload)
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

  return (
    <section aria-label={t('refuel.logTitle')} className="flex flex-col gap-6">
      {/* 1. Intelligent Fuel Timing Assistant card */}
      <FuelTimingAssistantCard
        estimate={estimate}
        settings={settings}
        prefs={prefs}
        mpg={mpg}
        busy={busy}
        onQuickRefuel={handleQuickRefuel}
        onOpenCreate={openCreateModal}
        onSaveSettings={handleSaveSettings}
      />

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
            {events.map((event) => (
              <RefuelRecordCard
                key={event.id}
                event={event}
                onEdit={openEditModal}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>

      {/* 3. Add / Edit Modal Dialog */}
      <RefuelModal
        isOpen={modalOpen}
        isEditing={Boolean(editingId)}
        draftAt={draftAt}
        draftStation={draftStation}
        draftPrice={draftPrice}
        draftGallons={draftGallons}
        draftCost={draftCost}
        draftNotes={draftNotes}
        onClose={() => setModalOpen(false)}
        onSave={handleSaveModal}
        onChangeAt={setDraftAt}
        onChangeStation={setDraftStation}
        onChangeAddress={setDraftAddress}
        onChangePriceOrGallons={handlePriceOrGallonsChange}
        onChangeCost={setDraftCost}
        onChangeNotes={setDraftNotes}
      />
    </section>
  )
}
