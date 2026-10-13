import type { VehicleIdentity } from './vehicleIdentity'
export const US_STATES = 'AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split(' ')
export function validIdentity(identity: VehicleIdentity): boolean {
  if (!identity || !identity.value || !['vin','plate'].includes(identity.kind)) return false
  return identity.kind === 'vin'
    ? /^[A-HJ-NPR-Z0-9]{17}$/.test(identity.value.vin)
    : /^[A-Z0-9]{1,10}$/.test(identity.value.plate) && US_STATES.includes(identity.value.state)
}
export const emptyIdentity = (): VehicleIdentity => ({ kind: 'plate', value: { state: 'CA', plate: '' } })
