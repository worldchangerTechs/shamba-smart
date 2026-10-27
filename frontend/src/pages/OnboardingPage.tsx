import { useEffect, useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthProvider'
import { AuthLayout, AuthNotice } from '../components/auth/AuthLayout'
import { api } from '../lib/api'
import { getList } from '../types'
import type { ApiList, Farm } from '../types'
import '../components/auth/auth.css'

type Crop = { id: number; name: string }
type Step = 1 | 2

export function OnboardingPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [step, setStep] = useState<Step>(1)
  const [slope, setSlope] = useState<Farm['slope_class']>('GENTLE')
  const [crop, setCrop] = useState('')
  const [plantedOn, setPlantedOn] = useState(new Date().toISOString().slice(0, 10))
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(false)
  const farmsQuery = useQuery({
    queryKey: ['onboarding-farms'],
    queryFn: async () => getList<Farm>((await api.get<Farm[] | ApiList<Farm>>('/farms/')).data),
  })
  const cropsQuery = useQuery({
    queryKey: ['public-crops'],
    queryFn: async () => getList<Crop>((await api.get<Crop[] | ApiList<Crop>>('/crops/')).data),
  })
  const farmerQuery = useQuery({
    queryKey: ['onboarding-farmer'],
    queryFn: async () => getList<{ main_crop: number | null }>((await api.get('/farmers/')).data)[0],
  })

  useEffect(() => {
    if (farmerQuery.data?.main_crop) setCrop(String(farmerQuery.data.main_crop))
  }, [farmerQuery.data?.main_crop])

  if (user && user.role !== 'FARMER') return <Navigate to="/app" replace />

  const completeStep = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setNotice('')
    const farm = farmsQuery.data?.[0]
    if (!farm) {
      setNotice('Your starter farm could not be found. Try again or skip setup.')
      return
    }
    if (step === 1) {
      setLoading(true)
      try {
        await api.patch(`/farms/${farm.id}/`, { slope_class: slope })
        setStep(2)
      } catch {
        setNotice('We could not save your slope. Try again or skip setup.')
      } finally {
        setLoading(false)
      }
      return
    }
    if (!crop) {
      setNotice('Choose your first crop to continue.')
      return
    }
    const harvest = new Date(`${plantedOn}T00:00:00`)
    harvest.setDate(harvest.getDate() + 120)
    setLoading(true)
    try {
      await api.post('/plantings/', {
        farm: farm.id,
        crop: Number(crop),
        variety: 'Local variety',
        planted_on: plantedOn,
        expected_harvest: harvest.toISOString().slice(0, 10),
      })
      navigate('/app', { replace: true })
    } catch {
      setNotice('We could not save your crop details. Check the date and try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout variant="onboarding">
      <div className="auth-panel-content">
        <p className="auth-step-indicator">Step {step} of 2</p>
        <h2 className="auth-panel-heading">{step === 1 ? 'Tell us about your slope' : 'What are you growing first?'}</h2>
        {farmsQuery.isLoading ? <p className="auth-success">Loading your starter farm.</p> : farmsQuery.isError ? <div className="auth-list-error" role="alert"><p>Your farm details could not load.</p><button type="button" onClick={() => void farmsQuery.refetch()}>Retry</button></div> : null}
        {step === 2 && cropsQuery.isError && <div className="auth-list-error" role="alert"><p>The crop list could not load.</p><button type="button" onClick={() => void cropsQuery.refetch()}>Retry crops</button></div>}
        <form className="auth-onboarding-steps" onSubmit={completeStep} noValidate>
          {step === 1 ? <div className="auth-field">
            <label className="auth-field-label" htmlFor="onboarding-slope">Plot slope</label>
            <select className="auth-field-select" id="onboarding-slope" value={slope} onChange={(event) => setSlope(event.target.value as Farm['slope_class'])}>
              <option value="FLAT">Flat</option>
              <option value="GENTLE">Gentle</option>
              <option value="STEEP">Steep</option>
            </select>
          </div> : <>
            <div className="auth-field">
              <label className="auth-field-label" htmlFor="onboarding-crop">First crop</label>
              <select className="auth-field-select" id="onboarding-crop" value={crop} onChange={(event) => setCrop(event.target.value)} required>
                <option value="">{cropsQuery.isLoading ? 'Loading crops' : 'Choose a crop'}</option>
                {(cropsQuery.data ?? []).map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
              </select>
            </div>
            <div className="auth-field">
              <label className="auth-field-label" htmlFor="onboarding-date">Planting date</label>
              <input className="auth-field-input" id="onboarding-date" type="date" value={plantedOn} onChange={(event) => setPlantedOn(event.target.value)} required />
            </div>
          </>}
          <AuthNotice>{notice}</AuthNotice>
          <div className="auth-onboarding-actions">
            <button className="auth-submit" type="submit" disabled={loading || farmsQuery.isLoading || farmsQuery.isError || (step === 2 && (cropsQuery.isLoading || cropsQuery.isError))}>
              {loading ? <span className="auth-loading"><span className="auth-spinner" aria-hidden="true" />Saving</span> : step === 1 ? 'Continue' : 'Finish setup'}
            </button>
            <button className="auth-skip" type="button" onClick={() => navigate('/app', { replace: true })}>Skip setup and go to Today</button>
          </div>
        </form>
      </div>
    </AuthLayout>
  )
}
