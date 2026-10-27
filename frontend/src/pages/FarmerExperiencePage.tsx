import { lazy, Suspense, useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  IconArrowRight as ArrowRight,
  IconAudioLines as AudioLines,
  IconBadgeCheck as BadgeCheck,
  IconAlert as Bell,
  IconLearn as BookOpen,
  IconPest as Bug,
  IconCalendar as CalendarDays,
  IconCheck as Check,
  IconCircleHelp as CircleHelp,
  IconCloudRain as CloudDrizzle,
  IconCloudRain as CloudRain,
  IconFlask as FlaskConical,
  IconHeadphones as Headphones,
  IconLeaf as Leaf,
  IconLocation as MapPin,
  IconPlus as Plus,
  IconWaste as Recycle,
  IconShieldCheck as ShieldCheck,
  IconSprout as Sprout,
  IconStore as Store,
  IconSun as Sun,
  IconTrendingUp as TrendingUp,
  IconWaves as Waves,
} from '../components/icons'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'
import { Skeleton } from '../components/ui/Skeleton'
import { SeverityPill } from '../components/ui/SeverityPill'
import { api, isQueuedOfflineResult, submitOfflineCapable } from '../lib/api'
import { compressImageForUpload } from '../lib/compressImage'
import { listQueuedRequests, OUTBOX_UPDATED_EVENT } from '../lib/offlineStore'
import { getList } from '../types'
import type { ApiList, FarmerAlert, Farm, Language, MarketPrice, WeatherSnapshot } from '../types'
import { useI18n } from '../i18n/I18nProvider'
import { useToast } from '../hooks/useToast'
import './farmer-experience.css'

const FarmerMap = lazy(() => import('../components/farmer/FarmerMap'))

type FarmerProfile = { id: number; ward: number; user: number }
type Crop = { id: number; name: string; water_needs?: string; ideal_ph_min?: number }
type Buyer = { id: number; name: string; type: string; contact: string; verified: boolean; crops: number[]; is_sample_data?: boolean }
type SellListing = { id: number; crop_name: string; quantity_kg: string; asking_price_per_kg: string; harvest_date: string; ward: string }
type Lesson = {
  id: number
  title: string
  problem_tag: string
  duration_sec: number
  steps: string[]
  quiz: { question: string; options: string[] }[]
  audio_url: string
  audio_by_language: Record<Language, string>
  photo: string | null
}
type LessonProgress = { id: number; lesson: number; completed: boolean; progress_percent: number; completed_steps: number; quiz_score: number | null }
type Badge = { id: number; name: string; code: string; description: string }
type OutbreakProperties = { id: number; ward: string; pest_name: string; confirmed_count: number; level: string; crop?: string; started_at: string }
type OutbreakFeatureCollection = { features: { geometry: { coordinates: [number, number] }; properties: OutbreakProperties }[] }
type PestKnowledge = { pest_name: string; pest_label: string; symptom_icons: string[]; safe_first_actions: string[]; symptoms: string[] }
type ApiAlertDelivery = { id: number; alert: number; channel: string; feedback: string | null; delivered: boolean }

function useListQuery<T>(key: string, url: string) {
  return useQuery({
    queryKey: [key],
    queryFn: async () => getList<T>((await api.get(url)).data as T[] | ApiList<T>),
  })
}

function PageTitle({ eyebrow, title, description, icon: Icon }: {
  eyebrow: string
  title: string
  description: string
  icon: typeof Sun
}) {
  return (
    <div className="farmer-page-title">
      <span className="farmer-page-icon"><Icon size={25} /></span>
      <div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="farmer-page-description">{description}</p></div>
    </div>
  )
}

function LoadingCard({ rows = 3 }: { rows?: number }) {
  return <Card className="farmer-loading-card"><Skeleton className="h-7 w-2/3" /><div className="mt-4 space-y-3">{Array.from({ length: rows }, (_, index) => <Skeleton key={index} className="h-12 w-full" />)}</div></Card>
}

function QueryError({ message, retry }: { message: string; retry: () => void }) {
  return <Card className="farmer-error" role="alert"><CircleHelp size={20} /><span>{message}</span><button onClick={retry}>Retry</button></Card>
}

function SelectFarm({ farms, value, onChange }: { farms: Farm[]; value: string; onChange: (value: string) => void }) {
  return <label className="farmer-field"><span>Choose a farm</span><select value={value} onChange={(event) => onChange(event.target.value)} required><option value="">Select your farm</option>{farms.map((farm) => <option key={farm.id} value={farm.id}>{farm.name}</option>)}</select></label>
}

function SelectCrop({ crops, value, onChange }: { crops: Crop[]; value: string; onChange: (value: string) => void }) {
  return <label className="farmer-field"><span>Crop</span><select value={value} onChange={(event) => onChange(event.target.value)} required><option value="">Choose a crop</option>{crops.map((crop) => <option key={crop.id} value={crop.id}>{crop.name}</option>)}</select></label>
}

function FormMessage({ message }: { message: string }) {
  return message ? <p className="farmer-form-message" role="status">{message}</p> : null
}

function formatTag(value: string) {
  return value.replace(/_/g, ' ')
}

function RiskGauge({ score }: { score: number }) {
  const boundedScore = Math.max(0, Math.min(100, score))
  return (
    <div className="risk-gauge" role="img" aria-label={`Erosion risk score ${boundedScore} out of 100`}>
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle cx="50" cy="50" r="42" />
        <circle className="risk-value-arc" cx="50" cy="50" r="42" strokeDasharray={`${boundedScore * 2.64} 264`} />
      </svg>
      <div className="risk-gauge-copy"><strong>{boundedScore}</strong><span>risk / 100</span></div>
    </div>
  )
}

function speak(text: string, language: Language, onEnd: () => void) {
  if (!('speechSynthesis' in window)) throw new Error('Voice playback is not available in this browser.')
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = language === 'sw' ? 'sw-KE' : language === 'guz' ? 'en-KE' : 'en-KE'
  utterance.onend = onEnd
  utterance.onerror = onEnd
  window.speechSynthesis.speak(utterance)
}

function AlertVoiceButton({ text, language }: { text: string; language: Language }) {
  const [playing, setPlaying] = useState(false)
  const play = () => {
    try {
      if (playing) {
        window.speechSynthesis.cancel()
        setPlaying(false)
      } else {
        speak(text, language, () => setPlaying(false))
        setPlaying(true)
      }
    } catch {
      setPlaying(false)
    }
  }
  return <button className={`voice-note-button ${playing ? 'voice-playing' : ''}`} onClick={play} aria-label={playing ? 'Stop voice playback' : 'Play voice note'}><Headphones size={17} /><span>{playing ? 'Stop voice' : 'Listen'}</span></button>
}

function FeedbackAlert({ alert, delivery, language, onFeedback, disabled, queuedFeedback }: {
  alert: FarmerAlert
  delivery?: ApiAlertDelivery
  language: Language
  onFeedback: (delivery: ApiAlertDelivery, value: 'HELPFUL' | 'NOT_RELEVANT') => void
  disabled: boolean
  queuedFeedback?: string
}) {
  const severity = alert.severity === 'CRITICAL' || alert.severity === 'HIGH' || alert.severity === 'URGENT'
    ? 'urgent'
    : alert.severity === 'MEDIUM' || alert.severity === 'WATCH' ? 'watch' : 'info'
  const body = alert.body_by_language?.[language] || alert.body_by_language?.en || ''
  return (
    <Card className={`farmer-alert-card farmer-alert-${severity}`}>
      <div className="farmer-alert-top"><SeverityPill severity={severity} label={alert.severity} /><time>{new Date(alert.created_at).toLocaleDateString()}</time></div>
      <h3>{alert.title}</h3>
      {body && <p>{body}</p>}
      <div className="farmer-alert-actions"><AlertVoiceButton text={`${alert.title}. ${body}`} language={language} /><div className="feedback-actions">
        <button disabled={!delivery || disabled || delivery.feedback !== null || Boolean(queuedFeedback)} onClick={() => delivery && onFeedback(delivery, 'HELPFUL')}><Check size={15} /> Helpful</button>
        <button disabled={!delivery || disabled || delivery.feedback !== null || Boolean(queuedFeedback)} onClick={() => delivery && onFeedback(delivery, 'NOT_RELEVANT')}>Not relevant</button>
      </div></div>
      {!delivery && <small className="feedback-note">Feedback is available after this alert is delivered to your account.</small>}
      {queuedFeedback && <small className="feedback-note">Feedback saved on this device and will sync when online.</small>}
      {delivery?.feedback && <small className="feedback-note">Thanks â€” your feedback was saved.</small>}
    </Card>
  )
}

