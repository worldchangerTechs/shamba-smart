import { useEffect, useMemo, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthProvider'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { Skeleton } from '../components/ui/Skeleton'
import { api } from '../lib/api'
import { getList } from '../types'
import type { ApiList } from '../types'
import './admin-warnings.css'

type Language = 'en' | 'sw' | 'guz'
type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
type TargetType = 'ward' | 'crop' | 'slope' | 'demo'
type Ward = { id: number; name: string }
type Crop = { id: number; name: string }
type Preview = {
  recipient_count: number
  skipped_count: number
  skipped: { phone: string; reason: string }[]
  message: string
  target_description: string
  provider: string
}
type Message = {
  id: number
  name: string
  phone: string
  status: 'QUEUED' | 'SENT' | 'DELIVERED' | 'FAILED'
  error: string
  updated_at: string
}
type Batch = {
  id: number
  provider: string
  total: number
  counts: Record<'queued' | 'sent' | 'delivered' | 'failed', number>
  messages: Message[]
  skipped: { phone: string; reason: string }[]
  provider_error?: string
}
type ProviderInfo = {
  provider: 'vendel' | 'simulator'
  base_url: string | null
  quota?: {
    sms_sent_this_month?: number
    max_sms_per_month?: number
    remaining?: number | null
  }
  error?: string
}
type AuditEntry = {
  id: number
  user: string
  template_code: string
  target_description: string
  count: number
  provider: string
  created_at: string
  batch_id: number
}

const templates: Record<string, { title: string; text: Record<Language, string> }> = {
  heavy_rain_steep: {
    title: 'Heavy rain on steep slopes',
    text: {
      en: 'Heavy rain is expected. Check drainage and protect soil on steep slopes.',
      sw: 'Mvua kubwa inatarajiwa. Kagua mifereji na ulinde udongo kwenye miteremko.',
      guz: 'Ekegusii text needs native-speaker review: heavy rain is expected; protect soil.',
    },
  },
  armyworm_nearby: {
    title: 'Fall armyworm confirmed nearby',
    text: {
      en: 'Fall armyworm is confirmed nearby. Check maize leaves and report new damage.',
      sw: 'Fall armyworm imethibitishwa karibu. Kagua majani ya mahindi na uripoti uharibifu.',
      guz: 'Ekegusii text needs native-speaker review: check maize for fall armyworm.',
    },
  },
  tomato_blight: {
    title: 'Tomato blight conditions',
    text: {
      en: 'Cool, wet weather may cause tomato blight. Check leaves and avoid wetting them.',
      sw: 'Baridi na unyevu vinaweza kusababisha blight ya nyanya. Kagua majani.',
      guz: 'Ekegusii text needs native-speaker review: inspect tomato leaves in cool wet weather.',
    },
  },
  dry_spell: {
    title: 'Dry spell',
    text: {
      en: 'Dry weather is expected. Mulch crops and water early if water is available.',
      sw: 'Hali kavu inatarajiwa. Weka matandazo na mwagilia mapema ikiwa maji yapo.',
      guz: 'Ekegusii text needs native-speaker review: mulch crops during the dry spell.',
    },
  },
  price_spike: {
    title: 'Market price increase',
    text: {
      en: 'Local crop prices have risen. Compare buyers and confirm prices before selling.',
      sw: 'Bei za mazao zimepanda. Linganisha wanunuzi na uthibitishe bei kabla ya kuuza.',
      guz: 'Ekegusii text needs native-speaker review: compare buyers before selling.',
    },
  },
  safe_reentry: {
    title: 'Safe re-entry after spraying',
    text: {
      en: 'Do not enter the sprayed field until the product re-entry time has passed.',
      sw: 'Usiingie shambani baada ya kunyunyiza hadi muda wa kusubiri upite.',
      guz: 'Ekegusii text needs native-speaker review: wait before entering a sprayed field.',
    },
  },
}

const deliveryEmptyIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M4 6.5h16v11H4z" />
    <path d="m4.5 7 7.5 5.5L19.5 7" />
  </svg>
)

