import { SourcePill } from './SourcePill'
import { RegionalPrice } from './RegionalPrice'
import {
  CarIcon,
  CaretDownIcon,
  CheckCircleIcon,
  ClockCounterClockwiseIcon,
  ClockIcon,
  CoinsIcon,
  CurrencyCircleDollarIcon,
  EqualsIcon,
  GasPumpIcon,
  LightningIcon,
  NavigationArrowIcon,
  PlusIcon,
  TrophyIcon,
  WarningIcon,
} from '@phosphor-icons/react'
import { StationDetails, StationRating, TopTierBadge } from './StationDetails'
import { useState } from 'react'
import type { RankedStation, StrategyKey } from '../../api/types'
import { LinkButton } from '../../components/ui'
import { type MessageKey, type Translate, useI18n } from '../../i18n'
import { comparisonPrice, age, gallons as gal, miles, minutes, perGallon, usd } from '../../lib/format'
import { navigationUrl } from '../../lib/navigation'
import type { NavApp } from '../../lib/prefs'
import { type Assessment, breakdown, openingLabel, type Pick, type Tradeoff } from '../../lib/recommend'

const ICON = { best_value: TrophyIcon, cheapest_overall: CoinsIcon, fastest_stop: LightningIcon, on_my_route: NavigationArrowIcon }

function pickLabel(key: StrategyKey, assessment: Assessment, t: Translate): string {
  return key === 'best_value' && assessment.level !== 'high' ? t('pick.bestVerified') : t(`pick.${key}`)
}

function Breakdown({ row, rows, gallons }: { row: RankedStation; rows: RankedStation[]; gallons: number }) {
  const { t } = useI18n()
  const b = breakdown(row, rows, gallons)
  const line = 'flex items-baseline justify-between gap-4 py-1.5'
  return (
    <div className="text-[14px]">
      <div className={line}>
        <span className="num text-muted">{t('breakdown.purchase', { gallons: gal(b.gallons, t), price: perGallon(b.pricePerGallon) })}</span>
        <span className="num">{usd(b.purchase)}</span>
      </div>
      <div className={line}>
        <span className="num text-muted">{t('breakdown.detour', { distance: miles(row.detour_miles, t) })}</span>
        <span className="num">{usd(b.detourFuel)}</span>
      </div>
      {Number(row.credit_cashback_amount ?? 0) > 0 ? <div className={`${line} text-accent`}><span>{t('prefs.cashback')}</span><span className="num">−{usd(row.credit_cashback_amount)}</span></div> : null}
      <div className={`${line} border-t border-line font-medium`}>
        <span>{t('breakdown.total')}</span>
        <span className="num">{usd(b.total)}</span>
      </div>
      {b.reference ? (
        <>
          <div className={line}>
            <span className="text-muted">{t('breakdown.reference', { name: b.reference.name })}</span>
            <span className="num text-muted">{usd(b.reference.total)}</span>
          </div>
          <div className={`${line} font-medium`}>
            <span>{t('breakdown.difference')}</span>
            <span className={`num ${Number(b.reference.savings) > 0 ? 'text-accent' : ''}`}>
              {Number(b.reference.savings) > 0 ? t('breakdown.save', { amount: usd(b.reference.savings) }) : usd(b.reference.savings)}
            </span>
          </div>
        </>
      ) : null}
      {b.breakEven ? <p className="mt-2 text-[13px] text-muted">{t(b.breakEven.key, { gallons: gal(b.breakEven.gallons, t) })}</p> : null}
      <p className="mt-3 text-[12px] leading-snug text-faint">
        {t('breakdown.note', { mpg: row.mpg_used ? t('unit.mpg', { n: Number(row.mpg_used) }) : t('breakdown.yourMpg') })}
      </p>
    </div>
  )
}

