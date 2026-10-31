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
    const specific = inferVehicleSilhouette(label)
    if (specific !== 'executive_sedan') {
      return specific
    }
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
    return specific
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
          {/* Mercedes E-Class Coupe - Sleek pillarless fastback arch with frameless side glass */}
          <path
            d="M 18 54 C 16 50 18 44 28 43 L 64 42 C 78 28 98 23 134 24 C 152 25 164 36 174 44 L 186 46 C 190 48 190 52 188 54 L 168 54 A 14 14 0 0 0 140 54 L 62 54 A 14 14 0 0 0 34 54 L 18 54 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Sweeping Pillarless Side Glass */}
          <path
            d="M 70 41 C 82 29 100 25 130 26 C 142 27 152 35 158 41 Z"
            fill={glassUrl}
          />
          {/* Characteristic Mercedes Shoulder Crease Line */}
          <path d="M 40 45 C 80 43 130 43 180 46" stroke={lineStroke} strokeWidth="0.75" strokeOpacity="0.4" />
          {/* LED Eyebrow Headlight */}
          <path d="M 182 46 L 188 47 L 185 50 Z" fill="#38bdf8" />
          {/* Horizontal Stardust OLED Taillight Strip */}
          <path d="M 17 46 L 24 46 L 22 50 L 17 50 Z" fill="#ef4444" />
        </g>
      )

    case 'muscle_coupe':
      return (
        <g>
          {/* Ford Mustang / Muscle Coupe - Long muscular hood, recessed shark nose, raised fastback haunches */}
          <path
            d="M 16 54 C 14 49 18 42 28 41 L 62 41 L 80 24 C 84 22 90 21 98 21 L 126 21 C 134 21 142 28 148 38 L 182 41 C 188 42 191 48 188 54 L 168 54 A 14 14 0 0 0 140 54 L 62 54 A 14 14 0 0 0 34 54 L 16 54 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Fastback Glass with Triangular Quarter Glass */}
          <path d="M 68 40 L 82 25 L 122 25 C 128 25 134 30 140 39 Z" fill={glassUrl} />
          {/* Rear Deck Spoiler */}
          <line x1="16" y1="41" x2="26" y2="41" stroke={lineStroke} strokeWidth="1.5" strokeLinecap="round" />
          {/* Tri-Bar LED Headlight */}
          <path d="M 182 43 L 187 44 L 185 47 Z" fill="#38bdf8" />
          {/* Iconic Tri-Bar Taillight */}
          <path d="M 16 43 L 20 43 L 19 49 L 16 49 Z" fill="#ef4444" />
        </g>
      )

    case 'porsche_coupe':
      return (
        <g>
          {/* Porsche 911 / Carrera - Iconic continuous flyline arch sloping down to the rear engine bumper */}
          <path
            d="M 16 54 C 15 48 18 46 28 45 C 50 42 74 25 106 24 C 136 24 154 36 172 45 L 186 48 C 190 50 190 53 188 54 L 168 54 A 14 14 0 0 0 140 54 L 62 54 A 14 14 0 0 0 34 54 L 16 54 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Teardrop Glasshouse */}
          <path d="M 68 43 C 80 29 100 27 128 27 C 140 28 150 35 158 42 Z" fill={glassUrl} />
          {/* Sloping Rear Engine Lid Crease */}
          <line x1="32" y1="46" x2="64" y2="42" stroke={lineStroke} strokeWidth="0.75" strokeOpacity="0.4" />
          {/* Oval Porsche 4-point Headlight */}
          <ellipse cx="180" cy="48" rx="3.5" ry="2.5" fill="#38bdf8" />
          {/* Full-width LED Light Strip */}
          <line x1="16" y1="48" x2="26" y2="48" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" />
        </g>
      )

    case 'tesla_sedan':
      return (
        <g>
          {/* Tesla Model 3 / S - Minimalist all-glass aerodynamic teardrop fastback */}
          <path
            d="M 18 54 C 16 49 20 44 32 43 L 60 41 C 74 26 98 22 130 23 C 148 24 162 34 174 44 L 186 47 C 190 49 190 52 188 54 L 168 54 A 14 14 0 0 0 140 54 L 62 54 A 14 14 0 0 0 34 54 L 18 54 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Panoramic Arch Glass Roof */}
          <path d="M 64 40 C 76 27 98 24 126 25 C 138 26 150 34 158 41 Z" fill={glassUrl} />
          {/* Flush Aero Door Handle Accents */}
          <line x1="84" y1="43" x2="94" y2="43" stroke={lineStroke} strokeWidth="1" strokeOpacity="0.5" />
          <line x1="124" y1="43" x2="134" y2="43" stroke={lineStroke} strokeWidth="1" strokeOpacity="0.5" />
          {/* Sleek Blade Headlight */}
          <path d="M 180 46 L 186 48 L 183 51 Z" fill="#38bdf8" />
          {/* LED Taillight */}
          <path d="M 18 46 L 22 46 L 20 51 L 18 51 Z" fill="#ef4444" />
        </g>
      )

    case 'cybertruck':
      return (
        <g>
          {/* Tesla Cybertruck - Polygonal stainless steel triangular origami geometry */}
          <path
            d="M 16 54 L 14 48 L 78 44 L 112 19 L 168 42 L 190 46 L 190 54 L 168 54 A 14 14 0 0 0 140 54 L 62 54 A 14 14 0 0 0 34 54 L 16 54 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="1"
          />
          {/* Triangular Flat Facet Glass */}
          <polygon points="80,43 110,21 162,41 80,43" fill={glassUrl} />
          {/* Full-width Front Cyber Light Bar */}
          <line x1="185" y1="46" x2="190" y2="47" stroke="#38bdf8" strokeWidth="2" />
          {/* Full-width Rear Red Blade Bar */}
          <line x1="14" y1="46" x2="15" y2="51" stroke="#ef4444" strokeWidth="2" />
        </g>
      )

    case 'pickup_truck':
      return (
        <g>
          {/* Full-size Pickup (F-150 / Silverado / Ram) - Upright tall front, SuperCrew cab, low open bed */}
          <path
            d="M 18 54 L 14 50 L 14 36 L 86 36 L 90 20 C 92 18 96 17 102 17 L 140 17 C 146 17 152 21 156 28 L 164 35 L 188 37 C 192 38 193 42 192 48 L 186 54 L 168 54 A 14 14 0 0 0 140 54 L 62 54 A 14 14 0 0 0 34 54 L 18 54 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* SuperCrew Windows */}
          <path d="M 94 20 L 118 20 L 118 34 L 94 34 Z" fill={glassUrl} />
          <path d="M 122 20 L 138 20 C 142 20 146 23 150 28 L 154 34 L 122 34 Z" fill={glassUrl} />
          {/* Open Bed Tie-down Rail */}
          <line x1="16" y1="34" x2="86" y2="34" stroke={lineStroke} strokeWidth="2" strokeLinecap="round" />
          {/* C-Clamp Headlight */}
          <rect x="186" y="39" width="4" height="8" rx="1.5" fill="#38bdf8" />
          {/* Vertical Taillight */}
          <rect x="15" y="38" width="4" height="8" rx="1" fill="#ef4444" />
        </g>
      )

    case 'boxy_suv':
      return (
        <g>
          {/* Rugged Off-Road 4x4 (G-Class / Wrangler / Bronco / Defender) - Upright boxy cabin, flat roof, rear spare tire */}
          <path
            d="M 22 54 L 18 50 L 18 20 L 22 18 L 132 18 C 136 18 140 21 144 28 L 152 38 L 184 40 L 184 48 L 180 54 L 168 54 A 14 14 0 0 0 140 54 L 62 54 A 14 14 0 0 0 34 54 L 22 54 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Flat Upright Windows */}
          <path d="M 24 22 L 68 22 L 68 36 L 24 36 Z" fill={glassUrl} />
          <path d="M 72 22 L 104 22 L 104 36 L 72 36 Z" fill={glassUrl} />
          <path d="M 108 22 L 130 22 C 133 22 136 24 139 29 L 144 36 L 108 36 Z" fill={glassUrl} />
          {/* Rear External Spare Tire */}
          <ellipse cx="14" cy="40" rx="6" ry="12" fill="#0f172a" stroke="#334155" strokeWidth="1.5" />
          <circle cx="14" cy="40" r="3" fill="#64748b" />
          {/* Round Iconic Headlamp */}
          <circle cx="180" cy="44" r="3.5" fill="#38bdf8" />
          {/* Square Taillight */}
          <rect x="19" y="44" width="4" height="6" rx="1" fill="#ef4444" />
        </g>
      )

    case 'crossover_suv':
      return (
        <g>
          {/* Crossover SUV (Chevrolet Blazer / RAV4 / CR-V / Model Y) - Athletic stance, high roofline, steep raked tailgate, NO sedan trunk */}
          <path
            d="M 20 52 C 16 48 16 44 20 42 L 32 19 C 34 18 38 18 44 18 L 124 18 C 130 18 136 21 142 28 L 152 35 L 182 38 C 186 39 188 42 187 46 C 185 50 182 53 178 53 L 168 53 A 14 14 0 0 0 140 53 L 62 53 A 14 14 0 0 0 34 53 L 20 52 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Aerodynamic Roof Rails */}
          <line x1="48" y1="16" x2="118" y2="16" stroke={lineStroke} strokeWidth="1.75" strokeLinecap="round" />
          <line x1="54" y1="16" x2="54" y2="18" stroke={lineStroke} strokeWidth="1.2" />
          <line x1="112" y1="16" x2="112" y2="18" stroke={lineStroke} strokeWidth="1.2" />
          {/* Rear Hatch Aerodynamic Spoiler Overhang */}
          <path d="M 28 20 L 36 18 L 38 20 Z" fill={lineStroke} />
          {/* Crossover Window Greenhouse: 3-pane profile with floating roof C-pillar */}
          <path d="M 36 22 L 56 22 L 56 36 L 27 36 C 25 36 29 30 36 22 Z" fill={glassUrl} />
          <path d="M 60 22 L 92 22 L 92 36 L 60 36 Z" fill={glassUrl} />
          <path d="M 96 22 L 122 22 C 126 22 131 25 135 30 L 142 36 L 96 36 Z" fill={glassUrl} />
          {/* Modern Crossover Shoulder Line & Door Sculpting */}
          <path d="M 26 42 Q 100 40 184 41" stroke={lineStroke} strokeWidth="0.8" strokeOpacity="0.4" fill="none" />
          <path d="M 64 47 L 138 47" stroke={lineStroke} strokeWidth="0.75" strokeOpacity="0.3" />
          {/* Wheel Arch Protective Cladding Trim */}
          <path d="M 34 53 A 14 14 0 0 1 62 53" stroke={lineStroke} strokeWidth="1.5" fill="none" strokeOpacity="0.5" />
          <path d="M 140 53 A 14 14 0 0 1 168 53" stroke={lineStroke} strokeWidth="1.5" fill="none" strokeOpacity="0.5" />
          {/* Slim Aggressive DRL & Headlight */}
          <path d="M 180 39 L 186 40 L 183 43 Z" fill="#38bdf8" />
          {/* LED Taillight */}
          <path d="M 18 42 L 25 42 L 23 47 L 18 47 Z" fill="#ef4444" />
        </g>
      )

    case 'roadster_convertible':
      return (
        <g>
          {/* Mazda MX-5 Miata - Ultra-compact low roadster, open cockpit with sports roll hoop */}
          <path
            d="M 18 54 C 18 50 24 47 40 46 L 76 46 C 82 46 86 48 94 48 L 138 48 C 150 48 162 48 174 50 C 184 52 188 53 186 54 L 168 54 A 14 14 0 0 0 140 54 L 62 54 A 14 14 0 0 0 34 54 L 18 54 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Sport Raked Windshield */}
          <path d="M 112 47 L 132 32 C 134 30 136 31 138 33 L 134 47 Z" fill={glassUrl} />
          {/* Twin Sport Roll Hoops */}
          <path d="M 88 46 C 88 38 96 38 96 46 Z" fill={lineStroke} stroke={lineStroke} strokeWidth="1" />
          {/* LED Headlight */}
          <path d="M 180 50 L 186 51 L 183 53 Z" fill="#38bdf8" />
          {/* Round Taillight */}
          <circle cx="20" cy="50" r="2.5" fill="#ef4444" />
        </g>
      )

    case 'aero_hatch_prius':
      return (
        <g>
          {/* Toyota Prius - One-motion aero wedge from low nose through roof apex down to split tail */}
          <path
            d="M 16 54 C 16 50 20 43 32 40 L 98 22 C 104 22 112 25 120 30 L 164 45 L 180 49 C 186 51 188 53 186 54 L 168 54 A 14 14 0 0 0 140 54 L 62 54 A 14 14 0 0 0 34 54 L 16 54 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Sloping Wedge Glass */}
          <path d="M 44 40 L 96 24 L 118 30 L 150 43 L 40 43 Z" fill={glassUrl} />
          {/* Aero Split Rear Glass Detail */}
          <line x1="24" y1="42" x2="36" y2="42" stroke={glassUrl} strokeWidth="2" />
          {/* Bi-LED Headlight */}
          <path d="M 176 49 L 184 51 L 180 53 Z" fill="#38bdf8" />
          {/* Vertical Rear Tailfin Light */}
          <path d="M 18 42 L 22 40 L 20 52 L 17 52 Z" fill="#ef4444" />
        </g>
      )

    case 'hatchback_golf':
      return (
        <g>
          {/* VW Golf GTI - Iconic solid thick C-pillar, European compact hot hatch silhouette */}
          <path
            d="M 18 54 C 18 49 22 43 32 40 L 56 26 C 60 24 65 23 72 23 L 126 23 C 132 23 140 27 146 35 L 160 45 C 172 48 184 51 182 54 L 168 54 A 14 14 0 0 0 140 54 L 62 54 A 14 14 0 0 0 34 54 L 18 54 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Golf 2-box Side Windows */}
          <path d="M 48 38 L 60 26 L 88 26 L 88 42 L 40 42 Z" fill={glassUrl} />
          <path d="M 92 26 L 122 26 C 127 26 132 29 136 34 L 142 42 L 92 42 Z" fill={glassUrl} />
          {/* Red GTI Grille Accent Line */}
          <line x1="172" y1="49" x2="182" y2="50" stroke="#ef4444" strokeWidth="1.5" />
          {/* Headlight */}
          <path d="M 176 48 L 182 49 L 178 52 Z" fill="#38bdf8" />
          {/* L-shaped Taillight */}
          <path d="M 20 44 L 25 42 L 23 49 L 19 49 Z" fill="#ef4444" />
        </g>
      )

    case 'wagon_estate':
      return (
        <g>
          {/* Subaru Outback / Estate Wagon - Extended roofline, extra cargo glass, adventure cladding */}
          <path
            d="M 16 54 C 16 49 21 44 32 42 L 44 25 C 46 23 50 22 56 22 L 138 22 C 145 22 154 27 160 35 L 172 44 C 182 47 186 50 184 54 L 168 54 A 14 14 0 0 0 140 54 L 62 54 A 14 14 0 0 0 34 54 L 16 54 Z"
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
          <path d="M 180 47 L 186 49 L 183 52 Z" fill="#38bdf8" />
          {/* Taillight */}
          <path d="M 17 46 L 22 46 L 20 52 L 17 52 Z" fill="#ef4444" />
        </g>
      )

    case 'minivan':
      return (
        <g>
          {/* Toyota Sienna / Minivan - Spacious monovolume aerovan profile, large passenger glass */}
          <path
            d="M 16 54 C 16 49 22 38 32 30 C 36 26 42 24 50 24 L 134 24 C 142 24 152 30 160 40 L 176 47 C 184 49 187 52 186 54 L 168 54 A 14 14 0 0 0 140 54 L 62 54 A 14 14 0 0 0 34 54 L 16 54 Z"
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
          <path d="M 180 48 L 186 50 L 182 53 Z" fill="#38bdf8" />
          {/* Vertical Rear Taillight */}
          <rect x="17" y="38" width="4" height="13" rx="1" fill="#ef4444" />
        </g>
      )

    case 'executive_sedan':
    default:
      return (
        <g>
          {/* Toyota Camry / Honda Accord / Executive Sedan - Balanced 3-box sedan, elegant proportions */}
          <path
            d="M 16 54 C 16 49 22 45 36 44 L 62 43 L 78 28 C 82 25 88 24 96 24 L 130 24 C 138 24 146 28 152 36 L 164 45 L 174 46 C 184 48 188 51 186 54 L 168 54 A 14 14 0 0 0 140 54 L 62 54 A 14 14 0 0 0 34 54 L 16 54 Z"
            fill={paintUrl}
            stroke={lineStroke}
            strokeWidth="0.75"
          />
          {/* Passenger Cabin Glass with B-Pillar */}
          <path d="M 68 42 L 80 28 L 102 28 L 102 42 Z" fill={glassUrl} />
          <path d="M 106 28 L 128 28 C 134 28 139 31 144 37 L 148 42 L 106 42 Z" fill={glassUrl} />
          <line x1="104" y1="26" x2="104" y2="43" stroke={lineStroke} strokeWidth="2" />
          {/* Character Beltline */}
          <path d="M 40 45 C 90 44 130 44 174 46" stroke={lineStroke} strokeWidth="0.75" strokeOpacity="0.35" />
          {/* Headlight */}
          <path d="M 180 47 L 186 49 L 183 52 Z" fill="#38bdf8" />
          {/* Taillight */}
          <path d="M 17 46 L 22 46 L 20 52 L 17 52 Z" fill="#ef4444" />
        </g>
      )
  }
}

