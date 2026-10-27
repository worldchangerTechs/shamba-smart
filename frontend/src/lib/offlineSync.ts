import { api } from './api'
import {
  isNetworkError,
  listQueuedRequests,
  queuedRequestBody,
  removeQueuedRequest,
  updateQueuedRequest,
} from './offlineStore'

let syncInProgress: Promise<void> | null = null

export function syncOfflineQueue() {
  if (syncInProgress || !navigator.onLine) return syncInProgress ?? Promise.resolve()
  syncInProgress = (async () => {
    const queued = await listQueuedRequests()
    for (const entry of queued) {
      if (!navigator.onLine) break
      try {
        const body = queuedRequestBody(entry)
        if (entry.method === 'PATCH') {
          await api.patch(entry.url, body)
        } else {
          await api.post(entry.url, body, body instanceof FormData ? undefined : { headers: { 'Content-Type': 'application/json' } })
        }
        await removeQueuedRequest(entry.id)
      } catch (error) {
        const updated = {
          ...entry,
          attempts: entry.attempts + 1,
          lastError: isNetworkError(error)
            ? 'Waiting for an internet connection.'
            : 'The server rejected this saved action. Sign in and review it before retrying.',
        }
        await updateQueuedRequest(updated)
        if (isNetworkError(error)) break
      }
    }
  })().finally(() => {
    syncInProgress = null
  })
  return syncInProgress
}

export function installOfflineSync() {
  const onOnline = () => {
    void syncOfflineQueue()
  }
  const onSyncRequested = () => {
    void syncOfflineQueue()
  }
  window.addEventListener('online', onOnline)
  window.addEventListener('shamba:sync-requested', onSyncRequested)
  if (navigator.onLine) void syncOfflineQueue()
  return () => {
    window.removeEventListener('online', onOnline)
    window.removeEventListener('shamba:sync-requested', onSyncRequested)
  }
}
