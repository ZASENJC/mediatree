import { getCached, setCache, clearCache } from '../cache'
import { clearActiveLibrary, getApiBase, getToken, setToken } from './session'

export async function request<T>(url: string, options?: RequestInit & { signal?: AbortSignal }, cacheKey?: string): Promise<T> {
  if (cacheKey) {
    const cached = getCached<T>(cacheKey)
    if (cached !== null) return cached
  }
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string> || {}),
  }
  const token = getToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const { signal, ...fetchOptions } = (options || {}) as RequestInit & { signal?: AbortSignal }
  const res = await fetch(`${getApiBase()}${url}`, { ...fetchOptions, signal, headers, cache: 'no-store' })
  if (res.status === 401) {
    setToken('')
    clearActiveLibrary()
    if (window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const text = await res.text()
    let message = text || res.statusText
    try {
      const parsed = JSON.parse(text)
      message = parsed?.detail || parsed?.error || message
    } catch {}
    throw new Error(message)
  }
  const data = await res.json()
  if (cacheKey) setCache(cacheKey, data)
  return data
}

export { clearCache }
