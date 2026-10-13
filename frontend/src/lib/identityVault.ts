/** Browser-only authenticated encryption. No network, localStorage, or plaintext fallback. */
import {validIdentity} from './identity'
import type {VehicleIdentity} from './vehicleIdentity'

const DATABASE = 'gaswise-private-v1'
const STORE = 'vault'
const SLOT = 'vehicle'
const MAX_AGE = 30 * 24 * 60 * 60 * 1000
const aad = (expires:number)=>new TextEncoder().encode(`GasWise:vehicle-identity:v1:${expires}`)
type Record = {key:CryptoKey; iv:Uint8Array<ArrayBuffer>; ciphertext:ArrayBuffer; expires:number}
let queue:Promise<unknown> = Promise.resolve()

function open():Promise<IDBDatabase> {
  return new Promise((resolve,reject)=>{
    const request=indexedDB.open(DATABASE,1)
    request.onupgradeneeded=()=>request.result.createObjectStore(STORE)
    request.onsuccess=()=>resolve(request.result)
    request.onerror=()=>reject(new Error('private_storage_unavailable'))
    request.onblocked=()=>reject(new Error('private_storage_unavailable'))
  })
}
async function read():Promise<Record|undefined> {
  const db=await open()
  try {return await new Promise((resolve,reject)=>{
    const tx=db.transaction(STORE,'readonly'), request=tx.objectStore(STORE).get(SLOT)
    request.onsuccess=()=>resolve(request.result)
    request.onerror=()=>reject(new Error('private_storage_unavailable'))
  })} finally {db.close()}
}
async function write(record:Record|null) {
  const db=await open()
  try {await new Promise<void>((resolve,reject)=>{
    const tx=db.transaction(STORE,'readwrite'), store=tx.objectStore(STORE)
    if(record) store.put(record,SLOT); else store.delete(SLOT)
    tx.oncomplete=()=>resolve()
    tx.onerror=tx.onabort=()=>reject(new Error('private_storage_unavailable'))
  })} finally {db.close()}
}
export function supportsIdentityVault() {
  return typeof indexedDB!=='undefined' && !!globalThis.crypto?.subtle
}
export async function loadIdentity():Promise<VehicleIdentity|null> {
  if(!supportsIdentityVault()) return null
  const record=await read()
  if(!record) return null
  if(record.expires<=Date.now()) {await write(null);return null}
  try {
    if(!Number.isFinite(record.expires)||record.key.extractable||record.key.algorithm.name!=='AES-GCM') throw new Error('invalid_record')
    const plaintext=await crypto.subtle.decrypt({name:'AES-GCM',iv:record.iv,additionalData:aad(record.expires)},record.key,record.ciphertext)
    const identity=JSON.parse(new TextDecoder().decode(plaintext)) as VehicleIdentity
    if(!validIdentity(identity)) throw new Error('invalid_identity')
    return identity
  } catch {await write(null);return null}
}
export function saveIdentity(identity:VehicleIdentity|null):Promise<void> {
  const operation=queue.catch(()=>{}).then(async()=>{
    if(!supportsIdentityVault()) throw new Error('private_storage_unavailable')
    if(!identity) {await write(null);return}
    if(!validIdentity(identity)) throw new Error('invalid_identity')
    const previous=await read()
    const oldKey=previous?.key
    const key=oldKey?.type==='secret' && !oldKey.extractable && oldKey.algorithm.name==='AES-GCM'
      ? oldKey : await crypto.subtle.generateKey({name:'AES-GCM',length:256},false,['encrypt','decrypt'])
    const iv=crypto.getRandomValues(new Uint8Array(12))
    const expires=Date.now()+MAX_AGE
    const ciphertext=await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:aad(expires)},key,new TextEncoder().encode(JSON.stringify(identity)))
    await write({key,iv,ciphertext,expires})
  })
  queue=operation
  return operation
}
