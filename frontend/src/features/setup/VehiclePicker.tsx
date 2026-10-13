import { CarIcon, CheckCircleIcon } from '@phosphor-icons/react'
import { type FormEvent, useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../../api/client'
import type { FuelType, VehicleResolution, VehicleResolveRequest, VinResolution } from '../../api/types'
import { IdentityFields } from './IdentityFields'
import { emptyIdentity, validIdentity } from '../../lib/identity'
import { useVehicleIdentity, type VehicleIdentity } from '../../lib/vehicleIdentity'
import { Button, Segmented, TextInput } from '../../components/ui'
import { type MessageKey, useI18n } from '../../i18n'
import { fuelKey } from '../../lib/format'
import type { SavedVehicle } from '../../lib/prefs'

const NUMERIC_FIELDS = new Set(['year', 'option_vehicle_id'])

// Backend prompts are not localized; the answer field and enum values are stable, so translate those.
const QUESTION_FIELDS = new Set(['year', 'make', 'model', 'body_style', 'drivetrain', 'catalog_model', 'option_vehicle_id'])
const ENUM_CHOICES = new Set(['coupe', 'convertible', 'wagon', 'other', 'standard', '4matic'])
const ENUM_FIELDS = new Set(['body_style', 'drivetrain'])

function gradeOf(resolution: VehicleResolution): FuelType {
  const recommended = resolution.fuel_recommendation?.fuel_type ?? resolution.vehicle?.fuel_recommendation?.fuel_type
  if (recommended) return recommended
  const epa = resolution.vehicle?.fuel_type.toLowerCase() ?? ''
  if (epa.includes('premium')) return 'premium'
  if (epa.includes('diesel')) return 'diesel'
  if (epa.includes('midgrade')) return 'midgrade'
  return 'regular'
}

export function VehiclePicker({
  vehicle,
  onChange,
}: {
  vehicle: SavedVehicle | null
  onChange: (vehicle: SavedVehicle | null) => void
}) {
  const { t } = useI18n()
  const active = useRef(true)
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  const { identity: sharedIdentity, setIdentity } = useVehicleIdentity()
  const [editing, setEditing] = useState(false)
  const [mode, setMode] = useState<'model' | 'vin' | 'plate'>('model')
  const [identity, setLocalIdentity] = useState<VehicleIdentity>(sharedIdentity ?? emptyIdentity())
  const [identityQuestion, setIdentityQuestion] = useState<VinResolution | null>(null)
  const [text, setText] = useState('')
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [question, setQuestion] = useState<VehicleResolution | null>(null)

  async function resolve(body: VehicleResolveRequest) {
    setPending(true)
    setMessage(null)
    try {
      const resolution = await api.resolveVehicle(body)
      if (!active.current) return
      if (resolution.status === 'resolved' && resolution.vehicle) {
        const v = resolution.vehicle
        onChange({
          id: v.id,
          label: `${v.year} ${v.make} ${v.model}`,
          fuelType: gradeOf(resolution),
          combinedMpg: v.combined_mpg,
        })
        setIdentity(null)
        setEditing(false)
        setQuestion(null)
        setText('')
      } else if (resolution.status === 'needs_input' && resolution.choices?.length) {
        setQuestion(resolution)
      } else {
        setQuestion(null)
        setMessage(t('vehicle.noMatch'))
      }
    } catch (error) {
      if (!active.current) return
      setMessage(t(error instanceof ApiError && error.status === 0 ? 'vehicle.offline' : 'vehicle.unavailable'))
    } finally {
      if (active.current) setPending(false)
    }
  }

  async function resolveIdentity(vehicleId?: number) {
    setPending(true)
    setMessage(null)
    try {
      const response = identity.kind === 'vin'
        ? await api.resolveVin({ ...identity.value, ...(vehicleId ? { vehicle_id: vehicleId } : {}) })
        : (await api.resolvePlate({ ...identity.value, ...(vehicleId ? { vehicle_id: vehicleId } : {}) })).resolution
      if (!active.current) return
      if (response.status === 'resolved' && response.vehicle) {
        const v = response.vehicle
        onChange({ id: v.id, label: `${v.year} ${v.make} ${v.model}`, fuelType: gradeOf({ status: 'resolved', vehicle: v, fuel_recommendation: response.fuel_recommendation } as VehicleResolution), combinedMpg: v.combined_mpg })
        setIdentity({ ...identity, value: { ...identity.value, vehicle_id: v.id } } as VehicleIdentity)
        setIdentityQuestion(null)
        setEditing(false)
      } else if (response.choices?.length) setIdentityQuestion(response)
      else { if (response.decoded) { setIdentity(identity); onChange(null) } setMessage(t('vehicle.partial')) }
    } catch (error) {
      if (!active.current) return
      setMessage(t(error instanceof ApiError && error.status === 0 ? 'vehicle.offline' : 'vehicle.unavailable'))
    } finally { if (active.current) setPending(false) }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (text.trim().length >= 3) void resolve({ text: text.trim() })
  }

  function choose(value: string) {
    if (!question?.selection || !question.answer_field) return
    const field = question.answer_field
    void resolve({ ...question.selection, [field]: NUMERIC_FIELDS.has(field) ? Number(value) : value })
  }

  if (vehicle && !editing) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-control border border-line bg-surface px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-3">
          <CheckCircleIcon size={20} weight="fill" className="shrink-0 text-accent" />
          <div className="min-w-0">
            <p className="line-clamp-2 text-[15px] font-medium leading-snug">{vehicle.label}</p>
            <p className="text-[13px] text-muted">
              {t('vehicle.summary', { fuel: t(fuelKey(vehicle.fuelType)), mpg: Number(vehicle.combinedMpg) })}
            </p>
          </div>
        </div>
        <Button variant="ghost" className="h-9 px-3 text-sm" onClick={() => setEditing(true)}>
          {t('vehicle.change')}
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <Segmented label={t('prefs.car')} value={mode}
        options={[{ value: 'model', label: t('vehicle.byText') }, { value: 'plate', label: t('vehicle.byPlate') }, { value: 'vin', label: t('vehicle.byVin') }]}
        disabled={pending}
        onChange={(value) => { setMode(value); setMessage(null); setQuestion(null); setIdentityQuestion(null); if (value !== 'model') setLocalIdentity(value === 'vin' ? { kind: 'vin', value: { vin: '' } } : emptyIdentity()) }} />
      {mode === 'model' ? <><form onSubmit={submit} className="flex gap-2">
        <label className="sr-only" htmlFor="vehicle-text">
          {t('vehicle.inputLabel')}
        </label>
        <TextInput
          disabled={pending}
          id="vehicle-text"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder={t('vehicle.placeholder')}
          autoComplete="off"
          enterKeyHint="search"
        />
        <Button type="submit" variant="secondary" disabled={pending || text.trim().length < 3} className="shrink-0">
          <CarIcon size={18} />
          {pending ? t('vehicle.finding') : t('vehicle.find')}
        </Button>
      </form>
      {question ? (
        <div className="flex flex-col gap-2 rounded-control bg-sunken p-3">
          <p className="text-sm font-medium">
            {t(
              question.answer_field && QUESTION_FIELDS.has(question.answer_field)
                ? (`vehicle.q.${question.answer_field}` as MessageKey)
                : 'vehicle.q.default',
            )}
          </p>
          <div className="flex flex-wrap gap-2">
            {(question.choices ?? []).map((choice) => (
              <button
                key={choice.value}
                type="button"
                disabled={pending}
                onClick={() => choose(choice.value)}
                className="w-full min-w-0 rounded-control border border-line bg-surface px-3 py-2 text-left text-sm whitespace-normal break-words hover:border-ink disabled:opacity-50"
              >
                {question.answer_field && ENUM_FIELDS.has(question.answer_field) && ENUM_CHOICES.has(choice.value)
                  ? t(`vehicle.c.${choice.value}` as MessageKey)
                  : choice.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      </> : <div className="flex flex-col gap-3">
        <fieldset disabled={pending}><IdentityFields identity={identity} onChange={(value) => { setLocalIdentity(value); setIdentityQuestion(null) }} showMode={false} /></fieldset>
        <Button disabled={pending || !validIdentity(identity)} onClick={() => void resolveIdentity()}>{pending ? t('vehicle.finding') : t('vehicle.find')}</Button>
        {identityQuestion ? <div className="flex flex-col gap-2 rounded-control bg-sunken p-3">
          <p className="text-sm">{t('vehicle.confirmConfig')}</p>
          {(identityQuestion.choices ?? []).map((choice) => <button type="button" key={choice.value} aria-label={choice.label} className="min-h-11 w-full min-w-0 rounded-control border border-line bg-surface px-3 py-2 text-left text-sm leading-snug whitespace-normal break-words hover:border-accent disabled:opacity-50" disabled={pending} onClick={() => void resolveIdentity(Number(choice.value))}><span className="block font-medium">{choice.label.split(' · ')[0]}</span><span className="mt-1 block text-xs text-muted">{choice.label.split(' · ').slice(1).join(' · ')}</span></button>)}
        </div> : null}
      </div>}
      {message ? <p className="text-[13px] text-danger">{message}</p> : null}
    </div>
  )
}
