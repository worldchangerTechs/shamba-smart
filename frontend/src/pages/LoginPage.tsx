import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { AuthLayout, AuthNotice } from '../components/auth/AuthLayout'
import { KENYAN_PHONE_ERROR, normalizeKenyanPhone } from '../auth/phone'
import '../components/auth/auth.css'

function responseErrors(error: unknown) {
  let phoneError = ''
  let passwordError = ''
  let notice = 'We could not sign you in. Check your details and try again.'
  if (error && typeof error === 'object' && 'response' in error) {
    const response = (error as { response?: { data?: Record<string, unknown> } }).response
    const data = response?.data
    const detail = data?.detail
    const phone = data?.phone
    const password = data?.password
    if (typeof detail === 'string') notice = detail
    if (Array.isArray(phone) && typeof phone[0] === 'string') phoneError = phone[0]
    if (typeof phone === 'string') phoneError = phone
    if (Array.isArray(password) && typeof password[0] === 'string') passwordError = password[0]
    if (typeof password === 'string') passwordError = password
  }
  return { phoneError, passwordError, notice }
}

export function LoginPage() {
  const { user, signIn } = useAuth()
  const navigate = useNavigate()
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [phoneError, setPhoneError] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(false)

  if (user) return <Navigate to="/app" replace />

  const validatePhone = () => {
    const error = normalizeKenyanPhone(phone) ? '' : KENYAN_PHONE_ERROR
    setPhoneError(error)
    return !error
  }

  const validatePassword = () => {
    const error = password ? '' : 'Enter your password.'
    setPasswordError(error)
    return !error
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setNotice('')
    if (!validatePhone() || !validatePassword()) return
    setLoading(true)
    try {
      await signIn(phone, password)
      navigate('/app', { replace: true })
    } catch (error) {
      const errors = responseErrors(error)
      setPhoneError(errors.phoneError)
      setPasswordError(errors.passwordError)
      setNotice(errors.notice)
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout variant="login">
      <div className="auth-panel-content">
        <h2 className="auth-panel-heading">Sign in</h2>
        <form className="auth-form" onSubmit={submit} noValidate>
          <div className={`auth-field ${phoneError ? 'auth-field-invalid' : ''}`}>
            <label className="auth-field-label" htmlFor="login-phone">Phone number</label>
            <div className="auth-phone-control">
              <span className="auth-phone-prefix" aria-hidden="true">+254</span>
              <input
                className="auth-field-input"
                id="login-phone"
                type="tel"
                inputMode="tel"
                autoComplete="tel-national"
                placeholder="712 345 678"
                value={phone}
                onChange={(event) => { setPhone(event.target.value); setPhoneError(''); setNotice('') }}
                onBlur={validatePhone}
                aria-invalid={Boolean(phoneError)}
                aria-describedby={phoneError ? 'login-phone-error' : undefined}
                required
              />
            </div>
            {phoneError && <p className="auth-field-error" id="login-phone-error">{phoneError}</p>}
          </div>
          <div className={`auth-field ${passwordError ? 'auth-field-invalid' : ''}`}>
            <label className="auth-field-label" htmlFor="login-password">Password</label>
            <input
              className="auth-field-input"
              id="login-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => { setPassword(event.target.value); setPasswordError(''); setNotice('') }}
              onBlur={validatePassword}
              aria-invalid={Boolean(passwordError)}
              aria-describedby={passwordError ? 'login-password-error' : undefined}
              required
            />
            {passwordError && <p className="auth-field-error" id="login-password-error">{passwordError}</p>}
          </div>
          <AuthNotice>{notice}</AuthNotice>
          <button className="auth-submit" type="submit" disabled={loading}>
            {loading ? <span className="auth-loading"><span className="auth-spinner" aria-hidden="true" />Signing in</span> : 'Sign in'}
          </button>
        </form>
        <Link className="auth-alternate-link" to="/register">New here? Create an account.</Link>
      </div>
    </AuthLayout>
  )
}
