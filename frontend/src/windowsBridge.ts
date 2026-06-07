export interface WindowsShellInfo {
  version?: string
  backendUrl?: string
}

export interface WindowsBridge {
  getShellInfo?: () => Promise<WindowsShellInfo>
  pickFolder?: () => Promise<string>
  openLogs?: () => Promise<void>
  restartBackend?: () => Promise<void>
}

declare global {
  interface Window {
    chrome?: {
      webview?: unknown
    }
    mediaTreeWindows?: WindowsBridge
  }
}

export function isWindowsShell(): boolean {
  return Boolean(window.mediaTreeWindows || window.chrome?.webview)
}

export function getWindowsBridge(): WindowsBridge | null {
  return window.mediaTreeWindows || null
}
