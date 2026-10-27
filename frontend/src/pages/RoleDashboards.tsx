import { lazy, Suspense, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  IconActivity as Activity,
  IconAlert as AlertTriangle,
  IconBadgeCheck as BadgeCheck,
  IconPest as Bug,
  IconCheck as Check,
  IconCircleHelp as CircleHelp,
  IconDownload as Download,
  IconEye as Eye,
  IconEyeOff as EyeOff,
  IconFileCheck as FileCheck2,
  IconHeadphones as Headphones,
  IconLocation as MapPin,
  IconMessageSquare as MessageSquareText,
  IconPhone as Phone,
  IconSend as Send,
  IconShieldCheck as ShieldCheck,
  IconUsers as Users,
} from '../components/icons'
import { Navigate } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useAuth } from '../auth/AuthProvider'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { Skeleton } from '../components/ui/Skeleton'
import { api } from '../lib/api'
import { getList } from '../types'
import type { ApiList, FarmerUser, Farm, Language } from '../types'
import { useToast } from '../hooks/useToast'
import './role-dashboards.css'

const CountyMap = lazy(() => import('../components/dashboard/CountyDashboardMap'))

type Ward = { id: number; name: string; sub_county: string; lat: number; lng: number }
type Farmer = { id: number; user: number; ward: number; literacy_level: string; has_smartphone: boolean }
type OfficerUser = FarmerUser & { channel_preference?: string; consent_sms?: boolean }
type Alert = { id: number; farmer: number; rule: number | null; severity: string; created_at: string; title: string }
type Delivery = { id: number; alert: number; channel: string; sent_at: string | null; delivered: boolean; feedback: 'HELPFUL' | 'NOT_RELEVANT' | null }
type Rule = { id: number; code: string; problem_tag: string; severity: string; active: boolean }
type PestReport = { id: number; farmer: number; crop: number | null; ward: number; status: string; pest_name: string; created_at: string }
type MarketPrice = { crop: number | { id: number; name: string }; market_name: string; ward: number | { id: number; name: string }; price_per_kg: string; date: string; is_sample_data?: boolean }
type Question = { id: number; farmer: number; ward: number; question: string; voice_note: string | null; created_at: string; status: string }
type VerificationReport = {
  id: number
  farmer: number
  farm: number | null
  crop: number | null
  photo: string
  description: string
  symptoms: string
  lat: number | null
  lng: number | null
  ward: number
  status: string
  created_at: string
}
type GeoJSONOutbreaks = import('../components/dashboard/CountyDashboardMap').CountyOutbreaks
type PriceSeriesPoint = { date: string; [cropName: string]: string | number }

const palette = ['#1B4D1E', '#5B8C3A', '#D8972C', '#9E2012', '#7897B3', '#87916D', '#B46A45', '#404D36']
const pestChoices = [
  ['fall_armyworm', 'Fall armyworm'],
  ['aphids', 'Aphids'],
  ['whitefly', 'Whitefly'],
  ['tomato_leafminer', 'Tomato leafminer (Tuta absoluta)'],
  ['late_blight', 'Late blight'],
  ['coffee_berry_disease', 'Coffee berry disease'],
]

function useApiList<T>(key: string, url: string) {
  return useQuery({
    queryKey: [key],
    queryFn: async () => getList<T>((await api.get(url)).data as T[] | ApiList<T>),
  })
}

function useApiUserList() {
  return useQuery({
    queryKey: ['dashboard-users'],
    queryFn: async () => getList<OfficerUser>((await api.get('/users/')).data),
  })
}

function Header({ eyebrow, title, description, icon: Icon }: { eyebrow: string; title: string; description: string; icon: typeof Users }) {
  return <header className="role-dashboard-header"><span className="role-dashboard-icon"><Icon size={24} /></span><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div></header>
}

function Metric({ label, value, note, icon: Icon }: { label: string; value: string | number; note: string; icon: typeof Users }) {
  return <Card className="role-metric"><span className="role-metric-icon"><Icon size={18} /></span><strong>{value}</strong><span>{label}</span><small>{note}</small></Card>
}

function ErrorState({ text, retry }: { text: string; retry: () => void }) {
  return <Card className="dashboard-error" role="alert"><CircleHelp size={19} /><span>{text}</span><button onClick={retry}>Retry</button></Card>
}

function PhotoDialog({ src, onClose }: { src: string; onClose: () => void }) {
  return <div className="photo-dialog-backdrop" role="presentation" onClick={onClose}><div className="photo-dialog" role="dialog" aria-modal="true" aria-label="Pest report photo" onClick={(event) => event.stopPropagation()}><button className="photo-dialog-close" onClick={onClose} aria-label="Close photo"><EyeOff size={19} /></button><img src={src} alt="Zoomed farmer-submitted crop photo" /></div></div>
}

