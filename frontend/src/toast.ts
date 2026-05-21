import { useState, useEffect, useCallback } from 'react'

type ToastItem = { id: number; message: string }

let _id = 0
let _addToast: ((msg: string) => void) | null = null

export function showToast(message: string) {
  if (_addToast) _addToast(message)
}

export function useToastController() {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const add = useCallback((message: string) => {
    const id = ++_id
    setToasts(prev => [...prev, { id, message }])
    window.setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 3000)
  }, [])

  useEffect(() => {
    _addToast = add
    return () => { _addToast = null }
  }, [add])

  return toasts
}
