import type {Station} from '../api/types'

type Place = Pick<Station,'name'|'address'|'location'|'canonical_id'|'details'>

/** Only accept provider-owned HTTPS links; never turn upstream text into arbitrary links. */
function officialLink(value: unknown, hosts: string[]): string | undefined {
  if (typeof value !== 'string') return undefined
  try {
    const url = new URL(value)
    if (url.protocol==='https:' && !url.username && !url.password && hosts.includes(url.hostname)) return url.href
  } catch { /* no provider link */ }
}

export function googleStationUrl(station: Place): string {
  const shared=officialLink(station.details?.google_maps_share_url,['maps.app.goo.gl','goo.gl','www.google.com','maps.google.com'])
  if (shared) return shared
  const params=new URLSearchParams({api:'1',query:`${station.name} ${station.address ?? `${station.location.lat},${station.location.lng}`}`})
  const id=station.canonical_id?.replace(/^google_places:/,'')
  if (station.canonical_id?.startsWith('google_places:') && id) params.set('query_place_id',id)
  return `https://www.google.com/maps/search/?${params}`
}

export function stationSourceUrl(source:string,id:string,station:Place):string|undefined {
  if(source==='gasbuddy_web') {
    const shared=officialLink(station.details?.gasbuddy_share_url,['www.gasbuddy.com','gasbuddy.com'])
    return shared ?? (/^\d+$/.test(id) ? `https://www.gasbuddy.com/station/${id}` : undefined)
  }
  if(source==='waze') return officialLink(station.details?.waze_share_url,['waze.com','www.waze.com']) ?? `https://waze.com/ul?ll=${station.location.lat},${station.location.lng}`
  if(source==='google_maps_web'||source==='google_places') return googleStationUrl(station)
}