function TodayScreen() {
  const { user } = useAuth()
  const { language } = useI18n()
  const toast = useToast()
  const queryClient = useQueryClient()
  const alertsQuery = useListQuery<FarmerAlert>('farmer-alerts', '/alerts/')
  const deliveriesQuery = useListQuery<ApiAlertDelivery>('alert-deliveries', '/alert-deliveries/')
  const farmsQuery = useListQuery<Farm>('farmer-farms', '/farms/')
  const [queuedFeedback, setQueuedFeedback] = useState<Record<number, string>>({})
  useEffect(() => {
    const refreshQueuedFeedback = () => {
      void listQueuedRequests().then((items) => {
        const values: Record<number, string> = {}
        items.forEach((item) => {
          const match = item.url.match(/\/alert-deliveries\/(\d+)\/feedback\//)
          if (match && item.body.kind === 'json' && item.body.data && typeof item.body.data === 'object' && 'feedback' in item.body.data) {
            values[Number(match[1])] = String(item.body.data.feedback)
          }
        })
        setQueuedFeedback(values)
      })
    }
    refreshQueuedFeedback()
    window.addEventListener(OUTBOX_UPDATED_EVENT, refreshQueuedFeedback)
    return () => window.removeEventListener(OUTBOX_UPDATED_EVENT, refreshQueuedFeedback)
  }, [])
  const feedbackMutation = useMutation({
    mutationFn: async ({ delivery, feedback }: { delivery: ApiAlertDelivery; feedback: 'HELPFUL' | 'NOT_RELEVANT' }) =>
      submitOfflineCapable('POST', `/alert-deliveries/${delivery.id}/feedback/`, { feedback }),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['alert-deliveries'] })
      toast(isQueuedOfflineResult(result) ? 'Feedback saved offline; it will sync when you are online.' : 'Thank you. Your feedback was saved.')
    },
    onError: () => toast('Could not save alert feedback. Try again.', 'error'),
  })
  const alerts = (alertsQuery.data ?? []).filter((alert) => alert.status !== 'RESOLVED').slice(0, 3)
  const deliveries = deliveriesQuery.data ?? []
  const mostImportant = alerts[0]
  const firstName = user?.first_name || 'farmer'
  const farm = farmsQuery.data?.[0]
  const nextAction = mostImportant?.title || (farm ? 'Check your farm and plan todayâ€™s work.' : 'Add your first farm to get local advice.')

  return (
    <div className="farmer-page-stack">
      <PageTitle eyebrow="YOUR FARM Â· TODAY" title={`Habari, ${firstName}`} description="One useful next step for your farm today." icon={Sun} />
      {alertsQuery.isLoading ? <Skeleton className="today-hero-skeleton" /> : alertsQuery.isError ? <QueryError message="Todayâ€™s alerts could not load." retry={() => void alertsQuery.refetch()} /> : (
        <section className={`today-hero ${mostImportant && ['HIGH', 'CRITICAL', 'URGENT'].includes(mostImportant.severity) ? 'today-hero-urgent' : ''}`}>
          <div className="today-hero-copy"><span className="today-hero-kicker"><Sun size={16} /> MOST IMPORTANT TODAY</span><h2>{nextAction}</h2><p>{mostImportant?.body_by_language?.[language] || (farm ? `${farm.name} Â· your farm plan is ready to check.` : 'Add a plot so Shamba can tailor weather and crop advice to you.')}</p>
            {mostImportant ? <AlertVoiceButton text={`${mostImportant.title}. ${mostImportant.body_by_language?.[language] || ''}`} language={language} /> : <Button variant="secondary" onClick={() => window.location.assign('/app/farms')}>{farm ? 'Open Mvua Planner' : 'Add my farm'} <ArrowRight size={16} /></Button>}
          </div>
          <span className="today-hero-illustration"><Sprout size={66} /></span>
        </section>
      )}
      {farmsQuery.isError && <QueryError message="Your farm information could not load." retry={() => void farmsQuery.refetch()} />}
      {deliveriesQuery.isError && <QueryError message="Alert feedback status could not load." retry={() => void deliveriesQuery.refetch()} />}
      <div className="farmer-section-heading"><div><p className="eyebrow">PERSONAL TO YOUR FARM</p><h2>Alerts that matter</h2></div><span className="farmer-result-count">{alerts.length} of 3</span></div>
      {alertsQuery.isLoading ? <LoadingCard rows={2} /> : alerts.length ? alerts.map((alert) => {
        const delivery = deliveries.find((item) => item.alert === alert.id)
        return <FeedbackAlert key={alert.id} alert={alert} delivery={delivery} language={language} onFeedback={(item, feedback) => feedbackMutation.mutate({ delivery: item, feedback })} disabled={feedbackMutation.isPending} queuedFeedback={delivery ? queuedFeedback[delivery.id] : undefined} />
      }) : <Card className="farmer-empty-card"><EmptyState icon={<Bell size={25} />} title="No new alerts" description="Youâ€™re all caught up. Weâ€™ll show timely advice here when something needs your attention." /></Card>}
      {alertsQuery.isError && <QueryError message="Alerts could not load." retry={() => void alertsQuery.refetch()} />}
    </div>
  )
}

function FarmsScreen() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const farmsQuery = useListQuery<Farm>('farmer-farms', '/farms/')
  const cropsQuery = useListQuery<Crop>('crop-reference', '/crops/')
  const farmerQuery = useListQuery<FarmerProfile>('my-farmer-profile', '/farmers/')
  const [formOpen, setFormOpen] = useState(false)
  const [name, setName] = useState('')
  const [acres, setAcres] = useState('')
  const [slope, setSlope] = useState('GENTLE')
  const [soilType, setSoilType] = useState('')
  const [lat, setLat] = useState('-0.68')
  const [lng, setLng] = useState('34.76')
  const [cropId, setCropId] = useState('')
  const [plantedOn, setPlantedOn] = useState(new Date().toISOString().slice(0, 10))
  const [variety, setVariety] = useState('')
  const [error, setError] = useState('')
  const farms = farmsQuery.data ?? []
  const createFarm = useMutation({
    mutationFn: async () => {
      const farmer = farmerQuery.data?.[0]
      if (!farmer) throw new Error('Your farmer profile is missing.')
      const farm = (await api.post<Farm>('/farms/', {
        farmer: farmer.id, name, size_acres: acres, slope_class: slope, soil_type: soilType,
        lat: Number(lat), lng: Number(lng), soil_ph: null, last_lime_date: null,
      })).data
      if (cropId) {
        const estimate = new Date(plantedOn)
        estimate.setDate(estimate.getDate() + 120)
        await api.post('/plantings/', {
          farm: farm.id, crop: Number(cropId), variety: variety || 'Local variety',
          planted_on: plantedOn, expected_harvest: estimate.toISOString().slice(0, 10),
        })
      }
      return farm
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['farmer-farms'] })
      setFormOpen(false); setName(''); setAcres(''); setError('')
      toast('Your plot was added.')
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : 'Could not add this plot.'),
  })
  return (
    <div className="farmer-page-stack">
      <PageTitle eyebrow="MY LAND Â· MY CROPS" title="My Farm" description="Your plots, crops and planting dates in one place." icon={Sprout} />
      <div className="farmer-section-heading"><div><p className="eyebrow">YOUR PLOTS</p><h2>Farm map</h2></div><Button onClick={() => setFormOpen((open) => !open)}><Plus size={17} /> Add plot</Button></div>
      <Card className="farmer-map-card">
        {farmsQuery.isLoading ? <Skeleton className="farmer-map-skeleton" /> : farmsQuery.isError ? <QueryError message="Farm map could not load." retry={() => void farmsQuery.refetch()} /> : farms.length
          ? <Suspense fallback={<Skeleton className="farmer-map-skeleton" />}><FarmerMap markers={farms.map((farm) => ({ id: farm.id, lat: farm.lat, lng: farm.lng, label: farm.name, detail: `${farm.size_acres} acres Â· ${farm.slope_class.toLowerCase()} slope` }))} /></Suspense>
          : <div className="map-placeholder"><MapPin size={30} /><strong>Your farm map starts here</strong><span>Add a plot to see it on the map.</span></div>}
      </Card>
      {formOpen && <Card className="farmer-form-card"><div className="farmer-section-heading"><div><p className="eyebrow">NEW PLOT</p><h2>Tell us about your land</h2></div></div>
        <form className="farmer-form-grid" onSubmit={(event) => { event.preventDefault(); setError(''); createFarm.mutate() }}>
          <label className="farmer-field"><span>Plot name</span><input value={name} onChange={(event) => setName(event.target.value)} required placeholder="e.g. Upper garden" /></label>
          <label className="farmer-field"><span>Size (acres)</span><input type="number" min="0.01" step="0.01" value={acres} onChange={(event) => setAcres(event.target.value)} required /></label>
          <label className="farmer-field"><span>Slope</span><select value={slope} onChange={(event) => setSlope(event.target.value)}><option value="FLAT">Flat</option><option value="GENTLE">Gentle</option><option value="STEEP">Steep</option></select></label>
          <label className="farmer-field"><span>Soil type</span><input value={soilType} onChange={(event) => setSoilType(event.target.value)} required placeholder="e.g. Red loam" /></label>
          <label className="farmer-field"><span>Latitude</span><input type="number" step="any" value={lat} onChange={(event) => setLat(event.target.value)} required /></label>
          <label className="farmer-field"><span>Longitude</span><input type="number" step="any" value={lng} onChange={(event) => setLng(event.target.value)} required /></label>
          {cropsQuery.isError ? <QueryError message="The crop list could not load." retry={() => void cropsQuery.refetch()} /> : cropsQuery.data?.length ? <>
            <SelectCrop crops={cropsQuery.data} value={cropId} onChange={setCropId} />
            <label className="farmer-field"><span>Variety</span><input value={variety} onChange={(event) => setVariety(event.target.value)} placeholder="Optional" /></label>
            <label className="farmer-field"><span>Planting date</span><input type="date" value={plantedOn} onChange={(event) => setPlantedOn(event.target.value)} /></label>
          </> : null}
          <FormMessage message={error} />
          <div className="farmer-form-actions"><Button type="submit" loading={createFarm.isPending}>Save plot</Button><Button type="button" variant="ghost" onClick={() => setFormOpen(false)}>Cancel</Button></div>
        </form>
      </Card>}
      <div className="farmer-section-heading"><div><p className="eyebrow">PLOT LIST</p><h2>{farms.length} {farms.length === 1 ? 'plot' : 'plots'}</h2></div></div>
      {farmsQuery.isLoading ? <LoadingCard rows={3} /> : farmsQuery.isError ? <QueryError message="Your plot list could not load." retry={() => void farmsQuery.refetch()} /> : farms.length ? <div className="farm-plot-list">{farms.map((farm) => <Card className="farm-plot-card" key={farm.id}><span className="farm-plot-icon"><Sprout size={22} /></span><div className="farm-plot-main"><strong>{farm.name}</strong><span>{farm.size_acres} acres Â· {farm.slope_class.toLowerCase()} slope Â· {farm.soil_type}</span><small>{farm.lat.toFixed(3)}, {farm.lng.toFixed(3)}</small></div><MapPin size={17} className="farm-plot-pin" /></Card>)}</div> : <Card className="farmer-empty-card"><EmptyState icon={<Sprout size={25} />} title="No plots yet" description="Add a farm plot to get weather and crop advice for your own land." /></Card>}
      {farmerQuery.isError && <QueryError message="Your farmer profile could not load, so a plot cannot be saved." retry={() => void farmerQuery.refetch()} />}
    </div>
  )
}

