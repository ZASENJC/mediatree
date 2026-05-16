const KEY = 'mediatree_excluded'

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
