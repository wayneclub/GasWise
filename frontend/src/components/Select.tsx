import { CaretDownIcon, CheckIcon } from '@phosphor-icons/react'
import { useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

export type SelectOption<T extends string> = {
  value: T
  label: string
  icon?: ReactNode
  description?: string
  disabled?: boolean
}

export type SelectProps<T extends string> = {
  label: string
  value: T
  options: readonly SelectOption<T>[]
  onChange: (value: T) => void
  disabled?: boolean
  /** A compact trigger still announces label and selected value to assistive technology. */
  iconOnly?: boolean
  triggerIcon?: ReactNode
  align?: 'start' | 'end'
  panelWidth?: number
  className?: string
  triggerClassName?: string
  panelClassName?: string
  optionClassName?: string
  renderValue?: (option: SelectOption<T>) => ReactNode
  renderOption?: (option: SelectOption<T>, selected: boolean) => ReactNode
}

const focusRing = 'outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface'

/** Single-choice listbox: portal avoids clipping, viewport-aware placement works on touch and desktop. */
export function Select<T extends string>({ label, value, options, onChange, disabled = false, iconOnly = false,
  triggerIcon, align = 'start', panelWidth = 288, className = '', triggerClassName = '', panelClassName = '',
  optionClassName = '', renderValue, renderOption }: SelectProps<T>) {
  const id = useId()
  const trigger = useRef<HTMLButtonElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const optionRefs = useRef(new Map<string, HTMLButtonElement>())
  const initialFocus = useRef<T | undefined>(undefined)
  const focusPending = useRef(false)
  const typeahead = useRef({ text: '', at: 0 })
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState<CSSProperties>({ visibility: 'hidden' })
  const selected = options.find(option => option.value === value)
  const enabled = options.filter(option => !option.disabled)
  const expanded = open && !disabled

  useEffect(() => {
    if (disabled) setOpen(false)
  }, [disabled])

  function close(restoreFocus = false) {
    setOpen(false)
    if (restoreFocus) trigger.current?.focus()
  }

  useLayoutEffect(() => {
    if (!expanded) return
    focusPending.current = true
    const viewport = window.visualViewport
    function place() {
      const rect = trigger.current?.getBoundingClientRect()
      if (!rect) return
      const x = viewport?.offsetLeft ?? 0
      const y = viewport?.offsetTop ?? 0
      const width = viewport?.width ?? window.innerWidth
      const height = viewport?.height ?? window.innerHeight
      const gutter = 12
      const panelSize = Math.min(Math.max(panelWidth, rect.width), width - gutter * 2)
      const below = y + height - rect.bottom - gutter - 8
      const above = rect.top - y - gutter - 8
      const desired = Math.min(panel.current?.scrollHeight ?? 360, 360)
      const flipped = below < desired && above > below
      setPosition({
        width: panelSize,
        left: Math.max(x + gutter, Math.min(align === 'end' ? rect.right - panelSize : rect.left, x + width - panelSize - gutter)),
        ...(flipped ? { bottom: window.innerHeight - rect.top + 8 } : { top: rect.bottom + 8 }),
        maxHeight: Math.max(1, Math.min(360, flipped ? above : below)),
      })
    }
    place()
    function outside(event: PointerEvent) {
      const node = event.target as Node
      if (!trigger.current?.contains(node) && !panel.current?.contains(node)) setOpen(false)
    }
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    viewport?.addEventListener('resize', place)
    viewport?.addEventListener('scroll', place)
    document.addEventListener('pointerdown', outside)
    return () => {
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
      viewport?.removeEventListener('resize', place)
      viewport?.removeEventListener('scroll', place)
      document.removeEventListener('pointerdown', outside)
    }
    // Focus is set once per opening; a translated label must not reset keyboard navigation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded, align, panelWidth])

  useLayoutEffect(() => {
    // Browsers cannot focus the initially hidden portal until placement has committed.
    if (!expanded || position.visibility === 'hidden' || !focusPending.current) return
    const target = initialFocus.current ?? (selected?.disabled ? undefined : selected?.value) ?? enabled[0]?.value
    initialFocus.current = undefined
    focusPending.current = false
    if (target !== undefined) {
      const option = optionRefs.current.get(target)
      option?.focus({ preventScroll: true })
      option?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' })
    }
  }, [expanded, position, selected, enabled])

  useEffect(() => {
    if (!expanded) return
    function focusOutside(event: FocusEvent) {
      const node = event.target as Node
      if (!trigger.current?.contains(node) && !panel.current?.contains(node)) setOpen(false)
    }
    document.addEventListener('focusin', focusOutside)
    return () => document.removeEventListener('focusin', focusOutside)
  }, [expanded])

  return <div className={className}>
    <button ref={trigger} type="button" aria-label={label} title={label} disabled={disabled}
      aria-haspopup="listbox" aria-expanded={expanded} aria-controls={expanded ? id : undefined}
      aria-describedby={selected ? `${id}-value` : undefined}
      className={`inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-control text-sm text-ink transition hover:bg-sunken disabled:opacity-50 ${focusRing} ${iconOnly ? 'size-11' : 'w-full border border-line bg-surface px-3 py-2 text-left'} ${triggerClassName}`}
      onClick={() => setOpen(!expanded)}
      onKeyDown={event => {
        if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
          event.preventDefault()
          initialFocus.current = event.key === 'End' || event.key === 'ArrowUp' ? enabled.at(-1)?.value : event.key === 'Home' ? enabled[0]?.value : selected?.disabled ? enabled[0]?.value : selected?.value
          setOpen(true)
        } else if (event.key === 'Escape') close()
      }}>
      {triggerIcon ? <span aria-hidden="true" className="shrink-0">{triggerIcon}</span> : null}
      <span id={`${id}-value`} className={iconOnly ? 'sr-only' : 'min-w-0 flex-1 break-words'}>{selected ? renderValue?.(selected) ?? selected.label : value}</span>
      {!iconOnly ? <CaretDownIcon size={16} aria-hidden="true" className="shrink-0 text-muted" /> : null}
    </button>
    {expanded ? createPortal(<div ref={panel} id={id} role="listbox" aria-label={label} style={position}
      className={`fixed z-50 overflow-y-auto overscroll-contain rounded-box border border-line bg-surface p-1.5 text-ink shadow-raised ${panelClassName}`}
      onKeyDown={event => {
        const current = enabled.findIndex(option => optionRefs.current.get(option.value) === document.activeElement)
        if ((event.key === 'Enter' || event.key === ' ') && enabled[current]) {
          event.preventDefault()
          onChange(enabled[current].value)
          close(true)
          return
        }
        let next: number | undefined
        if (event.key === 'ArrowDown') next = (current + 1) % enabled.length
        if (event.key === 'ArrowUp') next = (current - 1 + enabled.length) % enabled.length
        if (event.key === 'Home') next = 0
        if (event.key === 'End') next = enabled.length - 1
        if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(true) }
        if (event.key === 'Tab') close(true)
        if (event.key.length === 1 && event.key !== ' ' && !event.ctrlKey && !event.metaKey && !event.altKey) {
          const now = Date.now()
          const previous = now - typeahead.current.at < 600 ? typeahead.current.text : ''
          const text = previous + event.key.toLocaleLowerCase()
          typeahead.current = { text, at: now }
          const matches = (prefix: string) => enabled.findIndex((option, index) => index > current && option.label.toLocaleLowerCase().startsWith(prefix))
          next = matches(text)
          if (next < 0) next = enabled.findIndex(option => option.label.toLocaleLowerCase().startsWith(text))
          if (next < 0 && previous === event.key.toLocaleLowerCase()) next = matches(event.key.toLocaleLowerCase())
        }
        if (next !== undefined && enabled[next]) {
          event.preventDefault()
          optionRefs.current.get(enabled[next].value)?.focus()
        }
      }}>
      {options.map((option, index) => <button key={option.value} type="button" role="option" aria-label={option.label} aria-selected={option.value === value}
        aria-describedby={option.description && !renderOption ? `${id}-description-${index}` : undefined}
        disabled={option.disabled} tabIndex={-1} ref={node => { if (node) optionRefs.current.set(option.value, node); else optionRefs.current.delete(option.value) }}
        className={`flex min-h-12 w-full items-center gap-3 rounded-control px-3 py-2.5 text-left text-sm hover:bg-sunken focus:bg-sunken disabled:opacity-50 ${focusRing} ${optionClassName}`}
        onClick={() => { onChange(option.value); close(true) }}>
        {renderOption ? renderOption(option, option.value === value) : <>
          {option.icon ? <span aria-hidden="true" className="grid size-6 shrink-0 place-items-center text-xl">{option.icon}</span> : null}
          <span className="min-w-0 flex-1 break-words"><span className="block font-medium">{option.label}</span>{option.description ? <span id={`${id}-description-${index}`} className="mt-0.5 block text-xs text-muted">{option.description}</span> : null}</span>
        </>}
        <CheckIcon size={18} aria-hidden="true" className={`ml-auto shrink-0 text-accent ${option.value === value ? '' : 'invisible'}`} />
      </button>)}
    </div>, document.body) : null}
  </div>
}