function PlannerScreen() {
  const farmsQuery = useListQuery<Farm>('farmer-farms', '/farms/')
  const [farmId, setFarmId] = useState('')
  const farms = farmsQuery.data ?? []
  const selected = farms.find((farm) => String(farm.id) === farmId) ?? farms[0]
  const plannerQuery = useQuery({
    queryKey: ['farm-planner', selected?.id],
    queryFn: async () => (await api.get(`/farms/${selected?.id}/planner/`)).data,
    enabled: !!selected,
  })
  const weatherQuery = useQuery({
    queryKey: ['farm-weather', selected?.id],
    queryFn: async () => getList<WeatherSnapshot>((await api.get(`/farms/${selected?.id}/weather/`)).data),
    enabled: !!selected,
  })
  const planner = plannerQuery.data as {
    planting_window?: { status: string; wait_days: number | null; reason: string; crop: string }
    rain_alerts?: { code: string; severity: string; date: string; message: string }[]
    calendar?: { weeks: { week: number; start: string; end: string; actions: { type: string; date: string; description: string }[] }[] }
    sms?: Partial<Record<Language, string>>
  } | undefined
  const forecast = weatherQuery.data?.filter((day) => day.forecast_json && (day.forecast_json as { is_forecast?: boolean }).is_forecast)
  const isSampleForecast = forecast?.some((day) => (day.forecast_json as { source?: string } | undefined)?.source === 'demo')
  return <div className="farmer-page-stack">
    <PageTitle eyebrow="WEATHER Â· CROP TIMING" title="Mvua Planner" description="Plan this weekâ€™s farm work around the rain." icon={CloudRain} />
    {isSampleForecast && <span className="sample-label">SAMPLE WEATHER Â· NOT A LIVE FORECAST</span>}
    {farmsQuery.isLoading ? <Skeleton className="h-14" /> : farmsQuery.isError ? <QueryError message="Your farms could not load, so the planner is unavailable." retry={() => void farmsQuery.refetch()} /> : farms.length ? <SelectFarm farms={farms} value={selected ? String(selected.id) : farmId} onChange={setFarmId} /> : <Card className="farmer-empty-card"><EmptyState icon={<Sprout size={25} />} title="Add a farm first" description="The planner uses your ward forecast and crop to build a planting calendar." /></Card>}
    {plannerQuery.isLoading && selected ? <LoadingCard rows={4} /> : plannerQuery.isError ? <QueryError message="Planner data could not load." retry={() => void plannerQuery.refetch()} /> : planner && selected && <>
      <Card className={`planting-window-card ${planner.planting_window?.status === 'RECOMMENDED_NOW' ? 'planting-good' : 'planting-wait'}`}>
        <span className="planting-window-icon">{planner.planting_window?.status === 'RECOMMENDED_NOW' ? <Check size={24} /> : <CloudDrizzle size={24} />}</span>
        <div><p className="eyebrow">PLANTING WINDOW Â· {planner.planting_window?.crop}</p><h2>{planner.planting_window?.status ? formatTag(planner.planting_window.status) : 'Add a crop to plan'}</h2><p>{planner.planting_window?.reason}</p></div>
      </Card>
      {weatherQuery.isLoading ? <LoadingCard rows={2} /> : weatherQuery.isError ? <QueryError message="The latest forecast could not load." retry={() => void weatherQuery.refetch()} /> : forecast?.length ? <div className="weather-chip-row">{forecast.slice(0, 7).map((day) => <Card className="forecast-chip" key={day.id}><small>{new Date(day.date).toLocaleDateString(undefined, { weekday: 'short' })}</small><CloudRain size={17} /><strong>{Math.round(day.rain_mm)} mm</strong><span>{Math.round(day.temp_min)}â€“{Math.round(day.temp_max)}Â°</span></Card>)}</div> : <Card className="farmer-empty-card"><EmptyState icon={<CloudRain size={24} />} title="No forecast snapshots yet" description="Weather will appear after the next forecast refresh for your ward." /></Card>}
      {planner.rain_alerts?.length ? <div className="planner-alert-list">{planner.rain_alerts.map((alert, index) => <Card key={`${alert.code}-${index}`} className="planner-alert"><SeverityPill severity={alert.severity === 'HIGH' ? 'urgent' : 'watch'} label={formatTag(alert.code)} /><p>{alert.message}</p><time>{alert.date}</time></Card>)}</div> : <Card className="planner-clear"><Sun size={18} /> No rain alerts for this forecast window.</Card>}
      <div className="farmer-section-heading"><div><p className="eyebrow">YOUR CALENDAR</p><h2>Week by week</h2></div></div>
      <div className="planner-calendar">{planner.calendar?.weeks?.map((week) => <Card key={week.week} className="planner-week"><div className="planner-week-head"><span>WEEK {week.week}</span><time>{week.start} â€“ {week.end}</time></div>{week.actions.length ? <ul>{week.actions.map((action, index) => <li key={`${action.type}-${index}`}><span className={`calendar-action-dot action-${action.type}`} /><div><strong>{action.type.replace('_', ' ')}</strong><p>{action.description}</p></div><time>{action.date.slice(5)}</time></li>)}</ul> : <p className="planner-no-action">No scheduled actions this week.</p>}</Card>)}</div>
      {planner.sms?.en && <div className="sms-preview"><MessageText /> <span>SMS preview Â· {planner.sms.en}</span></div>}
    </>}
  </div>
}

function MessageText() { return <AudioLines size={18} /> }

const quizQuestions = [
  { key: 'leaf_colour', label: 'What colour are most crop leaves?', options: [['green', 'Healthy green'], ['pale', 'Pale'], ['yellow', 'Yellowing']] },
  { key: 'soil_colour', label: 'What does your soil look like?', options: [['dark', 'Dark and rich'], ['pale', 'Pale or light']] },
  { key: 'past_yields', label: 'How have harvests changed?', options: [['good', 'Good harvests'], ['steady', 'About the same'], ['falling', 'Getting smaller']] },
  { key: 'rain_washing', label: 'Does rain wash soil away?', options: [['no', 'No'], ['yes', 'Yes']] },
  { key: 'mulch_use', label: 'Do you cover soil with mulch?', options: [['yes', 'Yes'], ['no', 'No']] },
  { key: 'manure_use', label: 'Do you add compost or manure?', options: [['yes', 'Yes'], ['no', 'No']] },
] as const

