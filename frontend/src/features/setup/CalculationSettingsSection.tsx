import { Field, Segmented, Stepper, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n'
import { gallons } from '../../lib/format'
import type { Prefs } from '../../lib/prefs'
import { SettingsSection } from './SettingsSection'

interface CalculationSettingsSectionProps {
  prefs: Prefs
  update: (change: Partial<Prefs>) => void
}

export function CalculationSettingsSection({ prefs, update }: CalculationSettingsSectionProps) {
  const { t } = useI18n()

  return (
    <SettingsSection
      id="section-calculation"
      title={t('prefs.gallons')}
      description={t('prefs.gallonsHint')}
    >
      <Field label={t('prefs.gallons')}>
        <Stepper
          label={t('ui.gallons')}
          value={prefs.gallons}
          min={1}
          max={30}
          step={1}
          format={(value) => gallons(value, t)}
          onChange={(value) => update({ gallons: value })}
        />
      </Field>

      <Field label={t('prefs.payment')} hint={prefs.payment === 'cash_or_credit' ? t('prefs.allHint') : undefined}>
        <Segmented
          label={t('prefs.payment')}
          value={prefs.payment}
          options={[
            { value: 'cash_or_credit', label: t('prefs.all') },
            { value: 'credit', label: t('prefs.card') },
            { value: 'cash', label: t('prefs.cash') },
          ]}
          onChange={(payment) => update({ payment })}
        />
      </Field>

      <Field label={t('prefs.cashback')} hint={t(prefs.payment === 'cash' ? 'prefs.cashbackCash' : 'prefs.cashbackHint')}>
        <div className="relative max-w-44">
          <TextInput
            type="number"
            inputMode="decimal"
            min={0}
            max={100}
            step="0.1"
            aria-label={t('prefs.cashback')}
            disabled={prefs.payment === 'cash'}
            value={prefs.creditCashbackPercent}
            className="num pr-9"
            onChange={(event) => {
              const value = event.target.value
              if (value === '' || Number.isFinite(Number(value))) {
                update({
                  creditCashbackPercent:
                    value === '' ? '' : String(Math.max(0, Math.min(100, Number(value)))),
                })
              }
            }}
          />
          <span className={`pointer-events-none absolute right-3.5 top-3 text-sm ${prefs.payment === 'cash' ? 'text-faint' : 'text-muted'}`}>
            %
          </span>
        </div>
        {prefs.payment !== 'cash' ? (
          <div className="mt-2.5 flex flex-wrap gap-1.5 text-xs">
            {[
              { label: 'Costco (4%)', val: '4' },
              { label: 'Citi / Amex (5%)', val: '5' },
              { label: 'Amex BCE (3%)', val: '3' },
              { label: '2%', val: '2' },
              { label: '1.5%', val: '1.5' },
              { label: '0%', val: '0' },
            ].map(({ label, val }) => (
              <button
                key={val}
                type="button"
                onClick={() => update({ creditCashbackPercent: val })}
                className={`rounded-control border px-2 py-0.5 transition ${
                  prefs.creditCashbackPercent === val
                    ? 'border-accent bg-accent-soft/30 text-accent font-semibold'
                    : 'border-line text-muted hover:border-accent hover:text-ink'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        ) : null}
      </Field>
    </SettingsSection>
  )
}
