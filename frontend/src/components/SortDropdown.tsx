import { memo, useEffect, useRef, useState } from 'react'

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
  const menuRef = useRef<HTMLDivElement>(null)
  const currentLabel = options.find(opt => opt.key === current)?.label || '排序'

  const selectOption = (key: string) => {
    onChange(key)
    setOpen(false)
  }

  useEffect(() => {
    if (!open) return

    const handlePointerDown = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
      }
    }

    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  if (variant === 'menu') {
    return (
      <div ref={menuRef} className="relative inline-flex">
        <button
          type="button"
          onClick={() => setOpen(value => !value)}
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

        <div
          className={`absolute right-0 top-10 z-[100] min-w-[132px] origin-top-right overflow-hidden rounded-[18px] border border-white/[0.14] bg-[rgba(8,10,18,0.72)] p-1.5 shadow-[0_24px_80px_rgba(0,0,0,0.42),inset_0_1px_0_rgba(255,255,255,0.10)] backdrop-blur-[24px] backdrop-saturate-[160%] transition-all duration-200 ${
            open ? 'pointer-events-auto translate-y-0 scale-100 opacity-100' : 'pointer-events-none -translate-y-2 scale-95 opacity-0'
          }`}
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
