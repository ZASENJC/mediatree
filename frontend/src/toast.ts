import { useState, useEffect, useCallback } from 'react'

type ToastItem = { id: number; message: string }

type ToastListener = (message: string) => void
const listeners = new Set<ToastListener>()

export function showToast(message: string) {
  listeners.forEach(fn => fn(message))
}

export function useToastController() {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const add = useCallback((message: string) => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, message }])
    window.setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 3000)
  }, [])

  useEffect(() => {
    listeners.add(add)
    return () => { listeners.delete(add) }
  }, [add])

  return toasts
}
