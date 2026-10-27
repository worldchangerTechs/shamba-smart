import axios, { AxiosError, AxiosHeaders, InternalAxiosRequestConfig } from 'axios'
import { enqueueRequest, isNetworkError, readApiCache, saveApiCache } from './offlineStore'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'

export const api = axios.create({
  baseURL: baseURL.replace(/\/+$/, ''),
})

interface AuthTokens {
  access: string
  refresh: string
}

interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

export type QueuedOfflineResult = { queued_offline: true; queue_id: string }

export function isQueuedOfflineResult(value: unknown): value is QueuedOfflineResult {
  return Boolean(value && typeof value === 'object' && 'queued_offline' in value && (value as QueuedOfflineResult).queued_offline)
}

function cacheableApiUrl(config: InternalAxiosRequestConfig) {
  if (config.method?.toLowerCase() !== 'get') return null
  const url = new URL(api.getUri(config), window.location.origin)
  if (!/\/(?:lessons|advice-content|advice\/[^/]+|alerts|alert-deliveries|users)(?:\/|$)/.test(url.pathname)) return null
  return url.toString()
}

function noteCacheUpdated() {
  window.dispatchEvent(new Event('shamba:api-cache-updated'))
}

let refreshing: Promise<string | null> | null = null

api.interceptors.request.use((config) => {
  const access = localStorage.getItem('shamba_access')
  if (access) config.headers.Authorization = `Bearer ${access}`
  return config
})

api.interceptors.response.use(
  (response) => {
    const url = cacheableApiUrl(response.config)
    if (url && response.status >= 200 && response.status < 300) {
      void saveApiCache(url, response.data).then(noteCacheUpdated).catch((error: unknown) => {
        console.warn('Could not save an offline API response.', error)
      })
    }
    return response
  },
  async (error: AxiosError) => {
    const request = error.config as RetryConfig | undefined
    if (request && isNetworkError(error)) {
      const url = cacheableApiUrl(request)
      if (url) {
        try {
          const cached = await readApiCache(url)
          if (cached) {
            const config = request
            return {
              data: cached.data,
              status: 200,
              statusText: 'OK (offline cache)',
              headers: new AxiosHeaders({ 'x-shamba-cache-updated-at': String(cached.updatedAt) }),
              config,
            }
          }
        } catch (cacheError) {
          console.warn('Could not read the offline API cache.', cacheError)
        }
      }
    }
    const refresh = localStorage.getItem('shamba_refresh')
    if (
      error.response?.status !== 401
      || !request
      || request.url?.includes('/auth/token')
      || request._retry
      || !refresh
    ) {
      return Promise.reject(error)
    }

    request._retry = true
    if (!refreshing) {
      refreshing = axios
        .post<AuthTokens>(`${baseURL.replace(/\/+$/, '')}/auth/token/refresh/`, { refresh })
        .then(({ data }) => {
          localStorage.setItem('shamba_access', data.access)
          if (data.refresh) localStorage.setItem('shamba_refresh', data.refresh)
          return data.access
        })
        .catch(() => {
          localStorage.removeItem('shamba_access')
          localStorage.removeItem('shamba_refresh')
          window.dispatchEvent(new Event('shamba:session-expired'))
          return null
        })
        .finally(() => {
          refreshing = null
        })
    }

    const access = await refreshing
    if (!access) return Promise.reject(error)
    request.headers.Authorization = `Bearer ${access}`
    return api(request)
  },
)

export async function submitOfflineCapable<T>(
  method: 'POST' | 'PATCH',
  url: string,
  data: unknown,
): Promise<T | QueuedOfflineResult> {
  if (!navigator.onLine) {
    const queued = await enqueueRequest(method, url, data)
    return { queued_offline: true, queue_id: queued.id }
  }
  try {
    const response = method === 'POST' ? await api.post<T>(url, data) : await api.patch<T>(url, data)
    return response.data
  } catch (error) {
    if (!isNetworkError(error)) throw error
    const queued = await enqueueRequest(method, url, data)
    return { queued_offline: true, queue_id: queued.id }
  }
}
