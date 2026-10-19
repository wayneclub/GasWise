import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { PlateRequest, VinRequest } from '../api/types'
import {loadIdentity, saveIdentity, supportsIdentityVault} from './identityVault'
import {requestPersistentStorage} from './localProfile'

export type VehicleIdentity = { kind: 'vin'; value: VinRequest } | { kind: 'plate'; value: PlateRequest }
export const VehicleIdentityContext = createContext<{
  identity: VehicleIdentity | null
  setIdentity: (identity: VehicleIdentity | null) => void
  storageStatus?: 'encrypted' | 'session'
  storageError?: boolean
}>({ identity: null, setIdentity: () => {} })
export const useVehicleIdentity = () => useContext(VehicleIdentityContext)

export function useEncryptedVehicleIdentity() {
  const [identity,setValue]=useState<VehicleIdentity|null>(null)
  const [ready,setReady]=useState(!supportsIdentityVault())
  const [storageStatus,setStorageStatus]=useState<'encrypted'|'session'>('session')
  const [storageError,setStorageError]=useState(false)
  useEffect(()=>{
    if(!supportsIdentityVault()) return
    let active=true
    void loadIdentity().then(value=>{
      if(active) {setValue(value);setStorageStatus('encrypted');setReady(true)}
    }).catch(()=>{if(active) {setReady(true);setStorageError(true)}})
    return ()=>{active=false}
  },[])
  const setIdentity=useCallback((value:VehicleIdentity|null)=>{
    setValue(value)
    if(!supportsIdentityVault()) return
    void saveIdentity(value).then(()=>{setStorageStatus('encrypted');setStorageError(false);if(value) void requestPersistentStorage()})
      .catch(()=>{setStorageStatus('session');setStorageError(true)})
  },[])
  return {identity,setIdentity,storageStatus,storageError,ready}
}
