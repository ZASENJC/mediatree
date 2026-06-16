import { useEffect } from 'react'

type CardRect = {
  left: number
  top: number
}

type AnimatedCard = HTMLElement & {
  __mediaGridAnimation?: Animation
}

const MOVE_THRESHOLD_PX = 1
const ANIMATION_MS = 140
const ANIMATION_EASING = 'cubic-bezier(0.2, 0.8, 0.2, 1)'

function getCards(grid: Element) {
  return Array.from(grid.querySelectorAll<HTMLElement>(':scope > .media-grid-card'))
}

function readRects(grids: Iterable<Element>) {
  const rects = new WeakMap<HTMLElement, CardRect>()
  for (const grid of grids) {
    for (const card of getCards(grid)) {
      const rect = card.getBoundingClientRect()
      rects.set(card, { left: rect.left, top: rect.top })
    }
  }
  return rects
}

function animateGridShift(grid: Element, beforeRects: WeakMap<HTMLElement, CardRect>, nextRects: WeakMap<HTMLElement, CardRect>) {
  for (const card of getCards(grid)) {
    const before = beforeRects.get(card)
    const animatedCard = card as AnimatedCard
    const activeAnimation = animatedCard.__mediaGridAnimation
    const activeTransform = activeAnimation ? getComputedStyle(card).transform : 'none'
    animatedCard.__mediaGridAnimation?.cancel()

    const after = card.getBoundingClientRect()
    nextRects.set(card, { left: after.left, top: after.top })
    if (!before && activeTransform === 'none') continue

    const dx = (before?.left ?? after.left) - after.left
    const dy = (before?.top ?? after.top) - after.top
    const hasActiveTransform = activeTransform !== 'none'
    if (!hasActiveTransform && Math.abs(dx) < MOVE_THRESHOLD_PX && Math.abs(dy) < MOVE_THRESHOLD_PX) continue

    card.classList.add('is-layout-animating')
    const animation = card.animate(
      [
        { transform: hasActiveTransform ? activeTransform : `translate(${dx}px, ${dy}px)` },
        { transform: 'translate(0, 0)' },
      ],
      {
        duration: ANIMATION_MS,
        easing: ANIMATION_EASING,
        fill: 'both',
      },
    )
    animatedCard.__mediaGridAnimation = animation
    const cleanup = () => {
      if (animatedCard.__mediaGridAnimation !== animation) return
      delete animatedCard.__mediaGridAnimation
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
    const observeGrid = (grid: Element) => {
      if (grids.has(grid)) return
      grids.add(grid)
      resizeObserver.observe(grid)
    }
    const syncGrids = () => {
      document.querySelectorAll('.media-grid').forEach(observeGrid)
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

    const resizeObserver = new ResizeObserver(() => {
      runAnimation()
    })
    const mutationObserver = new MutationObserver((records) => {
      const hasStructuralChange = records.some((record) => record.type === 'childList' && (record.addedNodes.length > 0 || record.removedNodes.length > 0))
      if (!hasStructuralChange) return
      syncGrids()
      runAnimation()
    })

    syncGrids()
    lastRects = readRects(grids)
    mutationObserver.observe(document.body, { childList: true, subtree: true })

    return () => {
      for (const grid of grids) {
        for (const card of getCards(grid)) {
          ;(card as AnimatedCard).__mediaGridAnimation?.cancel()
        }
      }
      resizeObserver.disconnect()
      mutationObserver.disconnect()
      grids.clear()
    }
  }, [])
}
