import { useState, useEffect, useCallback } from 'react'

export interface TaskProgress {
  visible: boolean
  status: string
  done: number
  total: number
}

type TaskProgressListener = (state: TaskProgress) => void
const listeners = new Set<TaskProgressListener>()

export function showTaskProgress(state: Partial<Omit<TaskProgress, 'visible'>> & { visible?: boolean }) {
  listeners.forEach(fn => fn({ visible: true, status: '', done: 0, total: 0, ...state }))
}

export function hideTaskProgress() {
  listeners.forEach(fn => fn({ visible: false, status: '', done: 0, total: 0 }))
}

export function useTaskProgressController() {
  const [state, setState] = useState<TaskProgress>({ visible: false, status: '', done: 0, total: 0 })

  const handler = useCallback((s: TaskProgress) => {
    setState(s)
  }, [])

  useEffect(() => {
    listeners.add(handler)
    return () => { listeners.delete(handler) }
  }, [handler])

  return state
}
