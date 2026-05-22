import { type MediaRoot } from '../api'

interface LibraryModalProps {
  libraries: MediaRoot[]
  activeLib: string
  onSelect: (lib: MediaRoot) => void
  onClose: () => void
}

export default function LibraryModal({ libraries, activeLib, onSelect, onClose }: LibraryModalProps) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4 backdrop-blur-2xl">
      <div className="glass-modal w-full max-w-sm p-6">
        <h2 className="mb-1 text-lg font-bold">切换媒体库</h2>
        <p className="mb-4 text-xs text-gray-500">选择要浏览的媒体库</p>
        <div className="space-y-2">
          {libraries.map((lib) => (
            <button
              key={lib.path}
              onClick={() => onSelect(lib)}
              className={`w-full rounded-2xl border px-3 py-2.5 text-left transition-all ${
                lib.path === activeLib
                  ? 'border-apple-blue/40 bg-apple-blue/15 text-apple-blue'
                  : 'border-white/10 bg-white/[0.06] text-gray-300 hover:border-white/20 hover:bg-white/[0.1]'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-1.5 text-sm font-medium">
                  {lib.locked && (
                    <svg className="h-3 w-3 text-apple-yellow" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                    </svg>
                  )}
                  {lib.label}
                </span>
                {lib.movie_count > 0 && (
                  <span className="text-xs text-gray-500">{lib.movie_count} 部</span>
                )}
              </div>
            </button>
          ))}
        </div>
        <button
          onClick={onClose}
          className="mt-4 w-full rounded-full py-2 text-sm text-gray-500 transition-colors hover:bg-white/10 hover:text-white"
        >
          取消
        </button>
      </div>
    </div>
  )
}
