const KEY = 'mediatree_excluded'
const UI_PREFS_KEY = 'mediatree_ui_prefs'

export interface UiPrefs {
  hideHomeTitleText?: boolean
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
