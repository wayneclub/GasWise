import { useEffect, useId, useRef, useState } from 'react'
import { api } from '../../api/client'
import { Button, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n'
import type { Origin } from '../../lib/session'

export function LocationSearch({ onChoose }: { onChoose: (location: Origin, label: string) => void }) {
  const id = useId()
  const { t } = useI18n()
  const [text, setText] = useState('')
  const [items, setItems] = useState<{id: string; label: string; location: Origin}[]>([])
  const [status, setStatus] = useState<'idle' | 'pending' | 'empty' | 'error'>('idle')
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])
  return <form className="flex flex-col gap-3 text-left" onSubmit={async (event) => {
    event.preventDefault()
    if (text.trim().length < 3) return
    controller.current?.abort()
    const abort = new AbortController(); controller.current = abort
    setStatus('pending'); setItems([])
    try {
      const result = await api.resolveLocation(text.trim(), abort.signal)
      if (abort.signal.aborted) return
      setStatus(result.candidates.length ? 'idle' : 'empty')
      if (result.candidates.length === 1) {
        const [item] = result.candidates
        onChoose(item.location, item.label)
      } else setItems(result.candidates)
    } catch { if (!abort.signal.aborted) setStatus('error') }
  }}>
    <label className="text-sm font-medium" htmlFor={id}>{t('location.label')}</label>
    <div className="flex gap-2"><TextInput id={id} value={text} maxLength={200} placeholder={t('location.placeholder')} onChange={(e) => { controller.current?.abort(); setText(e.target.value); setItems([]); setStatus('idle') }} /><Button type="submit" disabled={status === 'pending' || text.trim().length < 3}>{t(status === 'pending' ? 'vehicle.finding' : 'vehicle.find')}</Button></div>
    <p className="text-xs leading-relaxed text-muted">{t('location.hint')} <a href="https://maps.google.com/" target="_blank" rel="noreferrer" className="underline">Google Maps</a></p>
    {status === 'error' || status === 'empty' ? <p role="status" className="text-sm text-caution">{t(status === 'error' ? 'location.error' : 'location.empty')}</p> : null}
    {items.map((item) => <button key={item.id} type="button" className="rounded-control border border-line bg-surface p-3 text-left text-sm hover:border-accent" onClick={() => { setItems([]); onChoose(item.location, item.label) }}>{item.label}</button>)}
  </form>
}
