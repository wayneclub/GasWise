import {render,screen} from '@testing-library/react'
import {expect,it} from 'vitest'
import {I18nProvider} from '../../i18n/I18nProvider'
import type {RankedStation} from '../../api/types'
import fixture from '../../test/fixtures/demo-search.json'
import {StationSources} from './SourcePill'

it('shows unique station evidence sources without adding unrelated providers',()=>{
  const row=structuredClone(fixture.ranking.results[0]) as unknown as RankedStation
  row.price_comparison={...row.price_comparison,evidence:[{source:'gasbuddy_web'},{source:'waze'},{source:'google_maps_web'},{source:'waze'}]} as RankedStation['price_comparison']
  render(<I18nProvider locale="en"><StationSources source="gasbuddy_web" row={row}/></I18nProvider>)
  expect(screen.getByText('GasBuddy')).toBeInTheDocument()
  expect(screen.getAllByText('Waze')).toHaveLength(1)
  expect(screen.getByText('Google Maps')).toBeInTheDocument()
  expect(screen.getByText('Displayed price')).toBeInTheDocument()
})
