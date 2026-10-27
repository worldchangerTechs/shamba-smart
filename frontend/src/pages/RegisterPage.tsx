import { useState, type FocusEvent, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import type { FarmerRegistration } from '../auth/AuthProvider'
import { KENYAN_PHONE_ERROR, normalizeKenyanPhone } from '../auth/phone'
import { useAuth } from '../auth/AuthProvider'
import { AuthLayout, AuthModal, AuthNotice, AuthDivider } from '../components/auth/AuthLayout'
import { api } from '../lib/api'
import { getList } from '../types'
import type { ApiList } from '../types'
import '../components/auth/auth.css'

type Ward = { id: number; name: string; sub_county: string }
type Crop = { id: number; name: string }
type RegisterField = 'full_name' | 'phone' | 'ward' | 'crop' | 'password' | 'password_confirm' | 'consent_sms'
type FormValues = Pick<FarmerRegistration, 'full_name' | 'phone' | 'password' | 'password_confirm'> & {
  ward: string
  crop: string
  consent_sms: boolean
}

const initialValues: FormValues = {
  full_name: '',
  phone: '',
  ward: '',
  crop: '',
  password: '',
  password_confirm: '',
  consent_sms: false,
}

const formFields: RegisterField[] = ['full_name', 'phone', 'ward', 'crop', 'password', 'password_confirm', 'consent_sms']

function apiErrors(error: unknown) {
  const fieldErrors: Partial<Record<RegisterField, string>> = {}
  let notice = ''
  if (!error || typeof error !== 'object' || !('response' in error)) {
    return { fieldErrors, notice: error instanceof Error ? error.message : 'We could not create your account. Try again.' }
  }
  const data = (error as { response?: { data?: Record<string, unknown> } }).response?.data
  if (!data) return { fieldErrors, notice: 'We could not reach the service. Check your connection and try again.' }
  for (const field of formFields) {
    const value = data[field]
    if (Array.isArray(value) && typeof value[0] === 'string') fieldErrors[field] = value[0]
  }
  const detail = data.detail
  if (typeof detail === 'string') notice = detail
  else if (Array.isArray(data.non_field_errors) && typeof data.non_field_errors[0] === 'string') notice = data.non_field_errors[0]
  if (!notice && !Object.keys(fieldErrors).length) notice = 'We could not create your account. Check your details and try again.'
  return { fieldErrors, notice }
}

function fieldMessage(field: RegisterField, values: FormValues) {
  if (field === 'full_name' && !values.full_name.trim()) return 'Enter your full name.'
  if (field === 'phone' && !normalizeKenyanPhone(values.phone)) return KENYAN_PHONE_ERROR
  if (field === 'ward' && !values.ward) return 'Choose your ward.'
  if (field === 'crop' && !values.crop) return 'Choose your main crop.'
  if (field === 'password' && values.password.length < 8) return 'Use at least 8 characters.'
  if (field === 'password_confirm' && values.password !== values.password_confirm) return 'Passwords do not match.'
  if (field === 'consent_sms' && !values.consent_sms) return 'Agree to receive farm warnings by SMS to continue.'
  return ''
}

function passwordStrength(password: string) {
  if (!password) return 0
  return Math.min(4, Number(password.length >= 8) + Number(/[a-z]/.test(password) && /[A-Z]/.test(password)) + Number(/\d/.test(password)) + Number(/[^A-Za-z0-9]/.test(password)))
}

export function RegisterPage() {
  const { user, registerFarmer } = useAuth()
  const navigate = useNavigate()
  const [values, setValues] = useState(initialValues)
  const [touched, setTouched] = useState<Partial<Record<RegisterField, boolean>>>({})
  const [serverErrors, setServerErrors] = useState<Partial<Record<RegisterField, string>>>({})
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [modal, setModal] = useState<'sms' | 'officer' | null>(null)
  const wardsQuery = useQuery({
    queryKey: ['public-wards'],
    queryFn: async () => getList<Ward>((await api.get<Ward[] | ApiList<Ward>>('/wards/')).data),
    staleTime: 5 * 60_000,
  })
  const cropsQuery = useQuery({
    queryKey: ['public-crops'],
    queryFn: async () => getList<Crop>((await api.get<Crop[] | ApiList<Crop>>('/crops/')).data),
    staleTime: 5 * 60_000,
  })

  if (user) return <Navigate to="/app" replace />

  const errorFor = (field: RegisterField) => serverErrors[field] || (touched[field] ? fieldMessage(field, values) : '')
  const update = (field: RegisterField, value: string | boolean) => {
    setValues((current) => ({ ...current, [field]: value }))
    setServerErrors((current) => ({ ...current, [field]: undefined }))
    setNotice('')
  }
  const blurField = (field: RegisterField, event?: FocusEvent<HTMLElement>) => {
    if (event?.relatedTarget instanceof HTMLElement && event.currentTarget.contains(event.relatedTarget)) return
    setTouched((current) => ({ ...current, [field]: true }))
  }
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setNotice('')
    setTouched(Object.fromEntries(formFields.map((field) => [field, true])))
    const errors = Object.fromEntries(formFields.map((field) => [field, fieldMessage(field, values)]).filter(([, message]) => message)) as Partial<Record<RegisterField, string>>
    if (Object.keys(errors).length) {
      setNotice('Please check the highlighted fields.')
      return
    }
    if (wardsQuery.isError || cropsQuery.isError || !wardsQuery.data?.length || !cropsQuery.data?.length) {
      setNotice('Ward and crop lists must load before you can sign up.')
      return
    }

    setLoading(true)
    setServerErrors({})
    try {
      const phone = normalizeKenyanPhone(values.phone)
      if (!phone) {
        setNotice(KENYAN_PHONE_ERROR)
        return
      }
      const registration: FarmerRegistration = {
        full_name: values.full_name.trim(),
        phone,
        ward: Number(values.ward),
        crop: Number(values.crop),
        password: values.password,
        password_confirm: values.password_confirm,
        consent_sms: true,
      }
      await registerFarmer(registration)
      navigate('/onboarding', { replace: true })
    } catch (error) {
      const result = apiErrors(error)
      setServerErrors(result.fieldErrors)
      setNotice(result.notice)
    } finally {
      setLoading(false)
    }
  }

  const strength = passwordStrength(values.password)
  const optionLoadError = wardsQuery.isError || cropsQuery.isError

  return (
    <AuthLayout variant="register">
      <div className="auth-panel-content">
        <h2 className="auth-panel-heading">Sign up</h2>
        <div className="auth-register-grid">
          <form className="auth-form" onSubmit={submit} noValidate>
            <div className="auth-fields-grid">
              <div className={`auth-field ${errorFor('full_name') ? 'auth-field-invalid' : ''}`} onBlur={(event) => blurField('full_name', event)}>
                <label className="auth-field-label" htmlFor="register-name">Full name</label>
                <input className="auth-field-input" id="register-name" autoComplete="name" value={values.full_name} onChange={(event) => update('full_name', event.target.value)} aria-invalid={Boolean(errorFor('full_name'))} aria-describedby={errorFor('full_name') ? 'register-name-error' : undefined} required />
                {errorFor('full_name') && <p className="auth-field-error" id="register-name-error">{errorFor('full_name')}</p>}
              </div>
              <div className={`auth-field ${errorFor('phone') ? 'auth-field-invalid' : ''}`} onBlur={(event) => blurField('phone', event)}>
                <label className="auth-field-label" htmlFor="register-phone">Phone number</label>
                <div className="auth-phone-control"><span className="auth-phone-prefix" aria-hidden="true">+254</span><input className="auth-field-input" id="register-phone" type="tel" inputMode="tel" autoComplete="tel-national" placeholder="712 345 678" value={values.phone} onChange={(event) => update('phone', event.target.value)} aria-invalid={Boolean(errorFor('phone'))} aria-describedby={errorFor('phone') ? 'register-phone-error' : undefined} required /></div>
                {errorFor('phone') && <p className="auth-field-error" id="register-phone-error">{errorFor('phone')}</p>}
              </div>
              <div className={`auth-field ${errorFor('ward') ? 'auth-field-invalid' : ''}`} onBlur={(event) => blurField('ward', event)}>
                <label className="auth-field-label" htmlFor="register-ward">Ward</label>
                <select className="auth-field-select" id="register-ward" value={values.ward} onChange={(event) => update('ward', event.target.value)} aria-invalid={Boolean(errorFor('ward'))} aria-describedby={errorFor('ward') ? 'register-ward-error' : undefined} required>
                  <option value="">{wardsQuery.isLoading ? 'Loading wards' : 'Choose a ward'}</option>
                  {(wardsQuery.data ?? []).map((ward) => <option value={ward.id} key={ward.id}>{ward.name}</option>)}
                </select>
                {errorFor('ward') && <p className="auth-field-error" id="register-ward-error">{errorFor('ward')}</p>}
              </div>
              <div className={`auth-field ${errorFor('crop') ? 'auth-field-invalid' : ''}`} onBlur={(event) => blurField('crop', event)}>
                <label className="auth-field-label" htmlFor="register-crop">Main crop</label>
                <select className="auth-field-select" id="register-crop" value={values.crop} onChange={(event) => update('crop', event.target.value)} aria-invalid={Boolean(errorFor('crop'))} aria-describedby={errorFor('crop') ? 'register-crop-error' : undefined} required>
                  <option value="">{cropsQuery.isLoading ? 'Loading crops' : 'Choose a crop'}</option>
                  {(cropsQuery.data ?? []).map((crop) => <option value={crop.id} key={crop.id}>{crop.name}</option>)}
                </select>
                {errorFor('crop') && <p className="auth-field-error" id="register-crop-error">{errorFor('crop')}</p>}
              </div>
              <div className={`auth-field ${errorFor('password') ? 'auth-field-invalid' : ''}`} onBlur={(event) => blurField('password', event)}>
                <label className="auth-field-label" htmlFor="register-password">Create password</label>
                <div className="auth-password-wrap">
                  <input className="auth-field-input" id="register-password" type={showPassword ? 'text' : 'password'} autoComplete="new-password" value={values.password} onChange={(event) => update('password', event.target.value)} aria-invalid={Boolean(errorFor('password'))} aria-describedby={errorFor('password') ? 'password-strength register-password-error' : 'password-strength'} required />
                  <button className="auth-text-toggle" type="button" onClick={() => setShowPassword((current) => !current)}>{showPassword ? 'Hide' : 'Show'}</button>
                </div>
                <div className="auth-strength" id="password-strength" role="meter" aria-label="Password strength" aria-valuemin={0} aria-valuemax={4} aria-valuenow={strength}>
                  {[0, 1, 2, 3].map((index) => <span className={`auth-strength-segment ${index < strength ? 'auth-strength-segment-filled' : ''}`} key={index} />)}
                </div>
                <p className="auth-strength-copy">{values.password.length < 8 ? 'Use at least 8 characters.' : strength < 3 ? 'Add a number or capital letter for a stronger password.' : 'Good password strength.'}</p>
                {errorFor('password') && <p className="auth-field-error" id="register-password-error">{errorFor('password')}</p>}
              </div>
              <div className={`auth-field ${errorFor('password_confirm') ? 'auth-field-invalid' : ''}`} onBlur={(event) => blurField('password_confirm', event)}>
                <label className="auth-field-label" htmlFor="register-password-confirm">Repeat password</label>
                <div className="auth-password-wrap">
                  <input className="auth-field-input" id="register-password-confirm" type={showPassword ? 'text' : 'password'} autoComplete="new-password" value={values.password_confirm} onChange={(event) => update('password_confirm', event.target.value)} aria-invalid={Boolean(errorFor('password_confirm'))} aria-describedby={errorFor('password_confirm') ? 'register-password-confirm-error' : undefined} required />
                  <button className="auth-text-toggle" type="button" onClick={() => setShowPassword((current) => !current)}>{showPassword ? 'Hide' : 'Show'}</button>
                </div>
                {errorFor('password_confirm') && <p className="auth-field-error" id="register-password-confirm-error">{errorFor('password_confirm')}</p>}
              </div>
            </div>
            <div className={`auth-checkbox-row ${errorFor('consent_sms') ? 'auth-field-invalid' : ''}`} onBlur={(event) => blurField('consent_sms', event)}>
              <input id="register-consent" type="checkbox" checked={values.consent_sms} onChange={(event) => update('consent_sms', event.target.checked)} aria-invalid={Boolean(errorFor('consent_sms'))} aria-describedby={errorFor('consent_sms') ? 'register-consent-error' : undefined} required />
              <div>
                <label htmlFor="register-consent">I agree to receive farm warnings by SMS.</label>
                <button className="auth-inline-link" type="button" onClick={() => setModal('sms')}>What we send and how to stop</button>
                {errorFor('consent_sms') && <p className="auth-field-error" id="register-consent-error">{errorFor('consent_sms')}</p>}
              </div>
            </div>
            {optionLoadError && <div className="auth-list-error" role="alert">
              <p>Ward or crop options could not load.</p>
              {wardsQuery.isError && <button type="button" onClick={() => void wardsQuery.refetch()}>Retry wards</button>}
              {cropsQuery.isError && <button type="button" onClick={() => void cropsQuery.refetch()}>Retry crops</button>}
            </div>}
            <AuthNotice>{notice}</AuthNotice>
            <button className="auth-submit" type="submit" disabled={loading || wardsQuery.isLoading || cropsQuery.isLoading || optionLoadError}>
              {loading ? <span className="auth-loading"><span className="auth-spinner" aria-hidden="true" />Creating account</span> : 'Sign up'}
            </button>
            <Link className="auth-alternate-link" to="/login">Already a member? Sign in here.</Link>
          </form>
          <aside className="auth-register-aside" aria-label="Other ways to get started">
            <AuthDivider />
            <div className="auth-side-options">
              <Link className="auth-chip" to="/simulator">Register by USSD</Link>
              <button className="auth-chip" type="button" onClick={() => setModal('officer')}>Ask an officer</button>
            </div>
          </aside>
        </div>
      </div>
      {modal === 'sms' && <AuthModal title="Farm warnings by SMS" onClose={() => setModal(null)}>
        <p>We send about three non-urgent farm messages a week. Urgent safety and weather alerts can arrive at any time.</p>
        <p>Reply STOP to opt out of SMS warnings. You can still use the app and other available channels.</p>
      </AuthModal>}
      {modal === 'officer' && <AuthModal title="Register with an officer" onClose={() => setModal(null)}>
        <p>An extension officer can create your farmer profile, choose your ward, and add your farm details with you.</p>
        <p>Visit your local agriculture office or ask your cooperative to connect you with an officer. You do not need a smartphone to receive basic-phone support.</p>
      </AuthModal>}
    </AuthLayout>
  )
}
