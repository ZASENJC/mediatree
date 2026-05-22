/**
 * Adaptive polling helper with idle exponential backoff.
 * - activeInterval: polling interval when a scan is in progress (default 2s)
 * - idleMin→idleMax: exponential backoff when idle, doubling each poll (default 5→30s)
 */
export function createAdaptiveInterval(
  activeInterval = 2000,
  idleMin = 5000,
  idleMax = 30000,
) {
  let currentIdle = idleMin

  return {
    /** Call when a scan is active — keep fast polling */
    active() {
      currentIdle = idleMin
      return activeInterval
    },
    /** Call when no scan is active — exponentially back off */
    idle() {
      const delay = currentIdle
      currentIdle = Math.min(currentIdle * 2, idleMax)
      return delay
    },
  }
}
