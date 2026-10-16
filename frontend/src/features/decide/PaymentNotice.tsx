import { useI18n } from '../../i18n'
import type { StationSummary } from './StationDetails'

/** Raw payment terms stay separate from a same-grade price-match inference. */
export function PaymentNotice({ station }: { station: StationSummary }) {
  const { t } = useI18n()
  if (station.payment_type !== 'unknown') return null
  const classification = station.payment_inference?.classification
  const isGoogle = station.source === 'google_maps_web' || station.source === 'google_places'
  return <div className="mt-2 space-y-1 text-xs text-caution">
    {isGoogle ? <p>{t('payment.mapsNote')}</p> : null}
    {classification === 'cash' || classification === 'credit' || classification === 'same_price'
      ? <p>{t('payment.matchNote', { kind: t(classification === 'cash' ? 'payment.inferredCash' : classification === 'credit' ? 'payment.inferredCredit' : 'payment.samePrice') })}</p>
      : null}
  </div>
}
