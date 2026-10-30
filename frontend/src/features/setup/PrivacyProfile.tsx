import { useEffect, useRef, useState } from 'react'
import { Field, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n'
import { saveIdentity } from '../../lib/identityVault'
import { exportPrivateBackup, getLocalProfile, importPrivateBackup, requestPersistentStorage, resetLocalProfile, shortProfileId } from '../../lib/localProfile'
import { DEFAULT_PREFS, type Prefs } from '../../lib/prefs'
import { useVehicleIdentity } from '../../lib/vehicleIdentity'
import { clearSmartAlertStorage } from '../../lib/smartAlerts'
import { clearFuelAssistant, replaceFuelAssistant } from '../../lib/fuelAssistant'
import { clearLifeZones, replaceLifeZones } from '../../lib/lifeZones'
import { clearFavorites, replaceFavorites } from '../../lib/favorites'

type Notice = 'exported' | 'imported' | 'cleared' | 'error' | null

export function PrivacyProfile({ prefs, replace }: { prefs: Prefs; replace: (prefs: Prefs) => void }) {
  const { t, locale } = useI18n()
  const { identity, setIdentity } = useVehicleIdentity()
  const [profile, setProfile] = useState('…')
  const [passphrase, setPassphrase] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<Notice>(null)
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => { void getLocalProfile().then(value => setProfile(shortProfileId(value))).catch(() => setNotice('error')) }, [])

  async function download() {
    setBusy(true); setNotice(null)
    try {
      const contents = await exportPrivateBackup(prefs, identity, passphrase)
      const url = URL.createObjectURL(new Blob([contents], { type: 'application/json' }))
      const link = document.createElement('a')
      link.href = url
      link.download = `gaswise-private-backup-${new Date().toISOString().slice(0, 10)}.json`
      link.click()
      URL.revokeObjectURL(url)
      void requestPersistentStorage()
      setNotice('exported')
    } catch { setNotice('error') } finally { setBusy(false) }
  }

  async function restore() {
    if (!file) return
    setBusy(true); setNotice(null)
    try {
      const restored = await importPrivateBackup(await file.text(), passphrase)
      await replaceFuelAssistant(restored.assistant ?? null)
      if (restored.lifeZones) await replaceLifeZones(restored.lifeZones)
      if (restored.favorites) await replaceFavorites(restored.favorites)
      await saveIdentity(restored.identity)
      setIdentity(restored.identity)
      replace(restored.prefs)
      setProfile(shortProfileId(restored.profile))
      setNotice('imported')
      void requestPersistentStorage()
    } catch { setNotice('error') } finally { setBusy(false) }
  }

  async function clear() {
    if (!window.confirm(t('privacy.clearConfirm'))) return
    setBusy(true); setNotice(null)
    try {
      await clearSmartAlertStorage()
      await clearFuelAssistant()
      await clearLifeZones()
      await clearFavorites()
      await saveIdentity(null)
      setIdentity(null)
      localStorage.clear()
      sessionStorage.clear()
      replace(DEFAULT_PREFS)
      const next = await resetLocalProfile()
      setProfile(shortProfileId(next))
      setPassphrase('')
      setFile(null)
      if (input.current) input.current.value = ''
      setNotice('cleared')
    } catch { setNotice('error') } finally { setBusy(false) }
  }

  return (
    <>
      <section
        id="section-privacy"
        className="grid grid-cols-1 gap-6 border-b border-line py-8 first:pt-0 last:border-b-0 lg:grid-cols-[280px_1fr] lg:gap-10 lg:py-10"
        aria-label={t('privacy.title')}
      >
        <div className="flex flex-col gap-2 lg:pt-1">
          <h2 className="text-base font-semibold text-ink">{t('privacy.title')}</h2>
          <p className="text-[13px] leading-relaxed text-muted">{t('privacy.description')}</p>
          <div className="mt-2 inline-flex items-center gap-1.5 rounded-control bg-sunken px-2.5 py-1.5 text-xs text-muted self-start">
            <span className="num font-mono">{t('privacy.profileId', { id: profile })}</span>
          </div>
        </div>

        <div className="liquid-panel rounded-box p-5 sm:p-6 flex flex-col gap-6 min-w-0">
          <div className="grid gap-5 md:grid-cols-2">
            <Field label={t('privacy.passphrase')} hint={t('privacy.passphraseHint')}>
              <TextInput
                type="password"
                autoComplete="new-password"
                minLength={8}
                value={passphrase}
                onChange={event => setPassphrase(event.target.value)}
                placeholder="••••••••"
              />
            </Field>
            <Field label={t('privacy.backupFile')}>
              <div className="relative flex min-h-11 items-center gap-2 rounded-control border border-line bg-surface p-1.5">
                <button
                  type="button"
                  onClick={() => input.current?.click()}
                  className="inline-flex h-8 shrink-0 items-center justify-center rounded-[10px] border border-line bg-canvas px-3 text-xs font-medium text-ink hover:bg-sunken"
                >
                  {file ? (locale.startsWith('zh') ? '更換檔案' : 'Change') : (locale.startsWith('zh') ? '選擇檔案' : 'Select file')}
                </button>
                <span className="truncate text-xs text-muted px-1">
                  {file ? file.name : (locale.startsWith('zh') ? '未選取任何檔案 (.json)' : 'No file chosen (.json)')}
                </span>
                <input
                  ref={input}
                  type="file"
                  accept="application/json,.json"
                  onChange={event => setFile(event.target.files?.[0] ?? null)}
                  className="sr-only"
                  aria-label={t('privacy.backupFile')}
                />
              </div>
            </Field>
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
            <button
              type="button"
              disabled={busy || passphrase.length < 8}
              onClick={() => void download()}
              className="inline-flex h-11 items-center justify-center rounded-control border border-line bg-surface px-4 text-sm font-medium text-ink hover:bg-sunken active:scale-[0.98] disabled:opacity-50"
            >
              {t('privacy.export')}
            </button>
            <button
              type="button"
              disabled={busy || passphrase.length < 8 || !file}
              onClick={() => void restore()}
              className="inline-flex h-11 items-center justify-center rounded-control border border-line bg-surface px-4 text-sm font-medium text-ink hover:bg-sunken active:scale-[0.98] disabled:opacity-50"
            >
              {t('privacy.import')}
            </button>
          </div>

          {notice ? (
            <p role="status" className={`text-xs ${notice === 'error' ? 'text-caution' : 'text-muted'}`}>
              {t(`privacy.${notice}`)}
            </p>
          ) : null}
        </div>
      </section>

      <section
        id="section-danger"
        className="grid grid-cols-1 gap-6 border-b border-line py-8 first:pt-0 last:border-b-0 lg:grid-cols-[280px_1fr] lg:gap-10 lg:py-10"
        aria-label={t('privacy.clearAll')}
      >
        <div className="flex flex-col gap-2 lg:pt-1">
          <h2 className="text-base font-semibold text-danger">{t('privacy.clearAll')}</h2>
          <p className="text-[13px] leading-relaxed text-muted">
            {t('privacy.clearConfirm')}
          </p>
        </div>

        <div className="liquid-panel rounded-box border border-danger/20 p-5 sm:p-6 flex flex-col gap-4 min-w-0">
          <p className="text-xs leading-relaxed text-muted">
            {t('privacy.clearConfirm')}
          </p>
          <div>
            <button
              type="button"
              disabled={busy}
              onClick={() => void clear()}
              className="inline-flex h-11 items-center justify-center rounded-control border border-danger/40 bg-danger/5 px-4 text-sm font-medium text-danger hover:bg-danger/10 active:scale-[0.98] disabled:opacity-50"
            >
              {t('privacy.clearAll')}
            </button>
          </div>
        </div>
      </section>
    </>
  )
}
