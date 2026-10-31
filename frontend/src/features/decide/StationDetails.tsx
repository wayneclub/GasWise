import { PaymentNotice } from './PaymentNotice'
import { CopyAddress } from '../../components/CopyAddress'
import { PriceHistory } from './PriceHistory'
import {googleStationUrl,stationSourceUrl} from '../../lib/stationLinks'
import { SourcePill, StationSources } from './SourcePill'
import { StarIcon, ShieldCheckIcon, CheckCircleIcon } from '@phosphor-icons/react'
import type { RankedStation, Station } from '../../api/types'
import { useState } from 'react'
import { Button, LinkButton, Sheet } from '../../components/ui'
import { useI18n } from '../../i18n'
import { comparisonPrice, age, fuelKey, perGallon, usd, miles, minutes } from '../../lib/format'
import { navigationUrl } from '../../lib/navigation'
import { recordStationRefuel } from '../../lib/fuelAssistant'
import type { NavApp } from '../../lib/prefs'
import { WatchStation } from './WatchStation'
import { FavoriteButton } from '../../components/FavoriteButton'

export type StationSummary = Pick<Station, 'name' | 'location'> & Partial<Station> & { discovery_state?: 'observed' | 'known'; last_seen_at?: string | null }
import { reasonKey } from '../../lib/stationStatus'
export const TOP_TIER_LIST_URL = 'https://www.toptiergas.com/gasoline-brands/'

/** Brand-level license from the automaker-run TOP TIER program; not a government rating. */
export function TopTierBadge({ brand, size: _size = 'sm' }: { brand: string; size?: 'sm' | 'lg' }) {
  const { t } = useI18n()
  return <span role="img" title={t('topTier.note', { brand })} aria-label={t('topTier.label', { brand })} className="inline-flex shrink-0 items-center gap-0.5 rounded-full border border-accent/20 bg-accent-soft px-1.5 py-0 text-[9px] font-semibold tracking-wide text-accent">
    <ShieldCheckIcon size={10}/><span>TOP TIER</span>
  </span>
}

