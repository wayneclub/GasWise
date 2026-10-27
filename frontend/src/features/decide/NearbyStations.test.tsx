import {render, screen} from '@testing-library/react'
import {expect, it} from 'vitest'
import type {SmartResult} from '../../api/types'
import {I18nProvider} from '../../i18n/I18nProvider'
import fixture from '../../test/fixtures/demo-search.json'
import {NearbyStations} from './NearbyStations'

it('hides unpriced discoveries after merging sources and retains a real quote from another source', () => {
  const result = structuredClone(fixture) as unknown as SmartResult
  const quote = {...result.snapshot.stations[0], canonical_id:'google_places:shared', name:'Priced via Waze', source:'waze', open_now:true as const}
  result.snapshot.stations = [quote]
  result.snapshot.inventory = ['missing','shared'].map(place_id => ({
    discovery_state: 'observed', place_id, name:place_id === 'missing' ? 'No source has a price' : 'Maps discovery',
    location:quote.location, address:quote.address, distance_meters:100,
    available_fuel_types:[], open_now:true,
  }))
  result.ranking = null
  // Omit old computed coverage: represent the new response, not fixture indices.
  Reflect.deleteProperty(result, 'coverage')
  render(<I18nProvider locale="en"><NearbyStations result={result} navApp="google"/></I18nProvider>)
  expect(screen.queryByText('No source has a price')).not.toBeInTheDocument()
  expect(screen.queryByText('Price unavailable')).not.toBeInTheDocument()
  expect(screen.getByText('Priced via Waze')).toBeInTheDocument()
})
