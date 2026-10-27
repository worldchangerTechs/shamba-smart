export type QueuedRequest = {
  id: string
  userId: number
  method: 'POST' | 'PATCH'
  url: string
  body:
    | { kind: 'json'; data: unknown }
    | { kind: 'form'; entries: [string, string | Blob][] }
  createdAt: number
  attempts: number
  lastError?: string
}

export type CachedResponse = {
  key: string
  userId: number
  data: unknown
  updatedAt: number
}

const DATABASE_NAME = 'shamba-smart-offline'
const DATABASE_VERSION = 1
const CACHE_STORE = 'api-cache'
const OUTBOX_STORE = 'outbox'
const OUTBOX_UPDATED_EVENT = 'shamba:outbox-updated'

let databasePromise: Promise<IDBDatabase> | undefined

function currentUserId() {
  const value = Number(localStorage.getItem('shamba_user_id'))
  return Number.isInteger(value) && value > 0 ? value : null
}

function openDatabase() {
  if (!('indexedDB' in window)) {
    return Promise.reject(new Error('Offline storage is not available in this browser.'))
  }
  if (!databasePromise) {
    databasePromise = new Promise<IDBDatabase>((resolve, reject) => {
      const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION)
      request.onupgradeneeded = () => {
        const database = request.result
        if (!database.objectStoreNames.contains(CACHE_STORE)) {
          database.createObjectStore(CACHE_STORE, { keyPath: 'key' })
        }
        if (!database.objectStoreNames.contains(OUTBOX_STORE)) {
          const outbox = database.createObjectStore(OUTBOX_STORE, { keyPath: 'id' })
          outbox.createIndex('userId', 'userId')
        }
      }
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error ?? new Error('Could not open offline storage.'))
      request.onblocked = () => reject(new Error('Offline storage is blocked by another open app tab.'))
    }).catch((error: unknown) => {
      databasePromise = undefined
      throw error
    })
  }
  return databasePromise
}

function requestValue<T>(request: IDBRequest<T>) {
  return new Promise<T>((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('Offline storage request failed.'))
  })
}

function transactionDone(transaction: IDBTransaction) {
  return new Promise<void>((resolve, reject) => {
    transaction.oncomplete = () => resolve()
    transaction.onabort = () => reject(transaction.error ?? new Error('Offline storage transaction aborted.'))
    transaction.onerror = () => reject(transaction.error ?? new Error('Offline storage transaction failed.'))
  })
}

export async function saveApiCache(url: string, data: unknown) {
  const userId = currentUserId()
  if (!userId) return
  const database = await openDatabase()
  const transaction = database.transaction(CACHE_STORE, 'readwrite')
  transaction.objectStore(CACHE_STORE).put({
    key: `${userId}:${url}`,
    userId,
    data,
    updatedAt: Date.now(),
  } satisfies CachedResponse)
  await transactionDone(transaction)
}

export async function readApiCache(url: string) {
  const userId = currentUserId()
  if (!userId) return null
  const database = await openDatabase()
  const transaction = database.transaction(CACHE_STORE, 'readonly')
  const result = await requestValue<CachedResponse | undefined>(
    transaction.objectStore(CACHE_STORE).get(`${userId}:${url}`),
  )
  await transactionDone(transaction)
  return result ?? null
}

export async function getLastApiUpdate() {
  const userId = currentUserId()
  if (!userId) return null
  const database = await openDatabase()
  const transaction = database.transaction(CACHE_STORE, 'readonly')
  const entries = await requestValue<CachedResponse[]>(
    transaction.objectStore(CACHE_STORE).getAll(),
  )
  await transactionDone(transaction)
  return entries
    .filter((entry) => entry.userId === userId)
    .reduce<number | null>((latest, entry) => latest === null ? entry.updatedAt : Math.max(latest, entry.updatedAt), null)
}

function buildBody(data: unknown): QueuedRequest['body'] {
  if (data instanceof FormData) {
    return {
      kind: 'form',
      entries: [...data.entries()].map(([key, value]) => [key, value]),
    }
  }
  return { kind: 'json', data }
}

export async function enqueueRequest(method: QueuedRequest['method'], url: string, data: unknown) {
  const userId = currentUserId()
  if (!userId) throw new Error('Sign in before saving an offline action.')
  const database = await openDatabase()
  const id = typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`
  const record: QueuedRequest = {
    id,
    userId,
    method,
    url,
    body: buildBody(data),
    createdAt: Date.now(),
    attempts: 0,
  }
  const transaction = database.transaction(OUTBOX_STORE, 'readwrite')
  transaction.objectStore(OUTBOX_STORE).add(record)
  await transactionDone(transaction)
  window.dispatchEvent(new Event(OUTBOX_UPDATED_EVENT))
  return record
}

export async function listQueuedRequests() {
  const userId = currentUserId()
  if (!userId) return []
  const database = await openDatabase()
  const transaction = database.transaction(OUTBOX_STORE, 'readonly')
  const entries = await requestValue<QueuedRequest[]>(
    transaction.objectStore(OUTBOX_STORE).index('userId').getAll(userId),
  )
  await transactionDone(transaction)
  return entries.sort((a, b) => a.createdAt - b.createdAt)
}

export async function updateQueuedRequest(entry: QueuedRequest) {
  const database = await openDatabase()
  const transaction = database.transaction(OUTBOX_STORE, 'readwrite')
  transaction.objectStore(OUTBOX_STORE).put(entry)
  await transactionDone(transaction)
  window.dispatchEvent(new Event(OUTBOX_UPDATED_EVENT))
}

export async function removeQueuedRequest(id: string) {
  const database = await openDatabase()
  const transaction = database.transaction(OUTBOX_STORE, 'readwrite')
  transaction.objectStore(OUTBOX_STORE).delete(id)
  await transactionDone(transaction)
  window.dispatchEvent(new Event(OUTBOX_UPDATED_EVENT))
}

export function queuedRequestBody(entry: QueuedRequest) {
  if (entry.body.kind === 'json') return entry.body.data
  const form = new FormData()
  for (const [key, value] of entry.body.entries) {
    form.append(key, value)
  }
  return form
}

export function isNetworkError(error: unknown): error is { isAxiosError: true; response?: unknown } {
  return Boolean(error && typeof error === 'object' && 'isAxiosError' in error && 'response' in error && !(error as { response?: unknown }).response)
}

export { OUTBOX_UPDATED_EVENT }
