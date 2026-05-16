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
  background: '#181818',
  border: '1px solid #303030',
  borderRadius: 8,
  boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
  padding: '4px 0',
  minWidth: 100,
}

const itemBase: React.CSSProperties = {
  display: 'block',
  width: 'calc(100% - 8px)',
  textAlign: 'left',
  padding: '4px 12px',
  fontSize: 14,
  margin: '0 4px',
  borderRadius: 4,
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  color: '#d1d5db',
  transition: 'background 0.15s, color 0.15s',
}

const itemHover: React.CSSProperties = {
  background: '#303030',
  color: '#fff',
}

const itemDanger: React.CSSProperties = {
  ...itemBase,
  color: '#f87171',
}

const itemDangerHover: React.CSSProperties = {
  background: 'rgba(239,68,68,0.15)',
  color: '#fca5a5',
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
