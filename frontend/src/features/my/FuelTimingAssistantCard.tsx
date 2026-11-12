import { GasPumpIcon, PlusIcon, SparkleIcon } from '@phosphor-icons/react'
import { Button } from '../../components/ui'
import { useI18n } from '../../i18n'
import type { FuelAssistantSettings, NeedEstimate } from '../../lib/fuelAssistant'
import type { Prefs } from '../../lib/prefs'

interface FuelTimingAssistantCardProps {
  estimate: NeedEstimate
  settings: FuelAssistantSettings
  prefs: Prefs
  mpg: number
  busy: boolean
  onQuickRefuel: (now: Date) => Promise<void>
  onOpenCreate: () => void
  onSaveSettings: (settings: FuelAssistantSettings, now: Date) => Promise<void>
}

export function FuelTimingAssistantCard({
  estimate,
  settings,
  prefs,
  mpg,
  busy,
  onQuickRefuel,
  onOpenCreate,
  onSaveSettings,
}: FuelTimingAssistantCardProps) {
  const { t } = useI18n()

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
          onClick={() => void onQuickRefuel(new Date())}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-control bg-ink px-4 text-sm font-semibold text-surface transition hover:opacity-90 active:scale-[0.98] disabled:opacity-50 shadow-sm"
        >
          <GasPumpIcon size={18} weight="fill" />
          <span>{t('assistant.justFilled')}</span>
        </button>

        <Button
          variant="secondary"
          onClick={onOpenCreate}
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
                void onSaveSettings(
                  { ...settings, weeklyMiles: Number(event.target.value) },
                  new Date(),
                )
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
                void onSaveSettings(
                  { ...settings, typicalGallons: Number(event.target.value) },
                  new Date(),
                )
              }
              className="h-11 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent"
            />
          </label>
        </div>
      </details>
    </div>
  )
}
