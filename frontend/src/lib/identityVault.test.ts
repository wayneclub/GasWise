/// <reference types="node" />
import {webcrypto} from 'node:crypto'
import {IDBFactory} from 'fake-indexeddb'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {loadIdentity,saveIdentity} from './identityVault'
import type {VehicleIdentity} from './vehicleIdentity'

const identity:VehicleIdentity={kind:'vin',value:{vin:'A'.repeat(17)}}
beforeEach(()=>{vi.stubGlobal('indexedDB',new IDBFactory());vi.stubGlobal('crypto',webcrypto)})
afterEach(()=>{vi.unstubAllGlobals();vi.useRealTimers()})

async function stored(change?:(record:any)=>void):Promise<any> {
  return new Promise((resolve,reject)=>{
    const request=indexedDB.open('gaswise-private-v1',1)
    request.onsuccess=()=>{
      const db=request.result,tx=db.transaction('vault',change?'readwrite':'readonly'),store=tx.objectStore('vault')
      const get=store.get('vehicle');let result:any
      get.onsuccess=()=>{result=get.result;if(change){change(result);store.put(result,'vehicle')}}
      tx.oncomplete=()=>{db.close();resolve(result)}
      tx.onerror=()=>{db.close();reject(new Error('test_storage_error'))}
    }
    request.onerror=()=>reject(new Error('test_storage_error'))
  })
}
it('round-trips identity with real AES-GCM and stores no plaintext or exportable key',async()=>{
  await saveIdentity(identity)
  const record=await stored()
  expect(record.key.extractable).toBe(false)
  expect(record.key.algorithm.name).toBe('AES-GCM')
  await expect(crypto.subtle.exportKey('raw',record.key)).rejects.toThrow()
  expect(new TextDecoder().decode(record.ciphertext)).not.toContain(identity.value.vin)
  expect(record).not.toHaveProperty('identity')
  expect(localStorage.length).toBe(0)
  expect(await loadIdentity()).toEqual(identity)
})
it('rejects tampering and removes the damaged record',async()=>{
  await saveIdentity(identity)
  await stored(record=>{new Uint8Array(record.ciphertext)[0]^=1})
  expect(await loadIdentity()).toBeNull()
  expect(await stored()).toBeUndefined()
})
it('authenticates expiration metadata as well as the encrypted identity',async()=>{
  await saveIdentity(identity)
  await stored(record=>{record.expires+=86400000})
  expect(await loadIdentity()).toBeNull()
  expect(await stored()).toBeUndefined()
})
it('expires after 30 days and deletes both ciphertext and key',async()=>{
  await saveIdentity(identity)
  vi.spyOn(Date,'now').mockReturnValue(Date.now()+31*86400000)
  expect(await loadIdentity()).toBeNull()
  expect(await stored()).toBeUndefined()
  vi.restoreAllMocks()
})
it('queues clear after an outstanding save so the old identity cannot reappear',async()=>{
  const save=saveIdentity(identity),clear=saveIdentity(null)
  await Promise.all([save,clear])
  expect(await loadIdentity()).toBeNull()
  expect(await stored()).toBeUndefined()
})
it('never falls back to plaintext when storage is unavailable',async()=>{
  vi.stubGlobal('indexedDB',undefined)
  await expect(saveIdentity(identity)).rejects.toThrow('private_storage_unavailable')
  expect(await loadIdentity()).toBeNull()
  expect(localStorage.length).toBe(0)
})
