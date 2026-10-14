import { CheckIcon, CopyIcon } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import { useI18n } from '../i18n'

/** Display may be abbreviated, but the clipboard always receives the full address. */
export function CopyAddress({ address, display, className = '' }: {
  address?: string | null; display?: string; className?: string
}) {
  if (!address?.trim()) return null
  return <AddressButton key={address} address={address} display={display} className={className} />
}

function AddressButton({ address, display, className }: { address: string; display?: string; className: string }) {
  const { t } = useI18n()
  const [status, setStatus] = useState<'idle' | 'pending' | 'copied' | 'error'>('idle')
  const timeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const attempt = useRef(0)
  useEffect(() => {
    return () => {
      attempt.current += 1
      if (timeout.current) clearTimeout(timeout.current)
    }
  }, [])

  async function copy() {
    const current = ++attempt.current
    if (timeout.current) clearTimeout(timeout.current)
    setStatus('pending')
    try {
      await navigator.clipboard.writeText(address)
      if (current !== attempt.current) return
      setStatus('copied')
      timeout.current = setTimeout(() => setStatus('idle'), 2500)
    } catch {
      if (current === attempt.current) setStatus('error')
    }
  }

  return <span className={`inline-flex min-w-0 max-w-full flex-col ${className}`}>
    <button type="button" onClick={() => void copy()} disabled={status === 'pending'}
      aria-label={t('address.copy', { address })} title={t('address.copy', { address })}
      className="flex min-h-11 w-full min-w-0 items-center gap-1.5 rounded-lg text-left text-inherit outline-none hover:underline focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-60">
      <span className="min-w-0 truncate">{display ?? address}</span>
      {status === 'copied' ? <CheckIcon size={14} aria-hidden="true" className="shrink-0" /> : <CopyIcon size={14} aria-hidden="true" className="shrink-0 opacity-70" />}
    </button>
    <span role="status" aria-live="polite" className="text-[11px] leading-relaxed">
      {status === 'copied' ? t('address.copied') : status === 'error' ? t('address.failed') : ''}
    </span>
    {status === 'error' ? <span className="select-text break-words text-xs">{address}</span> : null}
  </span>
}
