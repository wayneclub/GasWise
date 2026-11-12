import { CarIcon, IdentificationCardIcon } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { PartsResult, PartsSearchResult } from '../../api/types'
import { Button, Field, TextInput, Segmented } from '../../components/ui'
import { useI18n } from '../../i18n'
import type { SavedVehicle } from '../../lib/prefs'
import { useVehicleIdentity, type VehicleIdentity } from '../../lib/vehicleIdentity'
import { validIdentity } from '../../lib/identity'
import { IdentityFields } from '../setup/IdentityFields'
import { VehicleThumbnail } from '../my/VehicleThumbnail'
import { GarageVehicleSwitcher } from '../my/GarageVehicleSwitcher'
import { isAmazonProduct } from '../../lib/partsLinks'
import { CATEGORIES, PART_CHOICES, type PartCategory } from './partsCategories'
import { PartsSearchResults } from './PartsSearchResults'
import { PartsFitmentResult } from './PartsFitmentResult'

export function Parts({
  vehicle,
  garage = [],
  onSelectVehicle,
  onChooseCar,
}: {
  vehicle: SavedVehicle | null
  garage?: SavedVehicle[]
  onSelectVehicle?: (car: SavedVehicle) => void
  onChooseCar: () => void
}) {
  const { t } = useI18n()
  const { identity, setIdentity, setVehicleIdentity } = useVehicleIdentity()
  const [settingIdentity, setSettingIdentity] = useState(false)
  const [inlineIdentity, setInlineIdentity] = useState<VehicleIdentity>({ kind: 'vin', value: { vin: '' } })
  const [mode, setMode] = useState<'search' | 'product'>('search')
  const [keyword, setKeyword] = useState('oil filter')
  const [partCategory, setPartCategory] = useState<PartCategory>('all')
  const [searchResult, setSearchResult] = useState<PartsSearchResult | null>(null)
  const [url, setUrl] = useState('')
  const [result, setResult] = useState<PartsResult | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(false)
  const controller = useRef<AbortController | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  const invalidate = () => {
    controller.current?.abort()
    setPending(false)
    setResult(null)
    setSearchResult(null)
    setError(false)
  }

  useEffect(() => {
    setSettingIdentity(false)
    setInlineIdentity({ kind: 'vin', value: { vin: '' } })
  }, [vehicle?.id])

  async function search() {
    controller.current?.abort()
    const abort = new AbortController()
    controller.current = abort
    setPending(true)
    setError(false)
    setResult(null)
    setSearchResult(null)
    try {
      if (!identity) return
      const identityBody = identity.kind === 'vin' ? { vin: identity.value } : { plate: identity.value }
      if (mode === 'search') {
        const next = await api.partsSearch({ keyword: keyword.trim(), max_results: 6, ...identityBody }, abort.signal)
        if (!abort.signal.aborted) setSearchResult(next)
      } else {
        const next = await api.parts({ amazon_url: url.trim(), ...identityBody }, abort.signal)
        if (!abort.signal.aborted) setResult(next)
      }
    } catch {
      if (!abort.signal.aborted) setError(true)
    } finally {
      if (!abort.signal.aborted) setPending(false)
    }
  }

  useEffect(() => {
    controller.current?.abort()
    queueMicrotask(() => {
      setPending(false)
      setResult(null)
      setSearchResult(null)
    })
  }, [identity])

  const replacements = (result?.evidence ?? []).flatMap((e) =>
    (e.replacement_candidates ?? []).map((c): Record<string, string> => ({ ...c, source: e.source })),
  )
  const decoded = searchResult?.vehicle ?? result?.vehicle
  const checkedName = decoded
    ? [
        decoded.year,
        decoded.make,
        decoded.model,
        decoded.trim,
        decoded.engine_liters ? `${Number(decoded.engine_liters).toFixed(1)}L` : '',
      ]
        .filter(Boolean)
        .join(' ')
    : ''

  return (
    <main className="mx-auto w-full max-w-2xl px-4 pb-12 pt-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t('parts.title')}</h1>
      {identity ? (
        <p className="mt-2 text-sm leading-relaxed text-muted">
          {t(mode === 'search' ? 'parts.searchLead' : 'parts.productLead')}
        </p>
      ) : null}

      {!identity ? (
        <section className="mt-6 rounded-box border border-line bg-surface p-6 sm:p-8">
          {garage.length > 0 && onSelectVehicle ? (
            <div className="mb-6 pb-5 border-b border-line/60">
              <GarageVehicleSwitcher
                garage={garage}
                activeVehicleId={vehicle?.id}
                onSelectVehicle={onSelectVehicle}
                onManageGarage={onChooseCar}
                showIdentity
              />
            </div>
          ) : null}

          {vehicle ? (
            <div className="mb-4">
              <VehicleThumbnail
                label={vehicle.label}
                color={vehicle.color}
                imageUrl={vehicle.imageUrl}
                size="lg"
                className="w-full max-w-xs"
              />
            </div>
          ) : (
            <span className="grid size-14 place-items-center rounded-2xl bg-accent-soft text-accent">
              <CarIcon size={32} weight="duotone" />
            </span>
          )}

          <h2 className="mt-4 text-xl font-semibold">{t('parts.startTitle')}</h2>
          {vehicle ? <p className="mt-2 text-base font-bold text-ink">{vehicle.label}</p> : null}
          <p className="mt-2 max-w-md text-sm leading-relaxed text-muted">{t('parts.startLead')}</p>

          {vehicle ? (
            settingIdentity ? (
              <div className="mt-5 rounded-xl border border-line bg-sunken/40 p-4">
                <IdentityFields
                  identity={inlineIdentity}
                  onChange={(val) => setInlineIdentity(val)}
                  showMode={true}
                />
                <div className="mt-4 flex items-center justify-between pt-3 border-t border-line/40">
                  <Button variant="ghost" onClick={() => setSettingIdentity(false)} className="text-xs">
                    {t('garage.cancel')}
                  </Button>
                  <Button
                    disabled={!validIdentity(inlineIdentity)}
                    onClick={() => {
                      if (validIdentity(inlineIdentity)) {
                        setIdentity(inlineIdentity)
                        if (vehicle.id) {
                          setVehicleIdentity(vehicle.id, inlineIdentity)
                        }
                        setSettingIdentity(false)
                      }
                    }}
                    className="text-xs"
                  >
                    {t('parts.saveAndSearch')}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="mt-6 flex flex-wrap items-center gap-3">
                <Button onClick={() => setSettingIdentity(true)}>
                  <IdentificationCardIcon size={18} />
                  {t('parts.bindIdentity')}
                </Button>
                <Button variant="secondary" onClick={onChooseCar}>
                  <CarIcon size={18} />
                  {t('parts.manageGarage')}
                </Button>
              </div>
            )
          ) : (
            <Button className="mt-6" onClick={onChooseCar}>
              <CarIcon size={18} />
              {t('parts.addCar')}
            </Button>
          )}
        </section>
      ) : (
        <>
          <div className="mt-5">
            <Segmented
              label={t('parts.title')}
              value={mode}
              options={[
                { value: 'search', label: t('parts.searchMode') },
                { value: 'product', label: t('parts.checkMode') },
              ]}
              onChange={(value) => {
                invalidate()
                setMode(value)
              }}
            />
          </div>

          <details open={!result && !searchResult} className="mt-5 rounded-box border border-line bg-surface p-5">
            <summary className="cursor-pointer text-sm font-medium">{t('parts.edit')}</summary>
            <div className="mt-4">
              {garage.length > 0 && onSelectVehicle ? (
                <div className="mb-5 pb-4 border-b border-line/60">
                  <GarageVehicleSwitcher
                    garage={garage}
                    activeVehicleId={vehicle?.id}
                    onSelectVehicle={onSelectVehicle}
                    onManageGarage={onChooseCar}
                    showIdentity
                  />
                </div>
              ) : vehicle ? (
                <div className="flex items-center gap-3">
                  <VehicleThumbnail
                    label={vehicle.label}
                    color={vehicle.color}
                    imageUrl={vehicle.imageUrl}
                    size="sm"
                  />
                  <p className="text-sm font-medium">{t('parts.car', { name: vehicle.label })}</p>
                </div>
              ) : null}

              <p className="mt-2 text-xs leading-relaxed text-muted">{t('parts.identityNeeded')}</p>

              <form
                className="mt-5 flex flex-col gap-5"
                onSubmit={(event) => {
                  event.preventDefault()
                  if (
                    identity &&
                    validIdentity(identity) &&
                    (mode === 'search' ? keyword.trim().length >= 2 : isAmazonProduct(url.trim()))
                  ) {
                    void search()
                  }
                }}
              >
                <div className="rounded-control bg-sunken p-3 flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-medium">
                      {identity ? t('vehicle.sharedReady') : t('vehicle.sharedMissing')}
                    </p>
                    {identity ? (
                      <p className="font-mono text-xs text-muted mt-0.5">
                        {identity.kind === 'vin'
                          ? `VIN · •••••••••••••${identity.value.vin.slice(-4)}`
                          : `${identity.value.state} · •••${identity.value.plate.slice(-2)}`}
                      </p>
                    ) : null}
                  </div>
                  <Button variant="ghost" onClick={onChooseCar} className="text-xs">
                    {t('parts.manageGarage')}
                  </Button>
                </div>

                {mode === 'search' ? (
                  <Field label={t('parts.keyword')}>
                    <TextInput
                      aria-label={t('parts.keyword')}
                      value={keyword}
                      maxLength={100}
                      onChange={(e) => {
                        invalidate()
                        setKeyword(e.target.value)
                      }}
                    />
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {CATEGORIES.map((cat) => (
                        <button
                          key={cat.id}
                          type="button"
                          onClick={() => setPartCategory(cat.id)}
                          className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                            partCategory === cat.id
                              ? 'bg-ink text-surface shadow-xs'
                              : 'border border-line bg-surface text-muted hover:bg-sunken hover:text-ink'
                          }`}
                        >
                          {t(cat.label)}
                        </button>
                      ))}
                    </div>
                    <div className="flex flex-wrap gap-2 pt-1">
                      {(partCategory === 'all'
                        ? PART_CHOICES
                        : PART_CHOICES.filter((p) => p.category === partCategory)
                      ).map((choice) => {
                        const isSelected = keyword.toLowerCase() === choice.value
                        return (
                          <Button
                            key={choice.value}
                            variant="ghost"
                            className={`h-auto min-h-10 px-3 py-1.5 text-xs ${
                              isSelected ? 'bg-sunken text-ink font-semibold ring-1 ring-accent' : ''
                            }`}
                            onClick={() => {
                              invalidate()
                              setKeyword(choice.value)
                            }}
                          >
                            <choice.icon size={16} />
                            {t(choice.label)}
                          </Button>
                        )
                      })}
                    </div>
                  </Field>
                ) : (
                  <Field label={t('parts.url')}>
                    <TextInput
                      type="url"
                      aria-label={t('parts.url')}
                      value={url}
                      placeholder="https://www.amazon.com/dp/…"
                      onChange={(e) => {
                        invalidate()
                        setUrl(e.target.value)
                      }}
                    />
                  </Field>
                )}

                <Button
                  type="submit"
                  className="h-auto min-h-11 py-2"
                  style={{ whiteSpace: 'normal' }}
                  disabled={
                    pending ||
                    !(identity && validIdentity(identity)) ||
                    (mode === 'search' ? keyword.trim().length < 2 : !isAmazonProduct(url.trim()))
                  }
                >
                  {pending
                    ? t(mode === 'search' ? 'parts.finding' : 'parts.pending')
                    : t(mode === 'search' ? 'parts.find' : 'parts.submit')}
                </Button>
              </form>
            </div>
          </details>

          {error ? (
            <p role="alert" className="mt-4 rounded-control bg-caution-soft p-4 text-sm text-caution">
              {t('parts.error')}
            </p>
          ) : null}

          {searchResult ? (
            <PartsSearchResults result={searchResult} checkedName={checkedName} />
          ) : null}

          {result ? (
            <PartsFitmentResult
              result={result}
              checkedName={checkedName}
              replacements={replacements}
            />
          ) : null}
        </>
      )}
    </main>
  )
}
