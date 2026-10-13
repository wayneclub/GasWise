import {expect,it} from 'vitest'
import type {Station} from '../api/types'
import {googleStationUrl,stationSourceUrl} from './stationLinks'
const station={name:'Shell',address:'900 N Hill St',location:{lat:34,lng:-118},canonical_id:'google_places:ChIJtest',details:{}} as Station
it('links a station by place ID and uses its source station ID',()=>{
 expect(new URL(googleStationUrl(station)).searchParams.get('query_place_id')).toBe('ChIJtest')
 expect(stationSourceUrl('gasbuddy_web','123',station)).toBe('https://www.gasbuddy.com/station/123')
 expect(stationSourceUrl('waze','venue',station)).toBe('https://waze.com/ul?ll=34,-118')
 expect(stationSourceUrl('gasbuddy_web','javascript:bad',station)).toBeUndefined()
})
it('prefers official short links and rejects untrusted URLs',()=>{
 expect(googleStationUrl({...station,details:{google_maps_share_url:'https://maps.app.goo.gl/example'}})).toBe('https://maps.app.goo.gl/example')
 expect(googleStationUrl({...station,details:{google_maps_share_url:'https://evil.example/'}})).toContain('query_place_id=ChIJtest')
})
