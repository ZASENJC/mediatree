interface CoverItem {
  url: string
  source: string
  width?: number
  height?: number
  language?: string
}

interface CoverPickerModalProps {
  title?: string
  subtitle?: string
  covers: CoverItem[]
  backdrops?: CoverItem[]
  loading?: boolean
  onSelectCover: (url: string) => Promise<void>
  onSelectBackdrop?: (url: string) => void
  onUpload?: () => void
  onClose: () => void
}

export default function CoverPickerModal({
  title,
  subtitle,
  covers,
  backdrops,
  loading,
  onSelectCover,
  onSelectBackdrop,
  onUpload,
  onClose,
}: CoverPickerModalProps) {
  return (
    <div className="glass-modal max-h-[85vh] w-full max-w-3xl overflow-y-auto p-4 sm:p-5">
      <h2 className="mb-1 text-lg font-bold text-white">{title || '更换封面'}</h2>
      <p className="mb-4 text-xs text-gray-500">
        {subtitle || (backdrops && backdrops.length > 0
          ? '选择封面图或背景图应用'
          : `${covers.length} 张可选 · 点击即可应用`)}
      </p>

      {loading && (
        <div className="flex items-center justify-center py-8">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-apple-blue border-t-transparent" />
        </div>
      )}

      {!loading && covers.length > 0 && (
        <>
          <h3 className="mb-2 text-sm font-medium text-gray-400">封面图 (竖屏海报)</h3>
          <div className="mb-4 grid grid-cols-3 gap-3 sm:grid-cols-4">
            {covers.map((c, i) => (
              <div
                key={i}
                onClick={() => onSelectCover(c.url)}
                className="group cursor-pointer overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] transition-all hover:border-apple-blue/40 hover:shadow-glow"
              >
                <div className="aspect-[2/3]">
                  <img src={c.url} alt={c.source} className="h-full w-full object-cover" />
                </div>
                <div className="p-2">
                  <p className="truncate text-[10px] text-gray-500">
                    {c.language ? c.language.toUpperCase() : c.source}
                  </p>
                  {c.width && c.height && (
                    <p className="text-[9px] text-gray-600">{c.width}x{c.height}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {!loading && backdrops && backdrops.length > 0 && (
        <>
          <h3 className="mb-2 mt-4 text-sm font-medium text-gray-400">背景图 (横屏 Fanart)</h3>
          <div className="mb-4 grid grid-cols-2 gap-3">
            {backdrops.map((b, i) => (
              <div
                key={i}
                onClick={() => onSelectBackdrop?.(b.url)}
                className="cursor-pointer overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] transition-all hover:border-apple-blue/40 hover:shadow-glow"
              >
                <div className="aspect-video">
                  <img src={b.url} alt={b.source} className="h-full w-full object-cover" />
                </div>
                <div className="p-1 text-center text-[9px] text-gray-500">{b.source}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {!loading && covers.length === 0 && (!backdrops || backdrops.length === 0) && (
        <p className="py-4 text-center text-sm text-gray-500">没有可用的封面或背景图</p>
      )}

      <div className="flex gap-3">
        {onUpload && (
          <button onClick={onUpload} className="glass-button flex-1 py-2 text-sm text-gray-300">
            上传本地图片
          </button>
        )}
        <button onClick={onClose} className="glass-button flex-1 py-2 text-sm text-gray-300">
          取消
        </button>
      </div>
    </div>
  )
}