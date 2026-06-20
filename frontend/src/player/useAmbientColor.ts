import { useEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'
import type Artplayer from 'artplayer'

export type AmbientColor = { r: number; g: number; b: number } | null
export type TheaterPlayerSize = { width: number; height: number }

const AMBIENT_SAMPLE_INTERVAL = 200
const AMBIENT_COLOR_THRESHOLD = 12

export function useAmbientColor(
  artRef: { current: Artplayer | null },
  enabled: boolean,
): AmbientColor {
  const [color, setColor] = useState<AmbientColor>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const lastSampleAtRef = useRef(0)
  const lastColorRef = useRef({ r: 10, g: 10, b: 12 })
  const visibleRef = useRef(true)

  useEffect(() => {
    if (!enabled) {
      setColor(null)
      return
    }

    const handleVisibility = () => { visibleRef.current = !document.hidden }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [enabled])

  useEffect(() => {
    if (!enabled) return

    const sample = () => {
      if (!visibleRef.current) return
      const art = artRef.current
      const video = art?.video as HTMLVideoElement | undefined
      if (!video || video.paused || video.readyState < 2) return
      if (video.videoWidth === 0 || video.videoHeight === 0) return

      const now = Date.now()
      if (now - lastSampleAtRef.current < AMBIENT_SAMPLE_INTERVAL) return
      lastSampleAtRef.current = now

      try {
        if (!canvasRef.current) {
          canvasRef.current = document.createElement('canvas')
          canvasRef.current.width = 1
          canvasRef.current.height = 1
        }
        const ctx = canvasRef.current.getContext('2d', { willReadFrequently: true })
        if (!ctx) return
        ctx.drawImage(video, 0, 0, 1, 1)
        const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data
        const prev = lastColorRef.current
        if (
          Math.abs(r - prev.r) > AMBIENT_COLOR_THRESHOLD ||
          Math.abs(g - prev.g) > AMBIENT_COLOR_THRESHOLD ||
          Math.abs(b - prev.b) > AMBIENT_COLOR_THRESHOLD
        ) {
          const next = { r, g, b }
          lastColorRef.current = next
          setColor(next)
        }
      } catch {
        // Cross-origin canvas pollution is expected for some playback URLs.
      }
    }

    let raf = 0
    const loop = () => { sample(); raf = requestAnimationFrame(loop) }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [enabled])

  return color
}

export function usePlayerRect(
  targetRef: RefObject<HTMLDivElement | null>,
  enabled: boolean,
): DOMRect | null {
  const [rect, setRect] = useState<DOMRect | null>(null)

  useEffect(() => {
    if (!enabled) {
      setRect(null)
      return
    }
    const el = targetRef.current
    if (!el) return

    let raf = 0
    const update = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        setRect(el.getBoundingClientRect())
      })
    }

    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update, { passive: true })

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      window.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
    // targetRef is stable (from useRef)
  }, [enabled])

  return rect
}

export function calculateTheaterPlayerSize(
  maxWidth: number,
  maxHeight: number,
  aspect: number,
  heightOffset = 0,
): TheaterPlayerSize | null {
  const availableWidth = Math.floor(maxWidth)
  const availableHeight = Math.floor(Math.max(0, maxHeight - heightOffset))
  if (availableWidth <= 0 || availableHeight <= 0) return null

  const safeAspect = Number.isFinite(aspect) && aspect > 0 ? aspect : 16 / 9
  let width = availableWidth
  let height = width / safeAspect
  if (height > availableHeight) {
    height = availableHeight
    width = height * safeAspect
  }

  return {
    width: Math.floor(Math.min(width, availableWidth)),
    height: Math.floor(Math.min(height, availableHeight)),
  }
}

function isSameTheaterPlayerSize(
  current: TheaterPlayerSize,
  next: TheaterPlayerSize,
): boolean {
  return Math.abs(current.width - next.width) < 1 && Math.abs(current.height - next.height) < 1
}

export function useTheaterPlayerSize(
  wrapperRef: RefObject<HTMLDivElement | null>,
  enabled: boolean,
  aspect: number,
  heightOffset = 0,
): TheaterPlayerSize | null {
  const [size, setSize] = useState<TheaterPlayerSize | null>(null)

  useEffect(() => {
    if (!enabled) {
      setSize(null)
      return
    }

    const el = wrapperRef.current
    if (!el) {
      setSize(null)
      return
    }

    let raf = 0

    const update = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const next = calculateTheaterPlayerSize(el.clientWidth, el.clientHeight, aspect, heightOffset)
        setSize(prev => {
          if (!next || !prev) return next
          return isSameTheaterPlayerSize(prev, next) ? prev : next
        })
      })
    }

    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    window.addEventListener('resize', update, { passive: true })
    window.visualViewport?.addEventListener('resize', update, { passive: true })

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      window.removeEventListener('resize', update)
      window.visualViewport?.removeEventListener('resize', update)
    }
  }, [enabled, aspect, heightOffset])

  return size
}
