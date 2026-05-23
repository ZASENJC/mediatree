const KEY = 'mediatree_excluded'
const UI_PREFS_KEY = 'mediatree_ui_prefs'

export interface UiPrefs {
  hideHomeTitleText?: boolean
  ambientMode?: boolean
  showSourceName?: boolean
  updateAvailable?: boolean
  lastUpdateCheck?: number
  dismissedUpdateVersion?: string
}

export function getExcluded(): Set<string> {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return new Set()
    return new Set(JSON.parse(raw))
  } catch {
    return new Set()
  }
}

export function setExcluded(set: Set<string>) {
  localStorage.setItem(KEY, JSON.stringify([...set]))
}

export function getUiPrefs(): UiPrefs {
  try {
    const raw = localStorage.getItem(UI_PREFS_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

export function setUiPrefs(prefs: UiPrefs) {
  try {
    localStorage.setItem(UI_PREFS_KEY, JSON.stringify(prefs))
  } catch {}
}

export function getUpdateNotification(): { available: boolean; lastCheck: number; dismissed: string } {
  const prefs = getUiPrefs()
  return {
    available: prefs.updateAvailable || false,
    lastCheck: prefs.lastUpdateCheck || 0,
    dismissed: prefs.dismissedUpdateVersion || '',
  }
}

export function dismissUpdate(version: string) {
  const prefs = getUiPrefs()
  setUiPrefs({ ...prefs, updateAvailable: false, dismissedUpdateVersion: version })
}
