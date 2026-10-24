import { MinusIcon, PlusIcon, XIcon } from '@phosphor-icons/react'
import { type ButtonHTMLAttributes, type ReactNode, useEffect, useId, useRef } from 'react'
import { useI18n } from '../i18n'

const press = 'transition active:scale-[0.98] disabled:opacity-50 disabled:active:scale-100'
const focus = 'outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas'

type Variant = 'primary' | 'secondary' | 'ghost'

export function Button({
  variant = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  const tone = {
    primary: 'bg-ink text-surface hover:opacity-90',
    secondary: 'liquid-control text-ink hover:bg-sunken',
    ghost: 'text-muted hover:text-ink hover:bg-sunken',
  }[variant]
  return (
    <button
      type="button"
      className={`inline-flex h-11 items-center justify-center gap-2 whitespace-nowrap rounded-control px-4 text-[15px] font-medium ${tone} ${press} ${focus} ${className}`}
      {...props}
    />
  )
}

export function LinkButton({
  href,
  children,
  className = '',
}: {
  href: string
  children: ReactNode
  className?: string
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={`inline-flex h-12 items-center justify-center gap-2 whitespace-nowrap rounded-control bg-ink px-5 text-[15px] font-semibold text-surface hover:opacity-90 ${press} ${focus} ${className}`}
    >
      {children}
    </a>
  )
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-medium text-ink">{label}</span>
      {children}
      {hint ? <span className="text-[13px] leading-snug text-muted">{hint}</span> : null}
    </div>
  )
}

export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
  disabled = false,
}: {
  label: string
  value: T
  options: { value: T; label: string }[]
  disabled?: boolean
  onChange: (value: T) => void
}) {
  return (
    <div role="radiogroup" aria-label={label} className="grid auto-cols-fr grid-flow-col gap-1 liquid-segment rounded-control p-1">
      {options.map((option) => {
        const active = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            disabled={disabled}
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option.value)}
            className={`min-h-9 min-w-0 whitespace-nowrap rounded-[11px] px-1.5 py-1 text-[13px] font-medium leading-snug transition sm:text-sm ${focus} ${
              active ? 'liquid-selection text-ink' : 'text-muted hover:text-ink'
            }`}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

export function Stepper({
  label,
  value,
  min,
  max,
  step,
  format,
  onChange,
  className = '',
}: {
  className?: string
  label: string
  value: number
  min: number
  max: number
  step: number
  format: (value: number) => string
  onChange: (value: number) => void
}) {
  const { t } = useI18n()
  const clamp = (next: number) => Math.min(max, Math.max(min, Math.round(next * 10) / 10))
  const button = `grid size-9 place-items-center rounded-[11px] text-ink hover:bg-sunken ${press} ${focus}`
  return (
    <div className={`inline-flex h-11 items-center gap-1 self-start liquid-control rounded-control p-1 ${className}`} role="group" aria-label={label}>
      <button type="button" className={button} aria-label={t('ui.decrease', { label })} disabled={value <= min} onClick={() => onChange(clamp(value - step))}>
        <MinusIcon size={16} weight="bold" />
      </button>
      <output className="num flex-1 min-w-[4.5rem] text-center text-[15px] font-medium" aria-live="polite">
        {format(value)}
      </output>
      <button type="button" className={button} aria-label={t('ui.increase', { label })} disabled={value >= max} onClick={() => onChange(clamp(value + step))}>
        <PlusIcon size={16} weight="bold" />
      </button>
    </div>
  )
}

export function Toggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string
  description?: string
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  const id = useId()
  return (
    <label htmlFor={id} className="flex cursor-pointer items-start justify-between gap-4">
      <span className="flex flex-col gap-0.5">
        <span className="text-[15px] text-ink">{label}</span>
        {description ? <span className="text-[13px] leading-snug text-muted">{description}</span> : null}
      </span>
      <span className="relative mt-0.5 inline-flex shrink-0">
        <input id={id} type="checkbox" className="peer sr-only" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        <span className="h-6 w-10 rounded-full bg-line transition peer-checked:bg-accent peer-focus-visible:ring-2 peer-focus-visible:ring-accent peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-canvas" />
        <span className="absolute left-0.5 top-0.5 size-5 rounded-full bg-surface shadow-sm transition peer-checked:translate-x-4" />
      </span>
    </label>
  )
}

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`h-11 w-full rounded-control border border-line bg-surface px-3 text-[15px] text-ink placeholder:text-faint ${focus} ${props.className ?? ''}`}
    />
  )
}

/** Bottom sheet on phones, centered panel on wider screens. Native dialog handles focus and Escape. */
export function Sheet({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
}) {
  const { t } = useI18n()
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(event) => event.target === ref.current && onClose()}
      aria-label={title}
      className="liquid-sheet m-0 mt-auto max-h-[92dvh] w-full max-w-none rounded-t-box p-0 text-ink shadow-raised backdrop:bg-[#3a3328]/25 backdrop:backdrop-blur-[2px] sm:m-auto sm:max-w-md sm:rounded-box"
    >
      <div className="sticky top-0 z-10 flex items-center justify-between liquid-sheet-heading px-5 py-4">
        <h2 className="text-base font-semibold">{title}</h2>
        <button type="button" onClick={onClose} aria-label={t('ui.close')} className={`grid size-9 place-items-center rounded-control text-muted hover:bg-sunken hover:text-ink ${focus}`}>
          <XIcon size={18} />
        </button>
      </div>
      {open ? <div className="px-5 pb-8 pt-5">{children}</div> : null}
    </dialog>
  )
}
