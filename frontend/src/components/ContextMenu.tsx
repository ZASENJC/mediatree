import { useEffect, useRef, useState } from 'react'

export interface ContextMenuItem {
  label: string
  danger?: boolean
  onClick: () => void
}

interface Props {
  x: number
  y: number
  items: ContextMenuItem[]
  onClose: () => void
}

let activeOnClose: (() => void) | null = null

const containerStyle: React.CSSProperties = {
  position: 'fixed',
  zIndex: 100,
  background: 'rgba(8, 10, 18, 0.72)',
  border: '1px solid rgba(255, 255, 255, 0.14)',
  borderRadius: 18,
  boxShadow: '0 24px 80px rgba(0,0,0,0.42), inset 0 1px 0 rgba(255,255,255,0.10)',
  backdropFilter: 'blur(24px) saturate(160%)',
  padding: '6px',
  minWidth: 132,
}

const itemBase: React.CSSProperties = {
  display: 'block',
  width: '100%',
  textAlign: 'left',
  padding: '7px 12px',
  fontSize: 14,
  borderRadius: 12,
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  color: '#d1d5db',
  transition: 'background 0.15s, color 0.15s',
}

const itemHover: React.CSSProperties = {
  background: 'rgba(255,255,255,0.12)',
  color: '#fff',
}

const itemDanger: React.CSSProperties = {
  ...itemBase,
  color: '#fb7185',
}

const itemDangerHover: React.CSSProperties = {
  background: 'rgba(255,55,95,0.16)',
  color: '#fecdd3',
}

export default function ContextMenu({ x, y, items, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ x, y })
  const [hoverIdx, setHoverIdx] = useState(-1)

  useEffect(() => {
    if (activeOnClose && activeOnClose !== onClose) {
      activeOnClose()
    }
    activeOnClose = onClose
    return () => {
      if (activeOnClose === onClose) activeOnClose = null
    }
  }, [onClose])

  useEffect(() => {
    if (ref.current) {
      const rect = ref.current.getBoundingClientRect()
      let nx = x
      let ny = y
      if (nx + rect.width > window.innerWidth) nx = window.innerWidth - rect.width - 8
      if (ny + rect.height > window.innerHeight) ny = window.innerHeight - rect.height - 8
      setPos({ x: nx, y: ny })
    }
  }, [x, y])

  useEffect(() => {
    let cleanup: (() => void) | null = null
    const timer = setTimeout(() => {
      const handler = () => onClose()
      document.addEventListener('click', handler)
      document.addEventListener('contextmenu', handler)
      cleanup = () => {
        document.removeEventListener('click', handler)
        document.removeEventListener('contextmenu', handler)
      }
    }, 0)
    return () => {
      clearTimeout(timer)
      cleanup?.()
    }
  }, [onClose])

  return (
    <div ref={ref} style={{ ...containerStyle, left: pos.x, top: pos.y }}>
      {items.map((item, i) => (
        <button
          key={i}
          onClick={(e) => {
            e.stopPropagation()
            item.onClick()
            onClose()
          }}
          onMouseEnter={() => setHoverIdx(i)}
          onMouseLeave={() => setHoverIdx(-1)}
          style={(() => {
            if (item.danger) {
              return hoverIdx === i ? { ...itemDanger, ...itemDangerHover } : itemDanger
            }
            return hoverIdx === i ? { ...itemBase, ...itemHover } : itemBase
          })()}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}