function SoilScreen() {
  const cropsQuery = useListQuery<Crop>('crop-reference', '/crops/')
  const [cropId, setCropId] = useState('')
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [result, setResult] = useState<{ summary: string; tasks: { code: string; title: string; body: string; cost_kes_per_acre: { min: number; max: number } | null }[]; warning?: { body: string } }>()
  const [error, setError] = useState('')
  const mutation = useMutation({
    mutationFn: async () => {
      const crop = cropsQuery.data?.find((item) => String(item.id) === cropId)
      if (!crop) throw new Error('Choose a crop to continue.')
      const quiz = Object.fromEntries(quizQuestions.map(({ key }) => [key, answers[key]]))
      return (await api.post('/advice/udongo-doctor/', { crop: crop.name, quiz })).data
    },
    onSuccess: (data) => { setResult(data); setError('') },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : 'The soil guide could not run.'),
  })
  return <div className="farmer-page-stack">
    <PageTitle eyebrow="SOIL Â· FERTILITY" title="Udongo Doctor" description="Answer six simple questions to get a practical, ranked soil plan." icon={FlaskConical} />
    {cropsQuery.isLoading ? <Skeleton className="h-14" /> : cropsQuery.isError ? <QueryError message="Crop list could not load." retry={() => void cropsQuery.refetch()} /> : cropsQuery.data?.length ? <SelectCrop crops={cropsQuery.data} value={cropId} onChange={(value) => { setCropId(value); setResult(undefined) }} /> : <Card className="farmer-empty-card"><EmptyState icon={<Sprout size={25} />} title="Crop list is empty" description="A crop catalogue is needed before the soil guide can make a tailored plan." /></Card>}
    <Card className="quiz-card"><div className="farmer-section-heading"><div><p className="eyebrow">VISUAL SOIL CHECK</p><h2>What do you see in your field?</h2></div><span className="quiz-step-count">{Object.keys(answers).length}/6</span></div>
      <div className="soil-quiz">{quizQuestions.map((question, index) => <fieldset className="quiz-question" key={question.key}><legend><span>{String(index + 1).padStart(2, '0')}</span>{question.label}</legend><div className="quiz-options">{question.options.map(([value, label]) => <label className={`quiz-option ${answers[question.key] === value ? 'quiz-option-selected' : ''}`} key={value}><input type="radio" name={question.key} value={value} checked={answers[question.key] === value} onChange={() => setAnswers((current) => ({ ...current, [question.key]: value }))} /><span className={`visual-dot visual-${value}`} />{label}</label>)}</div></fieldset>)}</div>
      {error && <FormMessage message={error} />}
      <Button onClick={() => { setError(''); mutation.mutate() }} loading={mutation.isPending} disabled={!cropId || Object.keys(answers).length !== 6}>Get my soil plan <ArrowRight size={17} /></Button>
    </Card>
    {result && <section className="farmer-page-stack"><Card className="advice-summary"><p className="eyebrow">YOUR SOIL PLAN</p><h2>{result.summary}</h2>{result.warning?.body && <p className="soil-warning"><ShieldCheck size={17} />{result.warning.body}</p>}</Card><div className="farmer-section-heading"><div><p className="eyebrow">PRIORITISED FOR YOU</p><h2>Start with these tasks</h2></div></div><div className="ranked-advice">{result.tasks?.map((task, index) => <Card key={task.code} className="ranked-task"><span className="rank-number">{String(index + 1).padStart(2, '0')}</span><div><h3>{task.title}</h3><p>{task.body}</p>{task.cost_kes_per_acre && <span className="cost-tag">KES {task.cost_kes_per_acre.min}â€“{task.cost_kes_per_acre.max} / acre</span>}</div></Card>)}</div></section>}
  </div>
}

type SprayResponse = {
  checklist: { code: string; name: string; checked: boolean }[]
  reentry_at: string
  reentry_remaining_seconds: number
  pre_harvest_interval_days: number
  locked_harvest_date: string
  harvest_locked: boolean
}

type PpeGapResult = {
  missing_items: { code: string; name: string; lowest_price_kes: number | null; supplier: { name: string; type: string; ward: string; contact: string; distance_km: number } | null }[]
  nearest_supplier: { name: string; type: string; ward: string; contact: string; distance_km: number; available_items: string[] } | null
}

const ppeOptions = [
  ['mask', 'Mask'],
  ['gloves', 'Gloves'],
  ['boots', 'Boots'],
  ['overall', 'Overall'],
  ['goggles', 'Goggles'],
] as const

