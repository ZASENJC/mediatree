export type GestureCleanup = () => void
export type SeekPreviewPayload = { target: number; delta: number; duration: number }

type GestureZone = 'left' | 'center' | 'right'
type GestureHandler = (gesture: string) => void
type SeekPreviewHandler = (payload: SeekPreviewPayload | null, commit?: boolean) => void
type SeekState = { current: number; duration: number; playing: boolean; disabled: boolean }

export function bindGestureLayer(
  element: HTMLElement,
  isMobile: () => boolean,
  onGesture: GestureHandler,
  onSeekPreview: SeekPreviewHandler,
  getSeekState: () => SeekState,
): GestureCleanup {
  let lastTap = { time: 0, x: 0, y: 0, zone: 'center' as GestureZone }
  let pointer = { id: -1, type: '', x: 0, y: 0, zone: 'center' as GestureZone, down: false, longPressed: false }
  let seekGesture: null | { startX: number; startY: number; base: number; duration: number; playing: boolean; target: number } = null
  let timer = 0

  const zoneFor = (clientX: number): GestureZone => {
    const rect = element.getBoundingClientRect()
    const x = clientX - rect.left
    if (x < rect.width / 3) return 'left'
    if (x > rect.width * 2 / 3) return 'right'
    return 'center'
  }
  const clearTimer = () => {
    window.clearTimeout(timer)
    timer = 0
  }
  const stopLongPress = () => {
    if (pointer.longPressed) {
      pointer.longPressed = false
      onGesture('speed-hold-end')
    }
  }
  const onPointerDown = (event: PointerEvent) => {
    if (event.pointerType === 'mouse' && event.button !== 0) return
    const zone = zoneFor(event.clientX)
    pointer = {
      id: event.pointerId,
      type: event.pointerType,
      x: event.clientX,
      y: event.clientY,
      zone,
      down: true,
      longPressed: false,
    }
    element.setPointerCapture?.(event.pointerId)
    clearTimer()
    const longPressEnabled = isMobile() || event.pointerType !== 'mouse' || zone !== 'center'
    if (longPressEnabled) {
      timer = window.setTimeout(() => {
        if (!pointer.down) return
        pointer.longPressed = true
        onGesture('speed-hold-start')
      }, 420)
    }
  }
  const onPointerMove = (event: PointerEvent) => {
    if (!pointer.down || pointer.id !== event.pointerId) return
    const dx = Math.abs(event.clientX - pointer.x)
    const dy = Math.abs(event.clientY - pointer.y)
    const touchLike = isMobile() || pointer.type !== 'mouse'
    if (touchLike && !pointer.longPressed) {
      if (seekGesture) {
        event.preventDefault()
        const rawDelta = event.clientX - seekGesture.startX
        const secondsPerPx = seekGesture.duration > 7200 ? 0.8 : seekGesture.duration > 3600 ? 0.5 : 0.3
        const delta = Math.round(rawDelta * secondsPerPx)
        const target = Math.max(0, Math.min(seekGesture.duration, seekGesture.base + delta))
        seekGesture.target = target
        onSeekPreview({ target, delta, duration: seekGesture.duration })
        return
      }
      if (dx > 20 && dx > dy * 1.35) {
        const state = getSeekState()
        if (!state.disabled && state.duration > 0 && isFinite(state.duration)) {
          clearTimer()
          seekGesture = {
            startX: pointer.x,
            startY: pointer.y,
            base: state.current,
            duration: state.duration,
            playing: state.playing,
            target: state.current,
          }
          event.preventDefault()
          onSeekPreview({ target: state.current, delta: 0, duration: state.duration })
          return
        }
      }
    }
    if ((dx > 28 || dy > 28) && !pointer.longPressed) clearTimer()
  }
  const onPointerUp = (event: PointerEvent) => {
    if (!pointer.down || pointer.id !== event.pointerId) return
    clearTimer()
    if (seekGesture) {
      const sg = seekGesture
      seekGesture = null
      pointer.down = false
      element.releasePointerCapture?.(event.pointerId)
      onSeekPreview({ target: sg.target, delta: Math.round(sg.target - sg.base), duration: sg.duration }, true)
      return
    }
    const state = pointer
    pointer.down = false
    element.releasePointerCapture?.(event.pointerId)
    if (state.longPressed) {
      stopLongPress()
      return
    }
    const dx = Math.abs(event.clientX - state.x)
    const dy = Math.abs(event.clientY - state.y)
    if (dx > 28 || dy > 28) return
    const touchLike = isMobile() || state.type !== 'mouse'
    if (!touchLike) {
      onGesture('tap')
      return
    }
    const now = Date.now()
    const samePlace = now - lastTap.time < 330
      && Math.abs(event.clientX - lastTap.x) < 28
      && Math.abs(event.clientY - lastTap.y) < 28
      && lastTap.zone === state.zone
    if (samePlace) {
      onGesture(`doubletap-${state.zone}`)
      lastTap = { time: 0, x: 0, y: 0, zone: state.zone }
      return
    }
    lastTap = { time: now, x: event.clientX, y: event.clientY, zone: state.zone }
  }
  const onPointerCancel = (event: PointerEvent) => {
    if (pointer.id !== event.pointerId) return
    clearTimer()
    pointer.down = false
    seekGesture = null
    onSeekPreview(null)
    stopLongPress()
  }

  element.addEventListener('pointerdown', onPointerDown)
  element.addEventListener('pointermove', onPointerMove)
  element.addEventListener('pointerup', onPointerUp)
  element.addEventListener('pointercancel', onPointerCancel)
  return () => {
    clearTimer()
    element.removeEventListener('pointerdown', onPointerDown)
    element.removeEventListener('pointermove', onPointerMove)
    element.removeEventListener('pointerup', onPointerUp)
    element.removeEventListener('pointercancel', onPointerCancel)
  }
}
