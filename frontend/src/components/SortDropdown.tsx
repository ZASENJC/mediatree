import { memo, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

interface SortOption {
  key: string
  label: string
}

interface Props {
  options: SortOption[]
  current: string
  onChange: (key: string) => void
  variant?: 'select' | 'menu'
}

export default memo(function SortDropdown({ options, current, onChange, variant = 'select' }: Props) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0 })
  const [positionReady, setPositionReady] = useState(false)
  const currentLabel = options.find(opt => opt.key === current)?.label || '排序'

  const updateMenuPosition = () => {
    const trigger = triggerRef.current
    if (!trigger) return false

    const margin = 8
    const gap = 8
    const rect = trigger.getBoundingClientRect()
    const menuWidth = menuRef.current?.offsetWidth || 132
    const menuHeight = menuRef.current?.offsetHeight || (options.length * 34 + 12)

    let left = rect.right - menuWidth
    left = Math.max(margin, Math.min(left, window.innerWidth - menuWidth - margin))

    let top = rect.bottom + gap
    if (top + menuHeight > window.innerHeight - margin) {
      top = Math.max(margin, rect.top - menuHeight - gap)
    }

    setMenuPosition({ top, left })
    setPositionReady(true)
    return true
  }

  const selectOption = (key: string) => {
    onChange(key)
    setOpen(false)
    setPositionReady(false)
  }

  const toggleMenu = () => {
    if (open) {
      setOpen(false)
      setPositionReady(false)
      return
    }
    if (updateMenuPosition()) {
      setOpen(true)
    }
  }

  useEffect(() => {
    if (!open) return

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node
      if (!triggerRef.current?.contains(target) && !menuRef.current?.contains(target)) {
        setOpen(false)
        setPositionReady(false)
      }
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
        setPositionReady(false)
      }
    }

    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  useLayoutEffect(() => {
    if (!open) return

    updateMenuPosition()
    window.addEventListener('resize', updateMenuPosition)
    window.addEventListener('scroll', updateMenuPosition, true)
    return () => {
      window.removeEventListener('resize', updateMenuPosition)
      window.removeEventListener('scroll', updateMenuPosition, true)
    }
  }, [open, options.length])

  if (variant === 'menu') {
    const menu = (
      <div
        ref={menuRef}
        className="fixed z-[9999] min-w-[132px] origin-top-right translate-y-0 scale-100 overflow-hidden rounded-[18px] border border-white/[0.14] bg-[rgba(8,10,18,0.72)] p-1.5 opacity-100 shadow-[0_24px_80px_rgba(0,0,0,0.42),inset_0_1px_0_rgba(255,255,255,0.10)] backdrop-blur-[24px] backdrop-saturate-[160%] transition-[opacity,transform] duration-150"
        style={{ top: menuPosition.top, left: menuPosition.left }}
        onPointerDown={e => e.stopPropagation()}
        role="menu"
        aria-label="排序方式"
      >
        {options.map(opt => {
          const active = opt.key === current
          return (
            <button
              key={opt.key}
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                selectOption(opt.key)
              }}
              onPointerDown={e => e.stopPropagation()}
              className={`flex w-full select-none items-center justify-between rounded-xl border-0 bg-transparent px-3 py-[7px] text-left text-sm transition-colors duration-150 focus:outline-none [-webkit-tap-highlight-color:transparent] ${
                active
                  ? 'bg-white/[0.12] text-white'
                  : 'text-gray-300 hover:bg-white/[0.12] hover:text-white'
              }`}
              role="menuitemradio"
              aria-checked={active}
            >
              <span className="truncate">{opt.label}</span>
              {active && (
                <span className="ml-2 h-1.5 w-1.5 shrink-0 rounded-full bg-white/90" aria-hidden="true" />
              )}
            </button>
          )
        })}
      </div>
    )

    return (
      <div ref={triggerRef} className="relative inline-flex">
        <button
          type="button"
          onClick={toggleMenu}
          className={`inline-flex h-8 w-12 select-none items-center justify-center rounded-full text-gray-200 shadow-[0_10px_26px_rgba(0,0,0,0.26),inset_0_1px_0_rgba(255,255,255,0.12)] backdrop-blur-xl transition-all duration-200 hover:bg-white/[0.14] active:scale-95 focus:outline-none [-webkit-tap-highlight-color:transparent] ${
            open ? 'bg-white/[0.16]' : 'bg-white/[0.08]'
          }`}
          aria-label={`排序方式：${currentLabel}`}
          aria-expanded={open}
          aria-haspopup="menu"
        >
          <span className="relative h-3.5 w-4" aria-hidden="true">
            <span className={`absolute left-0 top-0 h-0.5 w-4 rounded-full bg-current transition-transform duration-200 ${open ? 'translate-y-0.5' : ''}`} />
            <span className="absolute left-0 top-1.5 h-0.5 w-4 rounded-full bg-current" />
            <span className={`absolute bottom-0 left-0 h-0.5 w-4 rounded-full bg-current transition-transform duration-200 ${open ? '-translate-y-0.5' : ''}`} />
          </span>
        </button>
        {open && positionReady && typeof document !== 'undefined' && createPortal(menu, document.body)}
      </div>
    )
  }

  return (
    <select
      value={current}
      onChange={e => onChange(e.target.value)}
      className="glass-input cursor-pointer appearance-none px-3 py-1.5 text-center text-xs text-gray-300"
      style={{ textAlignLast: 'center' }}
      aria-label="排序方式"
    >
      {options.map(opt => (
        <option key={opt.key} value={opt.key}>{opt.label}</option>
      ))}
    </select>
  )
})
