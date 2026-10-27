import { lazy, Suspense } from 'react'
import { useReducedMotion } from './hooks/useReducedMotion'
import { ToastProvider } from './hooks/useToast'
import { useAuth } from './auth/AuthProvider'
import { AppLayout } from './components/layout/AppLayout'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { OnboardingPage } from './pages/OnboardingPage'
import { Navigate, Route, Routes } from 'react-router-dom'
import { SimulatorPage } from './pages/SimulatorPage'

const FarmerExperiencePage = lazy(() => import('./pages/FarmerExperiencePage').then((module) => ({ default: module.FarmerExperiencePage })))
const RoleDashboardPage = lazy(() => import('./pages/RoleDashboards').then((module) => ({ default: module.RoleDashboardPage })))
const LandingPage = lazy(() => import('./pages/LandingPage').then((module) => ({ default: module.LandingPage })))
const AdminWarningsPage = lazy(() => import('./pages/AdminWarningsPage').then((module) => ({ default: module.AdminWarningsPage })))

function RouteLoading() {
  return <div className="p-6"><div className="skeleton h-32 w-full" /></div>
}

function AppHome() {
  const { user } = useAuth()
  if (user?.role === 'FARMER') return <Suspense fallback={<RouteLoading />}><FarmerExperiencePage /></Suspense>
  return <Suspense fallback={<RouteLoading />}><RoleDashboardPage /></Suspense>
}

export function App() {
  useReducedMotion()
  return (
    <ToastProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        {/* Public simulator — no auth required */}
        <Route path="/simulator" element={<SimulatorPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/admin/warnings" element={<Suspense fallback={<RouteLoading />}><AdminWarningsPage /></Suspense>} />
          <Route path="/app" element={<AppLayout />}>
            <Route index element={<AppHome />} />
            <Route path="*" element={<Suspense fallback={<RouteLoading />}><FarmerExperiencePage /></Suspense>} />
          </Route>
        </Route>
        <Route path="/" element={<Suspense fallback={<RouteLoading />}><LandingPage /></Suspense>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ToastProvider>
  )
}