/** Purchase plus the fuel burned driving to the station: the total the ranking actually compares. */
function CostEquation({ row, tripMode }: { row: RankedStation; tripMode: 'round_trip' | 'on_route' }) {
  const { t } = useI18n()
  const item = 'flex min-w-0 flex-col'
  return (
    <div className="mt-4 rounded-control bg-sunken px-3 py-2.5 text-[12px] text-muted">
      {row.route.source === "straight_line_estimate" ? <p className="text-xs text-caution">{t("coverage.estimated_route")}</p> : null}
      <div className="flex items-center gap-2">
      <GasPumpIcon size={16} className="shrink-0 text-ink" />
      <span className={item}>{t(Number(row.credit_cashback_amount ?? 0) > 0 ? 'reward.netFill' : 'cost.fill')}<span className="num text-[14px] font-medium text-ink">{usd(row.net_purchase_cost ?? row.purchase_cost)}</span><span className="num whitespace-nowrap text-[11px] text-faint">{gal(Math.round(Number(row.purchase_cost) / Number(comparisonPrice(row.station))), t)}</span></span>
      <PlusIcon size={12} className="shrink-0" />
      <CarIcon size={16} className="shrink-0 text-ink" />
      <span className={item}>
        {t(tripMode === 'on_route' ? 'cost.tripRoute' : 'cost.trip')}
        <span className="num text-[14px] font-medium text-ink">{usd(row.detour_fuel_cost)}</span>
        <span className="num whitespace-nowrap text-[11px] text-faint">{gal(Number(row.detour_fuel_gallons).toFixed(2), t)}</span>
      </span>
      <EqualsIcon size={12} className="shrink-0" />
      <span className={`${item} ml-auto text-right`}>{t('cost.total')}<span className="num text-[14px] font-semibold text-ink">{usd(row.actual_fuel_cost)}</span></span>
      </div>
      {Number(row.credit_cashback_amount ?? 0) > 0 ? <p className="mt-2 border-t border-line pt-2 text-accent">{t('reward.explanation', { purchase: usd(row.purchase_cost), reward: usd(row.credit_cashback_amount) })}</p> : null}
    </div>
  )
}

/** Money and time against the opposite extreme, so the trade-off is explicit. */
function Comparison({ pick, row, trade, tripMode }: { pick: Pick; row: RankedStation | null; trade: Tradeoff | null; tripMode: 'round_trip' | 'on_route' }) {
  const { t } = useI18n()
  const drive = t(tripMode === 'on_route' ? 'route.extraTime' : 'pick.roundTrip', { time: minutes(pick.recommendation.extra_travel_minutes, t) })
  const tile = 'flex min-w-0 flex-col gap-0.5 rounded-control border border-line px-3 py-2.5'
  const label = 'flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-faint'
  let money: { text: string; good: boolean; caption: string } | null = null
  let time: { text: string; good: boolean } | null = null
  if (trade) {
    const caption = t(trade.heroIsCheaper ? 'compare.vsQuickest' : 'compare.vsCheapest', { name: trade.name })
    money = { text: t(trade.heroIsCheaper ? 'compare.save' : 'compare.more', { amount: usd(trade.saved) }), good: trade.heroIsCheaper, caption }
    time = { text: t(trade.heroIsCheaper ? 'compare.adds' : 'compare.saves', { minutes: minutes(trade.minutes, t) }), good: !trade.heroIsCheaper }
  } else if (row?.break_even && row.break_even.reference_station_id !== row.station.id) {
    const savings = Number(row.break_even.fuel_savings_at_requested_gallons)
    money = {
      text: savings > 0 ? t('compare.save', { amount: usd(savings) }) : savings < 0 ? t('compare.more', { amount: usd(-savings) }) : t('compare.same'),
      good: savings > 0,
      caption: t('compare.vsQuickest', { name: row.break_even.reference_station_name }),
    }
  }
  const both = !trade && pick.keys.includes('cheapest_overall') && pick.keys.includes('fastest_stop')
  return (
    <div className="mt-3">
      <div className="grid grid-cols-2 gap-2">
        <div className={tile}>
          <span className={label}><CurrencyCircleDollarIcon size={13} />{t('compare.money')}</span>
          {money ? <>
            <span className={`num text-[17px] font-semibold ${money.good ? 'text-accent' : 'text-ink'}`}>{money.text}</span>
            <span className="truncate text-[12px] text-muted">{money.caption}</span>
          </> : <span className="text-[14px] font-medium text-ink">{both ? t('compare.bestBoth') : t('pick.closest')}</span>}
        </div>
        <div className={tile}>
          <span className={label}><ClockIcon size={13} />{t('compare.time')}</span>
          {time ? <span className={`num text-[17px] font-semibold ${time.good ? 'text-accent' : 'text-ink'}`}>{time.text}</span> : null}
          <span className={`num ${time ? 'text-[12px] text-muted' : 'text-[17px] font-semibold text-ink'}`}>{drive}</span>
        </div>
      </div>
      {trade ? <p className="mt-2 text-[12px] text-muted">{t('compare.rate', { rate: usd(trade.perHour) })}</p> : null}
    </div>
  )
}