function SpraySafeScreen() {
  const toast = useToast()
  const farmsQuery = useListQuery<Farm>('farmer-farms', '/farms/')
  const [farmId, setFarmId] = useState('')
  const [product, setProduct] = useState('')
  const [ingredient, setIngredient] = useState('')
  const [reentry, setReentry] = useState('24')
  const [interval, setInterval] = useState('7')
  const [ppeChecked, setPpeChecked] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<SprayResponse>()
  const [now, setNow] = useState(Date.now())
  const [ownedPpe, setOwnedPpe] = useState<string[]>([])
  const [ppeGap, setPpeGap] = useState<PpeGapResult>()
  const mutation = useMutation({
    mutationFn: async () => submitOfflineCapable<SprayResponse>('POST', '/spray-logs/', {
      farm: Number(farmId), product_name: product, active_ingredient: ingredient,
      sprayed_at: new Date().toISOString(), ppe_checked: ppeChecked,
      reentry_hours: Number(reentry), pre_harvest_days: Number(interval),
    }),
    onSuccess: (data) => {
      setError('')
      if (isQueuedOfflineResult(data)) {
        toast('Spray log saved on this device and will sync when online. The safety countdown will appear after sync.')
        return
      }
      setResult(data)
    },
    onError: () => setError('Could not save the spray log. Check the details and try again.'),
  })
  const ppeMutation = useMutation({
    mutationFn: async () => (await api.post<PpeGapResult>('/advice/ppe-gap-finder/', { owned_items: ownedPpe, ...(farmId ? { farm_id: Number(farmId) } : {}) })).data,
    onSuccess: setPpeGap,
    onError: () => setError('Could not find the nearest PPE supplier. Try again.'),
  })
  useEffect(() => {
    if (!result) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [result])
  const seconds = result ? Math.max(0, Math.floor((new Date(result.reentry_at).getTime() - now) / 1000)) : 0
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainingSeconds = seconds % 60
  return <div className="farmer-page-stack">
    <PageTitle eyebrow="CHEMICAL SAFETY Â· HARVEST" title="Spray Safe" description="Record a spray. Check your protective gear. Know when it is safe to return and harvest." icon={ShieldCheck} />
    <Card className="safety-reminder"><ShieldCheck size={22} /><p><strong>Always follow the product label.</strong><span>Use the labelâ€™s re-entry time and pre-harvest interval when they are longer than your local guidance.</span></p></Card>
    <Card className="farmer-form-card"><h2>Log a spray</h2><form className="farmer-form-grid" onSubmit={(event) => { event.preventDefault(); setError(''); mutation.mutate() }}>
      <div className="field-span">{farmsQuery.isLoading ? <Skeleton className="h-14" /> : farmsQuery.isError ? <QueryError message="Your farms could not load." retry={() => void farmsQuery.refetch()} /> : farmsQuery.data?.length ? <SelectFarm farms={farmsQuery.data} value={farmId} onChange={setFarmId} /> : <EmptyState icon={<Sprout size={24} />} title="Add a farm first" description="A spray log must be linked to one of your farm plots." />}</div>
      <label className="farmer-field"><span>Product name</span><input value={product} onChange={(event) => setProduct(event.target.value)} required /></label>
      <label className="farmer-field"><span>Active ingredient</span><input value={ingredient} onChange={(event) => setIngredient(event.target.value)} required /></label>
      <label className="farmer-field"><span>Re-entry (hours)</span><input type="number" min="0" value={reentry} onChange={(event) => setReentry(event.target.value)} required /></label>
      <label className="farmer-field"><span>Pre-harvest wait (days)</span><input type="number" min="0" value={interval} onChange={(event) => setInterval(event.target.value)} required /></label>
      <label className="ppe-check-field"><input type="checkbox" checked={ppeChecked} onChange={(event) => setPpeChecked(event.target.checked)} /><span><strong>I wore all required PPE</strong><small>Mask, gloves, boots, overall and goggles</small></span></label>
      {error && <FormMessage message={error} />}
      <div className="field-span"><Button type="submit" loading={mutation.isPending} disabled={!farmId}>Save spray and start countdown</Button></div>
    </form></Card>
    {result && <section className="spray-result-grid"><Card className="countdown-card"><p className="eyebrow">RE-ENTRY COUNTDOWN</p><div className="countdown-digits"><strong>{String(hours).padStart(2, '0')}</strong><span>:</span><strong>{String(minutes).padStart(2, '0')}</strong><span>:</span><strong>{String(remainingSeconds).padStart(2, '0')}</strong></div><p>{seconds ? 'Stay out of the treated area until this timer ends.' : 'Re-entry time has passed. Check the label before returning.'}</p></Card><Card className="harvest-lock-card"><CalendarDays size={24} /><p className="eyebrow">HARVEST SAFETY</p><h3>{result.harvest_locked ? 'Harvest is locked' : 'Harvest interval passed'}</h3><p>Earliest safe harvest date</p><strong>{new Date(result.locked_harvest_date).toLocaleDateString()}</strong><span>{result.pre_harvest_interval_days}-day pre-harvest interval</span></Card><Card className="spray-checklist"><h3>PPE checklist</h3>{result.checklist.map((item) => <div key={item.code}><span className={item.checked ? 'checklist-done' : ''}>{item.checked ? <Check size={15} /> : <ShieldCheck size={15} />}</span>{item.name}<strong>{item.checked ? 'Checked' : 'Not checked'}</strong></div>)}</Card></section>}
    <Card className="ppe-gap-card"><div><p className="eyebrow">PPE GAP FINDER</p><h2>What protective gear do you have?</h2><p>Select what you own to find the cheapest missing items nearby.</p></div><div className="ppe-owned-options">{ppeOptions.map(([code, label]) => <label key={code}><input type="checkbox" checked={ownedPpe.includes(code)} onChange={() => setOwnedPpe((items) => items.includes(code) ? items.filter((item) => item !== code) : [...items, code])} />{label}</label>)}</div><Button variant="secondary" onClick={() => { setError(''); ppeMutation.mutate() }} loading={ppeMutation.isPending}>Find missing PPE</Button>
      {ppeGap && <div className="ppe-gap-results">{ppeGap.missing_items.length ? <div><strong>Cheapest missing items</strong>{ppeGap.missing_items.map((item) => <p key={item.code}><span>{item.name}</span><b>{item.lowest_price_kes === null ? 'Ask a local supplier' : `KES ${item.lowest_price_kes}`}</b></p>)}</div> : <p>You have all five core PPE items.</p>}
        {ppeGap.nearest_supplier && <div className="nearest-supplier"><MapPin size={17} /><span><strong>{ppeGap.nearest_supplier.name}</strong><small>{ppeGap.nearest_supplier.type} Â· {ppeGap.nearest_supplier.distance_km} km Â· {ppeGap.nearest_supplier.ward}{ppeGap.nearest_supplier.contact ? ` Â· ${ppeGap.nearest_supplier.contact}` : ''}</small></span></div>}
      </div>}
      {error && <FormMessage message={error} />}
    </Card>
  </div>
}

function ErosionScreen() {
  const farmsQuery = useListQuery<Farm>('farmer-farms', '/farms/')
  const [farmId, setFarmId] = useState('')
  const [cover, setCover] = useState('30')
  const [tillage, setTillage] = useState('conventional')
  const [result, setResult] = useState<{ risk_score: number; risk_level: string; controls: { code: string; title: string; body: string; cost_kes_per_acre: { min: number; max: number } | null; effort: string }[]; seasonal_erosion_calendar: Record<string, string> }>()
  const [error, setError] = useState('')
  const mutation = useMutation({
    mutationFn: async () => (await api.post('/advice/mteremko-guard/', { farm_id: Number(farmId), ground_cover_percent: Number(cover), tillage })).data,
    onSuccess: (data) => { setResult(data); setError('') },
    onError: () => setError('Could not calculate erosion risk. Choose a farm and retry.'),
  })
  return <div className="farmer-page-stack">
    <PageTitle eyebrow="SOIL Â· HEAVY RAIN" title="Mteremko Guard" description="See your erosion risk and start with controls that fit your slope and budget." icon={Waves} />
    <Card className="farmer-form-card"><div className="farmer-form-grid"><div className="field-span">{farmsQuery.isLoading ? <Skeleton className="h-14" /> : farmsQuery.isError ? <QueryError message="Your farms could not load." retry={() => void farmsQuery.refetch()} /> : farmsQuery.data?.length ? <SelectFarm farms={farmsQuery.data} value={farmId} onChange={setFarmId} /> : <EmptyState icon={<Sprout size={24} />} title="Add a farm first" description="Erosion risk needs a farm plot and its slope." />}</div>
      <label className="farmer-field"><span>Ground cover Â· {cover}%</span><input type="range" min="0" max="100" step="5" value={cover} onChange={(event) => setCover(event.target.value)} /></label>
      <label className="farmer-field"><span>Tillage direction</span><select value={tillage} onChange={(event) => setTillage(event.target.value)}><option value="contour">Along the contour</option><option value="conventional">Conventional</option><option value="upslope">Upslope</option></select></label>
      <Button onClick={() => { setError(''); mutation.mutate() }} loading={mutation.isPending} disabled={!farmId}>Check erosion risk</Button>
      {error && <FormMessage message={error} />}
    </div></Card>
    {result && <section className="farmer-page-stack"><Card className={`erosion-score-card score-${result.risk_level.toLowerCase()}`}><RiskGauge score={result.risk_score} /><div><p className="eyebrow">YOUR EROSION RISK Â· {result.risk_level}</p><h2>{result.risk_score < 40 ? 'Keep the soil covered.' : result.risk_score < 70 ? 'Plan simple barriers before heavy rain.' : 'Protect your slope before the next storm.'}</h2><p>Risk uses your slope, 14-day rain outlook, ground cover and tillage.</p></div></Card><div className="farmer-section-heading"><div><p className="eyebrow">RANKED FOR YOUR FARM</p><h2>Controls to consider</h2></div></div><div className="ranked-advice">{result.controls.map((control, index) => <Card key={control.code} className="ranked-task"><span className="rank-number">{String(index + 1).padStart(2, '0')}</span><div><h3>{control.title}</h3><p>{control.body}</p><div className="control-meta"><span>{control.cost_kes_per_acre ? `KES ${control.cost_kes_per_acre.min}â€“${control.cost_kes_per_acre.max}/acre` : 'Low material cost'}</span><span>{control.effort} effort</span></div></div></Card>)}</div><Card className="calendar-note"><CalendarDays size={19} /><div><strong>Seasonal erosion calendar</strong>{Object.entries(result.seasonal_erosion_calendar ?? {}).map(([period, advice]) => <p key={period}><b>{formatTag(period)}:</b> {advice}</p>)}</div></Card></section>}
  </div>
}

const symptomOptions = [
  ['leaf_holes', 'Holes in leaves'],
  ['frass', 'Sawdust-like frass'],
  ['aphid_clusters', 'Small insects in clusters'],
  ['sticky_leaves', 'Sticky leaves'],
  ['whitefly_cloud', 'White insects fly up'],
  ['leafminer_tunnels', 'Tunnels in leaves'],
  ['dark_leaf_spots', 'Dark leaf spots'],
  ['white_leaf_growth', 'White growth on leaves'],
  ['dark_fruit_lesions', 'Dark fruit marks'],
  ['berry_drop', 'Coffee berries dropping'],
] as const

function PestScreen() {
  const farmsQuery = useListQuery<Farm>('farmer-farms', '/farms/')
  const cropsQuery = useListQuery<Crop>('crop-reference', '/crops/')
  const outbreaksQuery = useQuery({
    queryKey: ['pest-outbreaks'],
    queryFn: async () => (await api.get<OutbreakFeatureCollection>('/pests/outbreaks/')).data,
  })
  const knowledgeQuery = useQuery({
    queryKey: ['pest-knowledge'],
    queryFn: async () => (await api.get('/pests/knowledge/')).data as { results: PestKnowledge[]; guide_not_diagnosis: boolean },
  })
  const [farmId, setFarmId] = useState('')
  const [cropId, setCropId] = useState('')
  const [photo, setPhoto] = useState<File | null>(null)
  const [description, setDescription] = useState('')
  const [symptoms, setSymptoms] = useState<string[]>([])
  const [identified, setIdentified] = useState<{ notice: string; results: { pest_name: string; pest_label: string; confidence: string }[] }>()
  const [error, setError] = useState('')
  const queryClient = useQueryClient()
  const toast = useToast()
  const reportMutation = useMutation({
    mutationFn: async () => {
      if (!photo) throw new Error('Add a photo of the affected crop.')
      const compressedPhoto = await compressImageForUpload(photo)
      const body = new FormData()
      body.append('farm', farmId)
      body.append('crop', cropId)
      body.append('photo', compressedPhoto)
      body.append('description', description)
      body.append('symptoms', symptoms.join(', '))
      return submitOfflineCapable('POST', '/pest-reports/', body)
    },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['pest-outbreaks'] })
      setPhoto(null); setDescription(''); setError('')
      toast(isQueuedOfflineResult(result) ? 'Pest report saved on this device and will sync when online.' : 'Pest report sent to your local officer.')
    },
    onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : 'Could not send the pest report.'),
  })
  const identifyMutation = useMutation({
    mutationFn: async () => (await api.post('/pests/identify/', { symptom_icons: symptoms })).data,
    onSuccess: (data) => { setIdentified(data); setError('') },
    onError: () => setError('Choose three different symptoms to see the guide.'),
  })
  const outbreaks = outbreaksQuery.data?.features ?? []
  const markers = outbreaks.map(({ geometry, properties }) => ({
    id: properties.id,
    lat: geometry.coordinates[1],
    lng: geometry.coordinates[0],
    label: properties.ward,
    detail: `${properties.confirmed_count} confirmed Â· ${properties.pest_name}`,
  }))
  const toggleSymptom = (value: string) => setSymptoms((current) => current.includes(value) ? current.filter((item) => item !== value) : current.length < 3 ? [...current, value] : current)
  return <div className="farmer-page-stack">
    <PageTitle eyebrow="REPORT Â· VERIFY Â· ALERT" title="Pest Radar" description="Report a crop problem, choose symptoms for a learning guide, and check nearby confirmed reports." icon={Bug} />
    <Card className="guide-notice"><CircleHelp size={18} /><p><strong>The symptom helper is a guide, never a diagnosis.</strong><span>Ask an officer to confirm a pest before taking high-risk action.</span></p></Card>
    <div className="farmer-section-heading"><div><p className="eyebrow">FIELD GUIDE</p><h2>Pick three symptoms</h2></div><span className="quiz-step-count">{symptoms.length}/3</span></div>
    <Card className="symptom-card"><div className="symptom-grid">{symptomOptions.map(([value, label]) => <button className={`symptom-option ${symptoms.includes(value) ? 'symptom-selected' : ''}`} key={value} onClick={() => toggleSymptom(value)} aria-pressed={symptoms.includes(value)}><span className="symptom-leaf"><Leaf size={19} /></span><span>{label}</span>{symptoms.includes(value) && <Check size={15} />}</button>)}</div><Button variant="secondary" onClick={() => identifyMutation.mutate()} loading={identifyMutation.isPending} disabled={symptoms.length !== 3}>Show likely matches <ArrowRight size={16} /></Button>
      {identified && <div className="identification-result"><strong>{identified.notice}</strong>{identified.results.map((item) => <div key={item.pest_name}><span>{item.pest_label}</span><span className="confidence-label">{item.confidence}</span></div>)}</div>}
    </Card>
    {knowledgeQuery.isLoading ? <Skeleton className="h-20" /> : knowledgeQuery.isError ? <QueryError message="The pest knowledge guide could not load." retry={() => void knowledgeQuery.refetch()} /> : knowledgeQuery.data?.results?.length ? <details className="knowledge-accordion"><summary>Read safe first actions from the pest knowledge base</summary><div className="knowledge-grid">{knowledgeQuery.data.results.slice(0, 4).map((pest) => <Card key={pest.pest_name}><h3>{pest.pest_label}</h3><ul>{pest.safe_first_actions.slice(0, 3).map((action) => <li key={action}>{action}</li>)}</ul></Card>)}</div></details> : <Card className="farmer-empty-card"><EmptyState icon={<Bug size={24} />} title="No pest guide entries yet" description="Ask your agriculture officer for safe first steps while the guide is being prepared." /></Card>}
    <Card className="farmer-form-card"><div className="farmer-section-heading"><div><p className="eyebrow">ASK FOR HELP</p><h2>Send a pest report</h2></div></div><form className="farmer-form-grid" onSubmit={(event) => { event.preventDefault(); setError(''); reportMutation.mutate() }}>
      <div className="field-span">{farmsQuery.isLoading ? <Skeleton className="h-14" /> : farmsQuery.isError ? <QueryError message="Your farms could not load." retry={() => void farmsQuery.refetch()} /> : farmsQuery.data?.length ? <SelectFarm farms={farmsQuery.data} value={farmId} onChange={setFarmId} /> : <EmptyState icon={<Sprout size={24} />} title="Add a farm first" description="A report needs a farm location to reach the right officer." />}</div>
      <div className="field-span">{cropsQuery.isLoading ? <Skeleton className="h-14" /> : cropsQuery.isError ? <QueryError message="The crop list could not load." retry={() => void cropsQuery.refetch()} /> : cropsQuery.data?.length ? <SelectCrop crops={cropsQuery.data} value={cropId} onChange={setCropId} /> : <EmptyState icon={<Leaf size={24} />} title="No crops available" description="The crop catalogue is needed to classify your report." />}</div>
      <label className="farmer-field field-span"><span>Crop photo Â· camera or gallery</span><input type="file" accept="image/*" capture="environment" onChange={(event) => setPhoto(event.target.files?.[0] ?? null)} required /><small>{photo?.name || 'Location is taken from the selected farm plot.'}</small></label>
      <label className="farmer-field field-span"><span>What are you seeing?</span><textarea rows={3} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Optional details about the damage" /></label>
      {error && <FormMessage message={error} />}
      <div className="field-span"><Button type="submit" loading={reportMutation.isPending} disabled={!farmId || !cropId || !photo}><Bug size={17} /> Send to an officer</Button></div>
    </form></Card>
    <div className="farmer-section-heading"><div><p className="eyebrow">LOCAL SIGNALS Â· CONFIRMED</p><h2>Nearby outbreaks</h2></div></div>
    <Card className="farmer-map-card outbreak-app-map">{outbreaksQuery.isLoading ? <Skeleton className="farmer-map-skeleton" /> : outbreaksQuery.isError ? <QueryError message="Nearby outbreak reports could not load." retry={() => void outbreaksQuery.refetch()} /> : <Suspense fallback={<Skeleton className="farmer-map-skeleton" />}><FarmerMap markers={markers} /></Suspense>}</Card>
    {outbreaks.length ? <div className="outbreak-app-list">{outbreaks.map(({ properties: outbreak }) => <Card key={outbreak.id}><span className={`outbreak-level level-${outbreak.level.toLowerCase()}`} /><div><strong>{formatTag(outbreak.pest_name)}</strong><span>{outbreak.ward} Â· {outbreak.confirmed_count} confirmed{outbreak.crop ? ` Â· ${outbreak.crop}` : ''}</span></div><span>{outbreak.level}</span></Card>)}</div> : !outbreaksQuery.isLoading && !outbreaksQuery.isError && <p className="muted-helper">No active confirmed outbreaks are listed for your ward.</p>}
    <p className="small-disclaimer">Area alerts start after three confirmed reports of the same pest and crop in seven days.</p>
  </div>
}