function OfficerDashboard() {
  const { user } = useAuth()
  const toast = useToast()
  const client = useQueryClient()
  const wardsQuery = useApiList<Ward>('officer-wards', '/wards/')
  const farmersQuery = useApiList<Farmer>('officer-farmers', '/farmers/')
  const usersQuery = useApiUserList()
  const deliveriesQuery = useApiList<Delivery>('officer-deliveries', '/alert-deliveries/')
  const alertsQuery = useApiList<Alert>('officer-alerts', '/alerts/')
  const [ward, setWard] = useState('')
  const [phone, setPhone] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [language, setLanguage] = useState<Language>('en')
  const [literacy, setLiteracy] = useState('MEDIUM')
  const [consentSms, setConsentSms] = useState(false)
  const [answer, setAnswer] = useState<Record<number, string>>({})
  const [answerLanguage, setAnswerLanguage] = useState<Language>('en')
  const [activePhoto, setActivePhoto] = useState('')
  const [verifyChoices, setVerifyChoices] = useState<Record<number, string>>({})
  const [verifyNotes, setVerifyNotes] = useState<Record<number, string>>({})
  const [formError, setFormError] = useState('')

  const queueQuery = useQuery({
    queryKey: ['officer-pest-queue'],
    queryFn: async () => getList<VerificationReport>((await api.get('/pest-reports/verification-queue/')).data),
  })
  const questionsQuery = useQuery({
    queryKey: ['officer-question-queue'],
    queryFn: async () => getList<Question>((await api.get('/officer-questions/queue/')).data),
  })
  const availableWards = wardsQuery.data ?? []
  const selectedWard = ward || String(availableWards[0]?.id ?? '')
  const farmerProfiles = farmersQuery.data ?? []
  const deliveredAlertIds = useMemo(() => new Set((deliveriesQuery.data ?? []).filter((item) => item.delivered && item.sent_at && new Date(item.sent_at).getTime() >= Date.now() - 30 * 86400000).map((item) => item.alert)), [deliveriesQuery.data])
  const reachedFarmerIds = useMemo(() => {
    const alertFarmerById = new Map((alertsQuery.data ?? []).map((item) => [item.id, item.farmer]))
    return new Set([...deliveredAlertIds].map((id) => alertFarmerById.get(id)).filter((id): id is number => id !== undefined))
  }, [alertsQuery.data, deliveredAlertIds])
  const userById = useMemo(() => new Map((usersQuery.data ?? []).map((item) => [item.id, item])), [usersQuery.data])
  const unreachable = farmerProfiles.filter((farmer) => !reachedFarmerIds.has(farmer.id))

  const registerMutation = useMutation({
    mutationFn: async () => (await api.post('/farmers/register/', {
      phone: phone.trim(),
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      ward: Number(selectedWard),
      language,
      channel_preference: 'sms',
      consent_sms: consentSms,
      literacy_level: literacy,
      has_smartphone: false,
    })).data,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['officer-farmers'] })
      void client.invalidateQueries({ queryKey: ['dashboard-users'] })
      setPhone(''); setFirstName(''); setLastName(''); setFormError('')
      toast('Farmer registered. Phone access and SMS consent recorded.')
    },
    onError: (error) => setFormError(error instanceof Error ? error.message : 'Farmer could not be registered.'),
  })
  const answerMutation = useMutation({
    mutationFn: async ({ id, text }: { id: number; text: string }) => api.post(`/officer-questions/${id}/answer/`, { answer: text, language: answerLanguage }),
    onSuccess: (_result, variables) => {
      void client.invalidateQueries({ queryKey: ['officer-question-queue'] })
      setAnswer((current) => ({ ...current, [variables.id]: '' }))
      toast('Answer sent and added to searchable FAQs.')
    },
    onError: () => toast('Answer could not be sent. Please retry.', 'error'),
  })
  const verifyMutation = useMutation({
    mutationFn: async ({ id, decision }: { id: number; decision: 'CONFIRM' | 'REJECT' | 'NEEDS_INFO' }) => {
      const body = {
        decision,
        ...(decision === 'CONFIRM' ? { pest_name: verifyChoices[id] } : {}),
        note: verifyNotes[id] ?? '',
      }
      return api.patch(`/pest-reports/${id}/verify/`, body)
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['officer-pest-queue'] })
      void client.invalidateQueries({ queryKey: ['officer-alerts'] })
      toast('Pest report review saved.')
    },
    onError: () => toast('The report could not be updated. Check that the pest and note are set.', 'error'),
  })
  const unreadablePhoneCount = unreachable.filter((farmer) => !userById.get(farmer.user)?.phone).length

  if (!user || user.role === 'FARMER') return <Navigate to="/app" replace />
  return <div className="role-dashboard">
    <Header eyebrow="OFFICER FIELD DESK" title="Ward operations" description="Register farmers, verify local reports and close the loop with timely advice." icon={ShieldCheck} />
    <div className="role-metric-grid role-metric-grid-3">
      <Metric label="Farmers in your wards" value={farmersQuery.data?.length ?? 'â€”'} note="Ward-scoped roster" icon={Users} />
      <Metric label="Verification queue" value={queueQuery.data?.length ?? 'â€”'} note="Reports awaiting review" icon={Bug} />
      <Metric label="Not reached Â· 30 days" value={unreachable.length} note="No delivered alert recorded" icon={Phone} />
    </div>
    <div className="role-dashboard-columns">
      <Card className="role-panel"><div className="role-panel-heading"><div><p className="eyebrow">OFFLINE-FIRST ONBOARDING</p><h2>Register a farmer</h2><p>For a basic phone, capture their number and preferred language. SMS requires consent.</p></div></div>
        {wardsQuery.isLoading ? <Skeleton className="h-12" /> : wardsQuery.isError ? <ErrorState text="Assigned wards could not load." retry={() => void wardsQuery.refetch()} /> : <form className="dashboard-form-grid" onSubmit={(event) => { event.preventDefault(); setFormError(''); registerMutation.mutate() }}>
          <label className="dashboard-field"><span>Phone number</span><input type="tel" inputMode="tel" autoComplete="tel" value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+254 7â€¦" required /></label>
          <label className="dashboard-field"><span>Ward</span><select value={selectedWard} onChange={(event) => setWard(event.target.value)} required><option value="">Select assigned ward</option>{availableWards.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
          <label className="dashboard-field"><span>First name Â· optional</span><input value={firstName} onChange={(event) => setFirstName(event.target.value)} /></label>
          <label className="dashboard-field"><span>Last name Â· optional</span><input value={lastName} onChange={(event) => setLastName(event.target.value)} /></label>
          <label className="dashboard-field"><span>Language</span><select value={language} onChange={(event) => setLanguage(event.target.value as Language)}><option value="en">English</option><option value="sw">Kiswahili</option><option value="guz">Ekegusii</option></select></label>
          <label className="dashboard-field"><span>Literacy support</span><select value={literacy} onChange={(event) => setLiteracy(event.target.value)}><option value="LOW">Needs spoken support</option><option value="MEDIUM">Some support</option><option value="HIGH">Comfortable reading</option></select></label>
          <label className="dashboard-check dashboard-field-wide"><input type="checkbox" checked={consentSms} onChange={(event) => setConsentSms(event.target.checked)} /><span>Farmer agrees to receive SMS messages on this number.</span></label>
          {formError && <p className="dashboard-form-error" role="alert">{formError}</p>}
          <Button type="submit" loading={registerMutation.isPending} disabled={!phone.trim() || !selectedWard}><Users size={16} /> Register farmer</Button>
        </form>}
      </Card>
      <Card className="role-panel warning-center-card"><div className="role-panel-heading"><div><p className="eyebrow">MANUAL SMS DELIVERY</p><h2>Warning center</h2><p>Preview recipients, verify consent and confirm each SMS batch from the protected warning screen.</p></div></div>
        <a className="warning-admin-link" href="/admin/warnings">Open manual warning center</a>
      </Card>
    </div>
    <section className="role-section"><div className="role-section-heading"><div><p className="eyebrow">FIELD VERIFICATION</p><h2>Pest report queue</h2><p>Open each photo to zoom. Confirm only after selecting the pest type.</p></div><span className="queue-count">{queueQuery.data?.length ?? 0} pending</span></div>
      {queueQuery.isLoading ? <div className="queue-grid">{[1, 2].map((value) => <Skeleton className="queue-skeleton" key={value} />)}</div> : queueQuery.isError ? <ErrorState text="The pest queue could not load." retry={() => void queueQuery.refetch()} /> : queueQuery.data?.length ? <div className="queue-grid">{queueQuery.data.map((report) => {
        const crop = report.crop ? `Crop #${report.crop}` : 'Crop not recorded'
        return <Card className="verification-card" key={report.id}>
          <button className="verification-photo-button" onClick={() => setActivePhoto(report.photo)} aria-label="Zoom pest report photo"><img src={report.photo} alt={`Farmer crop report ${report.id}`} loading="lazy" /><span><Eye size={16} /> Zoom photo</span></button>
          <div className="verification-content"><div className="verification-meta"><span><MapPin size={14} /> Ward #{report.ward}</span><time>{new Date(report.created_at).toLocaleDateString()}</time></div><h3>{crop}</h3>
            <p>{report.description || report.symptoms || 'No description supplied.'}</p>
            <label className="dashboard-field"><span>Verified pest</span><select value={verifyChoices[report.id] ?? ''} onChange={(event) => setVerifyChoices((current) => ({ ...current, [report.id]: event.target.value }))}><option value="">Select pest</option>{pestChoices.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
            <label className="dashboard-field"><span>Note to farmer / reason</span><textarea rows={2} value={verifyNotes[report.id] ?? ''} onChange={(event) => setVerifyNotes((current) => ({ ...current, [report.id]: event.target.value }))} placeholder="Optional confirmation details; required for more info" /></label>
            <div className="verification-actions"><button disabled={verifyMutation.isPending || !verifyChoices[report.id]} onClick={() => verifyMutation.mutate({ id: report.id, decision: 'CONFIRM' })}><Check size={15} /> Confirm</button><button disabled={verifyMutation.isPending} onClick={() => verifyMutation.mutate({ id: report.id, decision: 'REJECT' })}><EyeOff size={15} /> Reject</button><button disabled={verifyMutation.isPending || !(verifyNotes[report.id] ?? '').trim()} onClick={() => verifyMutation.mutate({ id: report.id, decision: 'NEEDS_INFO' })}><MessageSquareText size={15} /> Ask for info</button></div>
          </div>
        </Card>
      })}</div> : <Card className="dashboard-empty"><EmptyState icon={<BadgeCheck size={27} />} title="The queue is clear" description="New farmer reports will appear here for verification." /></Card>}
    </section>
    <section className="role-section"><div className="role-section-heading"><div><p className="eyebrow">ASK AN OFFICER</p><h2>Farmer questions</h2><p>Send replies in the farmerâ€™s chosen language. Answers are saved to the searchable FAQ.</p></div></div>
      {questionsQuery.isLoading ? <Skeleton className="queue-skeleton" /> : questionsQuery.isError ? <ErrorState text="The question queue could not load." retry={() => void questionsQuery.refetch()} /> : questionsQuery.data?.length ? <div className="question-list">{questionsQuery.data.map((question) => {
        const farmer = farmerProfiles.find((item) => item.id === question.farmer)
        const farmerUser = farmer ? userById.get(farmer.user) : undefined
        return <Card className="question-card" key={question.id}><div className="question-heading"><span className="question-icon"><MessageSquareText size={18} /></span><div><strong>{farmerUser ? `${farmerUser.first_name} ${farmerUser.last_name}`.trim() || farmerUser.phone : `Farmer #${question.farmer}`}</strong><span>Ward #{question.ward} Â· {new Date(question.created_at).toLocaleDateString()}</span></div></div>{question.question && <p className="farmer-question-text">{question.question}</p>}{question.voice_note && <audio controls preload="none" src={question.voice_note}><Headphones size={14} /> Voice question</audio>}
          <form className="dashboard-form-grid" onSubmit={(event) => { event.preventDefault(); const text = answer[question.id]?.trim(); if (text) answerMutation.mutate({ id: question.id, text }) }}><label className="dashboard-field dashboard-field-wide"><span>Reply</span><textarea rows={3} value={answer[question.id] ?? ''} onChange={(event) => setAnswer((current) => ({ ...current, [question.id]: event.target.value }))} required /></label><label className="dashboard-field"><span>Answer language</span><select value={answerLanguage} onChange={(event) => setAnswerLanguage(event.target.value as Language)}><option value="en">English</option><option value="sw">Kiswahili</option><option value="guz">Ekegusii</option></select></label><div className="dashboard-form-end"><Button type="submit" loading={answerMutation.isPending} disabled={!(answer[question.id] ?? '').trim()}><Send size={15} /> Reply & publish FAQ</Button></div></form>
        </Card>
      })}</div> : <Card className="dashboard-empty"><EmptyState icon={<MessageSquareText size={26} />} title="No open questions" description="Farmer questions for your wards will appear here." /></Card>}
    </section>
    <section className="role-section"><div className="role-section-heading"><div><p className="eyebrow">OUTREACH FOLLOW-UP</p><h2>Farmers not reached</h2><p>No delivered alert was recorded in the last 30 days. Follow up using their phone number.</p></div><span className="queue-count">{unreachable.length} farmers</span></div>
      {farmersQuery.isLoading || usersQuery.isLoading || alertsQuery.isLoading || deliveriesQuery.isLoading ? <Skeleton className="h-20" /> : farmersQuery.isError || usersQuery.isError || alertsQuery.isError || deliveriesQuery.isError ? <ErrorState text="Outreach records could not all be loaded." retry={() => { void farmersQuery.refetch(); void usersQuery.refetch(); void alertsQuery.refetch(); void deliveriesQuery.refetch() }} /> : <div className="unreached-table-wrap"><table className="dashboard-table"><thead><tr><th>Farmer</th><th>Ward</th><th>Phone</th><th>Channel</th><th>Last delivered</th></tr></thead><tbody>{unreachable.map((farmer) => {
        const linkedUser = userById.get(farmer.user)
        const latestDelivery = (deliveriesQuery.data ?? []).filter((delivery) => {
          const alert = alertsQuery.data?.find((item) => item.id === delivery.alert)
          return alert?.farmer === farmer.id && delivery.delivered
        }).sort((a, b) => (b.sent_at ?? '').localeCompare(a.sent_at ?? ''))[0]
        const lastSent = latestDelivery?.sent_at
        return <tr key={farmer.id}><td>{linkedUser ? `${linkedUser.first_name} ${linkedUser.last_name}`.trim() || 'Farmer' : `Farmer #${farmer.id}`}</td><td>{availableWards.find((item) => item.id === farmer.ward)?.name ?? `Ward #${farmer.ward}`}</td><td><a href={linkedUser?.phone ? `tel:${linkedUser.phone}` : undefined}>{linkedUser?.phone ?? 'No phone listed'}</a></td><td>{linkedUser?.consent_sms ? 'SMS consented' : 'No SMS consent'}</td><td>{lastSent ? new Date(lastSent).toLocaleDateString() : 'No delivery on record'}</td></tr>
      })}</tbody></table>{unreachable.length === 0 && <p className="table-empty-note">Every farmer has a delivered alert recorded in the last 30 days.</p>}{unreadablePhoneCount > 0 && <p className="table-empty-note">{unreadablePhoneCount} farmer records need a phone number check.</p>}</div>}
    </section>
    {activePhoto && <PhotoDialog src={activePhoto} onClose={() => setActivePhoto('')} />}
  </div>
}

function downloadCsv(filename: string, rows: (string | number)[][]) {
  const quote = (value: string | number) => {
    const text = String(value)
    const safeText = /^[\t\r ]*[=+\-@]/.test(text) ? `'${text}` : text
    return `"${safeText.replace(/"/g, '""')}"`
  }
  const contents = rows.map((row) => row.map(quote).join(',')).join('\r\n')
  const blob = new Blob([`\uFEFF${contents}`], { type: 'text/csv;charset=utf-8' })
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(href)
}

function CountyAdminDashboard() {
  const { user } = useAuth()
  const [showOutbreaks, setShowOutbreaks] = useState(true)
  const [showErosion, setShowErosion] = useState(true)
  const summaryQuery = useQuery({ queryKey: ['county-summary'], queryFn: async () => (await api.get('/analytics/summary/')).data as { farmers: number; farms: number; open_alerts: number; pending_pest_reports: number } })
  const wardsQuery = useApiList<Ward>('county-wards', '/wards/')
  const farmsQuery = useApiList<Farm>('county-farms', '/farms/')
  const farmersQuery = useApiList<Farmer>('county-farmers', '/farmers/')
  const alertsQuery = useApiList<Alert>('county-alerts', '/alerts/')
  const deliveriesQuery = useApiList<Delivery>('county-deliveries', '/alert-deliveries/')
  const rulesQuery = useApiList<Rule>('county-rules', '/rules/')
  const reportsQuery = useApiList<PestReport>('county-pest-reports', '/pest-reports/')
  const pricesQuery = useApiList<MarketPrice>('county-market-prices', '/market-prices/')
  const outbreaksQuery = useQuery({ queryKey: ['county-outbreak-map'], queryFn: async () => (await api.get<GeoJSONOutbreaks>('/pests/outbreaks/')).data })

  if (!user || (user.role !== 'ADMIN' && user.role !== 'OFFICER')) return <Navigate to="/app" replace />
  const allErrors = [summaryQuery.isError, wardsQuery.isError, farmsQuery.isError, farmersQuery.isError, alertsQuery.isError, deliveriesQuery.isError, rulesQuery.isError, reportsQuery.isError, pricesQuery.isError, outbreaksQuery.isError].some(Boolean)
  const isLoading = [summaryQuery.isLoading, wardsQuery.isLoading, farmsQuery.isLoading, farmersQuery.isLoading, alertsQuery.isLoading, deliveriesQuery.isLoading, rulesQuery.isLoading, reportsQuery.isLoading, pricesQuery.isLoading, outbreaksQuery.isLoading].some(Boolean)
  const wards = wardsQuery.data ?? []
  const farmers = farmersQuery.data ?? []
  const alerts = alertsQuery.data ?? []
  const deliveries = deliveriesQuery.data ?? []
  const rules = rulesQuery.data ?? []
  const reports = reportsQuery.data ?? []
  const prices = pricesQuery.data ?? []
  const ruleById = new Map(rules.map((rule) => [rule.id, rule]))
  const deliveriesByAlert = new Map<number, Delivery[]>()
  deliveries.forEach((delivery) => deliveriesByAlert.set(delivery.alert, [...(deliveriesByAlert.get(delivery.alert) ?? []), delivery]))
  const feedback = deliveries.filter((delivery) => delivery.feedback)
  const helpfulRate = feedback.length ? Math.round(feedback.filter((item) => item.feedback === 'HELPFUL').length / feedback.length * 100) : null
  const reachedWardIds = new Set(alerts.filter((alert) => deliveriesByAlert.get(alert.id)?.some((delivery) => delivery.delivered)).map((alert) => farmers.find((farmer) => farmer.id === alert.farmer)?.ward).filter((id): id is number => typeof id === 'number'))
  const currentMonth = new Date()
  const firstDayMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1)
  const monthReports = reports.filter((report) => report.status === 'CONFIRMED' && new Date(report.created_at) >= firstDayMonth)
  const pestCounts = new Map<string, number>()
  monthReports.forEach((report) => { const name = report.pest_name || 'Unspecified'; pestCounts.set(name, (pestCounts.get(name) ?? 0) + 1) })
  const topPests = [...pestCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5)
  const byProblem = new Map<string, number>()
  alerts.forEach((alert) => { const tag = alert.rule ? ruleById.get(alert.rule)?.problem_tag ?? 'Other' : 'Broadcast'; byProblem.set(tag, (byProblem.get(tag) ?? 0) + 1) })
  const problemRows = [...byProblem.entries()].map(([problem, total]) => ({ problem: problem.replace(/_/g, ' '), alerts: total })).sort((a, b) => b.alerts - a.alerts)
  const ruleRows = rules.map((rule) => {
    const ruleAlerts = alerts.filter((alert) => alert.rule === rule.id)
    const ruleDeliveries = ruleAlerts.flatMap((alert) => deliveriesByAlert.get(alert.id) ?? [])
    const voted = ruleDeliveries.filter((delivery) => delivery.feedback)
    const helpful = voted.filter((delivery) => delivery.feedback === 'HELPFUL').length
    return { ...rule, alertCount: ruleAlerts.length, sentCount: ruleDeliveries.filter((delivery) => delivery.delivered).length, helpfulRate: voted.length ? Math.round(helpful / voted.length * 100) : null, notRelevant: voted.length - helpful }
  }).sort((a, b) => b.alertCount - a.alertCount)
  const marketByDate = new Map<string, Map<string, { total: number; count: number }>>()
  const marketTotals = new Map<string, number>()
  prices.forEach((price) => {
    const name = typeof price.crop === 'object' ? price.crop.name : `Crop ${price.crop}`
    marketTotals.set(name, (marketTotals.get(name) ?? 0) + 1)
  })
  const topMarketCrops = [...marketTotals.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4).map(([name]) => name)
  prices.forEach((price) => {
    const name = typeof price.crop === 'object' ? price.crop.name : `Crop ${price.crop}`
    if (!topMarketCrops.includes(name)) return
    const point = marketByDate.get(price.date) ?? new Map<string, { total: number; count: number }>()
    const current = point.get(name) ?? { total: 0, count: 0 }
    point.set(name, { total: current.total + Number(price.price_per_kg), count: current.count + 1 })
    marketByDate.set(price.date, point)
  })
  const marketSeries: PriceSeriesPoint[] = [...marketByDate.entries()].sort(([a], [b]) => a.localeCompare(b)).slice(-30).map(([date, crops]) => ({
    date: date.slice(5),
    ...Object.fromEntries([...crops.entries()].map(([name, value]) => [name, value.total / value.count])),
  }))
  const mapFarms = (farmsQuery.data ?? []).filter((farm) => Number.isFinite(farm.lat) && Number.isFinite(farm.lng)).map((farm) => ({
    id: farm.id, lat: farm.lat, lng: farm.lng, label: farm.name, slope: farm.slope_class,
  }))
  const confirmedCount = reports.filter((report) => ['CONFIRMED', 'REJECTED'].includes(report.status)).length
  const csvRows: (string | number)[][] = [
    ['Metric', 'Value'],
    ['Farmers registered', summaryQuery.data?.farmers ?? farmers.length],
    ['Wards reached', reachedWardIds.size],
    ['Alerts delivered', deliveries.filter((delivery) => delivery.delivered).length],
    ['Helpful rate (%)', helpfulRate ?? 'No feedback'],
    ['Pest reports verified', confirmedCount],
    [],
    ['Alert problem', 'Alert count'],
    ...problemRows.map((row) => [row.problem, row.alerts]),
    [],
    ['Top pest this month', 'Confirmed reports'],
    ...topPests.map(([pest, count]) => [pest, count]),
    [],
    ['Market price date', 'Crop', 'Average price KES/kg'],
    ...marketSeries.flatMap((point) => topMarketCrops.flatMap((crop) => typeof point[crop] === 'number' ? [[point.date, crop, point[crop] as number]] : [])),
    [],
    ['Rule', 'Problem', 'Severity', 'Active', 'Alerts', 'Delivered', 'Helpful rate (%)', 'Not relevant votes'],
    ...ruleRows.map((row) => [row.code, row.problem_tag, row.severity, row.active ? 'Yes' : 'No', row.alertCount, row.sentCount, row.helpfulRate ?? 'No votes', row.notRelevant]),
  ]

  return <div className="role-dashboard county-admin-dashboard">
    <Header eyebrow="COUNTY AGRICULTURE Â· KISII" title="County dashboard" description="A county-wide view of farmer reach, local signals, prices and rule performance." icon={Activity} />
    <div className="dashboard-actions"><span className="sample-label">Operational metrics Â· data may update with report delays</span><a className="warning-admin-link" href="/admin/warnings">Manual warning center</a><Button variant="secondary" onClick={() => downloadCsv(`shamba-kisii-dashboard-${new Date().toISOString().slice(0, 10)}.csv`, csvRows)}><Download size={16} /> Export CSV</Button></div>
    {allErrors && <ErrorState text="Some dashboard data did not load. Available panels are still shown; retry failed panels individually." retry={() => { void summaryQuery.refetch(); void wardsQuery.refetch(); void farmsQuery.refetch(); void farmersQuery.refetch(); void alertsQuery.refetch(); void deliveriesQuery.refetch(); void rulesQuery.refetch(); void reportsQuery.refetch(); void pricesQuery.refetch(); void outbreaksQuery.refetch() }} />}
    <div className="role-metric-grid role-metric-grid-5">
      <Metric label="Farmers registered" value={summaryQuery.data?.farmers ?? 'â€”'} note={`${summaryQuery.data?.farms ?? 0} plots recorded`} icon={Users} />
      <Metric label="Wards reached" value={wards.length ? `${reachedWardIds.size}/${wards.length}` : 'â€”'} note={`${reachedWardIds.size} wards had delivered alerts`} icon={MapPin} />
      <Metric label="Alerts sent" value={deliveries.filter((delivery) => delivery.delivered).length} note={`${alerts.length} alerts created`} icon={Send} />
      <Metric label="Helpful rate" value={helpfulRate === null ? 'â€”' : `${helpfulRate}%`} note={`${feedback.length} feedback votes`} icon={BadgeCheck} />
      <Metric label="Reports verified" value={confirmedCount} note={`${reports.filter((report) => report.status === 'PENDING').length} awaiting review`} icon={FileCheck2} />
    </div>
    <section className="role-section county-map-section"><div className="role-section-heading"><div><p className="eyebrow">MAP Â· KISII COUNTY</p><h2>Outbreaks and erosion screening</h2><p>The erosion overlay shows recorded farm slope classes as a screening layer, not a measured erosion diagnosis.</p></div></div>
      <Card className="county-map-card"><div className="county-map-controls"><label><input type="checkbox" checked={showOutbreaks} onChange={(event) => setShowOutbreaks(event.target.checked)} /><span className="legend-dot legend-outbreak" /> Confirmed outbreaks</label><label><input type="checkbox" checked={showErosion} onChange={(event) => setShowErosion(event.target.checked)} /><span className="legend-dot legend-erosion" /> Farm slope screen</label></div>
        {outbreaksQuery.isLoading || farmsQuery.isLoading ? <Skeleton className="county-map-skeleton" /> : outbreaksQuery.isError ? <ErrorState text="Outbreak layer could not load." retry={() => void outbreaksQuery.refetch()} /> : <Suspense fallback={<Skeleton className="county-map-skeleton" />}><CountyMap farms={mapFarms} outbreaks={outbreaksQuery.data} showErosion={showErosion} showOutbreaks={showOutbreaks} /></Suspense>}
        <div className="county-map-legend"><span><i className="legend-dot legend-flat" /> Flat</span><span><i className="legend-dot legend-gentle" /> Gentle</span><span><i className="legend-dot legend-steep" /> Steep</span><small>{mapFarms.length} mapped farm plots</small></div>
      </Card>
    </section>
    <div className="admin-analytics-grid">
      <Card className="analytics-panel"><div className="role-panel-heading"><div><p className="eyebrow">ALERT MIX</p><h2>Alerts by problem</h2></div></div>
        {isLoading ? <Skeleton className="chart-skeleton" /> : problemRows.length ? <ResponsiveContainer width="100%" height={280}><BarChart data={problemRows} margin={{ top: 8, right: 12, bottom: 34, left: -20 }}><CartesianGrid stroke="#e9ece5" vertical={false} /><XAxis dataKey="problem" angle={-25} textAnchor="end" interval={0} height={60} tick={{ fontSize: 10, fill: '#66695f' }} /><YAxis allowDecimals={false} tick={{ fontSize: 10, fill: '#777a70' }} /><Tooltip /><Bar dataKey="alerts" name="Alerts" radius={[6, 6, 0, 0]}>{problemRows.map((row, index) => <Cell key={row.problem} fill={palette[index % palette.length]} />)}</Bar></BarChart></ResponsiveContainer> : <EmptyState icon={<AlertTriangle size={25} />} title="No alert data" description="Problem categories appear when rules generate alerts." />}
      </Card>
      <Card className="analytics-panel"><div className="role-panel-heading"><div><p className="eyebrow">VERIFIED THIS MONTH</p><h2>Top pests</h2></div></div>
        {isLoading ? <Skeleton className="chart-skeleton" /> : topPests.length ? <div className="top-pests-chart"><ResponsiveContainer width="100%" height={240}><PieChart><Pie data={topPests.map(([name, count]) => ({ name: name.replace(/_/g, ' '), reports: count }))} dataKey="reports" nameKey="name" innerRadius={56} outerRadius={88} paddingAngle={3}>{topPests.map(([name], index) => <Cell key={name} fill={palette[index % palette.length]} />)}</Pie><Tooltip /><Legend /></PieChart></ResponsiveContainer><div className="top-pest-list">{topPests.map(([name, count], index) => <div key={name}><i style={{ backgroundColor: palette[index % palette.length] }} /><span>{name.replace(/_/g, ' ')}</span><strong>{count}</strong></div>)}</div></div> : <EmptyState icon={<Bug size={25} />} title="No verified pest reports" description="Confirmed pest types will be summarized here for this month." />}
      </Card>
      <Card className="analytics-panel admin-wide-panel"><div className="role-panel-heading"><div><p className="eyebrow">LOCAL MARKET SIGNALS</p><h2>Price trends Â· sample data marked</h2></div><span className="sample-label">{prices.some((price) => price.is_sample_data) ? 'INCLUDES SAMPLE DATA' : 'RECORDED PRICES'}</span></div>
        {isLoading ? <Skeleton className="chart-skeleton" /> : marketSeries.length ? <ResponsiveContainer width="100%" height={300}><LineChart data={marketSeries} margin={{ top: 8, right: 16, bottom: 4, left: -15 }}><CartesianGrid stroke="#e9ece5" strokeDasharray="3 3" /><XAxis dataKey="date" tick={{ fontSize: 10, fill: '#777a70' }} /><YAxis tick={{ fontSize: 10, fill: '#777a70' }} /><Tooltip formatter={(value) => [`KES ${value}/kg`, 'Average']} /><Legend />{topMarketCrops.map((crop, index) => <Line key={crop} type="monotone" dataKey={crop} stroke={palette[index % palette.length]} strokeWidth={2} dot={false} connectNulls />)}</LineChart></ResponsiveContainer> : <EmptyState icon={<Activity size={25} />} title="No price trend available" description="Recorded prices will appear after officers add market observations." />}
      </Card>
    </div>
    <section className="role-section"><div className="role-section-heading"><div><p className="eyebrow">RULE FEEDBACK</p><h2>Alert rule performance</h2><p>Helpful rate uses only delivery records with an explicit feedback vote.</p></div></div>
      <div className="rule-table-wrap"><table className="dashboard-table rule-performance-table"><thead><tr><th>Rule</th><th>Problem</th><th>Severity</th><th>State</th><th>Alerts</th><th>Delivered</th><th>Helpful</th><th>Not relevant</th></tr></thead><tbody>{ruleRows.map((rule) => <tr key={rule.id}><td><strong>{rule.code}</strong></td><td>{rule.problem_tag}</td><td><span className={`rule-severity rule-severity-${rule.severity.toLowerCase()}`}>{rule.severity}</span></td><td>{rule.active ? 'Active' : 'Paused'}</td><td>{rule.alertCount}</td><td>{rule.sentCount}</td><td>{rule.helpfulRate === null ? 'â€”' : `${rule.helpfulRate}%`}</td><td>{rule.notRelevant}</td></tr>)}</tbody></table>{!ruleRows.length && <p className="table-empty-note">No rules have been configured yet.</p>}</div>
    </section>
    {wardsQuery.data && <p className="dashboard-data-note">Coverage counts wards with at least one delivered alert in the available records. Alerts sent counts successful deliveries; pending and failed sends are excluded.</p>}
  </div>
}

export function RoleDashboardPage() {
  const { user } = useAuth()
  if (user?.role === 'OFFICER') return <OfficerDashboard />
  if (user?.role === 'ADMIN') return <CountyAdminDashboard />
  return <Navigate to="/login" replace />
}
