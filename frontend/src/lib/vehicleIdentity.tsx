import { createContext, useContext } from 'react'
import type { PlateRequest, VinRequest } from '../api/types'

export type VehicleIdentity = { kind: 'vin'; value: VinRequest } | { kind: 'plate'; value: PlateRequest }
export const VehicleIdentityContext = createContext<{
  identity: VehicleIdentity | null
  setIdentity: (identity: VehicleIdentity | null) => void
}>({ identity: null, setIdentity: () => {} })
export const useVehicleIdentity = () => useContext(VehicleIdentityContext)
