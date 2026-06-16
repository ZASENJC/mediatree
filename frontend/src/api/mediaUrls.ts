import { getApiBase, registerSessionResetHandler } from './session'
import { request } from './client'

const MEDIA_TOKEN_KEY = 'mediatree_media_token'

let memoryMediaToken = ''
let memoryMediaTokenExpiresAt = 0
let mediaTokenPromise: Promise<string> | null = null

function mediaTokenStillValid(expiresAt: number): boolean {
  return expiresAt > Math.floor(Date.now() / 1000) + 60
}

function readStoredMediaToken(): string {
  if (memoryMediaToken && mediaTokenStillValid(memoryMediaTokenExpiresAt)) return memoryMediaToken
  try {
    const raw = localStorage.getItem(MEDIA_TOKEN_KEY) || ''
    if (!raw) return ''
    const parsed = JSON.parse(raw) as { token?: string; expires_at?: number; api_base?: string }
    if (!parsed.token || !parsed.expires_at || parsed.api_base !== getApiBase() || !mediaTokenStillValid(parsed.expires_at)) {
      localStorage.removeItem(MEDIA_TOKEN_KEY)
      return ''
    }
    memoryMediaToken = parsed.token
    memoryMediaTokenExpiresAt = parsed.expires_at
    return parsed.token
  } catch {
    return ''
  }
}

function storeMediaToken(token: string, expiresAt: number) {
  memoryMediaToken = token
  memoryMediaTokenExpiresAt = expiresAt
  try {
    localStorage.setItem(MEDIA_TOKEN_KEY, JSON.stringify({ token, expires_at: expiresAt, api_base: getApiBase() }))
  } catch {}
}

function clearMediaToken() {
  memoryMediaToken = ''
  memoryMediaTokenExpiresAt = 0
  mediaTokenPromise = null
  try { localStorage.removeItem(MEDIA_TOKEN_KEY) } catch {}
}

export function getMediaTokenSync(): string {
  return readStoredMediaToken()
}

export async function ensureMediaToken(force = false): Promise<string> {
  if (!force) {
    const cached = getMediaTokenSync()
    if (cached) return cached
  }
  if (mediaTokenPromise) return mediaTokenPromise
  mediaTokenPromise = request<{ token: string; expires_at: number }>('/media-token', { method: 'POST' })
    .then(data => {
      storeMediaToken(data.token, data.expires_at)
      return data.token
    })
    .finally(() => {
      mediaTokenPromise = null
    })
  return mediaTokenPromise
}

export function appendMediaToken(url: string): string {
  const token = getMediaTokenSync()
  if (!token || /[?&]token=/.test(url)) return url
  return `${url}${url.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`
}

function isMediaApiPath(path: string): boolean {
  return [
    '/api/stream/',
    '/api/cover/',
    '/api/continue-cover/',
    '/api/episode-still/',
    '/api/thumbnail/',
    '/api/subtitle/',
    '/api/subtitle-file/',
    '/api/external-play/',
    '/api/media/',
  ].some(prefix => path.startsWith(prefix))
}

export function resolveApiUrl(url: string): string {
  if (!url) return url
  if (/^(https?:)?\/\//i.test(url) || url.startsWith('blob:') || url.startsWith('data:')) return url
  if (url === '/api') return getApiBase()
  if (url.startsWith('/api/')) return `${getApiBase()}${url.slice(4)}`
  return url
}

export function resolveMediaUrl(url: string): string {
  const resolved = resolveApiUrl(url)
  try {
    const parsed = new URL(resolved, window.location.origin)
    return isMediaApiPath(parsed.pathname) ? appendMediaToken(resolved) : resolved
  } catch {
    return isMediaApiPath(resolved) ? appendMediaToken(resolved) : resolved
  }
}

registerSessionResetHandler(clearMediaToken)