function Sparkline({ values }: { values: number[] }) {
  const maximum = Math.max(...values, 1)
  const minimum = Math.min(...values, 0)
  const points = values.map((value, index) => `${(index / (values.length - 1 || 1)) * 100},${30 - ((value - minimum) / (maximum - minimum || 1)) * 26}`).join(' ')
  return <svg className="market-sparkline" viewBox="0 0 100 32" role="img" aria-label="Recent market price trend"><polyline points={points} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" /></svg>
}

function MarketScreen() {
  const pricesQuery = useListQuery<MarketPrice>('market-prices', '/market-prices/')
  const cropsQuery = useListQuery<Crop>('crop-reference', '/crops/')
  const buyersQuery = useListQuery<Buyer>('verified-buyers', '/buyers/')
  const farmsQuery = useListQuery<Farm>('farmer-farms', '/farms/')
  const queryClient = useQueryClient()
  const toast = useToast()
  const [cropId, setCropId] = useState('')
  const [quantity, setQuantity] = useState('')
  const [harvestDate, setHarvestDate] = useState('')
  const [price, setPrice] = useState('')
  const [trendCropId, setTrendCropId] = useState('')
  const [error, setError] = useState('')
  const [listingMessage, setListingMessage] = useState('')
  const listingsQuery = useListQuery<SellListing>('sell-listings', '/sell-listings/')
  const postListing = useMutation({
    mutationFn: async () => (await api.post('/sell-listings/', { crop: Number(cropId), quantity_kg: quantity, harvest_date: harvestDate, asking_price_per_kg: price })).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['sell-listings'] })
      setListingMessage('Your crop offer is now visible to buyers.')
      setCropId(''); setQuantity(''); setHarvestDate(''); setPrice(''); setError('')
      toast('Your crop listing was posted.')
    },
    onError: () => setError('Could not post the crop listing. Check the details and try again.'),
  })
  const prices = pricesQuery.data ?? []
  const trendOptions = (cropsQuery.data ?? []).filter((crop) => prices.some((item) => (typeof item.crop === 'object' ? item.crop.id : item.crop) === crop.id))
  const selectedTrendCropId = trendCropId || String(trendOptions[0]?.id ?? '')
  const trendsQuery = useQuery({
    queryKey: ['market-trends', selectedTrendCropId],
    queryFn: async () => (await api.get('/market-prices/trends/', { params: { crop_id: selectedTrendCropId } })).data as PriceTrend,
    enabled: !!selectedTrendCropId,
  })
  const grouped = new Map<string, { price: MarketPrice; points: number[] }>()
  prices.forEach((item) => {
    const crop = typeof item.crop === 'object' ? item.crop.name : cropsQuery.data?.find((c) => c.id === item.crop)?.name ?? `Crop ${item.crop}`
    const value = Number(item.price_per_kg)
    const existing = grouped.get(crop)
    if (existing) existing.points.push(value)
    else grouped.set(crop, { price: item, points: [value] })
  })
  const farm = farmsQuery.data?.[0]
  const listings = listingsQuery.data ?? []
  return <div className="farmer-page-stack">
    <PageTitle eyebrow="LOCAL PRICES Â· LOCAL BUYERS" title="Soko Link" description="Compare current prices, find verified buyers and list a coming harvest." icon={Store} />
    <div className="farmer-section-heading"><div><p className="eyebrow">RECENT MARKET PRICES</p><h2>What crops are fetching</h2></div>{prices.some((item) => item.is_sample_data) && <span className="sample-label">SAMPLE PRICES</span>}</div>
    {pricesQuery.isLoading ? <LoadingCard rows={4} /> : pricesQuery.isError ? <QueryError message="Market prices could not load." retry={() => void pricesQuery.refetch()} /> : prices.length ? <div className="price-table-wrap"><table className="price-table"><thead><tr><th>Crop</th><th>Market</th><th>Price / kg</th><th>Trend</th><th>Date</th></tr></thead><tbody>{Array.from(grouped.entries()).map(([name, item]) => <tr key={name}><td><strong>{name}</strong></td><td>{item.price.market_name}</td><td><strong>KES {Number(item.price.price_per_kg).toLocaleString()}</strong></td><td><Sparkline values={item.points.slice(0, 7).reverse()} /></td><td>{item.price.date}</td></tr>)}</tbody></table></div> : <Card className="farmer-empty-card"><EmptyState icon={<TrendingUp size={25} />} title="No prices yet" description="Price records will appear here when your markets have reported." /></Card>}
    {trendOptions.length > 0 && <Card className="market-trend-card"><div className="farmer-section-heading"><div><p className="eyebrow">PRICE HISTORY</p><h2>7- and 30-day trends</h2></div></div><label className="farmer-field"><span>Choose a crop</span><select value={selectedTrendCropId} onChange={(event) => setTrendCropId(event.target.value)}>{trendOptions.map((crop) => <option key={crop.id} value={crop.id}>{crop.name}</option>)}</select></label>
      {trendsQuery.isLoading ? <Skeleton className="h-12" /> : trendsQuery.isError ? <QueryError message="Price trends could not load." retry={() => void trendsQuery.refetch()} /> : trendsQuery.data && <div className="trend-period-grid">{(['trend_7d', 'trend_30d'] as const).map((period) => {
        const trend = trendsQuery.data[period]
        const points = trend.daily_prices.map((item) => Number(item.average_price_per_kg))
        const change = trend.change_percent
        return <div className="trend-period" key={period}><div><span>{period === 'trend_7d' ? 'Last 7 days' : 'Last 30 days'}</span><strong>{trend.average_price_per_kg === null ? 'No recent data' : `KES ${Number(trend.average_price_per_kg).toLocaleString()} / kg`}</strong></div><Sparkline values={points.length ? points : [0]} /><small className={change !== null && change < 0 ? 'trend-down' : 'trend-up'}>{change === null ? 'Change unavailable' : `${change > 0 ? '+' : ''}${change}% vs previous period`}</small></div>
      })}</div>}
    </Card>}
    <div className="farmer-section-heading"><div><p className="eyebrow">VERIFIED BUYERS</p><h2>Find a buyer</h2></div></div>
    {buyersQuery.isLoading ? <LoadingCard rows={2} /> : buyersQuery.isError ? <QueryError message="Buyer directory could not load." retry={() => void buyersQuery.refetch()} /> : buyersQuery.data?.length ? <div className="buyer-list">{buyersQuery.data.slice(0, 5).map((buyer) => <Card key={buyer.id} className="buyer-card"><span className="buyer-icon"><Store size={18} /></span><div><strong>{buyer.name}</strong><span>{buyer.type.toLowerCase()} Â· {buyer.contact}</span>{buyer.is_sample_data && <small className="sample-label">SAMPLE LISTING</small>}</div>{buyer.verified && <BadgeCheck size={17} className="verified-icon" />}</Card>)}</div> : <Card className="farmer-empty-card"><EmptyState icon={<Store size={24} />} title="No buyers listed yet" description="Your cooperative or agriculture officer can help connect you with local buyers." /></Card>}
    <Card className="farmer-form-card"><div className="farmer-section-heading"><div><p className="eyebrow">SELL MY CROP</p><h2>Let buyers find you</h2></div></div>{farm && <p className="muted-helper">Listing from your farm in {farm.id ? 'your ward' : 'your area'}.</p>}
      <form className="farmer-form-grid" onSubmit={(event) => { event.preventDefault(); setError(''); setListingMessage(''); postListing.mutate() }}>
        <div className="field-span"><SelectCrop crops={cropsQuery.data ?? []} value={cropId} onChange={setCropId} /></div>
        <label className="farmer-field"><span>Quantity (kg)</span><input type="number" min="0.1" step="0.1" value={quantity} onChange={(event) => setQuantity(event.target.value)} required /></label>
        <label className="farmer-field"><span>Expected harvest</span><input type="date" min={new Date().toISOString().slice(0, 10)} value={harvestDate} onChange={(event) => setHarvestDate(event.target.value)} required /></label>
        <label className="farmer-field"><span>Asking price (KES/kg)</span><input type="number" min="0" step="0.01" value={price} onChange={(event) => setPrice(event.target.value)} required /></label>
        {error && <FormMessage message={error} />}{listingMessage && <p className="success-message" role="status">{listingMessage}</p>}
        <div className="field-span"><Button type="submit" loading={postListing.isPending} disabled={!cropId}>Post my crop</Button></div>
      </form>
    </Card>
    {listingsQuery.isError ? <QueryError message="Open crop listings could not load." retry={() => void listingsQuery.refetch()} /> : listingsQuery.isLoading ? <LoadingCard rows={2} /> : listings.length ? <><div className="farmer-section-heading"><div><p className="eyebrow">OPEN OFFERS</p><h2>Farmers are selling</h2></div></div><div className="buyer-list">{listings.slice(0, 5).map((listing) => <Card className="listing-card" key={listing.id}><div><strong>{listing.crop_name}</strong><span>{listing.quantity_kg} kg Â· harvest {listing.harvest_date}</span></div><strong>KES {listing.asking_price_per_kg}/kg</strong></Card>)}</div></> : <Card className="farmer-empty-card"><EmptyState icon={<Store size={24} />} title="No open crop offers yet" description="When a farmer lists a harvest, buyers can find it here." /></Card>}
  </div>
}

