import { useMemo } from 'react'
import { inferVehicleArchetype, type VehicleArchetype } from '../../lib/vehicleStyle'
import { useI18n } from '../../i18n'

interface VehicleThumbnailProps {
  label?: string | null
  bodyStyle?: VehicleArchetype | string | null
  className?: string
  size?: 'sm' | 'md' | 'lg'
  showBadge?: boolean
  active?: boolean
}

export function VehicleThumbnail({
  label,
  bodyStyle,
  className = '',
  size = 'md',
  showBadge = false,
  active = false,
}: VehicleThumbnailProps) {
  const { t } = useI18n()
  const archetype: VehicleArchetype = useMemo(() => {
    if (
      bodyStyle &&
      ['coupe', 'convertible', 'sedan', 'suv', 'truck', 'hatchback', 'wagon', 'van'].includes(bodyStyle)
    ) {
      return bodyStyle as VehicleArchetype
    }
    return inferVehicleArchetype(label)
  }, [bodyStyle, label])

  const dimensions = {
    sm: 'w-20 h-10',
    md: 'w-32 h-16',
    lg: 'w-48 h-24',
  }[size]

  return (
    <div className={`relative flex flex-col items-center justify-center ${className}`}>
      <div
        className={`relative flex items-center justify-center rounded-2xl border transition-all ${dimensions} ${
          active
            ? 'border-accent/40 bg-gradient-to-b from-accent/10 via-surface to-accent/5 shadow-sm'
            : 'border-line/80 bg-sunken/40 dark:bg-sunken/20'
        }`}
      >
        <svg
          viewBox="0 0 200 80"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="h-full w-full p-2 select-none"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id={`car-body-${archetype}`} x1="0" y1="0" x2="200" y2="80" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#334155" />
              <stop offset="50%" stopColor="#1e293b" />
              <stop offset="100%" stopColor="#0f172a" />
            </linearGradient>
            <linearGradient id={`car-glass-${archetype}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#94a3b8" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#334155" stopOpacity="0.85" />
            </linearGradient>
            <filter id={`car-shadow-${archetype}`} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur in="SourceAlpha" stdDeviation="3" />
              <feOffset dx="0" dy="4" result="offsetblur" />
              <feComponentTransfer>
                <feFuncA type="linear" slope="0.35" />
              </feComponentTransfer>
              <feMerge>
                <feMergeNode />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Underbody Ground Shadow */}
          <ellipse cx="100" cy="67" rx="84" ry="4" fill="currentColor" className="text-ink/15 dark:text-ink/30" />

          {/* Body and Greenhouse according to Archetype */}
          {renderSilhouette(archetype)}

          {/* Front & Rear Wheels (Common precision alloy design) */}
          {renderWheels(archetype)}
        </svg>
      </div>

      {showBadge ? (
        <span
          className={`mt-1.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium tracking-wide uppercase ${
            active
              ? 'bg-accent/15 text-accent font-semibold'
              : 'bg-sunken text-muted'
          }`}
        >
          {t(`garage.archetype.${archetype}`)}
        </span>
      ) : null}
    </div>
  )
}

function renderSilhouette(archetype: VehicleArchetype) {
  switch (archetype) {
    case 'coupe':
      return (
        <g>
          {/* Coupe Low Aerodynamic Body */}
          <path
            d="M 16 58 C 16 54 22 47 38 46 L 68 44 C 84 32 108 26 142 28 C 160 29 174 44 184 49 C 190 52 192 56 190 60 C 188 62 182 62 178 62 L 24 62 C 18 62 16 60 16 58 Z"
            fill="currentColor"
            className="text-slate-700 dark:text-slate-300 transition-colors"
          />
          {/* Fastback Glass */}
          <path
            d="M 72 43 C 86 33 108 28 138 30 C 148 31 156 38 162 44 L 72 43 Z"
            fill="currentColor"
            className="text-sky-200/80 dark:text-slate-900/90"
          />
          {/* Subtle Window Pillar */}
          <line x1="112" y1="29" x2="114" y2="43" stroke="currentColor" strokeWidth="2" className="text-slate-800 dark:text-slate-200" />
          {/* LED Headlight (Amber/Cyan) */}
          <path d="M 184 50 L 190 52 L 186 54 Z" fill="#38bdf8" />
          {/* Taillight Strip (Ruby Red) */}
          <path d="M 16 52 L 20 52 L 19 56 L 16 56 Z" fill="#ef4444" />
        </g>
      )

    case 'convertible':
      return (
        <g>
          {/* Convertible Open Roadster Body */}
          <path
            d="M 18 58 C 18 53 24 48 40 47 L 76 46 C 82 46 86 48 94 48 L 138 48 C 150 48 162 48 174 50 C 186 52 190 56 188 60 C 186 62 180 62 176 62 L 24 62 C 19 62 18 60 18 58 Z"
            fill="currentColor"
            className="text-slate-700 dark:text-slate-300 transition-colors"
          />
          {/* Raked Sport Windshield */}
          <path
            d="M 112 47 L 132 32 C 134 30 136 31 138 33 L 134 47 Z"
            fill="currentColor"
            className="text-sky-200/80 dark:text-slate-900/90"
          />
          {/* Interior Headrest Silhouette */}
          <path d="M 86 46 C 86 40 94 40 94 46 Z" fill="currentColor" className="text-slate-800 dark:text-slate-400" />
          {/* LED Headlight */}
          <path d="M 183 51 L 188 53 L 185 55 Z" fill="#38bdf8" />
          {/* Taillight */}
          <path d="M 18 52 L 22 52 L 21 55 L 18 55 Z" fill="#ef4444" />
        </g>
      )

    case 'suv':
      return (
        <g>
          {/* SUV Muscular High-riding Body */}
          <path
            d="M 15 56 C 15 50 20 44 32 44 L 46 44 L 56 26 C 58 24 62 23 68 23 L 136 23 C 142 23 150 27 156 34 L 172 44 C 182 46 190 50 189 57 C 188 61 180 62 175 62 L 25 62 C 18 62 15 60 15 56 Z"
            fill="currentColor"
            className="text-slate-700 dark:text-slate-300 transition-colors"
          />
          {/* Roof Rail */}
          <line x1="70" y1="21" x2="134" y2="21" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" className="text-slate-500 dark:text-slate-400" />
          {/* SUV Spacious Windows */}
          <path
            d="M 58 27 L 66 26 L 96 26 L 96 42 L 50 42 Z"
            fill="currentColor"
            className="text-sky-200/80 dark:text-slate-900/90"
          />
          <path
            d="M 100 26 L 132 26 C 137 26 142 29 146 34 L 152 42 L 100 42 Z"
            fill="currentColor"
            className="text-sky-200/80 dark:text-slate-900/90"
          />
          {/* Front LED Light */}
          <path d="M 183 47 L 189 49 L 186 52 Z" fill="#38bdf8" />
          {/* Rear Taillight */}
          <path d="M 16 46 L 22 46 L 20 53 L 16 53 Z" fill="#ef4444" />
        </g>
      )

    case 'truck':
      return (
        <g>
          {/* Pickup Cab and Open Bed Body */}
          <path
            d="M 14 58 C 14 52 18 46 26 46 L 86 46 L 92 27 C 94 25 98 24 104 24 L 140 24 C 146 24 153 28 158 35 L 168 45 L 188 47 C 192 48 193 54 191 58 C 189 62 182 62 178 62 L 22 62 C 16 62 14 60 14 58 Z"
            fill="currentColor"
            className="text-slate-700 dark:text-slate-300 transition-colors"
          />
          {/* Truck Cab Glass */}
          <path
            d="M 98 27 L 136 27 C 141 27 146 30 150 36 L 156 43 L 98 43 Z"
            fill="currentColor"
            className="text-sky-200/80 dark:text-slate-900/90"
          />
          {/* Open Bed Top Rail */}
          <line x1="26" y1="44" x2="86" y2="44" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" className="text-slate-500 dark:text-slate-400" />
          {/* Headlight */}
          <rect x="184" y="48" width="5" height="7" rx="1.5" fill="#38bdf8" />
          {/* Taillight */}
          <rect x="15" y="47" width="4" height="8" rx="1" fill="#ef4444" />
        </g>
      )

    case 'hatchback':
      return (
        <g>
          {/* Compact Sloping Tailgate Hatchback Body */}
          <path
            d="M 18 57 C 18 51 22 43 32 40 L 56 27 C 60 25 65 24 72 24 L 126 24 C 132 24 140 28 146 36 L 160 46 C 172 49 184 53 182 59 C 180 62 174 62 170 62 L 26 62 C 20 62 18 60 18 57 Z"
            fill="currentColor"
            className="text-slate-700 dark:text-slate-300 transition-colors"
          />
          {/* Side Glass */}
          <path
            d="M 46 39 L 60 28 L 88 28 L 88 42 L 38 42 Z"
            fill="currentColor"
            className="text-sky-200/80 dark:text-slate-900/90"
          />
          <path
            d="M 92 28 L 122 28 C 127 28 132 31 136 36 L 142 42 L 92 42 Z"
            fill="currentColor"
            className="text-sky-200/80 dark:text-slate-900/90"
          />
          {/* Headlight */}
          <path d="M 176 49 L 182 52 L 178 54 Z" fill="#38bdf8" />
          {/* Taillight */}
          <path d="M 20 45 L 25 43 L 23 50 L 19 50 Z" fill="#ef4444" />
        </g>
      )

    case 'wagon':
      return (
        <g>
          {/* Long Roof Estate Wagon Body */}
          <path
            d="M 16 57 C 16 51 21 44 32 42 L 44 26 C 46 24 50 23 56 23 L 138 23 C 145 23 154 28 160 36 L 172 45 C 182 48 188 52 186 58 C 184 62 178 62 174 62 L 24 62 C 18 62 16 60 16 57 Z"
            fill="currentColor"
            className="text-slate-700 dark:text-slate-300 transition-colors"
          />
          {/* Wagon 3-pane Extended Glass */}
          <path
            d="M 44 27 L 76 27 L 76 41 L 34 41 Z"
            fill="currentColor"
            className="text-sky-200/80 dark:text-slate-900/90"
          />
          <path
            d="M 80 27 L 110 27 L 110 41 L 80 41 Z"
            fill="currentColor"
            className="text-sky-200/80 dark:text-slate-900/90"
          />
          <path
            d="M 114 27 L 134 27 C 139 27 144 30 148 35 L 154 41 L 114 41 Z"
            fill="currentColor"
            className="text-sky-200/80 dark:text-slate-900/90"
          />
          {/* Headlight */}
          <path d="M 180 47 L 186 50 L 183 53 Z" fill="#38bdf8" />
          {/* Taillight */}
          <path d="M 17 46 L 22 46 L 20 52 L 17 52 Z" fill="#ef4444" />
        </g>
      )

    case 'van':
      return (
        <g>
          {/* Minivan Aerovan Body */}
          <path
            d="M 16 57 C 16 50 22 38 32 30 C 36 26 42 24 50 24 L 134 24 C 142 24 152 30 160 40 L 176 47 C 184 50 188 54 187 59 C 185 62 178 62 174 62 L 24 62 C 18 62 16 60 16 57 Z"
            fill="currentColor"
            className="text-slate-700 dark:text-slate-300 transition-colors"
          />
          {/* Large Window Greenhouse */}
          <path
            d="M 38 32 L 80 28 L 80 42 L 32 42 Z"
            fill="currentColor"
            className="text-sky-200/80 dark:text-slate-900/90"
          />
          <path
            d="M 84 28 L 126 28 L 126 42 L 84 42 Z"
            fill="currentColor"
            className="text-sky-200/80 dark:text-slate-900/90"
          />
          <path
            d="M 130 28 L 134 28 C 140 28 146 32 152 38 L 156 42 L 130 42 Z"
            fill="currentColor"
            className="text-sky-200/80 dark:text-slate-900/90"
          />
          {/* Sliding Door Guide Line */}
          <line x1="72" y1="46" x2="124" y2="46" stroke="currentColor" strokeWidth="1.5" className="text-slate-500/50 dark:text-slate-400/40" />
          {/* Headlight */}
          <path d="M 180 49 L 186 52 L 182 55 Z" fill="#38bdf8" />
          {/* Taillight */}
          <rect x="17" y="38" width="4" height="15" rx="1" fill="#ef4444" />
        </g>
      )

    case 'sedan':
    default:
      return (
        <g>
          {/* Classic Aerodynamic 3-Box Sedan Body */}
          <path
            d="M 16 58 C 16 52 22 46 36 45 L 62 44 L 78 28 C 82 25 88 24 96 24 L 130 24 C 138 24 146 28 152 36 L 164 45 L 174 46 C 184 48 189 53 188 59 C 186 62 180 62 176 62 L 24 62 C 18 62 16 60 16 58 Z"
            fill="currentColor"
            className="text-slate-700 dark:text-slate-300 transition-colors"
          />
          {/* Front & Rear Passenger Glass */}
          <path
            d="M 68 42 L 80 28 L 102 28 L 102 42 Z"
            fill="currentColor"
            className="text-sky-200/80 dark:text-slate-900/90"
          />
          <path
            d="M 106 28 L 128 28 C 134 28 139 31 144 37 L 148 42 L 106 42 Z"
            fill="currentColor"
            className="text-sky-200/80 dark:text-slate-900/90"
          />
          {/* Center Pillar */}
          <line x1="104" y1="26" x2="104" y2="43" stroke="currentColor" strokeWidth="2" className="text-slate-800 dark:text-slate-200" />
          {/* Headlight */}
          <path d="M 182 48 L 188 50 L 185 53 Z" fill="#38bdf8" />
          {/* Taillight */}
          <path d="M 17 48 L 22 48 L 20 54 L 17 54 Z" fill="#ef4444" />
        </g>
      )
  }
}

function renderWheels(archetype: VehicleArchetype) {
  // Placement adjusted slightly per archetype wheelbase
  const rearX = archetype === 'truck' ? 48 : archetype === 'hatchback' ? 44 : 46
  const frontX = archetype === 'truck' ? 156 : archetype === 'van' ? 152 : 154
  const radius = archetype === 'suv' || archetype === 'truck' ? 12 : 11
  const rimRadius = radius - 4

  return (
    <g>
      {/* Rear Wheel Well Cutout & Tire */}
      <circle cx={rearX} cy="62" r={radius} fill="#0f172a" stroke="#334155" strokeWidth="1.5" />
      <circle cx={rearX} cy="62" r={rimRadius} fill="#64748b" />
      <circle cx={rearX} cy="62" r={rimRadius - 2.5} fill="#0f172a" />
      <circle cx={rearX} cy="62" r="2" fill="#94a3b8" />

      {/* Front Wheel Well Cutout & Tire */}
      <circle cx={frontX} cy="62" r={radius} fill="#0f172a" stroke="#334155" strokeWidth="1.5" />
      <circle cx={frontX} cy="62" r={rimRadius} fill="#64748b" />
      <circle cx={frontX} cy="62" r={rimRadius - 2.5} fill="#0f172a" />
      <circle cx={frontX} cy="62" r="2" fill="#94a3b8" />
    </g>
  )
}
