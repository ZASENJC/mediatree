const apiCache = new Map<string, { data: unknown; timestamp: number }>()
const CACHE_TTL = 120000

export function getCached<T>(key: string): T | null {
  const entry = apiCache.get(key)
  if (!entry) return null
  if (Date.now() - entry.timestamp > CACHE_TTL) {
    apiCache.delete(key)
    return null
  }
  return entry.data as T
}

export function setCache(key: string, data: unknown) {
  apiCache.set(key, { data, timestamp: Date.now() })
}

export function clearCache(prefix?: string) {
  if (prefix) {
    for (const k of apiCache.keys()) {
      if (k.startsWith(prefix)) apiCache.delete(k)
    }
  } else {
    apiCache.clear()
  }
}

export function clearAllStoreData() {
  clearCache()
  try {
    const keys = ['mediatree_library']
    for (const k of keys) {
      localStorage.removeItem(k)
    }
  } catch {}
}
