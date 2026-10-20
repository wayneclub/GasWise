/// <reference types="node" />
import { webcrypto } from 'node:crypto'
import { IDBFactory } from 'fake-indexeddb'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { DEFAULT_PREFS } from './prefs'
import { exportPrivateBackup, getLocalProfile, importPrivateBackup, resetLocalProfile, shortProfileId } from './localProfile'
import type { VehicleIdentity } from './vehicleIdentity'
import { recordRefuel, saveFuelAssistantSettings } from './fuelAssistant'

const identity: VehicleIdentity = { kind: 'vin', value: { vin: 'A'.repeat(17) } }
const first = '11111111-1111-4111-8111-111111111111'
const second = '22222222-2222-4222-8222-222222222222'

beforeEach(() => {
  vi.stubGlobal('indexedDB', new IDBFactory())
  let next = first
  vi.stubGlobal('crypto', {
    subtle: webcrypto.subtle,
    getRandomValues: webcrypto.getRandomValues.bind(webcrypto),
    randomUUID: () => { const value = next; next = second; return value },
  })
})
afterEach(() => vi.unstubAllGlobals())

it('creates one browser-local profile and rotates it only when cleared', async () => {
  expect(await getLocalProfile()).toMatchObject({ id: first })
  expect(await getLocalProfile()).toMatchObject({ id: first })
  expect(shortProfileId(await resetLocalProfile())).toBe('22222222')
})

it('encrypts a complete private backup and restores it only with the password', async () => {
  await getLocalProfile()
  await saveFuelAssistantSettings({ weeklyMiles: 321, typicalGallons: 11 })
  await recordRefuel(new Date('2026-10-20T08:00:00Z'))
  const backup = await exportPrivateBackup({ ...DEFAULT_PREFS, gallons: 17 }, identity, 'correct horse')
  expect(backup).not.toContain(identity.value.vin)
  expect(backup).not.toContain('"gallons":17')
  await expect(importPrivateBackup(backup, 'wrong password')).rejects.toThrow('invalid_backup')
  const restored = await importPrivateBackup(backup, 'correct horse')
  expect(restored.identity).toEqual(identity)
  expect(restored.prefs.gallons).toBe(17)
  expect(restored.profile.id).toBe(first)
  expect(restored.assistant?.settings.weeklyMiles).toBe(321)
  expect(restored.assistant?.events[0].at).toBe('2026-10-20T08:00:00.000Z')
})

it('rejects short backup passwords and malformed files', async () => {
  await expect(exportPrivateBackup(DEFAULT_PREFS, null, 'short')).rejects.toThrow('weak_passphrase')
  await expect(importPrivateBackup('{}', 'long enough')).rejects.toThrow('invalid_backup')
})
