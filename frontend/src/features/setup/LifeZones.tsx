import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { Button, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n'
import {
  calculateArbitrage,
  deleteLifeZone,
  loadLifeZones,
  saveLifeZone,
  type ArbitrageOpportunity,
  type LifeZone,
} from '../../lib/lifeZones'
import type { Prefs } from '../../lib/prefs'

export function LifeZones({ prefs, onSelect }: { prefs: Prefs; onSelect?: (zone: LifeZone) => void }) {
  const { t, locale } = useI18n()
  const [zones, setZones] = useState<LifeZone[]>([])
  const [addingKind, setAddingKind] = useState<'home' | 'work' | 'custom' | null>(null)
  const [queryText, setQueryText] = useState('')
  const [nameText, setNameText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reload = async () => {
    const list = await loadLifeZones()
    setZones(list)
  }

  useEffect(() => {
    let ignore = false
    void loadLifeZones().then(list => {
      if (!ignore) setZones(list)
    })
    return () => {
      ignore = true
    }
  }, [])

  const handleAdd = async (kind: 'home' | 'work' | 'custom') => {
    if (!queryText.trim()) return
    setBusy(true)
    setError(null)
    try {
      const res = await api.resolveLocation(queryText.trim(), locale)
      const locations = res.candidates
      if (!locations || !locations.length) {
        setError('location_not_found')
        return
      }
      const top = locations[0]
      const defaultName = kind === 'home' ? t('lifezones.home') : kind === 'work' ? t('lifezones.work') : queryText.trim()
      const newZone: LifeZone = {
        id: kind === 'custom' ? crypto.randomUUID() : kind,
        kind,
        name: nameText.trim() || defaultName,
        query: queryText.trim(),
        origin: top.location,
        radiusMiles: 5,
        updatedAt: new Date().toISOString(),
      }
      await saveLifeZone(newZone)
      await reload()
      setAddingKind(null)
      setQueryText('')
      setNameText('')
    } catch {
      setError('location_search_failed')
    } finally {
      setBusy(false)
    }
  }

  const handleDelete = async (id: string) => {
    setBusy(true)
    try {
      await deleteLifeZone(id)
      await reload()
    } finally {
      setBusy(false)
    }
  }

  // Cross-zone arbitrage check
  const homeZone = zones.find(z => z.kind === 'home')
  const workZone = zones.find(z => z.kind === 'work')
  const arbitrage: ArbitrageOpportunity | null = (homeZone && workZone)
    ? calculateArbitrage(homeZone, workZone, prefs.gallons, Number(prefs.vehicle?.combinedMpg ?? prefs.mpg ?? 25))
    : null

  const hasHome = Boolean(homeZone)
  const hasWork = Boolean(workZone)

  return (
    <section
      id="section-lifezones"
      className="grid grid-cols-1 gap-6 border-b border-line py-8 first:pt-0 last:border-b-0 lg:grid-cols-[280px_1fr] lg:gap-10 lg:py-10"
      aria-label={t('lifezones.title')}
    >
      <div className="flex flex-col gap-2 lg:pt-1">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-ink">{t('lifezones.title')}</h2>
          <span className="inline-flex items-center rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent">
            Zero-Knowledge
          </span>
        </div>
        <p className="text-[13px] leading-relaxed text-muted">{t('lifezones.description')}</p>
        <p className="mt-1 text-xs leading-relaxed text-accent font-medium">{t('lifezones.privacy')}</p>
      </div>

      <div className="liquid-panel rounded-box p-5 sm:p-6 flex flex-col gap-5 min-w-0">
        {/* Arbitrage Notice Card */}
        {arbitrage && arbitrage.isBeneficial ? (
          <div className="rounded-control border border-accent/30 bg-accent-soft/20 p-4">
            <h3 className="text-sm font-semibold text-accent">{t('lifezones.arbitrageTitle')}</h3>
            <p className="mt-1 text-xs text-ink leading-relaxed">
              {t('lifezones.arbitrageHint', {
                zone: arbitrage.toZone.name,
                diff: `$${arbitrage.priceDiff.toFixed(2)}`,
                detour: arbitrage.detourMiles.toString(),
                amount: `$${arbitrage.netSavings.toFixed(2)}`,
              })}
            </p>
          </div>
        ) : null}

        {/* Existing Zones */}
        <div className="flex flex-col gap-3">
          {zones.map((zone) => (
            <div
              key={zone.id}
              className="flex items-center justify-between gap-3 rounded-control border border-line bg-surface p-3.5"
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-xl">
                  {zone.kind === 'home' ? '🏠' : zone.kind === 'work' ? '💼' : '📍'}
                </span>
                <div className="flex flex-col min-w-0">
                  <span className="text-sm font-medium text-ink truncate">{zone.name}</span>
                  <span className="text-xs text-muted truncate">{zone.query} ({zone.origin.lat.toFixed(4)}, {zone.origin.lng.toFixed(4)})</span>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                {onSelect ? (
                  <button
                    type="button"
                    onClick={() => onSelect(zone)}
                    className="rounded-control px-2.5 py-1 text-xs font-medium text-accent hover:bg-accent-soft/30 transition"
                  >
                    {t('lifezones.quickSwitch')}
                  </button>
                ) : null}
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void handleDelete(zone.id)}
                  className="rounded-control px-2 py-1 text-xs text-muted hover:text-caution transition disabled:opacity-50"
                  aria-label={t('lifezones.delete')}
                >
                  {t('lifezones.delete')}
                </button>
              </div>
            </div>
          ))}

          {!zones.length ? (
            <p className="text-xs text-muted italic">{t('lifezones.empty')}</p>
          ) : null}
        </div>

        {/* Add Zone Controls */}
        {addingKind ? (
          <div className="rounded-control border border-line bg-sunken p-4 flex flex-col gap-3">
            <h4 className="text-xs font-semibold text-ink">
              {addingKind === 'home' ? t('lifezones.home') : addingKind === 'work' ? t('lifezones.work') : t('lifezones.custom')}
            </h4>
            <div className="grid gap-2 sm:grid-cols-2">
              <TextInput
                value={nameText}
                placeholder={addingKind === 'home' ? '🏠 住家 (如 90015)' : addingKind === 'work' ? '💼 公司 (如 90007)' : '自訂名稱'}
                onChange={(e) => setNameText(e.target.value)}
              />
              <TextInput
                value={queryText}
                placeholder={t('lifezones.inputPlaceholder')}
                onChange={(e) => setQueryText(e.target.value)}
              />
            </div>
            {error ? <p className="text-xs text-caution">{error}</p> : null}
            <div className="flex items-center gap-2 justify-end">
              <Button variant="ghost" onClick={() => { setAddingKind(null); setError(null) }}>
                Cancel
              </Button>
              <Button disabled={busy || !queryText.trim()} onClick={() => void handleAdd(addingKind)}>
                {t('lifezones.add')}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-line">
            {!hasHome ? (
              <Button variant="secondary" onClick={() => { setAddingKind('home'); setNameText('🏠 住家 (90015)'); setQueryText('90015') }}>
                + {t('lifezones.home')}
              </Button>
            ) : null}
            {!hasWork ? (
              <Button variant="secondary" onClick={() => { setAddingKind('work'); setNameText('💼 公司 (90007)'); setQueryText('90007') }}>
                + {t('lifezones.work')}
              </Button>
            ) : null}
            {zones.length < 3 ? (
              <Button variant="ghost" onClick={() => { setAddingKind('custom'); setNameText(''); setQueryText('') }}>
                + {t('lifezones.custom')}
              </Button>
            ) : null}
          </div>
        )}
      </div>
    </section>
  )
}