function renderWheels(silhouette: VehicleSilhouette) {
  const rearX = 48
  const frontX = 154
  const cy = 54
  const radius =
    silhouette === 'crossover_suv' || silhouette === 'boxy_suv' || silhouette === 'pickup_truck' || silhouette === 'cybertruck'
      ? 11.5
      : 11
  const rimRadius = radius - 3.5

  return (
    <g>
      {/* Rear Wheel Tire & Rim */}
      <circle cx={rearX} cy={cy} r={radius} fill="#0f172a" stroke="#334155" strokeWidth="1.5" />
      <circle cx={rearX} cy={cy} r={rimRadius} fill="#64748b" />
      {/* 5-Spoke Machined Alloy Rim Geometry */}
      <circle cx={rearX} cy={cy} r={rimRadius - 2.5} fill="#0f172a" />
      <line x1={rearX - 3.5} y1={cy} x2={rearX + 3.5} y2={cy} stroke="#94a3b8" strokeWidth="1" />
      <line x1={rearX} y1={cy - 3.5} x2={rearX} y2={cy + 3.5} stroke="#94a3b8" strokeWidth="1" />
      <circle cx={rearX} cy={cy} r="1.8" fill="#e2e8f0" />

      {/* Front Wheel Tire & Rim */}
      <circle cx={frontX} cy={cy} r={radius} fill="#0f172a" stroke="#334155" strokeWidth="1.5" />
      <circle cx={frontX} cy={cy} r={rimRadius} fill="#64748b" />
      <circle cx={frontX} cy={cy} r={rimRadius - 2.5} fill="#0f172a" />
      <line x1={frontX - 3.5} y1={cy} x2={frontX + 3.5} y2={cy} stroke="#94a3b8" strokeWidth="1" />
      <line x1={frontX} y1={cy - 3.5} x2={frontX} y2={cy + 3.5} stroke="#94a3b8" strokeWidth="1" />
      <circle cx={frontX} cy={cy} r="1.8" fill="#e2e8f0" />
    </g>
  )
}
