import { LocationSearch } from './LocationSearch'
import { useState } from 'react'
import { Button, Field, Segmented, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n'
import type { Prefs } from '../../lib/prefs'

export function TripForm({ prefs, update }: { prefs: Prefs; update: (value: Partial<Prefs>) => void }) {
  const { t } = useI18n()
  const [mode, setMode] = useState(prefs.tripMode)
  const [lat, setLat] = useState(prefs.destination ? String(prefs.destination.lat) : '')
  const [lng, setLng] = useState(prefs.destination ? String(prefs.destination.lng) : '')
  const [invalid, setInvalid] = useState(false)
  return <Field label={t('route.mode')} hint={t('route.hint')}>
    <Segmented label={t('route.mode')} value={mode} options={[{ value: 'round_trip', label: t('route.nearby') }, { value: 'on_route', label: t('route.onRoute') }]}
      onChange={(value) => { setMode(value); setInvalid(false); if (value === 'round_trip') update({ tripMode: value, destination: null }) }} />
    {mode === 'on_route' ? <LocationSearch onChoose={(point) => { setLat(String(point.lat)); setLng(String(point.lng)); setInvalid(false) }} /> : null}
    {mode === 'on_route' ? <form className="flex flex-col gap-3" onSubmit={(event) => {
      event.preventDefault()
      const latitude = Number(lat), longitude = Number(lng)
      if (!lat.trim() || !lng.trim() || !Number.isFinite(latitude) || !Number.isFinite(longitude) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) { setInvalid(true); return }
      setInvalid(false); update({ tripMode: 'on_route', destination: { lat: latitude, lng: longitude } })
    }}>
      <div className="grid grid-cols-2 gap-3">
        <TextInput aria-label={t('route.lat')} placeholder={t('route.lat')} value={lat} onChange={(e) => setLat(e.target.value)} inputMode="decimal" />
        <TextInput aria-label={t('route.lng')} placeholder={t('route.lng')} value={lng} onChange={(e) => setLng(e.target.value)} inputMode="decimal" />
      </div>
      {invalid ? <p role="alert" className="text-sm text-danger">{t('route.invalid')}</p> : null}
      <Button type="submit" variant="secondary">{t('route.apply')}</Button>
    </form> : null}
  </Field>
}
