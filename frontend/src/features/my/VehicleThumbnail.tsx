import { useId, useMemo } from 'react'
import {
  inferVehicleArchetype,
  inferVehicleSilhouette,
  SILHOUETTE_TO_ARCHETYPE,
  type VehicleArchetype,
  type VehicleSilhouette,
} from '../../lib/vehicleStyle'
import { useI18n } from '../../i18n'

interface VehicleThumbnailProps {
  label?: string | null
  bodyStyle?: VehicleArchetype | string | null
  color?: string | null
  className?: string
  size?: 'sm' | 'md' | 'lg'
  showBadge?: boolean
  active?: boolean
}

// Adjust a hex color by a percentage (-100 to +100) to create realistic specular reflections and shadow tones
function adjustColor(hex: string, percent: number): string {
  let num = parseInt(hex.replace('#', ''), 16)
  if (isNaN(num)) return hex
  let r = (num >> 16) + Math.round(2.55 * percent)
  let g = ((num >> 8) & 0x00ff) + Math.round(2.55 * percent)
  let b = (num & 0x0000ff) + Math.round(2.55 * percent)
  r = Math.min(255, Math.max(0, r))
  g = Math.min(255, Math.max(0, g))
  b = Math.min(255, Math.max(0, b))
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`
}

export function VehicleThumbnail({
  label,
  bodyStyle,
  color,
  className = '',
  size = 'md',
  showBadge = false,
  active = false,
}: VehicleThumbnailProps) {
  const { t } = useI18n()
  const uid = useId().replace(/:/g, '')

  const silhouette: VehicleSilhouette = useMemo(() => {
    if (
      bodyStyle &&
      ['coupe', 'convertible', 'sedan', 'suv', 'truck', 'hatchback', 'wagon', 'van'].includes(bodyStyle)
    ) {
      if (bodyStyle === 'coupe') return 'e_class_coupe'
      if (bodyStyle === 'convertible') return 'roadster_convertible'
      if (bodyStyle === 'suv') return 'crossover_suv'
      if (bodyStyle === 'truck') return 'pickup_truck'
      if (bodyStyle === 'hatchback') return 'hatchback_golf'
      if (bodyStyle === 'wagon') return 'wagon_estate'
      if (bodyStyle === 'van') return 'minivan'
      return 'executive_sedan'
    }
    return inferVehicleSilhouette(label)
  }, [bodyStyle, label])

  const archetype: VehicleArchetype = useMemo(() => {
    return SILHOUETTE_TO_ARCHETYPE[silhouette] ?? inferVehicleArchetype(label)
  }, [silhouette, label])

  const baseColor = color && /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(color) ? color : '#1e293b'
  const highlightColor = adjustColor(baseColor, 28)
  const shadowColor = adjustColor(baseColor, -35)
  const isLightCar = useMemo(() => {
    let num = parseInt(baseColor.replace('#', ''), 16)
    if (isNaN(num)) return false
    const r = num >> 16
    const g = (num >> 8) & 0xff
    const b = num & 0xff
    return (r * 299 + g * 587 + b * 114) / 1000 > 165
  }, [baseColor])

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
            {/* Metallic Automotive Finish Gradient */}
            <linearGradient id={`car-paint-${uid}`} x1="0" y1="20" x2="0" y2="65" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor={highlightColor} />
              <stop offset="40%" stopColor={baseColor} />
              <stop offset="100%" stopColor={shadowColor} />
            </linearGradient>

            {/* Tinted Automotive Glass with Specular Glare */}
            <linearGradient id={`car-glass-${uid}`} x1="0" y1="24" x2="0" y2="44" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#bae6fd" stopOpacity="0.8" />
              <stop offset="45%" stopColor="#0f172a" stopOpacity="0.85" />
              <stop offset="100%" stopColor="#1e293b" stopOpacity="0.95" />
            </linearGradient>

            {/* Chrome Trim Accent */}
            <linearGradient id={`car-chrome-${uid}`} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#94a3b8" />
              <stop offset="50%" stopColor="#f8fafc" />
              <stop offset="100%" stopColor="#64748b" />
            </linearGradient>
          </defs>

          {/* Underbody Ground Shadow */}
          <ellipse cx="100" cy="67" rx="84" ry="4" fill="currentColor" className="text-ink/15 dark:text-ink/30" />

          {/* Real Body Panels & Silhouette */}
          {renderVehicleSilhouette(silhouette, `url(#car-paint-${uid})`, `url(#car-glass-${uid})`, isLightCar)}

          {/* Precision Wheels */}
          {renderWheels(silhouette)}
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

function renderVehicleSilhouette(
  silhouette: VehicleSilhouette,
  paintUrl: string,
  glassUrl: string,
  isLightCar: boolean,
) {
  const lineStroke = isLightCar ? '#475569' : '#0f172a'

  switch (silhouette) {
    case 'e_class_coupe':
      return (
        <g>
          {/* Mercedes E-Class Coupe (C238) - Sleek pillarless fastback arch with frameless side glass */}
          <path
            d="M 16 58 C 16 53 22 47 38 46 L 68 44 C 84 31 106 25 142 27 C 162 28 175 43 185 49 C 190 52 192 56 190 60 C 188 62 182 62 178 62 L 24 62 C 18 62 16 60 16 58 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Sweeping Pillarless Side Glass */}
          <path
            d="M 72 43 C 86 32 108 27 138 29 C 148 30 156 38 162 43 C 158 44 80 44 72 43 Z"
            fill={glassUrl}
          />
          {/* Characteristic Mercedes Shoulder Crease Line */}
          <path d="M 40 47 C 80 45 130 45 180 50" stroke={lineStroke} strokeWidth="0.75" strokeOpacity="0.4" />
          {/* LED Eyebrow Headlight */}
          <path d="M 183 50 L 190 52 L 186 54 Z" fill="#38bdf8" />
          {/* Horizontal Stardust OLED Taillight Strip */}
          <path d="M 16 51 L 24 51 L 22 55 L 16 55 Z" fill="#ef4444" />
        </g>
      )

    case 'muscle_coupe':
      return (
        <g>
          {/* Ford Mustang / Muscle Coupe - Long muscular hood, recessed shark nose, raised fastback haunches */}
          <path
            d="M 14 58 C 14 53 20 45 32 44 L 64 43 L 80 27 C 84 25 90 24 98 24 L 128 24 C 136 24 144 32 152 42 L 178 44 C 188 45 192 52 188 60 C 186 62 180 62 176 62 L 22 62 C 16 62 14 60 14 58 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Fastback Glass with Triangular Quarter Glass */}
          <path d="M 70 42 L 82 28 L 124 28 C 130 28 138 34 144 42 Z" fill={glassUrl} />
          {/* Rear Deck Spoiler */}
          <line x1="16" y1="44" x2="26" y2="44" stroke={lineStroke} strokeWidth="1.5" strokeLinecap="round" />
          {/* Tri-Bar LED Headlight */}
          <path d="M 183 47 L 188 49 L 186 53 Z" fill="#38bdf8" />
          {/* Iconic Tri-Bar Taillight */}
          <path d="M 15 47 L 20 47 L 19 54 L 15 54 Z" fill="#ef4444" />
        </g>
      )

    case 'porsche_coupe':
      return (
        <g>
          {/* Porsche 911 / Carrera - Iconic continuous flyline arch sloping down to the rear engine bumper */}
          <path
            d="M 16 60 C 16 54 22 50 36 49 L 66 43 C 80 27 106 25 136 26 C 158 27 172 44 186 52 C 190 55 191 58 189 60 C 187 62 180 62 176 62 L 24 62 C 18 62 16 61 16 60 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Teardrop Glasshouse */}
          <path d="M 72 42 C 84 29 104 27 132 28 C 144 29 154 36 162 43 Z" fill={glassUrl} />
          {/* Sloping Rear Engine Lid Crease */}
          <line x1="32" y1="50" x2="64" y2="44" stroke={lineStroke} strokeWidth="0.75" strokeOpacity="0.4" />
          {/* Oval Porsche 4-point Headlight */}
          <ellipse cx="182" cy="51" rx="3.5" ry="2.5" fill="#38bdf8" />
          {/* Full-width LED Light Strip */}
          <line x1="16" y1="52" x2="28" y2="52" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" />
        </g>
      )

    case 'tesla_sedan':
      return (
        <g>
          {/* Tesla Model 3 / S - Minimalist all-glass aerodynamic teardrop fastback */}
          <path
            d="M 16 58 C 16 53 22 47 36 46 L 64 43 C 78 27 106 23 138 24 C 158 25 170 38 184 49 C 189 53 190 57 188 60 C 186 62 180 62 176 62 L 24 62 C 18 62 16 60 16 58 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Panoramic Arch Glass Roof */}
          <path d="M 68 42 C 80 28 106 25 134 26 C 146 27 158 35 166 43 Z" fill={glassUrl} />
          {/* Flush Aero Door Handle Accents */}
          <line x1="84" y1="46" x2="94" y2="46" stroke={lineStroke} strokeWidth="1" strokeOpacity="0.5" />
          <line x1="126" y1="46" x2="136" y2="46" stroke={lineStroke} strokeWidth="1" strokeOpacity="0.5" />
          {/* Sleek Blade Headlight */}
          <path d="M 180 48 L 186 50 L 183 53 Z" fill="#38bdf8" />
          {/* LED Taillight */}
          <path d="M 17 48 L 22 48 L 20 54 L 17 54 Z" fill="#ef4444" />
        </g>
      )

    case 'cybertruck':
      return (
        <g>
          {/* Tesla Cybertruck - Polygonal stainless steel triangular origami geometry */}
          <polygon
            points="14,60 14,48 76,46 112,21 168,44 190,48 190,60 178,62 24,62"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="1"
          />
          {/* Triangular Flat Facet Glass */}
          <polygon points="78,45 110,23 162,43 78,45" fill={glassUrl} />
          {/* Full-width Front Cyber Light Bar */}
          <line x1="185" y1="47" x2="190" y2="48" stroke="#38bdf8" strokeWidth="2.5" />
          {/* Full-width Rear Red Blade Bar */}
          <line x1="14" y1="47" x2="15" y2="52" stroke="#ef4444" strokeWidth="2.5" />
        </g>
      )

    case 'pickup_truck':
      return (
        <g>
          {/* Ford F-150 / Pickup Truck - Upright bold front, distinct SuperCrew cab, flat open bed */}
          <path
            d="M 14 58 C 14 52 18 46 26 46 L 86 46 L 92 26 C 94 24 98 23 104 23 L 140 23 C 146 23 153 27 158 35 L 168 45 L 188 47 C 192 48 193 54 191 58 C 189 62 182 62 178 62 L 22 62 C 16 62 14 60 14 58 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Truck SuperCrew Windows */}
          <path d="M 98 26 L 136 26 C 141 26 146 30 150 36 L 156 43 L 98 43 Z" fill={glassUrl} />
          {/* Open Bed Tie-down Rail */}
          <line x1="26" y1="44" x2="86" y2="44" stroke={lineStroke} strokeWidth="2" strokeLinecap="round" />
          {/* C-Clamp Headlight */}
          <rect x="184" y="48" width="5" height="7" rx="1.5" fill="#38bdf8" />
          {/* Vertical Taillight */}
          <rect x="15" y="47" width="4" height="8" rx="1" fill="#ef4444" />
        </g>
      )

    case 'boxy_suv':
      return (
        <g>
          {/* Jeep Wrangler / G-Class - Rugged upright body, flat roof, rear mounted spare tire */}
          <path
            d="M 22 58 C 22 50 25 30 30 26 C 32 24 36 23 44 23 L 136 23 C 140 23 148 26 154 36 L 168 44 L 186 46 C 190 48 191 54 189 58 C 187 62 180 62 176 62 L 26 62 C 22 62 22 60 22 58 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Upright Flat Windows */}
          <path d="M 36 26 L 76 26 L 76 42 L 34 42 Z" fill={glassUrl} />
          <path d="M 82 26 L 132 26 C 136 26 142 30 146 36 L 152 42 L 82 42 Z" fill={glassUrl} />
          {/* Rear External Spare Tire */}
          <ellipse cx="16" cy="46" rx="6" ry="12" fill="#0f172a" stroke="#334155" strokeWidth="1.5" />
          <circle cx="16" cy="46" r="3" fill="#64748b" />
          {/* Round Iconic Headlight */}
          <circle cx="184" cy="50" r="3.5" fill="#38bdf8" />
          {/* Square Taillight */}
          <rect x="23" y="45" width="4" height="6" rx="1" fill="#ef4444" />
        </g>
      )

    case 'crossover_suv':
      return (
        <g>
          {/* Toyota RAV4 / CR-V / Model Y - High athletic stance, sloping roofline, sporty rear spoiler */}
          <path
            d="M 15 56 C 15 50 20 44 32 44 L 46 44 L 56 25 C 58 23 62 22 68 22 L 136 22 C 142 22 150 27 156 34 L 172 44 C 182 46 190 50 189 57 C 188 61 180 62 175 62 L 25 62 C 18 62 15 60 15 56 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Aerodynamic Roof Rails */}
          <line x1="70" y1="20" x2="134" y2="20" stroke={lineStroke} strokeWidth="2" strokeLinecap="round" />
          {/* SUV Dynamic Windows */}
          <path d="M 58 26 L 96 26 L 96 42 L 50 42 Z" fill={glassUrl} />
          <path d="M 100 26 L 132 26 C 137 26 142 29 146 34 L 152 42 L 100 42 Z" fill={glassUrl} />
          {/* Dark Wheel Arch Cladding Trim */}
          <path d="M 16 57 C 30 57 38 52 46 62" stroke={lineStroke} strokeWidth="1" strokeOpacity="0.5" />
          {/* Front LED Light */}
          <path d="M 183 47 L 189 49 L 186 52 Z" fill="#38bdf8" />
          {/* Rear Taillight */}
          <path d="M 16 46 L 22 46 L 20 53 L 16 53 Z" fill="#ef4444" />
        </g>
      )

    case 'roadster_convertible':
      return (
        <g>
          {/* Mazda MX-5 Miata - Ultra-compact low roadster, open cockpit with sports roll hoop */}
          <path
            d="M 18 58 C 18 53 24 48 40 47 L 76 46 C 82 46 86 48 94 48 L 138 48 C 150 48 162 48 174 50 C 186 52 190 56 188 60 C 186 62 180 62 176 62 L 24 62 C 19 62 18 60 18 58 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Sport Raked Windshield */}
          <path d="M 112 47 L 132 32 C 134 30 136 31 138 33 L 134 47 Z" fill={glassUrl} />
          {/* Twin Sport Roll Hoops */}
          <path d="M 88 46 C 88 38 96 38 96 46 Z" fill={lineStroke} stroke={lineStroke} strokeWidth="1" />
          {/* LED Headlight */}
          <path d="M 183 51 L 188 53 L 185 55 Z" fill="#38bdf8" />
          {/* Round Taillight */}
          <circle cx="20" cy="52" r="2.5" fill="#ef4444" />
        </g>
      )

    case 'aero_hatch_prius':
      return (
        <g>
          {/* Toyota Prius - One-motion aero wedge from low nose through roof apex down to split tail */}
          <path
            d="M 16 58 C 16 52 20 43 32 40 L 98 22 C 104 22 112 25 120 30 L 164 45 L 180 49 C 188 52 190 56 188 60 C 186 62 180 62 176 62 L 24 62 C 18 62 16 60 16 58 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Sloping Wedge Glass */}
          <path d="M 44 40 L 96 24 L 118 30 L 150 43 L 40 43 Z" fill={glassUrl} />
          {/* Aero Split Rear Glass Detail */}
          <line x1="24" y1="42" x2="36" y2="42" stroke={glassUrl} strokeWidth="2" />
          {/* Bi-LED Headlight */}
          <path d="M 176 50 L 185 52 L 180 55 Z" fill="#38bdf8" />
          {/* Vertical Rear Tailfin Light */}
          <path d="M 18 42 L 22 40 L 20 54 L 17 54 Z" fill="#ef4444" />
        </g>
      )

    case 'hatchback_golf':
      return (
        <g>
          {/* VW Golf GTI - Iconic solid thick C-pillar, European compact hot hatch silhouette */}
          <path
            d="M 18 57 C 18 51 22 43 32 40 L 56 26 C 60 24 65 23 72 23 L 126 23 C 132 23 140 27 146 35 L 160 45 C 172 48 184 52 182 58 C 180 62 174 62 170 62 L 26 62 C 20 62 18 60 18 57 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Golf 2-box Side Windows */}
          <path d="M 48 38 L 60 26 L 88 26 L 88 42 L 40 42 Z" fill={glassUrl} />
          <path d="M 92 26 L 122 26 C 127 26 132 29 136 34 L 142 42 L 92 42 Z" fill={glassUrl} />
          {/* Red GTI Grille Accent Line */}
          <line x1="172" y1="51" x2="182" y2="52" stroke="#ef4444" strokeWidth="1.5" />
          {/* Headlight */}
          <path d="M 176 49 L 182 51 L 178 54 Z" fill="#38bdf8" />
          {/* L-shaped Taillight */}
          <path d="M 20 45 L 25 43 L 23 50 L 19 50 Z" fill="#ef4444" />
        </g>
      )

    case 'wagon_estate':
      return (
        <g>
          {/* Subaru Outback / Estate Wagon - Extended roofline, extra cargo glass, adventure cladding */}
          <path
            d="M 16 57 C 16 51 21 44 32 42 L 44 25 C 46 23 50 22 56 22 L 138 22 C 145 22 154 27 160 35 L 172 44 C 182 47 188 51 186 57 C 184 62 178 62 174 62 L 24 62 C 18 62 16 60 16 57 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Roof Rack Rail */}
          <line x1="50" y1="20" x2="136" y2="20" stroke={lineStroke} strokeWidth="2" strokeLinecap="round" />
          {/* 3-Pane Extended Estate Glass */}
          <path d="M 44 26 L 76 26 L 76 41 L 34 41 Z" fill={glassUrl} />
          <path d="M 80 26 L 110 26 L 110 41 L 80 41 Z" fill={glassUrl} />
          <path d="M 114 26 L 134 26 C 139 26 144 29 148 34 L 154 41 L 114 41 Z" fill={glassUrl} />
          {/* Headlight */}
          <path d="M 180 47 L 186 50 L 183 53 Z" fill="#38bdf8" />
          {/* Taillight */}
          <path d="M 17 46 L 22 46 L 20 52 L 17 52 Z" fill="#ef4444" />
        </g>
      )

    case 'minivan':
      return (
        <g>
          {/* Toyota Sienna / Minivan - Spacious monovolume aerovan profile, large passenger glass */}
          <path
            d="M 16 57 C 16 50 22 38 32 30 C 36 26 42 24 50 24 L 134 24 C 142 24 152 30 160 40 L 176 47 C 184 50 188 54 187 59 C 185 62 178 62 174 62 L 24 62 C 18 62 16 60 16 57 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Panorama Passenger Window Strip */}
          <path d="M 38 32 L 80 28 L 80 42 L 32 42 Z" fill={glassUrl} />
          <path d="M 84 28 L 126 28 L 126 42 L 84 42 Z" fill={glassUrl} />
          <path d="M 130 28 L 134 28 C 140 28 146 32 152 38 L 156 42 L 130 42 Z" fill={glassUrl} />
          {/* Sliding Door Guide Seam */}
          <line x1="72" y1="46" x2="124" y2="46" stroke={lineStroke} strokeWidth="1" strokeOpacity="0.4" />
          {/* Headlight */}
          <path d="M 180 49 L 186 52 L 182 55 Z" fill="#38bdf8" />
          {/* Vertical Rear Taillight */}
          <rect x="17" y="38" width="4" height="15" rx="1" fill="#ef4444" />
        </g>
      )

    case 'executive_sedan':
    default:
      return (
        <g>
          {/* Toyota Camry / Honda Accord / Executive Sedan - Balanced 3-box sedan, elegant proportions */}
          <path
            d="M 16 58 C 16 52 22 46 36 45 L 62 44 L 78 28 C 82 25 88 24 96 24 L 130 24 C 138 24 146 28 152 36 L 164 45 L 174 46 C 184 48 189 53 188 59 C 186 62 180 62 176 62 L 24 62 C 18 62 16 60 16 58 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Passenger Cabin Glass with B-Pillar */}
          <path d="M 68 42 L 80 28 L 102 28 L 102 42 Z" fill={glassUrl} />
          <path d="M 106 28 L 128 28 C 134 28 139 31 144 37 L 148 42 L 106 42 Z" fill={glassUrl} />
          <line x1="104" y1="26" x2="104" y2="43" stroke={lineStroke} strokeWidth="2" />
          {/* Character Beltline */}
          <path d="M 40 46 C 90 45 130 45 174 48" stroke={lineStroke} strokeWidth="0.75" strokeOpacity="0.35" />
          {/* Headlight */}
          <path d="M 182 48 L 188 50 L 185 53 Z" fill="#38bdf8" />
          {/* Taillight */}
          <path d="M 17 48 L 22 48 L 20 54 L 17 54 Z" fill="#ef4444" />
        </g>
      )
  }
}

function renderWheels(silhouette: VehicleSilhouette) {
  const rearX = silhouette === 'pickup_truck' || silhouette === 'cybertruck' ? 48 : 46
  const frontX = silhouette === 'pickup_truck' || silhouette === 'cybertruck' ? 156 : 154
  const radius =
    silhouette === 'crossover_suv' || silhouette === 'boxy_suv' || silhouette === 'pickup_truck' || silhouette === 'cybertruck'
      ? 12
      : 11
  const rimRadius = radius - 4

  return (
    <g>
      {/* Rear Wheel Tire & Rim */}
      <circle cx={rearX} cy="62" r={radius} fill="#0f172a" stroke="#334155" strokeWidth="1.5" />
      <circle cx={rearX} cy="62" r={rimRadius} fill="#64748b" />
      {/* 5-Spoke Machined Alloy Rim Geometry */}
      <circle cx={rearX} cy="62" r={rimRadius - 2.5} fill="#0f172a" />
      <line x1={rearX - 3.5} y1="62" x2={rearX + 3.5} y2="62" stroke="#94a3b8" strokeWidth="1" />
      <line x1={rearX} y1={62 - 3.5} x2={rearX} y2={62 + 3.5} stroke="#94a3b8" strokeWidth="1" />
      <circle cx={rearX} cy="62" r="1.8" fill="#e2e8f0" />

      {/* Front Wheel Tire & Rim */}
      <circle cx={frontX} cy="62" r={radius} fill="#0f172a" stroke="#334155" strokeWidth="1.5" />
      <circle cx={frontX} cy="62" r={rimRadius} fill="#64748b" />
      <circle cx={frontX} cy="62" r={rimRadius - 2.5} fill="#0f172a" />
      <line x1={frontX - 3.5} y1="62" x2={frontX + 3.5} y2="62" stroke="#94a3b8" strokeWidth="1" />
      <line x1={frontX} y1={62 - 3.5} x2={frontX} y2={62 + 3.5} stroke="#94a3b8" strokeWidth="1" />
      <circle cx={frontX} cy="62" r="1.8" fill="#e2e8f0" />
    </g>
  )
}
