import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { PropsWithChildren } from 'react'
import { api } from '../lib/api'
import type { FarmerUser } from '../types'
import { normalizeKenyanPhone } from './phone'

export interface FarmerRegistration {
  full_name: string
  phone: string
  ward: number
  crop: number
  password: string
  password_confirm: string
  consent_sms: true
}

interface AuthContextValue {
  user: FarmerUser | null
  isLoading: boolean
  signIn: (phone: string, password: string) => Promise<void>
  registerFarmer: (data: FarmerRegistration) => Promise<void>
  signOut: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<FarmerUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const signOut = useCallback(() => {
    localStorage.removeItem('shamba_access')
    localStorage.removeItem('shamba_refresh')
    localStorage.removeItem('shamba_user_id')
    setUser(null)
  }, [])

  const establishSession = useCallback(async (tokens: { access: string; refresh: string }, phone: string) => {
    localStorage.setItem('shamba_access', tokens.access)
    localStorage.setItem('shamba_refresh', tokens.refresh)
    try {
      const { data: users } = await api.get<FarmerUser[]>('/users/')
      const current = users.find((candidate) => candidate.phone === phone)
      if (!current) throw new Error('Your account details could not be loaded.')
      localStorage.setItem('shamba_user_id', String(current.id))
      setUser(current)
      window.dispatchEvent(new Event('shamba:sync-requested'))
    } catch (error) {
      signOut()
      throw error
    }
  }, [signOut])

  const loadCurrentUser = useCallback(async () => {
    if (!localStorage.getItem('shamba_access')) {
      setIsLoading(false)
      return
    }
    try {
      const { data } = await api.get<FarmerUser[]>('/users/')
      const current = data[0] ?? null
      if (current) {
        localStorage.setItem('shamba_user_id', String(current.id))
        window.dispatchEvent(new Event('shamba:sync-requested'))
      }
      setUser(current)
    } catch (error) {
      signOut()
      throw error
    } finally {
      setIsLoading(false)
    }
  }, [signOut])

  useEffect(() => {
    void loadCurrentUser().catch(() => undefined)
    const onExpired = () => signOut()
    window.addEventListener('shamba:session-expired', onExpired)
    return () => window.removeEventListener('shamba:session-expired', onExpired)
  }, [loadCurrentUser, signOut])

  const signIn = useCallback(async (phone: string, password: string) => {
    const normalizedPhone = normalizeKenyanPhone(phone)
    if (!normalizedPhone) throw new Error('Enter a Kenyan phone number like 0712 345 678.')
    const { data } = await api.post<{ access: string; refresh: string }>('/auth/login/', {
      phone: normalizedPhone,
      password,
    })
    await establishSession(data, normalizedPhone)
  }, [establishSession])

  const registerFarmer = useCallback(async (registration: FarmerRegistration) => {
    const phone = normalizeKenyanPhone(registration.phone)
    if (!phone) throw new Error('Enter a Kenyan phone number like 0712 345 678.')
    const { data } = await api.post<{ access: string; refresh: string }>('/auth/register/', {
      ...registration,
      phone,
    })
    await establishSession(data, phone)
  }, [establishSession])

  const value = useMemo(() => ({ user, isLoading, signIn, registerFarmer, signOut }), [user, isLoading, signIn, registerFarmer, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
