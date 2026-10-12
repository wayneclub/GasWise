import type { NavApp } from './prefs'

export const NAV_APPS: { value: NavApp; label: string }[] = [
  { value: 'google', label: 'Google Maps' },
  { value: 'apple', label: 'Apple Maps' },
  { value: 'waze', label: 'Waze' },
]

/** Destination only: the user's origin never goes into the URL. */
export function navigationUrl(app: NavApp, lat: number, lng: number): string {
  const point = `${lat},${lng}`
  switch (app) {
    case 'apple':
      return `https://maps.apple.com/?daddr=${point}&dirflg=d`
    case 'waze':
      return `https://waze.com/ul?ll=${point}&navigate=yes`
    default:
      return `https://www.google.com/maps/dir/?api=1&destination=${point}&travelmode=driving`
  }
}
