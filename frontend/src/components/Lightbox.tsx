import { useEffect, useCallback } from 'react'

type LightboxImage = string | { src: string; fallback?: string; alt?: string }

interface Props {
  images: LightboxImage[]
  index: number
  onClose: () => void
  onPrev: () => void
  onNext: () => void
}

export default function Lightbox({ images, index, onClose, onPrev, onNext }: Props) {
  const handleKey = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose()
    if (e.key === 'ArrowLeft') onPrev()
    if (e.key === 'ArrowRight') onNext()
  }, [onClose, onPrev, onNext])

  useEffect(() => {
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [handleKey])

  if (index < 0 || index >= images.length) return null

  const current = images[index]
  const image = typeof current === 'string' ? { src: current, alt: `thumbnail ${index + 1}` } : current

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/45 p-4 backdrop-blur-2xl"
      onClick={onClose}
    >
      <button
        onClick={(e) => { e.stopPropagation(); onClose() }}
        className="glass-button absolute right-4 top-4 z-10 h-10 w-10 p-0 text-xl text-white/70 hover:text-white"
      >
        &times;
      </button>

      <span className="glass-chip absolute left-4 top-4 z-10 text-gray-300">
        {index + 1} / {images.length}
      </span>

      {images.length > 1 && (
        <>
          <button
            onClick={(e) => { e.stopPropagation(); onPrev() }}
            className="glass-button absolute left-4 top-1/2 z-10 h-12 w-12 -translate-y-1/2 p-0 text-3xl text-white/70 hover:text-white"
          >
            &#8249;
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onNext() }}
            className="glass-button absolute right-4 top-1/2 z-10 h-12 w-12 -translate-y-1/2 p-0 text-3xl text-white/70 hover:text-white"
          >
            &#8250;
          </button>
        </>
      )}

      <img
        src={image.src}
        alt={image.alt || `thumbnail ${index + 1}`}
        className="max-h-[90vh] max-w-[90vw] rounded-3xl border border-white/10 object-contain shadow-glass"
        onClick={(e) => e.stopPropagation()}
        onError={(e) => {
          if (image.fallback && (e.currentTarget as HTMLImageElement).src !== image.fallback) {
            ;(e.currentTarget as HTMLImageElement).src = image.fallback
          }
        }}
      />
    </div>
  )
}
