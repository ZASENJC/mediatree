import { Capacitor } from '@capacitor/core'

const DEFAULT_API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '') || '/api'
const SERVER_URL_KEY = 'mediatree_server_url'

let memoryToken = ''
let memoryActiveLibrary = ''
let memoryServerUrl = ''
const resetHandlers = new Set<() => void>()

export function registerSessionResetHandler(handler: () => void) {
  resetHandlers.add(handler)
  return () => resetHandlers.delete(handler)
}

function resetSessionDependents() {
  resetHandlers.forEach(handler => handler())
}

export function isNativeApp(): boolean {
  return Capacitor.isNativePlatform()
}

function normalizeServerUrl(input: string): string {
  let value = (input || '').trim()
  if (!value) return ''
  if (!/^https?:\/\//i.test(value)) value = `http://${value}`
  return value.replace(/\/+$/, '')
}

export function getServerUrl(): string {
  try {
    const stored = normalizeServerUrl(localStorage.getItem(SERVER_URL_KEY) || '')
    if (stored) memoryServerUrl = stored
    return stored || memoryServerUrl
  } catch {
    return memoryServerUrl
  }
}

export function setServerUrl(url: string): string {
  const normalized = normalizeServerUrl(url)
  if (normalized !== memoryServerUrl) resetSessionDependents()
  memoryServerUrl = normalized
  try {
    if (normalized) localStorage.setItem(SERVER_URL_KEY, normalized)
    else localStorage.removeItem(SERVER_URL_KEY)
  } catch {}
  return normalized
}

export function getApiBase(): string {
  const server = getServerUrl()
  return server ? `${server}/api` : DEFAULT_API_BASE
}

export function getToken(): string {
  try {
    const stored = localStorage.getItem('mediatree_token') || ''
    if (stored) memoryToken = stored
    return stored || memoryToken
  } catch {
    return memoryToken
  }
}

export function setToken(t: string) {
  memoryToken = t
  resetSessionDependents()
  try {
    if (t) localStorage.setItem('mediatree_token', t)
    else localStorage.removeItem('mediatree_token')
  } catch {}
}

export function getActiveLibrary(): string {
  try {
    const stored = localStorage.getItem('mediatree_library') || ''
    if (stored) memoryActiveLibrary = stored
    return stored || memoryActiveLibrary
  } catch {
    return memoryActiveLibrary
  }
}

export function setActiveLibrary(lib: string) {
  memoryActiveLibrary = lib
  try { localStorage.setItem('mediatree_library', lib) } catch {}
}

export function clearActiveLibrary() {
  memoryActiveLibrary = ''
  try { localStorage.removeItem('mediatree_library') } catch {}
}
