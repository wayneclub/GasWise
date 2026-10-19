import { useEffect, useRef, useState } from 'react'
import { Field, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n'
import { saveIdentity } from '../../lib/identityVault'
import { exportPrivateBackup, getLocalProfile, importPrivateBackup, requestPersistentStorage, resetLocalProfile, shortProfileId } from '../../lib/localProfile'
import { DEFAULT_PREFS, type Prefs } from '../../lib/prefs'
import { useVehicleIdentity } from '../../lib/vehicleIdentity'

type Notice = 'exported' | 'imported' | 'cleared' | 'error' | null

export function PrivacyProfile({ prefs, replace }: { prefs: Prefs; replace: (prefs: Prefs) => void }) {
  const { t } = useI18n()
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

  return <section className="flex min-w-0 flex-col gap-5 liquid-panel rounded-box p-4 sm:p-6 lg:col-span-2" aria-label={t('privacy.title')}>
    <div><h2 className="font-semibold">{t('privacy.title')}</h2><p className="mt-1 text-xs leading-relaxed text-muted">{t('privacy.description')}</p></div>
    <p className="font-mono text-xs text-muted">{t('privacy.profileId', { id: profile })}</p>
    <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <Field label={t('privacy.passphrase')} hint={t('privacy.passphraseHint')}>
        <TextInput type="password" autoComplete="new-password" minLength={8} value={passphrase} onChange={event => setPassphrase(event.target.value)} />
      </Field>
      <Field label={t('privacy.backupFile')}>
        <input ref={input} type="file" accept="application/json,.json" onChange={event => setFile(event.target.files?.[0] ?? null)} className="block min-h-11 w-full rounded-control border border-line bg-canvas p-2 text-sm" />
      </Field>
    </div>
    <div className="flex flex-wrap gap-3">
      <button type="button" disabled={busy || passphrase.length < 8} onClick={() => void download()} className="rounded-control border border-line px-4 py-2 text-sm disabled:opacity-50">{t('privacy.export')}</button>
      <button type="button" disabled={busy || passphrase.length < 8 || !file} onClick={() => void restore()} className="rounded-control border border-line px-4 py-2 text-sm disabled:opacity-50">{t('privacy.import')}</button>
      <button type="button" disabled={busy} onClick={() => void clear()} className="rounded-control border border-caution px-4 py-2 text-sm text-caution disabled:opacity-50">{t('privacy.clearAll')}</button>
    </div>
    {notice ? <p role="status" className={`text-xs ${notice === 'error' ? 'text-caution' : 'text-muted'}`}>{t(`privacy.${notice}`)}</p> : null}
  </section>
}