export function StationRating({ station }: { station: StationSummary }) {
  const { t } = useI18n()
  return <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-muted">
    <span className="inline-flex items-center gap-1">
      <StarIcon size={14} weight={station.rating == null ? 'regular' : 'fill'} className={station.rating == null ? 'text-faint' : 'text-caution'} />
      {station.rating == null ? t('station.noRating') : station.review_count == null
        ? t('station.ratingOnly', { rating: station.rating.toFixed(1) })
        : t('station.rating', { rating: station.rating.toFixed(1), count: station.review_count })}
    </span>
  </p>
}
export function StationDetails({ station, row, open, onClose, navApp, status, tripMode = 'round_trip' }: {
  station: StationSummary; row?: RankedStation | null; open: boolean; onClose: () => void; navApp: NavApp; status?: string; tripMode?: 'round_trip' | 'on_route'
}) {
  const { t, locale } = useI18n()
  const [recorded, setRecorded] = useState(false)
  const canonical = station.canonical_id?.startsWith('google_places:') ? station.canonical_id.slice(14) : null
  const maps = new URL('https://www.google.com/maps/search/')
  maps.searchParams.set('api', '1')
  maps.searchParams.set('query', `${station.location.lat},${station.location.lng}`)
  if (canonical) maps.searchParams.set('query_place_id', canonical)
  const services = Array.isArray(station.details?.services) ? station.details.services as { id?: string; label?: string }[] : []
  const phone = typeof station.details?.phone === 'string' ? station.details.phone : null
  const hours = Array.isArray(station.details?.opening_hours) ? station.details.opening_hours as { days?: number[]; from?: string; to?: string; is_24_hours?: boolean }[] : []
  let website: string | null = null
  if (typeof station.details?.website === 'string') {
    try { const url = new URL(station.details.website.startsWith('http') ? station.details.website : `https://${station.details.website}`); if (['http:', 'https:'].includes(url.protocol) && !url.username && !url.password) website = url.toString() } catch { /* unavailable */ }
  }
  return <Sheet open={open} onClose={onClose} title={t('station.details')}>
    <div className="flex flex-col gap-4">
      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <h3 className="text-xl font-semibold"><a href={googleStationUrl(station)} target="_blank" rel="noreferrer" className="underline decoration-line underline-offset-4">{station.name}</a></h3>
            {station.top_tier_brand ? <TopTierBadge brand={station.top_tier_brand} /> : null}
          </div>
          {station.id ? <FavoriteButton station={station as any} /> : null}
        </div>
        <CopyAddress address={station.address} className="mt-1 w-full text-sm text-muted" />
      </div>
      <StationRating station={station} />
      {station.rating != null ? <p className="text-xs text-faint">{t('station.ratingNote', { source: station.rating_source ?? 'Google Maps' })}</p> : null}
      {station.top_tier_brand ? <div className="flex items-start gap-3 rounded-control bg-sunken p-3">
        <p className="text-xs leading-snug text-muted">
        {t('topTier.note', { brand: station.top_tier_brand })}{' '}
        <a href={TOP_TIER_LIST_URL} target="_blank" rel="noreferrer" className="underline underline-offset-2">{t('topTier.source')}</a>
        </p>
      </div> : null}
      {status && status !== 'routed' ? <p className="rounded-control bg-caution-soft p-3 text-sm text-caution">{t(reasonKey(status))}</p> : null}
      <div className="rounded-control border border-line bg-surface p-4">
        <p className="text-2xl font-semibold num">{station.price_per_gallon ? perGallon(station.price_per_gallon) : t('coverage.noPrice')} <span className="text-sm font-normal text-muted">{station.fuel_type ? t(fuelKey(station.fuel_type)) : ''}</span></p>
        {station.price_per_gallon ? <>
          {station.comparison_price_per_gallon && station.price_per_gallon ? <p className="mt-2 text-xs text-caution">{perGallon(comparisonPrice({ ...station, price_per_gallon: station.price_per_gallon }))} · {t('payment.estimate', { adjustment: usd(station.payment_price_adjustment), raw: perGallon(station.price_per_gallon) })}</p> : null}
          <p className="mt-2 text-sm">{t('station.payment')}: {t(station.payment_type === 'cash' ? 'prefs.cash' : station.payment_type === 'credit' ? 'prefs.card' : 'station.unknownPayment')}</p>
          {station.payment_type === 'unknown' && station.payment_inference ? <p className="mt-1 text-xs text-caution">{t('payment.evidence', {kind: t(station.payment_inference.classification === 'cash' ? 'payment.inferredCash' : station.payment_inference.classification === 'credit' ? 'payment.inferredCredit' : station.payment_inference.classification === 'same_price' ? 'payment.samePrice' : 'payment.unresolved'), level: t(station.payment_inference.confidence === 'medium' ? 'confidence.medium' : 'confidence.low')})}</p> : null}
          <PaymentNotice station={station} />
          {station.membership_required ? <p className="mt-1 text-sm text-caution">{t('station.member', { name: station.membership_required })}</p> : null}
          <div className="mt-2"><StationSources source={station.source ?? ''} row={row}/></div>
          <p className="text-xs text-muted">{t('age.updated', { age: age(station.price_updated_at, t) })}</p>
        </> : null}
      </div>
      <PriceHistory station={station} />
      <WatchStation station={station} />
      <p className="text-sm">{t('station.hours')}: {t(station.open_now === true ? 'hours.open' : station.open_now === false ? 'hours.closed' : 'hours.unknown')}</p>
      {row?.route.source === "straight_line_estimate" ? <p className="text-xs text-caution">{t("coverage.estimated_route")}</p> : null}
      {row ? <dl className="grid grid-cols-2 gap-2 border-t border-line pt-3 text-sm">
        <dt>{t(station.comparison_price_per_gallon ? 'payment.assumedFill' : 'cost.fill')}</dt><dd className="text-right font-semibold num">{usd(row.purchase_cost)}</dd>
        <dt>{t('breakdown.total')}</dt><dd className="text-right font-semibold num">{usd(row.actual_fuel_cost)}</dd>
        {Number(row.credit_cashback_amount ?? 0) > 0 ? <><dt>{t('prefs.cashback')}</dt><dd className="text-right num text-accent">−{usd(row.credit_cashback_amount)}</dd></> : null}
        <dt>{t('breakdown.detour', { distance: miles(row.detour_miles, t) })}</dt><dd className="text-right num">{usd(row.detour_fuel_cost)}</dd>
        <dt>{t('pick.driveLabel')}</dt><dd className="text-right num">{tripMode === 'on_route' ? t('route.extraTime', { time: minutes(row.extra_travel_minutes, t) }) : t('pick.roundTrip', { time: minutes(row.extra_travel_minutes, t) })}</dd>
        {row.break_even && row.break_even.reference_station_id !== row.station.id ? (() => {
          const s = Number(row.break_even.fuel_savings_at_requested_gallons)
          return <>
            <dt>{t('breakdown.difference')}</dt>
            <dd className={`text-right font-semibold num ${s > 0 ? 'text-accent' : s < 0 ? 'text-caution' : ''}`}>
              {s > 0 ? t('badge.netSave', { amount: usd(s) }) : s < 0 ? t('badge.detourLoss', { amount: usd(Math.abs(s)) }) : '$0.00'}
            </dd>
          </>
        })() : null}
      </dl> : null}
      {row ? <p className="text-xs text-muted">{t('pick.comparisonNote')}</p> : null}
      {row?.price_comparison?.evidence.length ? <div className="rounded-control bg-sunken p-3 text-sm">
        {row.price_comparison.evidence.map((e, index) => <div key={`${e.source}:${e.payment_type}:${index}`} className="flex flex-wrap justify-between gap-2 border-b border-line py-2 last:border-0">
          <span className="flex flex-wrap items-center gap-2"><SourcePill source={e.source} href={stationSourceUrl(e.source,e.provider_station_id,station)}/>{t(e.payment_type === 'cash' ? 'prefs.cash' : e.payment_type === 'credit' ? 'prefs.card' : 'station.unknownPayment')}</span>
          <span className="num">{perGallon(e.price_per_gallon)}</span>
          {!e.eligible && e.exclusion_reason ? <span className="w-full text-xs text-caution">{t(reasonKey(e.exclusion_reason))}</span> : null}
        </div>)}
      </div> : null}
      {phone ? <p className="text-sm">{t('station.phone')}: <a className="underline" href={`tel:${phone.replace(/[^+\d]/g, '')}`}>{phone}</a></p> : null}
      {website ? <a className="text-sm underline" href={website} target="_blank" rel="noreferrer">{t('station.website')}</a> : null}
      {hours.length ? <div className="rounded-control bg-sunken p-3 text-sm"><h4 className="font-medium">{t('station.schedule')}</h4>
        {hours.map((h, i) => <p key={i} className="mt-1 text-muted">{(h.days ?? []).map((d) => new Intl.DateTimeFormat(locale, { weekday: 'short', timeZone: 'UTC' }).format(new Date(Date.UTC(2026, 0, 4 + d)))).join(', ')} · {h.is_24_hours ? t('station.allDay') : `${h.from}–${h.to}`}</p>)}
      </div> : null}
      {services.length ? <div><h4 className="text-sm font-medium">{t('station.amenities')}</h4><p className="mt-1 text-sm text-muted">{services.map((s) => s.id && ['RESTROOMS', 'PARKING_FOR_CUSTOMERS', 'CREDIT_CARDS', 'WHEELCHAIR_ACCESSIBLE', 'AIR_CONDITIONING', 'DELIVERIES', 'WIFI', 'DRIVE_THROUGH'].includes(s.id) ? t(`amenity.${s.id}` as import('../../i18n').MessageKey) : s.label ?? s.id).filter(Boolean).join(' · ')}</p></div> : null}
      <LinkButton
        href={navigationUrl(navApp, station.location.lat, station.location.lng)}
        onClick={() => {
          void recordStationRefuel(station, {
            fuelType: station.fuel_type,
            note: t('refuel.navigatedNote'),
          })
        }}
      >
        {t('pick.navigate')}
      </LinkButton>
      <Button
        variant="secondary"
        onClick={async () => {
          await recordStationRefuel(station, {
            fuelType: station.fuel_type,
          })
          setRecorded(true)
          setTimeout(() => setRecorded(false), 3000)
        }}
        className="gap-2"
      >
        <CheckCircleIcon size={16} weight={recorded ? 'fill' : 'regular'} className={recorded ? 'text-accent' : ''} />
        <span>{recorded ? t('station.recorded') : t('station.recordFuel')}</span>
      </Button>
      <Button variant="secondary" onClick={() => window.open(maps.toString(), '_blank', 'noopener,noreferrer')}>{t('station.maps')}</Button>
    </div>
  </Sheet>
}
