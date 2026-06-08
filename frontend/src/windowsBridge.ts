export interface WindowsShellInfo {
  version?: string
  backendUrl?: string
}

export interface WindowsBridge {
  getShellInfo?: () => Promise<WindowsShellInfo>
  pickFolder?: () => Promise<string>
  openMpv?: (url: string) => Promise<void>
  openLogs?: () => Promise<void>
  restartBackend?: () => Promise<void>
}

type WebViewMessageResult = {
  id?: string
  ok?: boolean
  result?: unknown
  error?: string
}

type WebViewHost = {
  postMessage?: (message: unknown) => void
  addEventListener?: (type: 'message', handler: (event: { data: WebViewMessageResult }) => void) => void
  removeEventListener?: (type: 'message', handler: (event: { data: WebViewMessageResult }) => void) => void
}

declare global {
  interface Window {
    chrome?: {
      webview?: WebViewHost
    }
    mediaTreeWindows?: WindowsBridge
  }
}

const pending = new Map<string, {
  resolve: (value: unknown) => void
  reject: (reason?: unknown) => void
}>()
let listenerInstalled = false

function installWebViewListener(webview: WebViewHost) {
  if (listenerInstalled || !webview.addEventListener) return
  webview.addEventListener('message', event => {
    const message = event.data
    const id = message?.id || ''
    const entry = pending.get(id)
    if (!entry) return
    pending.delete(id)
    if (message.ok) entry.resolve(message.result)
    else entry.reject(new Error(message.error || 'Windows shell request failed'))
  })
  listenerInstalled = true
}

function sendWebViewRequest<T>(action: string, payload: Record<string, unknown> = {}): Promise<T> {
  const webview = window.chrome?.webview
  if (!webview?.postMessage) return Promise.reject(new Error('Windows WebView2 bridge is not available'))
  installWebViewListener(webview)
  const id = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
  return new Promise<T>((resolve, reject) => {
    pending.set(id, { resolve: value => resolve(value as T), reject })
    webview.postMessage?.({ id, action, ...payload })
    window.setTimeout(() => {
      if (!pending.has(id)) return
      pending.delete(id)
      reject(new Error(`Windows shell request timed out: ${action}`))
    }, 30000)
  })
}

const postMessageBridge: WindowsBridge = {
  getShellInfo: () => sendWebViewRequest<WindowsShellInfo>('getShellInfo'),
  pickFolder: () => sendWebViewRequest<string>('pickFolder'),
  openMpv: (url: string) => sendWebViewRequest<void>('openMpv', { url }),
  openLogs: () => sendWebViewRequest<void>('openLogs'),
  restartBackend: () => sendWebViewRequest<void>('restartBackend'),
}

export function isWindowsShell(): boolean {
  return Boolean(window.mediaTreeWindows || window.chrome?.webview)
}

export function getWindowsBridge(): WindowsBridge | null {
  if (window.chrome?.webview?.postMessage) return postMessageBridge
  return window.mediaTreeWindows || null
}
