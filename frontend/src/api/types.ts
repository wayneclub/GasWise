import type { components } from './schema'

type Schemas = components['schemas']

export type SmartSearchBody = Schemas['SmartSearch']
export type SmartResult = Schemas['SmartResult']
export type SmartSnapshot = Schemas['SmartSnapshot-Output']
export type RankOptions = Schemas['RankOptions']
export type SearchResult = Schemas['SearchResult']
export type RankedStation = Schemas['RankedStation']
export type StrategyRecommendation = Schemas['StrategyRecommendation']
export type Station = Schemas['Station-Output']
export type VehicleResolveRequest = Schemas['VehicleResolveRequest']
export type VehicleResolution = Schemas['VehicleResolution']
export type VehicleProfile = Schemas['VehicleProfile-Output']

export type FuelType = 'regular' | 'midgrade' | 'premium' | 'diesel'
export type StrategyKey = 'best_value' | 'cheapest_overall' | 'fastest_stop' | 'on_my_route'

export type PartsRequest = Schemas['PartsRequest']
export type PartsResult = Schemas['PartsResult']
export type VinRequest = Schemas['VinRequest']
export type VinResolution = Schemas['VinResolution']
export type PlateRequest = Schemas['PlateRequest']
export type PlateResolution = Schemas['PlateResolution']
export type MapsWebStation = Schemas['MapsWebStation']

export type PartsSearchRequest = Schemas['PartsSearchRequest']
export type PartsSearchResult = Schemas['PartsSearchResult']

export type LocationResult = components['schemas']['LocationResult']