export function HeroPick({
  pick,
  assessment,
  rows,
  gallons,
  navApp,
  trade,
  tripMode = 'round_trip',
}: {
  pick: Pick
  assessment: Assessment
  rows: RankedStation[]
  gallons: number
  navApp: NavApp
  trade: Tradeoff | null
  tripMode?: 'round_trip' | 'on_route'
}) {
  const { t, locale } = useI18n()
  const [open, setOpen] = useState(false)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const { station, row } = pick
  const opening = openingLabel(station)
  const Icon = ICON[pick.keys[0]]
  return (
    <section aria-labelledby="hero-pick" className="rounded-box border border-line bg-surface p-5 shadow-raised">
      <div className="flex items-center justify-between gap-3">
        <p className="flex items-center gap-1.5 text-[13px] font-medium text-muted">
          <Icon size={16} weight="fill" className="shrink-0 text-accent" />
          {pickLabel(pick.keys[0], assessment, t)}
        </p>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2"><h2 id="hero-pick" className="text-[26px] font-semibold leading-tight tracking-tight">
        {station.name}
      </h2>{station.top_tier_brand ? <TopTierBadge brand={station.top_tier_brand} /> : null}</div>
      {station.address ? <p className="mt-0.5 truncate text-[14px] text-muted">{station.address}</p> : null}
      <div className="mt-2"><StationRating station={station} /></div>
      {row ? <RegionalPrice row={row}/> : null}
      {station.comparison_price_per_gallon ? <p className="mt-1 text-xs text-caution">{t('payment.estimate', { adjustment: usd(station.payment_price_adjustment), raw: perGallon(station.price_per_gallon) })}</p> : null}
      <div className="mt-2 flex flex-wrap items-center gap-2"><SourcePill source={station.source}/><p className="text-xs text-muted">{t(station.payment_type === 'cash' ? 'prefs.cash' : station.payment_type === 'credit' ? 'prefs.card' : 'station.unknownPayment')}{station.membership_required ? ` · ${t('station.member', { name: station.membership_required })}` : ''}</p></div>
      {row?.price_comparison && ['cash','credit'].every(payment=>row.price_comparison!.evidence.some(e=>e.payment_type===payment && e.source===station.source && e.price_updated_at && Date.now()-new Date(e.price_updated_at).getTime()<=24*60*60*1000)) ? <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted">{(['cash','credit'] as const).map(payment => {
        const quote = row.price_comparison?.evidence.filter(e => e.payment_type === payment && e.source === station.source && e.price_updated_at && Date.now()-new Date(e.price_updated_at).getTime() <= 24*60*60*1000).sort((a,b)=>new Date(b.price_updated_at!).getTime()-new Date(a.price_updated_at!).getTime())[0]
        return quote ? <span key={payment} className="rounded-full border border-line px-2 py-0.5">{t(payment === 'cash'?'prefs.cash':'prefs.card')} {perGallon(quote.price_per_gallon)}</span> : null
      })}</div> : null}


      {row?.route.source === "straight_line_estimate" ? <p className="mt-2 text-xs text-caution">{t("coverage.estimated_route")}</p> : null}
      <div className="mt-5 flex items-end justify-between gap-4">
        <p>
          <span className="num text-[44px] font-semibold leading-none tracking-[-0.03em]">{perGallon(comparisonPrice(station))}</span>
          <span className="ml-1 text-[14px] text-muted">{t('pick.perGallon')}</span>
        </p>
        {pick.recommendation.actual_fuel_cost ? (
          <p className="text-right text-[13px] leading-tight text-muted">
            {row && Number(row.credit_cashback_amount ?? 0) > 0 ? t('reward.total') : t('pick.totalFor', { gallons: gal(gallons, t) })}
            <span className="num mt-1 block text-[17px] font-medium text-ink">{usd(pick.recommendation.actual_fuel_cost)}</span>
          </p>
        ) : null}
      </div>


      <Comparison pick={pick} row={row} trade={trade} tripMode={tripMode} />

      {pick.recommendation.top_tier_preferred_over && station.top_tier_brand ? (
        <p className="mt-3 flex items-center gap-2 rounded-control bg-accent-soft px-3 py-2 text-[13px] text-accent">
          <TopTierBadge brand={station.top_tier_brand} />
          <span>{t('topTier.preferred', {
            amount: usd(pick.recommendation.top_tier_preferred_over.extra_cost),
            name: pick.recommendation.top_tier_preferred_over.station_name,
            margin: usd(pick.recommendation.top_tier_preferred_over.margin),
          })}</span>
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-1.5">
        {assessment.positives.map((signal) => (
          <span key={signal.key} className="flex items-center gap-1 rounded-full bg-accent-soft px-2.5 py-1 text-xs font-medium text-accent">
            <CheckCircleIcon size={13} weight="fill" />
            {signal.key === 'hours.open' && locale === 'en' && opening.label ? opening.label : t(signal.key, signal.vars)}
          </span>
        ))}
        {assessment.reasons.map((reason) => (
          <span key={reason.key} title={t(reason.key, reason.vars)} className="flex items-center gap-1 rounded-full bg-caution-soft px-2.5 py-1 text-xs text-caution">
            <WarningIcon size={13} />
            {t(reason.key.replace('reason.', 'signal.') as MessageKey)}
          </span>
        ))}
        <span className="flex items-center gap-1 px-1 text-xs text-faint">
          <ClockCounterClockwiseIcon size={13} />
          {station.price_updated_at ? t('age.updated', { age: age(station.price_updated_at, t) }) : t('age.unknown')}
        </span>
      </div>

      <LinkButton href={navigationUrl(navApp, station.location.lat, station.location.lng)} className="mt-5 w-full">
        <NavigationArrowIcon size={18} weight="fill" />
        {t('pick.navigate')}
      </LinkButton>

      <div className="mt-2 grid grid-cols-2 items-start gap-2"><button type="button" className="w-full rounded-control py-2 text-sm font-medium text-ink hover:bg-sunken" onClick={() => setDetailsOpen(true)}>{t('station.view')}</button>
      <StationDetails station={station} row={row} open={detailsOpen} onClose={() => setDetailsOpen(false)} navApp={navApp} tripMode={tripMode} />
      {row ? (
        <div className="contents">
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
            className="flex w-full items-center justify-center gap-1 rounded-control py-2 text-[14px] text-muted hover:text-ink"
          >
            {t('pick.why')}
            <CaretDownIcon size={14} className={`transition ${open ? 'rotate-180' : ''}`} />
          </button>
          {open ? (
            <div className="col-span-2 mt-2 rounded-control bg-sunken px-4 py-3"><CostEquation row={row} tripMode={tripMode}/>      {pick.keys.length > 1 ? (
        <p className="mt-2 flex flex-wrap gap-1.5">
          {pick.keys.slice(1).map((key) => (
            <span key={key} className="rounded-full bg-sunken px-2.5 py-0.5 text-[12px] text-muted">
              {t(`pick.also.${key}`)}
            </span>
          ))}
        </p>
      ) : null}
              <Breakdown row={row} rows={rows} gallons={gallons} />
            </div>
          ) : null}
        </div>
      ) : null}
      </div>
    </section>
  )
}

