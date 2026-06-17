import { useEffect } from 'react'

type CardRect = {
  left: number
  top: number
}

type AnimatedCard = HTMLElement & {
  __mediaGridAnimationCount?: number
}

const MOVE_THRESHOLD_PX = 0.5
const ANIMATION_MS = 180
const ANIMATION_EASING = 'cubic-bezier(0.2, 0.8, 0.2, 1)'
const RESIZE_TRACK_MS = 220

function getCards(grid: Element) {
  return Array.from(grid.querySelectorAll<HTMLElement>(':scope > .media-grid-card'))
}

function getDocumentCardRect(card: HTMLElement): CardRect {
  const rect = card.getBoundingClientRect()
  return {
    left: rect.left + window.scrollX,
    top: rect.top + window.scrollY,
  }
}

function readRects(grids: Iterable<Element>) {
  const rects = new WeakMap<HTMLElement, CardRect>()
  for (const grid of grids) {
    for (const card of getCards(grid)) {
      rects.set(card, getDocumentCardRect(card))
    }
  }
  return rects
}

function readTransformOffset(transform: string): CardRect {
  if (transform === 'none' || typeof DOMMatrixReadOnly === 'undefined') return { left: 0, top: 0 }
  try {
    const matrix = new DOMMatrixReadOnly(transform)
    return { left: matrix.m41, top: matrix.m42 }
  } catch {
    return { left: 0, top: 0 }
  }
}

function animateGridShift(grid: Element, beforeRects: WeakMap<HTMLElement, CardRect>, nextRects: WeakMap<HTMLElement, CardRect>) {
  for (const card of getCards(grid)) {
    const before = beforeRects.get(card)
    const animatedCard = card as AnimatedCard
    const activeTransform = getComputedStyle(card).transform
    const activeOffset = readTransformOffset(activeTransform)

    const after = getDocumentCardRect(card)
    const afterLayout = {
      left: after.left - activeOffset.left,
      top: after.top - activeOffset.top,
    }
    nextRects.set(card, afterLayout)
    if (!before && activeTransform === 'none') continue

    const dx = (before?.left ?? afterLayout.left) - afterLayout.left
    const dy = (before?.top ?? afterLayout.top) - afterLayout.top
    const fromX = dx + activeOffset.left
    const fromY = dy + activeOffset.top
    if (Math.abs(dx) < MOVE_THRESHOLD_PX && Math.abs(dy) < MOVE_THRESHOLD_PX) continue

    card.classList.add('is-layout-animating')
    animatedCard.__mediaGridAnimationCount = (animatedCard.__mediaGridAnimationCount || 0) + 1
    const animation = card.animate(
      [
        { transform: `translate(${fromX}px, ${fromY}px)` },
        { transform: 'translate(0, 0)' },
      ],
      {
        duration: ANIMATION_MS,
        easing: ANIMATION_EASING,
      },
    )
    const cleanup = () => {
      animatedCard.__mediaGridAnimationCount = Math.max((animatedCard.__mediaGridAnimationCount || 1) - 1, 0)
      if (animatedCard.__mediaGridAnimationCount > 0) return
      delete animatedCard.__mediaGridAnimationCount
      card.classList.remove('is-layout-animating')
    }
    animation.addEventListener('finish', cleanup, { once: true })
    animation.addEventListener('cancel', cleanup, { once: true })
  }
}

export function useMediaGridMotion() {
  useEffect(() => {
    if (typeof window === 'undefined' || typeof document === 'undefined') return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    if (typeof ResizeObserver === 'undefined' || typeof MutationObserver === 'undefined') return

    const grids = new Set<Element>()
    let lastRects = new WeakMap<HTMLElement, CardRect>()
    let resizeFrame = 0
    let resizeTrackingUntil = 0
    let lastViewportWidth = window.innerWidth
    const observeGrid = (grid: Element) => {
      if (grids.has(grid)) return
      grids.add(grid)
      resizeObserver.observe(grid)
    }
    const syncGrids = () => {
      document.querySelectorAll('.media-grid:not([data-media-grid-motion="off"])').forEach(observeGrid)
      for (const grid of Array.from(grids)) {
        if (!document.contains(grid)) {
          grids.delete(grid)
          resizeObserver.unobserve(grid)
        }
      }
    }
    const runAnimation = () => {
      const targets = Array.from(grids)
      const nextRects = new WeakMap<HTMLElement, CardRect>()
      for (const grid of targets) animateGridShift(grid, lastRects, nextRects)
      lastRects = nextRects
    }
    const runAnimationNow = () => {
      runAnimation()
    }
    const trackResizeMotion = (timestamp: number) => {
      resizeFrame = 0
      const currentViewportWidth = window.innerWidth
      if (currentViewportWidth !== lastViewportWidth) {
        lastViewportWidth = currentViewportWidth
        runAnimationNow()
      }
      if (timestamp < resizeTrackingUntil) {
        resizeFrame = window.requestAnimationFrame(trackResizeMotion)
      }
    }
    const scheduleResizeTracking = () => {
      resizeTrackingUntil = window.performance.now() + RESIZE_TRACK_MS
      if (resizeFrame) return
      resizeFrame = window.requestAnimationFrame(trackResizeMotion)
    }
    const handleWindowResize = () => {
      if (window.innerWidth === lastViewportWidth) return
      lastViewportWidth = window.innerWidth
      runAnimationNow()
      scheduleResizeTracking()
    }

    const resizeObserver = new ResizeObserver(() => {
      lastViewportWidth = window.innerWidth
      runAnimationNow()
      scheduleResizeTracking()
    })
    const mutationObserver = new MutationObserver((records) => {
      const hasStructuralChange = records.some((record) => record.type === 'childList' && (record.addedNodes.length > 0 || record.removedNodes.length > 0))
      if (!hasStructuralChange) return
      syncGrids()
      runAnimationNow()
    })

    syncGrids()
    lastRects = readRects(grids)
    mutationObserver.observe(document.body, { childList: true, subtree: true })
    window.addEventListener('resize', handleWindowResize, { passive: true })

    return () => {
      if (resizeFrame) window.cancelAnimationFrame(resizeFrame)
      window.removeEventListener('resize', handleWindowResize)
      resizeObserver.disconnect()
      mutationObserver.disconnect()
      grids.clear()
    }
  }, [])
}
