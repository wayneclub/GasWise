import { useId, useMemo, useState } from 'react'
import {
  inferVehicleArchetype,
  inferVehicleSilhouette,
  SILHOUETTE_TO_ARCHETYPE,
  type VehicleArchetype,
  type VehicleSilhouette,
} from '../../lib/vehicleStyle'
import { useDynamicVehiclePhoto } from '../../lib/dynamicVehiclePhoto'
import { useI18n } from '../../i18n'
import { VehicleSilhouetteSvg } from './VehicleSilhouetteSvg'

interface VehicleThumbnailProps {
  label?: string | null
  bodyStyle?: VehicleArchetype | string | null
  color?: string | null
  className?: string
  size?: 'sm' | 'md' | 'lg'
  showBadge?: boolean
  active?: boolean
  imageUrl?: string | null
  preferVector?: boolean
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
  imageUrl,
  preferVector = false,
}: VehicleThumbnailProps) {
  const { t } = useI18n()
  const uid = useId().replace(/:/g, '')
  const [imgError, setImgError] = useState(false)

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

  const { photoUrl, isStudio } = useDynamicVehiclePhoto(label, imageUrl, color)
  const showPhoto = Boolean(photoUrl && !imgError && !preferVector)

  const dimensions = {
    sm: 'w-20 h-10',
    md: 'w-32 h-16',
    lg: 'w-48 h-24',
  }[size]

  return (
    <div className={`relative flex flex-col items-center justify-center ${className}`}>
      <div
        className={`relative flex items-center justify-center overflow-hidden rounded-2xl border transition-all ${dimensions} ${
          active
            ? 'border-accent/40 bg-gradient-to-b from-accent/10 via-surface to-accent/5 shadow-sm'
            : 'border-line/80 bg-sunken/40 dark:bg-sunken/20'
        }`}
      >
        {showPhoto ? (
          <div className="relative flex h-full w-full items-center justify-center p-1">
            <img
              src={photoUrl!}
              alt={label || 'Vehicle'}
              onError={() => setImgError(true)}
              className={`h-full w-full object-contain select-none filter drop-shadow-sm transition-transform duration-200 hover:scale-105 ${
                isStudio ? '' : 'rounded-lg max-h-[92%]'
              }`}
              loading="lazy"
            />
          </div>
        ) : (
          <VehicleSilhouetteSvg
            silhouette={silhouette}
            baseColor={baseColor}
            highlightColor={highlightColor}
            shadowColor={shadowColor}
            isLightCar={isLightCar}
            uid={uid}
          />
        )}
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