type PriceTrend = {
  trend_7d: { daily_prices: { date: string; average_price_per_kg: string }[]; average_price_per_kg: string | null; change_percent: number | null }
  trend_30d: { daily_prices: { date: string; average_price_per_kg: string }[]; average_price_per_kg: string | null; change_percent: number | null }
}

function AcademyScreen() {
  const { language } = useI18n()
  const lessonsQuery = useListQuery<Lesson>('lessons', '/lessons/')
  const progressQuery = useListQuery<LessonProgress>('lesson-progress', '/lesson-progress/')
  const badgesQuery = useListQuery<Badge>('earned-badges', '/badges/')
  const queryClient = useQueryClient()
  const toast = useToast()
  const [selectedLesson, setSelectedLesson] = useState<number | null>(null)
  const [answers, setAnswers] = useState<number[]>([])
  const [error, setError] = useState('')
  const lessons = lessonsQuery.data ?? []
  const lesson = lessons.find((item) => item.id === selectedLesson) ?? lessons[0]
  const progress = progressQuery.data?.find((item) => item.lesson === lesson?.id)
  const stepIndex = progress?.completed_steps ?? 0
  const quiz = lesson?.quiz ?? []
  const saveProgress = useMutation({
    mutationFn: async ({ completed_steps, quiz_answers }: { completed_steps?: number; quiz_answers?: number[] }) => {
      const payload = { lesson: lesson?.id, completed_steps, quiz_answers }
      return progress
        ? api.patch(`/lesson-progress/${progress.id}/`, payload)
        : api.post('/lesson-progress/', payload)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['lesson-progress'] })
      void queryClient.invalidateQueries({ queryKey: ['earned-badges'] })
      setError('')
      toast('Lesson progress saved.')
    },
    onError: () => setError('Could not save lesson progress. Try again.'),
  })
  const pickLesson = (id: number) => { setSelectedLesson(id); setAnswers([]); setError('') }
  const audio = lesson?.audio_by_language?.[language] || lesson?.audio_url
  return <div className="farmer-page-stack">
    <PageTitle eyebrow="SHORT LESSONS Â· FIELD READY" title="Shamba Academy" description="Learn one practical action at a time. Every lesson takes two minutes or less." icon={BookOpen} />
    <div className="farmer-section-heading"><div><p className="eyebrow">YOUR BADGES</p><h2>Progress worth celebrating</h2></div></div>
    {badgesQuery.isError && <QueryError message="Earned badges could not load." retry={() => void badgesQuery.refetch()} />}
    <div className="badge-list">{['Soil Hero', 'Safe Sprayer', 'Erosion Fighter', 'Clean Farm', 'Market Ready'].map((name) => {
      const badge = badgesQuery.data?.find((item) => item.name === name)
      return <Card key={name} className={`academy-badge ${badge ? 'badge-earned' : ''}`}><span><BadgeCheck size={22} /></span><strong>{name}</strong><small>{badge ? 'Earned' : 'Keep learning'}</small></Card>
    })}</div>
    <div className="farmer-section-heading"><div><p className="eyebrow">TWO-MINUTE LEARNING</p><h2>Choose a lesson</h2></div></div>
    {progressQuery.isError && <QueryError message="Lesson progress could not load." retry={() => void progressQuery.refetch()} />}
    {lessonsQuery.isLoading ? <LoadingCard rows={3} /> : lessonsQuery.isError ? <QueryError message="Lessons could not load." retry={() => void lessonsQuery.refetch()} /> : lessons.length ? <div className="lesson-card-list">{lessons.map((item) => {
      const itemProgress = progressQuery.data?.find((entry) => entry.lesson === item.id)
      return <button className={`lesson-select-card ${lesson?.id === item.id ? 'lesson-selected' : ''}`} key={item.id} onClick={() => pickLesson(item.id)}>
        <span className="lesson-book-icon"><BookOpen size={19} /></span><span className="lesson-select-copy"><strong>{item.title}</strong><small>{formatTag(item.problem_tag)} Â· {Math.ceil(item.duration_sec / 60)} min</small></span><span className="lesson-progress-label">{itemProgress?.completed ? 'Done' : `${itemProgress?.progress_percent ?? 0}%`}</span>
      </button>
    })}</div> : <Card className="farmer-empty-card"><EmptyState icon={<BookOpen size={24} />} title="No lessons available yet" description="Ask your officer about upcoming farmer training while lessons are being added." /></Card>}
    {lesson && <Card className="lesson-detail-card">
      <div className="lesson-detail-head"><div><p className="eyebrow">YOUR NEXT STEP</p><h2>{lesson.title}</h2></div><span className="lesson-duration"><CalendarDays size={15} /> {Math.ceil(lesson.duration_sec / 60)} min</span></div>
      {lesson.photo && <img className="lesson-photo" src={lesson.photo} alt={`Illustration for ${lesson.title}`} loading="lazy" />}
      {audio && <audio className="lesson-audio" controls preload="none" src={audio}>Your browser does not support audio playback.</audio>}
      <ol className="lesson-step-list">{lesson.steps.map((step, index) => <li className={index < stepIndex ? 'lesson-step-done' : ''} key={`${index}-${step}`}><span>{index < stepIndex ? <Check size={16} /> : index + 1}</span><p>{step}</p></li>)}</ol>
      {stepIndex < lesson.steps.length && <Button variant="secondary" onClick={() => saveProgress.mutate({ completed_steps: stepIndex + 1 })} loading={saveProgress.isPending}><Check size={16} /> Mark step {stepIndex + 1} done</Button>}
      <div className="lesson-quiz"><h3>Quick check</h3>{quiz.map((question, questionIndex) => <fieldset className="quiz-question" key={question.question}><legend>{questionIndex + 1}. {question.question}</legend><div>{question.options.map((option, optionIndex) => <label key={option}><input type="radio" name={`lesson-${lesson.id}-q-${questionIndex}`} checked={answers[questionIndex] === optionIndex} onChange={() => setAnswers((previous) => { const next = [...previous]; next[questionIndex] = optionIndex; return next })} />{option}</label>)}</div></fieldset>)}<Button onClick={() => saveProgress.mutate({ quiz_answers: answers })} disabled={answers.length !== 3 || answers.some((answer) => answer === undefined)} loading={saveProgress.isPending}>Submit answers</Button></div>
      {error && <FormMessage message={error} />}
    </Card>}
  </div>
}

