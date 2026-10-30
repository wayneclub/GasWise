import {
  CaretDownIcon,
  CoinsIcon,
  GasPumpIcon,
  HeartIcon,
  NavigationArrowIcon,
  NotePencilIcon,
  ShieldCheckIcon,
  TrendUpIcon,
  TrashIcon,
} from '@phosphor-icons/react'
import { useMemo, useState } from 'react'
import { CopyAddress } from '../../components/CopyAddress'
import { Select } from '../../components/Select'
import { Button, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n'
import { fuelKey, perGallon, usd } from '../../lib/format'
import { navigationUrl } from '../../lib/navigation'
import type { Prefs } from '../../lib/prefs'
import { useFavorites, type FavoriteStation } from '../../lib/favorites'
import { PriceHistory } from '../decide/PriceHistory'
import { TopTierBadge } from '../decide/StationDetails'

type SortOption = 'price' | 'recent' | 'name'

export function MyPage({
  prefs,
  onNavigateToFuel,
}: {
  prefs: Prefs
  onNavigateToFuel: () => void
}) {
  const { t } = useI18n()
  const { favorites, remove, updateNotes } = useFavorites()
  const [sort, setSort] = useState<SortOption>('price')
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null)
  const [noteDraft, setNoteDraft] = useState('')
  const [expandedHistoryId, setExpandedHistoryId] = useState<string | null>(null)

  // Parse stations with numeric prices for analytics
  const pricedStations = useMemo(() => {
    return favorites
      .map((s) => {
        const raw = s.lastObservedPrice ?? (s as any).price_per_gallon
        return {
          ...s,
          numericPrice: raw ? Number(raw) : null,
        }
      })
      .filter((s): s is typeof s & { numericPrice: number } => s.numericPrice !== null && Number.isFinite(s.numericPrice) && s.numericPrice > 0)
  }, [favorites])

  // Price analytics metrics
  const analytics = useMemo(() => {
    if (pricedStations.length === 0) return null
    const prices = pricedStations.map((s) => s.numericPrice)
    const minPrice = Math.min(...prices)
    const maxPrice = Math.max(...prices)
    const sum = prices.reduce((acc, p) => acc + p, 0)
    const avgPrice = sum / prices.length
    const spread = maxPrice - minPrice
    const lowestStation = pricedStations.find((s) => s.numericPrice === minPrice)!
    const highestStation = pricedStations.find((s) => s.numericPrice === maxPrice)!
    const gallons = prefs.gallons || 10
    const maxSavings = spread * gallons

    // Check if there is a TOP TIER station close to min price
    const topTierStation = pricedStations.find(
      (s) => s.topTierBrand && s.numericPrice > minPrice && s.numericPrice - minPrice <= 0.08,
    )

    return {
      minPrice,
      maxPrice,
      avgPrice,
      spread,
      lowestStation,
      highestStation,
      gallons,
      maxSavings,
      topTierStation,
    }
  }, [pricedStations, prefs.gallons])

  // Sorted list for display
  const sortedFavorites = useMemo(() => {
    const list = [...favorites]
    if (sort === 'price') {
      return list.sort((a, b) => {
        const pa = a.lastObservedPrice ? Number(a.lastObservedPrice) : Infinity
        const pb = b.lastObservedPrice ? Number(b.lastObservedPrice) : Infinity
        return pa - pb
      })
    }
    if (sort === 'name') {
      return list.sort((a, b) => a.name.localeCompare(b.name))
    }
    // recent
    return list.sort((a, b) => Date.parse(b.addedAt) - Date.parse(a.addedAt))
  }, [favorites, sort])

  const startEditNote = (station: FavoriteStation) => {
    setEditingNoteId(station.id)
    setNoteDraft(station.notes ?? '')
  }

  const saveNote = async (id: string) => {
    await updateNotes(id, noteDraft)
    setEditingNoteId(null)
  }

  return (
    <main
      aria-label={t('favorites.myTitle')}
      className="mx-auto w-full max-w-md px-4 pb-16 pt-6 sm:max-w-2xl sm:px-6 lg:max-w-5xl"
    >
      {/* Header */}
      <div className="mb-6 flex flex-col gap-1 border-b border-line pb-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="grid size-10 place-items-center rounded-2xl bg-rose-500/10 text-rose-500">
              <HeartIcon size={22} weight="fill" />
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-ink sm:text-3xl">
              {t('favorites.myTitle')}
            </h1>
          </div>
          <span className="rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-muted">
            {t('favorites.count', { count: favorites.length })}
          </span>
        </div>
        <p className="mt-1 text-xs text-muted leading-relaxed">
          {t('favorites.description')}
        </p>
      </div>

      {favorites.length === 0 ? (
        /* Empty State */
        <div className="rounded-box border border-dashed border-line bg-surface/50 p-8 text-center sm:p-12">
          <span className="mx-auto mb-4 grid size-16 place-items-center rounded-3xl bg-rose-500/10 text-rose-500">
            <HeartIcon size={32} weight="duotone" />
          </span>
          <h2 className="text-lg font-semibold text-ink sm:text-xl">
            {t('favorites.empty')}
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted leading-relaxed">
            {t('favorites.emptyHint')}
          </p>
          <div className="mt-6 flex justify-center">
            <Button
              variant="primary"
              onClick={onNavigateToFuel}
              className="min-h-12 gap-2 px-6 text-sm font-semibold"
            >
              <GasPumpIcon size={18} weight="fill" />
              <span>{t('favorites.goSearch')}</span>
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          {/* Price Analytics Section */}
          {analytics ? (
            <section
              aria-label={t('favorites.analyticsTitle')}
              className="rounded-box border border-line bg-surface p-5 sm:p-6 shadow-sm"
            >
              <div className="flex items-center gap-2 mb-4">
                <TrendUpIcon size={20} weight="bold" className="text-accent" />
                <h2 className="text-base font-semibold text-ink sm:text-lg">
                  {t('favorites.analyticsTitle')}
                </h2>
              </div>

              {/* 4 Stat Cards */}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-control bg-accent-soft/40 border border-accent/20 p-3.5 flex flex-col justify-between">
                  <span className="text-xs font-medium text-muted">{t('favorites.lowestPrice')}</span>
                  <div className="mt-1">
                    <span className="num text-2xl font-bold text-accent">
                      {perGallon(String(analytics.minPrice))}
                    </span>
                    <span className="block truncate text-[11px] text-ink font-medium mt-0.5" title={analytics.lowestStation.name}>
                      {analytics.lowestStation.name}
                    </span>
                  </div>
                </div>

                <div className="rounded-control bg-sunken p-3.5 flex flex-col justify-between">
                  <span className="text-xs font-medium text-muted">{t('favorites.averagePrice')}</span>
                  <div className="mt-1">
                    <span className="num text-2xl font-semibold text-ink">
                      {perGallon(analytics.avgPrice.toFixed(3))}
                    </span>
                    <span className="block text-[11px] text-muted mt-0.5">
                      {pricedStations.length} {t('list.station')}
                    </span>
                  </div>
                </div>

                <div className="rounded-control bg-sunken p-3.5 flex flex-col justify-between">
                  <span className="text-xs font-medium text-muted">{t('favorites.spread')}</span>
                  <div className="mt-1">
                    <span className="num text-2xl font-semibold text-ink">
                      {analytics.spread > 0 ? usd(analytics.spread) : '$0.00'}
                    </span>
                    <span className="block text-[11px] text-muted mt-0.5">
                      /gal
                    </span>
                  </div>
                </div>

                <div className="rounded-control bg-emerald-500/10 border border-emerald-500/20 p-3.5 flex flex-col justify-between">
                  <span className="text-xs font-medium text-muted">{t('favorites.maxSavings')}</span>
                  <div className="mt-1">
                    <span className="num text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                      {usd(analytics.maxSavings)}
                    </span>
                    <span className="block text-[11px] text-muted mt-0.5">
                      {analytics.gallons} gal
                    </span>
                  </div>
                </div>
              </div>

              {/* Insights banner */}
              {analytics.spread >= 0.05 ? (
                <div className="mt-4 rounded-control bg-accent-soft/30 border border-accent/30 p-3 text-xs leading-relaxed text-ink flex items-start gap-2.5">
                  <CoinsIcon size={18} weight="fill" className="text-accent shrink-0 mt-0.5" />
                  <p>
                    {t('favorites.savingsNotice', {
                      gallons: String(analytics.gallons),
                      station: analytics.lowestStation.name,
                      amount: usd(analytics.maxSavings),
                    })}
                  </p>
                </div>
              ) : null}

              {analytics.topTierStation ? (
                <div className="mt-3 rounded-control bg-sunken p-3 text-xs leading-relaxed text-ink flex items-start gap-2.5">
                  <ShieldCheckIcon size={18} weight="fill" className="text-accent shrink-0 mt-0.5" />
                  <p>
                    {t('favorites.topTierNotice', {
                      station: analytics.topTierStation.name,
                      diff: usd(analytics.topTierStation.numericPrice - analytics.minPrice),
                    })}
                  </p>
                </div>
              ) : null}

              {/* Visual Price Comparison Bars */}
              {pricedStations.length >= 2 ? (
                <div className="mt-6 border-t border-line pt-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-muted mb-3">
                    {t('favorites.priceComparison')}
                  </h3>
                  <div className="flex flex-col gap-3">
                    {pricedStations
                      .sort((a, b) => a.numericPrice - b.numericPrice)
                      .map((station) => {
                        const diff = station.numericPrice - analytics.minPrice
                        const isLowest = diff === 0
                        const ratio = Math.min(
                          100,
                          analytics.spread > 0
                            ? 35 + ((station.numericPrice - analytics.minPrice) / analytics.spread) * 65
                            : 50,
                        )
                        return (
                          <div key={station.id} className="flex flex-col gap-1 text-xs">
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-1.5 min-w-0">
                                <span className={`font-medium truncate ${isLowest ? 'text-accent font-semibold' : 'text-ink'}`}>
                                  {station.name}
                                </span>
                                {station.topTierBrand ? (
                                  <TopTierBadge brand={station.topTierBrand} />
                                ) : null}
                              </div>
                              <div className="flex items-center gap-2 shrink-0">
                                {diff > 0 ? (
                                  <span className="text-muted text-[11px] num">
                                    +{usd(diff)}
                                  </span>
                                ) : (
                                  <span className="rounded-full bg-accent-soft px-1.5 py-0 text-[10px] font-semibold text-accent">
                                    {t('comparison.lowestCost')}
                                  </span>
                                )}
                                <span className="font-semibold num text-ink text-sm">
                                  {perGallon(String(station.numericPrice))}
                                </span>
                              </div>
                            </div>
                            <div className="h-2 w-full rounded-full bg-sunken overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all duration-300 ${
                                  isLowest ? 'bg-accent' : diff < 0.15 ? 'bg-amber-500' : 'bg-muted/70'
                                }`}
                                style={{ width: `${ratio}%` }}
                              />
                            </div>
                          </div>
                        )
                      })}
                  </div>
                </div>
              ) : null}
            </section>
          ) : null}

          {/* Stations List Section */}
          <section
            aria-label={t('favorites.title')}
            className="flex flex-col gap-4"
          >
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="text-lg font-semibold text-ink">
                {t('favorites.title')} ({favorites.length})
              </h2>
              {favorites.length > 1 ? (
                <div className="w-full sm:w-48">
                  <Select<SortOption>
                    label={t('comparison.sort')}
                    value={sort}
                    onChange={setSort}
                    options={[
                      { value: 'price', label: t('favorites.sortPrice') },
                      { value: 'recent', label: t('favorites.sortRecent') },
                      { value: 'name', label: t('favorites.sortName') },
                    ]}
                  />
                </div>
              ) : null}
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-1">
              {sortedFavorites.map((station) => {
                const navUrl = navigationUrl(prefs.navApp, station.location.lat, station.location.lng)
                const isHistoryExpanded = expandedHistoryId === station.id
                return (
                  <article
                    key={station.id}
                    className="rounded-box border border-line bg-surface p-4 sm:p-5 flex flex-col gap-3 transition shadow-sm hover:border-line/80"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <h3 className="font-semibold text-ink text-base break-words">
                            {station.name}
                          </h3>
                          {station.topTierBrand ? (
                            <TopTierBadge brand={station.topTierBrand} />
                          ) : null}
                        </div>
                        {station.address ? (
                          <CopyAddress
                            address={station.address}
                            className="mt-1 w-full text-xs text-muted"
                          />
                        ) : null}
                      </div>

                      <button
                        type="button"
                        onClick={() => remove(station.id)}
                        aria-label={`${t('favorites.remove')} ${station.name}`}
                        className="grid size-9 shrink-0 place-items-center rounded-control text-muted hover:text-caution hover:bg-caution-soft transition"
                        title={t('favorites.remove')}
                      >
                        <TrashIcon size={18} />
                      </button>
                    </div>

                    {station.lastObservedPrice || (station as any).price_per_gallon ? (
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm border-t border-line/60 pt-2.5">
                        <div className="flex items-baseline gap-1">
                          <span className="text-xl font-bold num text-ink">
                            {perGallon(String(station.lastObservedPrice ?? (station as any).price_per_gallon))}
                          </span>
                          {station.fuelType ? (
                            <span className="text-xs text-muted">
                              · {t(fuelKey(station.fuelType as any))}
                            </span>
                          ) : null}
                        </div>
                      </div>
                    ) : null}

                    {/* Private Notes */}
                    <div className="rounded-control bg-sunken/70 p-2.5 text-xs">
                      {editingNoteId === station.id ? (
                        <div className="flex flex-col gap-2">
                          <TextInput
                            value={noteDraft}
                            onChange={(e) => setNoteDraft(e.target.value)}
                            placeholder={t('favorites.notesPlaceholder')}
                            className="text-xs"
                            autoFocus
                          />
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              variant="ghost"
                              className="h-7 px-2 text-xs"
                              onClick={() => setEditingNoteId(null)}
                            >
                              {t('favorites.cancel')}
                            </Button>
                            <Button
                              variant="primary"
                              className="h-7 px-3 text-xs"
                              onClick={() => saveNote(station.id)}
                            >
                              {t('favorites.saveNotes')}
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-muted leading-relaxed italic break-words flex-1">
                            {station.notes ? (
                              station.notes
                            ) : (
                              <span className="opacity-60">{t('favorites.notesPlaceholder')}</span>
                            )}
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

                    {/* Actions & Price History Toggle */}
                    <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-line/60">
                      {station.source && station.fuelType ? (
                        <button
                          type="button"
                          onClick={() => setExpandedHistoryId(isHistoryExpanded ? null : station.id)}
                          className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-ink transition"
                        >
                          <TrendUpIcon size={15} className="text-accent" />
                          <span>{t('favorites.viewHistory')}</span>
                          <CaretDownIcon
                            size={14}
                            className={`transition-transform ${isHistoryExpanded ? 'rotate-180' : ''}`}
                          />
                        </button>
                      ) : <span />}

                      <a
                        href={navUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-control min-h-9 border border-line px-3.5 text-xs font-medium text-ink hover:bg-sunken transition active:scale-[0.98]"
                      >
                        <NavigationArrowIcon size={14} weight="fill" className="text-accent" />
                        <span>{t('favorites.navigate')}</span>
                      </a>
                    </div>

                    {/* Price History Component if open */}
                    {isHistoryExpanded ? (
                      <div className="mt-2 pt-2 border-t border-line">
                        <PriceHistory
                          station={{
                            id: station.stationId,
                            source: station.source as any,
                            canonical_id: station.canonicalId,
                            fuel_type: station.fuelType as any,
                            name: station.name,
                            location: station.location,
                          }}
                        />
                      </div>
                    ) : null}
                  </article>
                )
              })}
            </div>
          </section>
        </div>
      )}
    </main>
  )
}
