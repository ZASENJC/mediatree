function scrollKey(): string {
  return `scroll_${window.location.pathname}${window.location.search}`
}

export function saveScrollPos() {
  try {
    sessionStorage.setItem(scrollKey(), String(window.scrollY))
  } catch {}
}

export function restoreScrollPos() {
  try {
    const y = sessionStorage.getItem(scrollKey())
    if (y) {
      requestAnimationFrame(() => window.scrollTo(0, parseInt(y, 10)))
    }
  } catch {}
}
