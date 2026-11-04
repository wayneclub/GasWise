import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { PlateRequest, VinRequest } from '../api/types'
import {
  loadIdentity,
  loadAllIdentities,
  saveIdentity,
  saveVehicleIdentity,
  supportsIdentityVault,
} from './identityVault'
import { requestPersistentStorage } from './localProfile'

export type VehicleIdentity = { kind: 'vin'; value: VinRequest } | { kind: 'plate'; value: PlateRequest }

export interface VehicleIdentityContextValue {
  identity: VehicleIdentity | null
  setIdentity: (identity: VehicleIdentity | null) => void
  getVehicleIdentity: (vehicleId?: number | null) => VehicleIdentity | null
  setVehicleIdentity: (vehicleId: number, identity: VehicleIdentity | null) => void
  identities: Record<number, VehicleIdentity>
  storageStatus?: 'encrypted' | 'session'
  storageError?: boolean
  ready?: boolean
}

export const VehicleIdentityContext = createContext<VehicleIdentityContextValue>({
  identity: null,
  setIdentity: () => {},
  getVehicleIdentity: () => null,
  setVehicleIdentity: () => {},
  identities: {},
})

export const useVehicleIdentity = () => useContext(VehicleIdentityContext)

export function useEncryptedVehicleIdentity(activeVehicleId?: number | null) {
  const [identities, setIdentities] = useState<Record<number, VehicleIdentity>>({})
  const [legacyIdentity, setLegacyIdentity] = useState<VehicleIdentity | null>(null)
  const [ready, setReady] = useState(!supportsIdentityVault())
  const [storageStatus, setStorageStatus] = useState<'encrypted' | 'session'>('session')
  const [storageError, setStorageError] = useState(false)

  // Load encrypted vault on mount
  useEffect(() => {
    if (!supportsIdentityVault()) return
    let active = true
    Promise.all([loadIdentity(), loadAllIdentities()])
      .then(([single, map]) => {
        if (!active) return
        setLegacyIdentity(single)
        setIdentities(map)
        setStorageStatus('encrypted')
        setReady(true)
      })
      .catch(() => {
        if (active) {
          setReady(true)
          setStorageError(true)
        }
      })
    return () => {
      active = false
    }
  }, [])

  // Derived active identity:
  // If activeVehicleId is provided and exists in identities, use that.
  // Otherwise fallback to legacyIdentity.
  const currentIdentity = useMemo<VehicleIdentity | null>(() => {
    if (typeof activeVehicleId === 'number' && identities[activeVehicleId]) {
      return identities[activeVehicleId]
    }
    return legacyIdentity
  }, [activeVehicleId, identities, legacyIdentity])

  // Get identity for a specific vehicleId
  const getVehicleIdentity = useCallback(
    (vehicleId?: number | null): VehicleIdentity | null => {
      if (typeof vehicleId === 'number') {
        return identities[vehicleId] ?? (activeVehicleId === vehicleId ? legacyIdentity : null)
      }
      return currentIdentity
    },
    [identities, activeVehicleId, legacyIdentity, currentIdentity],
  )

  // Set identity for the active vehicle
  const setIdentity = useCallback(
    (value: VehicleIdentity | null) => {
      if (typeof activeVehicleId === 'number') {
        setIdentities((prev) => {
          const next = { ...prev }
          if (value) next[activeVehicleId] = value
          else delete next[activeVehicleId]
          return next
        })
      }
      setLegacyIdentity(value)

      if (!supportsIdentityVault()) return
      void saveIdentity(value, activeVehicleId)
        .then(() => {
          setStorageStatus('encrypted')
          setStorageError(false)
          if (value) void requestPersistentStorage()
        })
        .catch(() => {
          setStorageStatus('session')
          setStorageError(true)
        })
    },
    [activeVehicleId],
  )

  // Set identity for a specific vehicleId
  const setVehicleIdentity = useCallback(
    (vehicleId: number, value: VehicleIdentity | null) => {
      setIdentities((prev) => {
        const next = { ...prev }
        if (value) next[vehicleId] = value
        else delete next[vehicleId]
        return next
      })

      if (activeVehicleId === vehicleId || legacyIdentity === null) {
        setLegacyIdentity(value)
      }

      if (!supportsIdentityVault()) return
      void saveVehicleIdentity(vehicleId, value)
        .then(() => {
          setStorageStatus('encrypted')
          setStorageError(false)
          if (value) void requestPersistentStorage()
        })
        .catch(() => {
          setStorageStatus('session')
          setStorageError(true)
        })
    },
    [activeVehicleId, legacyIdentity],
  )

  return {
    identity: currentIdentity,
    setIdentity,
    getVehicleIdentity,
    setVehicleIdentity,
    identities,
    storageStatus,
    storageError,
    ready,
  }
}
