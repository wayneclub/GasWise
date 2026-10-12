import { GasPumpIcon } from '@phosphor-icons/react'
import { Button } from '../../components/ui'
import { useI18n } from '../../i18n'
import type { Prefs } from '../../lib/prefs'
import { PreferencesForm } from './PreferencesForm'

export function Setup({ prefs, update }: { prefs: Prefs; update: (change: Partial<Prefs>) => void }) {
  const { t } = useI18n()
  const ready = Boolean(prefs.vehicle || prefs.mpg)
  return (
    <main className="mx-auto flex min-h-[100dvh] w-full max-w-md flex-col px-4 pb-10 pt-8 sm:pt-14">
      <div className="flex items-center gap-2 text-ink">
        <GasPumpIcon size={22} weight="fill" className="text-ink" />
        <span className="text-[15px] font-semibold tracking-tight">{t('app.name')}</span>
      </div>
      <h1 className="mt-8 text-[28px] font-semibold leading-tight tracking-tight">{t('setup.title')}</h1>
      <p className="mt-2 max-w-[38ch] text-[15px] leading-relaxed text-muted">
        {t('setup.lead')}
      </p>
      <div className="mt-8">
        <PreferencesForm prefs={prefs} update={update} />
      </div>
      <Button className="mt-10 h-12 w-full" disabled={!ready} onClick={() => update({ onboarded: true })}>
        {t('setup.submit')}
      </Button>
      <p className="mt-3 text-center text-[13px] text-muted">{t('app.locationPrivacy')}</p>
    </main>
  )
}
