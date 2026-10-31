import {
  CaretDownIcon,
  CoinsIcon,
  GasPumpIcon,
  HeartIcon,
  NavigationArrowIcon,
  NotePencilIcon,
  ShieldCheckIcon,
  SparkleIcon,
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
import { MultiStationPriceChart, type TrendAnalysisSummary } from './MultiStationPriceChart'
import { SmartFuelAdvisor } from './SmartFuelAdvisor'
import { RefuelLog } from './RefuelLog'
import { GarageSection } from './GarageSection'
import { recordStationRefuel } from '../../lib/fuelAssistant'

type SortOption = 'price' | 'recent' | 'name'

export function MyPage({
  prefs,
  update = () => {},
  onNavigateToFuel,
}: {
  prefs: Prefs
  update?: (change: Partial<Prefs>) => void
  onNavigateToFuel: () => void
}) {
  const { t } = useI18n()
  const { favorites, remove, updateNotes } = useFavorites()
  const [sort, setSort] = useState<SortOption>('price')
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null)
  const [noteDraft, setNoteDraft] = useState('')
  const [expandedHistoryId, setExpandedHistoryId] = useState<string | null>(null)
  const [trendSummary, setTrendSummary] = useState<TrendAnalysisSummary | null>(null)

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

    // Top tier vs standard comparison
    const topTierStations = pricedStations.filter((s) => Boolean(s.topTierBrand))
    const standardStations = pricedStations.filter((s) => !s.topTierBrand)
    const topTierAvg = topTierStations.length > 0
      ? topTierStations.reduce((acc, s) => acc + s.numericPrice, 0) / topTierStations.length
      : null
    const standardAvg = standardStations.length > 0
      ? standardStations.reduce((acc, s) => acc + s.numericPrice, 0) / standardStations.length
      : null

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
      topTierStations,
      standardStations,
      topTierAvg,
      standardAvg,
    }
  }, [pricedStations, prefs.gallons])

  // Sorted list for display
  const sortedFavorites = useMemo(() => {
    const list = [...favorites]
    if (sort === 'price') {
      return list.sort((a, b) => {
        const pa = a.lastObservedPrice ?? (a as any).price_per_gallon ? Number(a.lastObservedPrice ?? (a as any).price_per_gallon) : Infinity
        const pb = b.lastObservedPrice ?? (b as any).price_per_gallon ? Number(b.lastObservedPrice ?? (b as any).price_per_gallon) : Infinity
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
      className="mx-auto w-full max-w-md px-4 pb-20 pt-6 sm:max-w-2xl sm:px-6 lg:max-w-5xl"
    >
      {/* 1. Vehicle Garage Command Hub */}
      <div className="mb-8">
        <GarageSection prefs={prefs} update={update} />
      </div>

      {/* 2. Intelligent Fuel Timing & Refuel Records */}
      <div className="mb-8">
        <RefuelLog prefs={prefs} />
      </div>

      {favorites.length === 0 ? (
        /* Empty State */
        <div className="rounded-box border border-dashed border-line bg-surface/50 p-8 text-center sm:p-14">
          <div className="mx-auto mb-4 grid size-16 place-items-center rounded-3xl bg-rose-500/10 text-rose-500">
            <HeartIcon size={32} weight="duotone" />
          </div>
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
              className="min-h-12 gap-2 px-6 text-sm font-semibold shadow-sm"
            >
              <GasPumpIcon size={18} weight="fill" />
              <span>{t('favorites.goSearch')}</span>
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          {/* 2. Fuel Price Analytics Dashboard */}
          {analytics ? (
            <section
              aria-label={t('favorites.analyticsTitle')}
              className="rounded-box border border-line bg-surface p-5 sm:p-6 shadow-sm flex flex-col gap-6"
            >
              <div className="flex items-center justify-between border-b border-line pb-3">
                <div className="flex items-center gap-2">
                  <TrendUpIcon size={22} weight="bold" className="text-accent" />
                  <h2 className="text-base font-bold text-ink sm:text-lg">
                    {t('favorites.analyticsTitle')}
                  </h2>
                </div>
                <span className="text-xs text-muted">
                  {pricedStations.length} {t('list.station')}
                </span>
              </div>

              {/* 4 Stat Cards */}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-control bg-accent-soft/50 border border-accent/30 p-4 flex flex-col justify-between">
                  <span className="text-xs font-medium text-muted">{t('favorites.lowestPrice')}</span>
                  <div className="mt-2">
                    <span className="num text-2xl font-bold text-accent sm:text-3xl">
                      {perGallon(String(analytics.minPrice))}
                    </span>
                    <span className="block truncate text-xs text-ink font-semibold mt-1" title={analytics.lowestStation.name}>
                      {analytics.lowestStation.name}
                    </span>
                  </div>
                </div>

                <div className="rounded-control bg-sunken p-4 flex flex-col justify-between">
                  <span className="text-xs font-medium text-muted">{t('favorites.averagePrice')}</span>
                  <div className="mt-2">
                    <span className="num text-2xl font-bold text-ink sm:text-3xl">
                      {perGallon(analytics.avgPrice.toFixed(3))}
                    </span>
                    <span className="block text-xs text-muted mt-1">
                      {t('favorites.pricePerGallon')}
                    </span>
                  </div>
                </div>

                <div className="rounded-control bg-sunken p-4 flex flex-col justify-between">
                  <span className="text-xs font-medium text-muted">{t('favorites.spread')}</span>
                  <div className="mt-2">
                    <span className="num text-2xl font-bold text-ink sm:text-3xl">
                      {analytics.spread > 0 ? usd(analytics.spread) : '$0.00'}
                    </span>
                    <span className="block text-xs text-muted mt-1">
                      {analytics.spread > 0 ? `Max - Min` : t('comparison.lowestCost')}
                    </span>
                  </div>
                </div>

                <div className="rounded-control bg-emerald-500/10 border border-emerald-500/25 p-4 flex flex-col justify-between">
                  <span className="text-xs font-medium text-emerald-800 dark:text-emerald-300 font-semibold">{t('favorites.maxSavings')}</span>
                  <div className="mt-2">
                    <span className="num text-2xl font-bold text-emerald-600 dark:text-emerald-400 sm:text-3xl">
                      {usd(analytics.maxSavings)}
                    </span>
                    <span className="block text-xs text-muted mt-1">
                      / {analytics.gallons} gal fill
                    </span>
                  </div>
                </div>
              </div>

              {/* Smart Savings Insight Banner */}
              {analytics.spread >= 0.05 ? (
                <div className="rounded-control bg-accent-soft/30 border border-accent/40 p-3.5 text-xs leading-relaxed text-ink flex items-start gap-3">
                  <CoinsIcon size={20} weight="fill" className="text-accent shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold text-ink text-sm">
                      {t('favorites.savingsNotice', {
                        gallons: String(analytics.gallons),
                        station: analytics.lowestStation.name,
                        amount: usd(analytics.maxSavings),
                      })}
                    </p>
                  </div>
                </div>
              ) : null}

              {/* 3. Price Distribution Spectrum (Horizontal Gauge) */}
              {pricedStations.length >= 2 ? (
                <div className="rounded-control bg-sunken/60 border border-line p-4 flex flex-col gap-3">
                  <div className="flex items-center justify-between text-xs font-semibold text-ink">
                    <div className="flex items-center gap-1.5">
                      <SparkleIcon size={16} weight="fill" className="text-accent" />
                      <span>{t('favorites.spectrumTitle')}</span>
                    </div>
                    <span className="text-muted font-normal text-[11px]">
                      {t('favorites.averagePrice')}: {perGallon(analytics.avgPrice.toFixed(2))}
                    </span>
                  </div>

                  {/* Spectrum Bar with Station Nodes */}
                  <div className="relative pt-6 pb-4">
                    {/* Background Track with Color Gradient */}
                    <div className="h-3 w-full rounded-full bg-gradient-to-r from-emerald-500 via-amber-400 to-rose-500 opacity-90 shadow-inner" />

                    {/* Average price reference dashed line */}
                    {analytics.spread > 0 ? (
                      <div
                        className="absolute top-2 bottom-1 w-0.5 border-l-2 border-dashed border-ink/40 z-0"
                        style={{
                          left: `${((analytics.avgPrice - analytics.minPrice) / analytics.spread) * 100}%`,
                        }}
                        title={`Average: ${perGallon(analytics.avgPrice.toFixed(2))}`}
                      />
                    ) : null}

                    {/* Station Pin Markers */}
                    {pricedStations.map((station) => {
                      const pos = analytics.spread > 0
                        ? ((station.numericPrice - analytics.minPrice) / analytics.spread) * 100
                        : 50
                      const isMin = station.numericPrice === analytics.minPrice
                      const isMax = station.numericPrice === analytics.maxPrice

                      return (
                        <div
                          key={station.id}
                          className="absolute top-0 -translate-x-1/2 flex flex-col items-center group cursor-pointer"
                          style={{ left: `${Math.max(4, Math.min(96, pos))}%` }}
                        >
                          <span
                            className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold shadow-sm whitespace-nowrap transition-transform group-hover:scale-110 ${
                              isMin
                                ? 'bg-emerald-600 text-white'
                                : isMax
                                ? 'bg-rose-600 text-white'
                                : 'bg-surface border border-line text-ink'
                            }`}
                          >
                            {perGallon(String(station.numericPrice))}
                          </span>
                          <div
                            className={`size-2.5 rounded-full border-2 border-surface shadow-sm mt-0.5 ${
                              isMin
                                ? 'bg-emerald-600'
                                : isMax
                                ? 'bg-rose-600'
                                : 'bg-amber-500'
                            }`}
                          />
                          <span className="hidden group-hover:block absolute top-7 text-[10px] font-medium text-ink bg-surface border border-line px-1.5 py-0.5 rounded shadow-md z-10 whitespace-nowrap">
                            {station.name}
                          </span>
                        </div>
                      )
                    })}
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-muted px-1">
                    <span>{t('favorites.lowestPrice')}: {perGallon(String(analytics.minPrice))}</span>
                    <span>{t('favorites.spread')}: {usd(analytics.spread)}</span>
                    <span>Max: {perGallon(String(analytics.maxPrice))}</span>
                  </div>
                </div>
              ) : null}

              {/* 4. Full Tank Cost Comparison (Waterfall / Bars) */}
              {pricedStations.length >= 2 ? (
                <div className="flex flex-col gap-3 border-t border-line pt-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-muted">
                      {t('favorites.tankCostTitle')} ({analytics.gallons} gal)
                    </h3>
                  </div>

                  <div className="flex flex-col gap-2.5">
                    {pricedStations
                      .sort((a, b) => a.numericPrice - b.numericPrice)
                      .map((station) => {
                        const cost = station.numericPrice * analytics.gallons
                        const minCost = analytics.minPrice * analytics.gallons
                        const diffCost = cost - minCost
                        const isLowest = diffCost === 0

                        return (
                          <div
                            key={station.id}
                            className="rounded-control bg-sunken/40 border border-line/60 p-3 flex flex-col gap-2 text-xs"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-2 min-w-0">
                                <span className="font-semibold text-ink text-sm truncate">
                                  {station.name}
                                </span>
                                {station.topTierBrand ? (
                                  <TopTierBadge brand={station.topTierBrand} />
                                ) : null}
                              </div>
                              <div className="flex items-center gap-2 shrink-0">
                                {isLowest ? (
                                  <span className="rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                                    {t('favorites.baseline')}
                                  </span>
                                ) : (
                                  <span className="rounded-full bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 text-[11px] font-semibold text-amber-700 dark:text-amber-400">
                                    {t('favorites.overpay', { amount: usd(diffCost) })}
                                  </span>
                                )}
                                <span className="font-bold text-ink num text-sm">
                                  {usd(cost)}
                                </span>
                              </div>
                            </div>

                            {/* Bar comparison */}
                            <div className="h-2 w-full rounded-full bg-sunken overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all duration-300 ${
                                  isLowest
                                    ? 'bg-emerald-500'
                                    : diffCost < 3
                                    ? 'bg-amber-500'
                                    : 'bg-rose-500'
                                }`}
                                style={{
                                  width: `${Math.min(100, Math.max(15, (cost / (analytics.maxPrice * analytics.gallons)) * 100))}%`,
                                }}
                              />
                            </div>
                          </div>
                        )
                      })}
                  </div>
                </div>
              ) : null}

              {/* 5. Quality vs Value Assessment (Top Tier Matrix) */}
              {analytics.topTierStations.length > 0 && analytics.standardStations.length > 0 && analytics.topTierAvg && analytics.standardAvg ? (
                <div className="rounded-control bg-surface border border-line p-4 flex flex-col gap-2 text-xs">
                  <div className="flex items-center gap-2 font-semibold text-ink">
                    <ShieldCheckIcon size={18} weight="fill" className="text-accent" />
                    <span>{t('favorites.qualityTitle')}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 mt-1">
                    <div className="rounded-control bg-accent-soft/30 p-2.5">
                      <span className="block text-[11px] text-muted">
                        {t('favorites.topTierAvg', { price: perGallon(analytics.topTierAvg.toFixed(2)) })}
                      </span>
                      <span className="font-semibold text-accent num">
                        {analytics.topTierStations.length} {t('list.station')}
                      </span>
                    </div>
                    <div className="rounded-control bg-sunken p-2.5">
                      <span className="block text-[11px] text-muted">
                        {t('favorites.standardAvg', { price: perGallon(analytics.standardAvg.toFixed(2)) })}
                      </span>
                      <span className="font-semibold text-ink num">
                        {analytics.standardStations.length} {t('list.station')}
                      </span>
                    </div>
                  </div>
                  <p className="mt-1 text-muted leading-relaxed">
                    {analytics.lowestStation.topTierBrand
                      ? t('favorites.qualityAdviceWin')
                      : t('favorites.qualityAdvicePremium', {
                          diff: usd(Math.max(0, analytics.topTierAvg - analytics.minPrice)),
                          tankDiff: usd(Math.max(0, (analytics.topTierAvg - analytics.minPrice) * analytics.gallons)),
                        })}
                  </p>
                </div>
              ) : null}
            </section>
          ) : null}

          {/* 3. Smart Fuel Recommendations & AI Advisor */}
          {analytics ? (
            <SmartFuelAdvisor
              analytics={analytics}
              trendSummary={trendSummary}
              vehicleSummary={prefs.vehicle ? prefs.vehicle.label : null}
            />
          ) : null}

          {/* 4. Multi-Station Historical Fuel Price Continuous Chart */}
          <MultiStationPriceChart
            favorites={favorites}
            fuelType={(prefs.fuelType as any) || 'regular'}
            onTrendAnalysis={setTrendSummary}
          />

          {/* 5. Stations List Section */}
          <section
            aria-label={t('favorites.title')}
            className="flex flex-col gap-4"
          >
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="text-lg font-bold text-ink">
                {t('favorites.title')} ({favorites.length})
              </h2>
              {favorites.length > 1 ? (
                <div className="w-full sm:w-52">
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
                const price = station.lastObservedPrice ?? (station as any).price_per_gallon
                const numeric = price ? Number(price) : null
                const isLowest = analytics && numeric === analytics.minPrice

                return (
                  <article
                    key={station.id}
                    className="rounded-box border border-line bg-surface p-4 sm:p-5 flex flex-col gap-3.5 transition shadow-sm hover:border-line/90"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="font-bold text-ink text-base sm:text-lg break-words">
                            {station.name}
                          </h3>
                          {station.topTierBrand ? (
                            <TopTierBadge brand={station.topTierBrand} />
                          ) : null}
                          {isLowest ? (
                            <span className="rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 text-[10px] font-bold text-emerald-600 dark:text-emerald-400">
                              {t('favorites.lowestPrice')}
                            </span>
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

                    {price ? (
                      <div className="flex flex-wrap items-baseline justify-between gap-2 border-t border-line/60 pt-3">
                        <div className="flex items-baseline gap-1.5">
                          <span className="text-2xl font-extrabold num text-ink">
                            {perGallon(String(price))}
                          </span>
                          {station.fuelType ? (
                            <span className="text-xs text-muted font-medium">
                              · {t(fuelKey(station.fuelType as any))}
                            </span>
                          ) : null}
                        </div>
                        {analytics && numeric && numeric > analytics.minPrice ? (
                          <span className="text-xs text-muted num">
                            +{usd(numeric - analytics.minPrice)}/gal vs min
                          </span>
                        ) : null}
                      </div>
                    ) : null}

                    {/* Private Notes in Yellow/Sunken Badge */}
                    <div className="rounded-control bg-sunken/70 border border-line/50 p-2.5 text-xs">
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
                        onClick={() => {
                          void recordStationRefuel(station, {
                            fuelType: station.fuelType,
                            gallons: prefs.gallons,
                            note: t('refuel.navigatedNote'),
                          })
                        }}
                        className="inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-control min-h-9 border border-line px-4 text-xs font-semibold text-ink hover:bg-sunken transition active:scale-[0.98] shadow-xs"
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