type TakaAdvice = {
  recipe: { title: string; body: string; metadata?: Record<string, unknown> }
  nearest_disposal_point: { id: number; name: string; type: string; lat: number; lng: number; ward: string; hours: string; contact: string; distance_km: number } | null
  clean_farm: { waste_action_count: number; score: number; score_per_logged_action: number }
}

const wasteChoices = [
  { value: 'CROP_RESIDUE', label: 'Crop residue', icon: Sprout },
  { value: 'CHEMICAL_CONTAINER', label: 'Pesticide containers', icon: ShieldCheck },
  { value: 'PACKAGING', label: 'Farm packaging', icon: Recycle },
]

function WasteScreen() {
  const [wasteType, setWasteType] = useState('CROP_RESIDUE')
  const [farmId, setFarmId] = useState('')
  const [error, setError] = useState('')
  const queryClient = useQueryClient()
  const toast = useToast()
  const farmsQuery = useListQuery<Farm>('farmer-farms', '/farms/')
  const adviceQuery = useQuery({
    queryKey: ['taka-loop', wasteType, farmId],
    queryFn: async () => (await api.get<TakaAdvice>('/advice/taka-loop/', { params: { waste_type: wasteType, ...(farmId ? { farm_id: farmId } : {}) } })).data,
  })
  const logMutation = useMutation({
    mutationFn: async () => api.post('/waste-logs/', { waste_type: wasteType, action: wasteType === 'CHEMICAL_CONTAINER' ? 'Triple-rinsed and taken to a collection point' : wasteType === 'CROP_RESIDUE' ? 'Composted crop residue' : 'Reused or safely sorted farm packaging' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['taka-loop'] })
      void queryClient.invalidateQueries({ queryKey: ['waste-logs'] })
      setError('')
      toast('Your safe waste action was logged.')
    },
    onError: () => setError('Could not log this waste action. Please try again.'),
  })
  const point = adviceQuery.data?.nearest_disposal_point
  const markers = point ? [{ id: point.id, lat: point.lat, lng: point.lng, label: point.name, detail: `${point.distance_km} km Â· ${point.ward}` }] : []
  const cleanFarm = adviceQuery.data?.clean_farm
  return <div className="farmer-page-stack">
    <PageTitle eyebrow="COMPOST Â· RINSE Â· RETURN" title="Taka Loop" description="Put farm waste to safer use and find the closest container drop-off." icon={Recycle} />
    <div className="farmer-section-heading"><div><p className="eyebrow">CHOOSE YOUR WASTE</p><h2>What are you handling?</h2></div></div>
    <div className="waste-choice-grid">{wasteChoices.map(({ value, label, icon: Icon }) => <button key={value} className={`waste-choice ${wasteType === value ? 'waste-choice-selected' : ''}`} onClick={() => setWasteType(value)} aria-pressed={wasteType === value}><Icon size={21} /><span>{label}</span><Check size={16} /></button>)}</div>
    {farmsQuery.isLoading ? <Skeleton className="h-14" /> : farmsQuery.isError ? <QueryError message="Your farms could not load." retry={() => void farmsQuery.refetch()} /> : farmsQuery.data?.length ? <SelectFarm farms={farmsQuery.data} value={farmId} onChange={setFarmId} /> : <EmptyState icon={<Sprout size={24} />} title="No farm selected" description="Add a farm plot to locate its nearest safe disposal point." />}
    {adviceQuery.isLoading ? <LoadingCard rows={3} /> : adviceQuery.isError ? <QueryError message="Waste advice could not load." retry={() => void adviceQuery.refetch()} /> : adviceQuery.data && <Card className="waste-recipe-card"><span className="waste-recipe-icon"><Recycle size={23} /></span><p className="eyebrow">SAFE FIRST ACTION</p><h2>{adviceQuery.data.recipe.title}</h2><p>{adviceQuery.data.recipe.body}</p>
      {wasteType === 'CHEMICAL_CONTAINER' && <ol className="rinse-steps"><li>Wear gloves and keep children away.</li><li>Empty the container into the spray tank while mixing.</li><li>Fill one-quarter with clean water, close, shake, and pour rinse water into the spray tank.</li><li>Repeat the rinse two more times. Never reuse the container.</li><li>Keep it secure and take it to an approved collection point.</li></ol>}
      <Button onClick={() => logMutation.mutate()} loading={logMutation.isPending}><Check size={17} /> Log safe action</Button>
      {error && <FormMessage message={error} />}
    </Card>}
    <div className="farmer-section-heading"><div><p className="eyebrow">NEAREST DROP-OFF</p><h2>Return containers safely</h2></div></div>
    {point ? <><Card className="disposal-point-card"><span className="disposal-icon"><MapPin size={21} /></span><div><strong>{point.name}</strong><span>{point.type} Â· {point.distance_km} km away Â· {point.ward}</span><small>{point.hours || 'Check opening hours before travelling'}{point.contact ? ` Â· ${point.contact}` : ''}</small></div></Card><Card className="farmer-map-card disposal-map"><Suspense fallback={<Skeleton className="farmer-map-skeleton" />}><FarmerMap markers={markers} /></Suspense></Card></> : adviceQuery.data && <Card className="farmer-empty-card"><EmptyState icon={<MapPin size={25} />} title="No collection point listed" description="Ask your local cooperative or agriculture officer about safe container collection." /></Card>}
    {cleanFarm && <Card className="clean-farm-score"><div className="clean-score-number">{cleanFarm.score}<small>/100</small></div><div><p className="eyebrow">CLEAN FARM SCORE</p><h3>{cleanFarm.waste_action_count} safe actions logged</h3><p>Each logged action adds {cleanFarm.score_per_logged_action} points.</p></div><Recycle size={25} /></Card>}
  </div>
}

export function FarmerExperiencePage() {
  const { pathname } = useLocation()
  const { user } = useAuth()
  const screens: Record<string, React.ComponentType> = {
    '/app': TodayScreen,
    '/app/farms': FarmsScreen,
    '/app/planner': PlannerScreen,
    '/app/soil': SoilScreen,
    '/app/spray-safe': SpraySafeScreen,
    '/app/erosion': ErosionScreen,
    '/app/pests': PestScreen,
    '/app/market': MarketScreen,
    '/app/learn': AcademyScreen,
    '/app/waste': WasteScreen,
    '/app/alerts': TodayScreen,
    '/app/weather': PlannerScreen,
  }
  const Screen = screens[pathname] ?? TodayScreen
  if (user && user.role !== 'FARMER') return <Navigate to="/app" replace />
  return <main className="farmer-experience"><Screen /></main>
}
