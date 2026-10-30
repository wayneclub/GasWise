import {
  CoinsIcon,
  CreditCardIcon,
  PiggyBankIcon,
  ShieldCheckIcon,
  SparkleIcon,
  TrendDownIcon,
  TrendUpIcon,
  WarningIcon,
} from '@phosphor-icons/react'
import { useI18n } from '../../i18n'
import { perGallon, usd } from '../../lib/format'
import type { FavoriteStation } from '../../lib/favorites'
import type { TrendAnalysisSummary } from './MultiStationPriceChart'

interface AnalyticsData {
  minPrice: number
  maxPrice: number
  avgPrice: number
  spread: number
  lowestStation: FavoriteStation & { numericPrice: number }
  highestStation: FavoriteStation & { numericPrice: number }
  gallons: number
  maxSavings: number
  topTierStation?: (FavoriteStation & { numericPrice: number }) | undefined
  topTierStations: (FavoriteStation & { numericPrice: number })[]
  standardStations: (FavoriteStation & { numericPrice: number })[]
  topTierAvg: number | null
  standardAvg: number | null
}

interface SmartFuelAdvisorProps {
  analytics: AnalyticsData
  trendSummary: TrendAnalysisSummary | null
  vehicleSummary?: string | null
}

export function SmartFuelAdvisor({
  analytics,
  trendSummary,
  vehicleSummary,
}: SmartFuelAdvisorProps) {
  const { t } = useI18n()

  // 1. Timing analysis
  const timingInsight = (() => {
    if (trendSummary?.preWeekendHikeRisk) {
      return {
        type: 'warning' as const,
        icon: <WarningIcon size={18} weight="bold" className="text-amber-500 shrink-0" />,
        badge: t('favorites.timingPreWeekendBadge'),
        text: t('favorites.timingPreWeekend'),
      }
    }
    if (trendSummary?.trend === 'falling') {
      return {
        type: 'falling' as const,
        icon: <TrendDownIcon size={18} weight="bold" className="text-emerald-500 shrink-0" />,
        badge: t('favorites.timingFallingBadge'),
        text: t('favorites.timingFalling', {
          days: 30,
          diff: usd(Math.abs(trendSummary.delta)),
        }),
      }
    }
    if (trendSummary?.cycleLow || (analytics.spread >= 0.15 && analytics.minPrice < analytics.avgPrice)) {
      return {
        type: 'good' as const,
        icon: <SparkleIcon size={18} weight="fill" className="text-accent shrink-0" />,
        badge: t('favorites.timingGoodBadge'),
        text: t('favorites.timingGood', { station: analytics.lowestStation.name }),
      }
    }
    if (trendSummary?.trend === 'rising') {
      return {
        type: 'rising' as const,
        icon: <TrendUpIcon size={18} weight="bold" className="text-rose-500 shrink-0" />,
        badge: t('favorites.timingRisingBadge'),
        text: t('favorites.timingRising', { diff: usd(Math.abs(trendSummary.delta)) }),
      }
    }
    return {
      type: 'normal' as const,
      icon: <SparkleIcon size={18} weight="fill" className="text-accent shrink-0" />,
      badge: t('favorites.timingNormalBadge'),
      text: t('favorites.timingNormal'),
    }
  })()

  // 2. Smart Station Pick
  const stationPickInsight = (() => {
    const isLowestTopTier = Boolean(analytics.lowestStation.topTierBrand)
    if (isLowestTopTier) {
      return {
        badge: t('favorites.smartPickTopTierCheapestBadge'),
        title: t('favorites.smartPickTopTierCheapest', {
          station: analytics.lowestStation.name,
        }),
        icon: <ShieldCheckIcon size={20} weight="fill" className="text-accent shrink-0" />,
      }
    }
    if (analytics.topTierStation) {
      const diff = analytics.topTierStation.numericPrice - analytics.minPrice
      return {
        badge: t('favorites.smartPickTopTierValueBadge'),
        title: t('favorites.smartPickTopTierValue', {
          station: analytics.topTierStation.name,
          diff: perGallon(diff.toFixed(2)),
        }),
        icon: <ShieldCheckIcon size={20} weight="fill" className="text-sky-500 shrink-0" />,
      }
    }
    return {
      badge: t('favorites.smartPickCheapestBadge'),
      title: t('favorites.smartPickCheapest', {
        station: analytics.lowestStation.name,
        savings: usd(analytics.maxSavings),
      }),
      icon: <CoinsIcon size={20} weight="fill" className="text-emerald-500 shrink-0" />,
    }
  })()

  // 3. Projected Annual Savings (36 typical fills/year)
  const savingsPerFill = Math.max(0.5, (analytics.avgPrice - analytics.minPrice) * analytics.gallons)
  const annualSavings = Math.round(savingsPerFill * 36)

  // 4. Cashback estimate (5% cash-back on lowest price)
  const cashbackPerGallon = (analytics.minPrice * 0.05).toFixed(2)

  return (
    <section
      aria-label={t('favorites.smartAdvisorTitle')}
      className="rounded-box border border-accent/30 bg-gradient-to-br from-surface via-surface to-accent-soft/20 p-5 sm:p-6 shadow-sm flex flex-col gap-5"
    >
      {/* Header */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between border-b border-line pb-3">
        <div className="flex items-center gap-2">
          <SparkleIcon size={22} weight="fill" className="text-accent" />
          <h2 className="text-base font-bold text-ink sm:text-lg">
            {t('favorites.smartAdvisorTitle')}
          </h2>
        </div>
        <span className="text-xs text-muted">
          {t('favorites.smartAdvisorSubtitle')}
        </span>
      </div>

      {/* 4 Rich Insight Cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* Card 1: Timing Advisor */}
        <div className="rounded-control bg-surface border border-line p-4 flex flex-col justify-between gap-3 shadow-xs">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-bold text-muted flex items-center gap-1.5 uppercase tracking-wider">
              {timingInsight.icon}
              {t('favorites.timingTitle')}
            </span>
            <span
              className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                timingInsight.type === 'good' || timingInsight.type === 'falling'
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                  : timingInsight.type === 'warning' || timingInsight.type === 'rising'
                  ? 'bg-amber-500/10 text-amber-700 dark:text-amber-300'
                  : 'bg-sunken text-muted'
              }`}
            >
              {timingInsight.badge}
            </span>
          </div>
          <p className="text-xs leading-relaxed text-ink">
            {timingInsight.text}
          </p>
        </div>

        {/* Card 2: Smart Pick Station */}
        <div className="rounded-control bg-surface border border-line p-4 flex flex-col justify-between gap-3 shadow-xs">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-bold text-muted flex items-center gap-1.5 uppercase tracking-wider">
              {stationPickInsight.icon}
              {t('favorites.smartPickTitle')}
            </span>
            <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-semibold text-accent">
              {stationPickInsight.badge}
            </span>
          </div>
          <p className="text-xs leading-relaxed text-ink">
            {stationPickInsight.title}
          </p>
        </div>

        {/* Card 3: Annual Projected Savings */}
        <div className="rounded-control bg-emerald-500/5 border border-emerald-500/25 p-4 flex flex-col justify-between gap-3 shadow-xs">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-bold text-emerald-800 dark:text-emerald-300 flex items-center gap-1.5 uppercase tracking-wider">
              <PiggyBankIcon size={18} weight="duotone" className="text-emerald-600 dark:text-emerald-400" />
              {t('favorites.annualSavingsTitle')}
            </span>
            <span className="num text-base font-bold text-emerald-600 dark:text-emerald-400 sm:text-lg">
              {t('favorites.annualSavingsValue', { amount: usd(annualSavings) })}
            </span>
          </div>
          <p className="text-[11px] leading-relaxed text-muted">
            {t('favorites.annualSavingsNote')}
            {vehicleSummary ? ` (${vehicleSummary})` : ''}
          </p>
        </div>

        {/* Card 4: Payment Cashback Tip */}
        <div className="rounded-control bg-surface border border-line p-4 flex flex-col justify-between gap-3 shadow-xs">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-bold text-muted flex items-center gap-1.5 uppercase tracking-wider">
              <CreditCardIcon size={18} weight="duotone" className="text-accent" />
              {t('favorites.paymentTipTitle')}
            </span>
            <span className="rounded-full bg-accent-soft/40 px-2 py-0.5 text-[11px] font-semibold text-accent num">
              ~5% Cashback
            </span>
          </div>
          <p className="text-[11px] leading-relaxed text-ink">
            {t('favorites.paymentTipContent', { amount: perGallon(cashbackPerGallon) })}
          </p>
        </div>
      </div>
    </section>
  )
}
