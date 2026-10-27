import { createContext, useCallback, useContext, useState } from 'react'
import type { PropsWithChildren } from 'react'
import { Toast } from '../components/ui/Toast'

type ToastMessage = { id: number; message: string; tone: 'success' | 'error' }
interface ToastContextValue {
  showToast: (message: string, tone?: ToastMessage['tone']) => void
}
const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: PropsWithChildren) {
  const [toast, setToast] = useState<ToastMessage | null>(null)
  const showToast = useCallback((message: string, tone: ToastMessage['tone'] = 'success') => {
    const id = Date.now()
    setToast({ id, message, tone })
    window.setTimeout(() => setToast((current) => current?.id === id ? null : current), 3500)
  }, [])
  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {toast && <Toast message={toast.message} tone={toast.tone} onDismiss={() => setToast(null)} />}
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used within ToastProvider')
  return context.showToast
}
