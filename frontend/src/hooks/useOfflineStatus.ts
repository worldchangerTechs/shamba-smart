import { useEffect, useState } from 'react'
import { getLastApiUpdate, listQueuedRequests, OUTBOX_UPDATED_EVENT } from '../lib/offlineStore'

export function useOfflineStatus() {
  const [online, setOnline] = useState(() => navigator.onLine)
  const [pendingCount, setPendingCount] = useState(0)
  const [failedCount, setFailedCount] = useState(0)
  const [lastUpdated, setLastUpdated] = useState<number | null>(null)

  useEffect(() => {
    const refresh = () => {
      setOnline(navigator.onLine)
      void listQueuedRequests().then((items) => {
        setPendingCount(items.filter((item) => !item.lastError || item.lastError.startsWith('Waiting')).length)
        setFailedCount(items.filter((item) => Boolean(item.lastError) && !item.lastError?.startsWith('Waiting')).length)
      }).catch(() => {
        setPendingCount(0)
        setFailedCount(0)
      })
      void getLastApiUpdate().then(setLastUpdated).catch(() => setLastUpdated(null))
    }
    refresh()
    window.addEventListener('online', refresh)
    window.addEventListener('offline', refresh)
    window.addEventListener(OUTBOX_UPDATED_EVENT, refresh)
    window.addEventListener('shamba:api-cache-updated', refresh)
    return () => {
      window.removeEventListener('online', refresh)
      window.removeEventListener('offline', refresh)
      window.removeEventListener(OUTBOX_UPDATED_EVENT, refresh)
      window.removeEventListener('shamba:api-cache-updated', refresh)
    }
  }, [])

  return { online, pendingCount, failedCount, lastUpdated }
}