export function AlternativePick({ pick, navApp, tripMode = 'round_trip' }: { pick: Pick; navApp: NavApp; tripMode?: 'round_trip' | 'on_route' }) {
  const { t } = useI18n()
  const [detailsOpen, setDetailsOpen] = useState(false)
  const { station, recommendation } = pick
  const Icon = ICON[pick.keys[0]]
  return (
    <li className="flex items-center gap-3 py-3">
      <span className="grid size-9 shrink-0 place-items-center rounded-control bg-sunken text-muted">
        <Icon size={18} weight="fill" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[12px] font-medium text-muted">{pick.keys.map((key) => t(`pick.${key}`)).join(' / ')}</p>
        <div className="flex items-center gap-1.5"><button type="button" onClick={() => setDetailsOpen(true)} className="min-w-0 truncate text-left text-[15px] font-medium underline decoration-line underline-offset-4" aria-label={`${t('station.view')} ${station.name}`}>{station.name}</button>{station.top_tier_brand ? <TopTierBadge brand={station.top_tier_brand} /> : null}</div>
        <StationRating station={station} />
        {pick.row?.route.source === "straight_line_estimate" ? <p className="text-xs text-caution">{t("coverage.estimated_route")}</p> : null}
        <p className="text-xs text-muted">{t(station.payment_type === 'cash' ? 'prefs.cash' : station.payment_type === 'credit' ? 'prefs.card' : 'station.unknownPayment')}</p>
      </div>
      <div className="text-right">
        <p className="num text-[15px] font-medium">{perGallon(comparisonPrice(station))}</p>
        <p className="num text-[12px] text-muted">{minutes(recommendation.extra_travel_minutes, t)}</p>
      </div>
      <a
        href={navigationUrl(navApp, station.location.lat, station.location.lng)}
        target="_blank"
        rel="noreferrer"
        aria-label={t('pick.navigateTo', { name: station.name })}
        className="grid size-10 shrink-0 place-items-center rounded-control border border-line text-ink hover:bg-sunken"
      >
        <NavigationArrowIcon size={17} />
      </a>
      <StationDetails station={station} row={pick.row} open={detailsOpen} onClose={() => setDetailsOpen(false)} navApp={navApp} tripMode={tripMode} />
    </li>
  )
}
