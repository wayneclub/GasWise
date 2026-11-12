import type { ReactNode } from 'react'

export interface SettingsSectionProps {
  id?: string
  title: string
  description?: string
  badge?: ReactNode
  aside?: ReactNode
  children: ReactNode
}

export function SettingsSection({
  id,
  title,
  description,
  badge,
  aside,
  children,
}: SettingsSectionProps) {
  return (
    <section
      id={id}
      aria-label={title}
      className="grid grid-cols-1 gap-6 border-b border-line py-8 first:pt-0 last:border-b-0 lg:grid-cols-[280px_1fr] lg:gap-10 lg:py-10"
    >
      <div className="flex flex-col gap-2 lg:pt-1">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-ink">{title}</h2>
          {badge}
        </div>
        {description ? <p className="text-[13px] leading-relaxed text-muted">{description}</p> : null}
        {aside ? <div className="mt-2 text-xs text-muted">{aside}</div> : null}
      </div>
      <div className="liquid-panel rounded-box p-5 sm:p-6 flex flex-col gap-6 min-w-0">
        {children}
      </div>
    </section>
  )
}