function listData<T>(data: T[] | ApiList<T>) {
  return getList<T>(data)
}

function getErrorMessage(error: unknown) {
  if (typeof error === 'object' && error && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: string; error?: string } } }).response
    if (response?.data?.detail) return response.data.detail
    if (response?.data?.error) return response.data.error
  }
  return error instanceof Error ? error.message : 'The request could not be completed.'
}

export function AdminWarningsPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [templateCode, setTemplateCode] = useState('heavy_rain_steep')
  const [language, setLanguage] = useState<Language>('en')
  const [severity, setSeverity] = useState<Severity>('MEDIUM')
  const [targetType, setTargetType] = useState<TargetType>('ward')
  const [targetValue, setTargetValue] = useState('')
  const [message, setMessage] = useState(templates.heavy_rain_steep.text.en)
  const [dryRun, setDryRun] = useState(true)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [confirmation, setConfirmation] = useState('')
  const [batchId, setBatchId] = useState<number | null>(null)
  const [requestError, setRequestError] = useState('')

  const providerQuery = useQuery({
    queryKey: ['warning-provider'],
    queryFn: async () => (await api.get<ProviderInfo>('/admin/warnings/provider/')).data,
    refetchInterval: 30000,
  })
  const wardsQuery = useQuery({
    queryKey: ['warning-wards'],
    queryFn: async () => listData<Ward>((await api.get('/wards/')).data),
  })
  const cropsQuery = useQuery({
    queryKey: ['warning-crops'],
    queryFn: async () => listData<Crop>((await api.get('/crops/')).data),
  })
  const batchQuery = useQuery({
    queryKey: ['warning-batch', batchId],
    queryFn: async () => (await api.get<Batch>(`/admin/warnings/${batchId}/`)).data,
    enabled: batchId !== null,
    refetchInterval: batchId === null ? false : 2000,
  })
  const auditQuery = useQuery({
    queryKey: ['warning-audit'],
    queryFn: async () => (await api.get<AuditEntry[]>('/admin/warnings/audit/')).data,
  })
  const target = useMemo(() => ({
    type: targetType,
    ...(targetType !== 'demo' ? { value: targetValue ? Number(targetValue) || targetValue : '' } : {}),
  }), [targetType, targetValue])
  const payload = useMemo(() => ({
    template_code: templateCode,
    language,
    severity,
    target,
    message,
  }), [templateCode, language, severity, target, message])
  const providerName = providerQuery.data?.provider ?? 'vendel'
  const providerError = providerQuery.isError || Boolean(providerQuery.data?.error)
  const providerUnavailable = providerQuery.isLoading || providerError
  const canSend = Boolean(preview && preview.recipient_count > 0 && message.trim() && message.length <= 160)

  useEffect(() => {
    setMessage(templates[templateCode]?.text[language] ?? '')
    setPreview(null)
  }, [templateCode, language])

  const previewMutation = useMutation({
    mutationFn: async () => (await api.post<Preview>('/admin/warnings/preview/', payload)).data,
    onSuccess: (data) => {
      setPreview(data)
      setRequestError('')
    },
    onError: (error) => {
      setPreview(null)
      setRequestError(getErrorMessage(error))
    },
  })
  const sendMutation = useMutation({
    mutationFn: async () => (await api.post<Batch>('/admin/warnings/send/', payload)).data,
    onSuccess: (data) => {
      setBatchId(data.id)
      setConfirmOpen(false)
      setConfirmation('')
      setRequestError('')
      void queryClient.invalidateQueries({ queryKey: ['warning-audit'] })
    },
    onError: (error) => setRequestError(getErrorMessage(error)),
  })
  const retryMutation = useMutation({
    mutationFn: async () => api.post(`/admin/warnings/${batchId}/retry/`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['warning-batch', batchId] })
      setRequestError('')
    },
    onError: (error) => setRequestError(getErrorMessage(error)),
  })

  if (!user || user.role === 'FARMER') return <Navigate to="/app" replace />
  const selectedTemplate = templates[templateCode]
  const quota = providerQuery.data?.quota
  const quotaText = quota?.max_sms_per_month !== undefined
    ? `${Math.max(0, quota.max_sms_per_month - (quota.sms_sent_this_month ?? 0))} remaining this month`
    : providerName === 'simulator' ? 'No network quota' : 'Quota unavailable'

  return (
    <main className="warning-admin">
      <header className="warning-header">
        <div>
          <p className="warning-eyebrow">MANUAL WARNING DELIVERY</p>
          <h1>Send a farm warning</h1>
          <p>Warnings are drafts until an authorized officer or admin confirms a send.</p>
        </div>
        <a href="#warning-audit">View audit log</a>
      </header>

      <section className={`warning-provider ${providerName === 'simulator' ? 'warning-provider-simulator' : ''}`} aria-live="polite">
        <div>
          <strong>{providerQuery.isLoading ? 'Checking provider' : providerName === 'simulator' ? 'Simulator' : providerUnavailable ? 'Vendel unavailable' : 'Vendel live'}</strong>
          <span>{providerName === 'vendel' ? providerQuery.data?.base_url ?? 'https://app.vendel.cc' : 'Network-free local delivery'}</span>
          {providerUnavailable && <span className="warning-error">{providerQuery.data?.error ?? getErrorMessage(providerQuery.error)}</span>}
        </div>
        <span>{quotaText}</span>
      </section>

      <div className="warning-columns">
        <Card className="warning-form-card">
          <div className="warning-card-heading">
            <div>
              <p className="warning-eyebrow">COMPOSE</p>
              <h2>Warning details</h2>
            </div>
          </div>
          <div className="warning-fields">
            <label>
              <span>Template</span>
              <select value={templateCode} onChange={(event) => setTemplateCode(event.target.value)}>
                {Object.entries(templates).map(([code, value]) => <option key={code} value={code}>{value.title}</option>)}
              </select>
            </label>
            <label>
              <span>Language</span>
              <select value={language} onChange={(event) => setLanguage(event.target.value as Language)}>
                <option value="en">English</option>
                <option value="sw">Kiswahili</option>
                <option value="guz">Ekegusii (needs native-speaker review)</option>
              </select>
            </label>
            <label>
              <span>Severity</span>
              <select value={severity} onChange={(event) => { setSeverity(event.target.value as Severity); setPreview(null) }}>
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">Urgent</option>
                <option value="CRITICAL">Critical</option>
              </select>
            </label>
            <label>
              <span>Target group</span>
              <select value={targetType} onChange={(event) => { setTargetType(event.target.value as TargetType); setTargetValue(''); setPreview(null) }}>
                <option value="ward">Ward</option>
                <option value="crop">Crop</option>
                <option value="slope">Slope class</option>
                {user.role === 'ADMIN' && <option value="demo">Demo Group</option>}
              </select>
            </label>
            {targetType === 'ward' && (
              <label>
                <span>Ward</span>
                {wardsQuery.isLoading ? <Skeleton className="h-12" /> : wardsQuery.isError ? <span className="warning-error">Ward list could not load. <button type="button" onClick={() => void wardsQuery.refetch()}>Retry</button></span> : (
                  <select value={targetValue} onChange={(event) => { setTargetValue(event.target.value); setPreview(null) }}>
                    <option value="">Select a ward</option>
                    {(wardsQuery.data ?? []).map((ward) => <option key={ward.id} value={ward.id}>{ward.name}</option>)}
                  </select>
                )}
              </label>
            )}
            {targetType === 'crop' && (
              <label>
                <span>Crop</span>
                {cropsQuery.isLoading ? <Skeleton className="h-12" /> : cropsQuery.isError ? <span className="warning-error">Crop list could not load. <button type="button" onClick={() => void cropsQuery.refetch()}>Retry</button></span> : (
                  <select value={targetValue} onChange={(event) => { setTargetValue(event.target.value); setPreview(null) }}>
                    <option value="">Select a crop</option>
                    {(cropsQuery.data ?? []).map((crop) => <option key={crop.id} value={crop.id}>{crop.name}</option>)}
                  </select>
                )}
              </label>
            )}
            {targetType === 'slope' && (
              <label>
                <span>Slope class</span>
                <select value={targetValue} onChange={(event) => { setTargetValue(event.target.value); setPreview(null) }}>
                  <option value="">Select a slope class</option>
                  <option value="FLAT">Flat</option>
                  <option value="GENTLE">Gentle</option>
                  <option value="STEEP">Steep</option>
                </select>
              </label>
            )}
            {targetType === 'demo' && <p className="warning-demo-note">Uses only E.164 recipients listed in DEMO_RECIPIENTS.</p>}
            <label className="warning-message-field">
              <span>Message</span>
              <textarea rows={5} value={message} maxLength={161} onChange={(event) => { setMessage(event.target.value); setPreview(null) }} />
            </label>
          </div>
          <div className={`warning-counter ${message.length > 160 ? 'warning-counter-error' : ''}`}>{message.length}/160 characters</div>
          <div className="warning-form-actions">
            <label className="warning-switch">
              <input type="checkbox" checked={dryRun} onChange={(event) => setDryRun(event.target.checked)} />
              <span>Dry run</span>
            </label>
            <Button
              type="button"
              onClick={() => previewMutation.mutate()}
              loading={previewMutation.isPending}
              disabled={!message.trim() || message.length > 160 || (targetType !== 'demo' && !targetValue)}
            >
              Preview recipients
            </Button>
            <Button
              type="button"
              className="warning-send-button"
              disabled={!canSend || dryRun || providerUnavailable}
              onClick={() => { setConfirmation(''); setConfirmOpen(true) }}
            >
              Send warning
            </Button>
          </div>
          {providerError && <p className="warning-error" role="alert">Sending is disabled while Vendel is unreachable. Use the simulator only when real delivery is not required.</p>}
          {requestError && <p className="warning-error" role="alert">{requestError}</p>}
        </Card>

        <aside className="warning-preview-column">
          <Card className="warning-phone-card">
            <p className="warning-eyebrow">FARMER PHONE PREVIEW</p>
            <div className="warning-phone">
              <span className="warning-phone-brand">SHAMBA SMART 360</span>
              <p>{message || 'Your SMS preview will appear here.'}</p>
              <span>{message.length}/160</span>
            </div>
          </Card>
          <Card className="warning-recipients-card">
            <div className="warning-recipient-summary">
              <div><span>Recipients</span><strong>{preview?.recipient_count ?? '—'}</strong></div>
              <div><span>Skipped</span><strong>{preview?.skipped_count ?? '—'}</strong></div>
            </div>
            {previewMutation.isPending && <Skeleton className="h-10" />}
            {preview && (
              <details className="warning-skipped">
                <summary>Skipped recipients and reasons</summary>
                {preview.skipped.length ? <ul>{preview.skipped.map((item, index) => <li key={`${item.phone}-${index}`}>{item.phone || 'Recipient'}: {item.reason.replace(/_/g, ' ')}</li>)}</ul> : <p>No recipients were skipped.</p>}
              </details>
            )}
            {!preview && !previewMutation.isPending && <p className="warning-muted">Preview recipient eligibility before sending.</p>}
          </Card>
        </aside>
      </div>

      {batchId !== null && (
        <section className="warning-live-section">
          <div className="warning-section-heading">
            <div><p className="warning-eyebrow">LIVE DELIVERY STATUS</p><h2>Batch {batchId}</h2></div>
            {batchQuery.data && batchQuery.data.counts.failed > 0 && (
              <Button type="button" onClick={() => retryMutation.mutate()} loading={retryMutation.isPending}>Retry failed</Button>
            )}
          </div>
          {batchQuery.isLoading ? <Skeleton className="h-24" /> : batchQuery.isError ? (
            <div className="warning-error-box" role="alert"><p>{getErrorMessage(batchQuery.error)}</p><button type="button" onClick={() => void batchQuery.refetch()}>Retry status check</button></div>
          ) : batchQuery.data ? (
            <>
              <div className="warning-status-counts">
                {(['queued', 'sent', 'delivered', 'failed'] as const).map((key) => <div key={key}><span>{key}</span><strong>{batchQuery.data.counts[key]}</strong></div>)}
              </div>
              {batchQuery.data.provider_error && <p className="warning-error" role="alert">{batchQuery.data.provider_error}</p>}
              <div className="warning-table-wrap">
                <table>
                  <thead><tr><th>Recipient</th><th>Phone</th><th>Status</th><th>Updated</th><th>Error</th></tr></thead>
                  <tbody>{batchQuery.data.messages.map((item) => <tr key={item.id}><td>{item.name}</td><td>{item.phone}</td><td><span className={`warning-status warning-status-${item.status.toLowerCase()}`}>{item.status}</span></td><td>{new Date(item.updated_at).toLocaleTimeString()}</td><td>{item.error || '—'}</td></tr>)}</tbody>
                </table>
              </div>
              {batchQuery.data.skipped.length > 0 && <p className="warning-muted">This batch also recorded {batchQuery.data.skipped.length} skipped recipient(s).</p>}
            </>
          ) : <EmptyState icon={deliveryEmptyIcon} title="No delivery data" description="Batch statuses will appear here when available." />}
        </section>
      )}

      <section className="warning-live-section" id="warning-audit">
        <div className="warning-section-heading"><div><p className="warning-eyebrow">AUDIT LOG</p><h2>Recent manual sends</h2></div></div>
        {auditQuery.isLoading ? <Skeleton className="h-24" /> : auditQuery.isError ? <div className="warning-error-box" role="alert"><p>{getErrorMessage(auditQuery.error)}</p><button type="button" onClick={() => void auditQuery.refetch()}>Retry</button></div> : auditQuery.data?.length ? (
          <div className="warning-table-wrap">
            <table><thead><tr><th>Time</th><th>Sender</th><th>Template</th><th>Target</th><th>Count</th><th>Provider</th></tr></thead>
              <tbody>{auditQuery.data.map((item) => <tr key={item.id}><td>{new Date(item.created_at).toLocaleString()}</td><td>{item.user}</td><td>{item.template_code}</td><td>{item.target_description}</td><td>{item.count}</td><td>{item.provider}</td></tr>)}</tbody>
            </table>
          </div>
        ) : <EmptyState icon={deliveryEmptyIcon} title="No warnings have been sent" description="Every confirmed send will be recorded here." />}
      </section>

      {confirmOpen && (
        <div className="warning-dialog-backdrop" role="presentation">
          <section className="warning-confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="warning-confirm-title">
            <h2 id="warning-confirm-title">Confirm SMS send</h2>
            <p><strong>Template:</strong> {selectedTemplate.title}</p>
            <p><strong>Target:</strong> {preview?.target_description}</p>
            <p><strong>Recipients:</strong> {preview?.recipient_count}; skipped: {preview?.skipped_count}</p>
            <p><strong>Provider:</strong> {providerName}</p>
            <label><span>Type SEND to confirm</span><input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoFocus /></label>
            {requestError && <p className="warning-error" role="alert">{requestError}</p>}
            <div className="warning-dialog-actions">
              <button type="button" onClick={() => setConfirmOpen(false)}>Cancel</button>
              <Button type="button" className="warning-send-button" loading={sendMutation.isPending} disabled={confirmation !== 'SEND' || providerUnavailable} onClick={() => sendMutation.mutate()}>Confirm send</Button>
            </div>
          </section>
        </div>
      )}
    </main>
  )
}
