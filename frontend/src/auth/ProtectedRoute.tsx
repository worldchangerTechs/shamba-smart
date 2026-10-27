import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './AuthProvider'
import { Skeleton } from '../components/ui/Skeleton'

export function ProtectedRoute() {
  const { user, isLoading } = useAuth()
  if (isLoading) return <div className="grid min-h-screen place-items-center p-6"><Skeleton className="h-24 w-full max-w-sm" /></div>
  return user ? <Outlet /> : <Navigate to="/login" replace />
}
