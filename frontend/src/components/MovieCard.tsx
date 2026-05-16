import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, Movie } from '../api'
import { saveScrollPos } from '../scroll'
import { WatchedBadge } from './WatchedBadge'
import ContextMenu, { ContextMenuItem } from './ContextMenu'
import EditModal from './EditModal'
import { clearCache } from '../cache'

interface MovieCardProps {
  movie: Movie
  onUpdated?: () => void
}

export function MovieCard({ movie, onUpdated }: MovieCardProps) {
  const navigate = useNavigate()
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null)
  const [showEdit, setShowEdit] = useState(false)
  const [showManualSearch, setShowManualSearch] = useState(false)
  const [manualQuery, setManualQuery] = useState('')
  const [manualScraper, setManualScraper] = useState('')
  const [showCoverPicker, setShowCoverPicker] = useState(false)
  const [altCovers, setAltCovers] = useState<{ url: string; source: string }[]>([])
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searching, setSearching] = useState(false)

  const goDetail = () => {
    saveScrollPos()
    navigate(`/detail/${movie.id}`)
  }

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault()
    setContextMenu({ x: e.clientX, y: e.clientY })
  }

  const isEpisode = movie.tmdb_type === 'tv' && movie.tmdb_episode != null
  const hasEpisodeStill = !!(isEpisode && movie.episode_still)
  const coverSrc = hasEpisodeStill
    ? api.episodeStillUrl(movie.id)
    : api.coverUrl(movie.id)
  const displayTitle = isEpisode
    ? `E${String(movie.tmdb_episode).padStart(2, '0')} ${movie.episode_title || movie.title || movie.code}`
    : (movie.title || movie.code)

  const handleRescrape = useCallback(async () => {
    try {
      await api.rescrapeMovie(movie.id)
      clearCache()
      onUpdated?.()
    } catch {
      console.error('Rescrape failed for movie', movie.id)
    }
  }, [movie.id, onUpdated])

  const handleSearch = useCallback(async () => {
    if (!manualQuery.trim()) return
    setSearching(true)
    try {
      const data = await api.searchScrape(manualQuery.trim(), manualScraper || undefined)
      setSearchResults(data.results || [])
      if ((data.results || []).length === 0) {
        alert('没有找到匹配结果')
      }
    } catch {
      console.error('Search scrape failed')
    }
    setSearching(false)
  }, [manualQuery, manualScraper])

  const handleSelectSearchResult = useCallback(async (result: any) => {
    try {
      await api.manualScrapeMovie(movie.id, result.title, result.source)
      clearCache()
      setShowManualSearch(false)
      setSearchResults([])
      setManualQuery('')
      onUpdated?.()
    } catch {
      console.error('Failed to apply scrape result')
    }
  }, [movie.id, onUpdated])

  const handleLoadAltCovers = useCallback(async () => {
    try {
      const data = await api.getAlternativeCovers(movie.id)
      if (!data.covers || data.covers.length === 0) {
        alert('没有找到备用封面')
        return
      }
      setAltCovers(data.covers)
      setShowCoverPicker(true)
    } catch {
      console.error('Failed to load alternative covers for movie', movie.id)
    }
  }, [movie.id])

  const handleSelectCover = useCallback(async (url: string) => {
    try {
      await api.changeCover(movie.id, url)
      clearCache()
      setShowCoverPicker(false)
      onUpdated?.()
    } catch {
      console.error('Failed to change cover for movie', movie.id)
    }
  }, [movie.id, onUpdated])

  const handleUploadCover = useCallback(() => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/*'
    input.onchange = async () => {
      const file = input.files?.[0]
      if (!file) return
      try {
        await api.changeCover(movie.id, file)
        clearCache()
        onUpdated?.()
      } catch {
        console.error('Failed to upload cover for movie', movie.id)
      }
    }
    input.click()
  }, [movie.id, onUpdated])

  const handleDelete = useCallback(async () => {
    if (!confirm(`确定要删除 "${movie.title || movie.code}"？\n此操作不可撤销。`)) return
    try {
      await api.deleteMovie(movie.id)
      clearCache()
      onUpdated?.()
    } catch {
      alert('删除失败，请检查权限')
    }
  }, [movie.id, onUpdated])

  const menuItems: ContextMenuItem[] = [
    { label: '重新刮削', onClick: handleRescrape },
    { label: '手动刮削', onClick: () => setShowManualSearch(true) },
    { label: '更换封面', onClick: handleLoadAltCovers },
    { label: '编辑信息', onClick: () => setShowEdit(true) },
    { label: '删除', danger: true, onClick: handleDelete },
  ]

  return (
    <>
      <div
        onClick={goDetail}
        onContextMenu={handleContextMenu}
        className="group cursor-pointer bg-dark-800 rounded-xl overflow-hidden border border-dark-700 hover:border-blue-500/40 transition-all hover:bg-dark-700/50"
      >
        <div className={`${hasEpisodeStill ? 'aspect-video' : 'aspect-[2/3]'} bg-dark-700 relative`}>
          <img
            src={coverSrc}
            alt={movie.code}
            className="w-full h-full object-cover"
            loading="lazy"
            onError={(e) => {
              const img = e.target as HTMLImageElement
              if (img.src === movie.episode_still) {
                img.src = api.coverUrl(movie.id)
              } else {
                img.style.display = 'none'
              }
            }}
          />
          <WatchedBadge watched={!!(movie.tags || []).includes('watched')} />

          {movie.javdb_score != null && movie.javdb_score > 0 && (
            <span className="absolute top-2 right-2 bg-dark-900/80 px-1.5 py-0.5 rounded text-xs text-yellow-400 z-10">
              {movie.javdb_score.toFixed(1)}
            </span>
          )}
          {movie.javdb_likes != null && movie.javdb_likes > 0 && (
            <span className="absolute top-7 right-2 bg-dark-900/80 px-1.5 py-0.5 rounded text-xs text-pink-400 z-10">
              {movie.javdb_likes >= 1000 ? `${(movie.javdb_likes / 1000).toFixed(1)}k` : movie.javdb_likes}
            </span>
          )}

          {isEpisode && (
            <span className="absolute top-2 left-2 bg-blue-600/85 px-1.5 py-0.5 rounded text-[10px] text-white z-10 font-medium">
              S{movie.tmdb_season}·E{movie.tmdb_episode}
            </span>
          )}

          <div className="absolute inset-0 bg-gradient-to-t from-dark-900 via-dark-900/30 to-transparent" />
          <div className="absolute bottom-0 left-0 right-0 p-3">
            <p className="text-sm font-semibold text-white truncate">{displayTitle}</p>
            <p className="text-xs text-gray-400 mt-0.5 truncate">{movie.code}</p>
          </div>
        </div>
      </div>

      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          items={menuItems}
          onClose={() => setContextMenu(null)}
        />
      )}

      {showEdit && (
        <EditModal
          movie={movie}
          onClose={() => setShowEdit(false)}
          onSaved={() => { onUpdated?.() }}
        />
      )}

      {showManualSearch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="bg-dark-800 border border-dark-600 rounded-xl p-5 w-full max-w-lg mx-4 shadow-2xl max-h-[80vh] overflow-y-auto">
            <h2 className="text-lg font-bold mb-3">手动刮削</h2>
            <p className="text-xs text-gray-500 mb-3">输入搜索关键词，选择刮削器</p>
            <div className="flex gap-2 mb-3">
              <input
                type="text" value={manualQuery} onChange={e => { setManualQuery(e.target.value); setSearchResults([]) }}
                onKeyDown={e => { if (e.key === 'Enter') handleSearch() }}
                placeholder="搜索关键词" autoFocus
                className="flex-1 px-3 py-2 bg-dark-700 border border-dark-600 rounded text-sm text-white focus:outline-none focus:border-blue-500"
              />
              <select
                value={manualScraper} onChange={e => setManualScraper(e.target.value)}
                className="px-3 py-2 bg-dark-700 border border-dark-600 rounded text-sm text-gray-300 focus:outline-none focus:border-blue-500"
              >
                <option value="">自动</option>
                <option value="tmdb">TMDB</option>
                <option value="bangumi">Bangumi</option>
                <option value="javdatabase">Javdatabase</option>
              </select>
              <button onClick={handleSearch} disabled={searching}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-sm">
                {searching ? '搜索中...' : '搜索'}
              </button>
            </div>

            {searchResults.length > 0 && (
              <div className="grid grid-cols-3 gap-3 max-h-[50vh] overflow-y-auto">
                {searchResults.map((r, i) => (
                  <div key={i}
                    onClick={() => handleSelectSearchResult(r)}
                    className="bg-dark-700 rounded overflow-hidden border border-dark-600 hover:border-blue-500 cursor-pointer transition-colors"
                  >
                    <div className="aspect-[2/3] bg-dark-800">
                      {r.poster_url ? (
                        <img src={r.poster_url} alt={r.title} className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-xs text-gray-600 p-2 text-center">{r.title}</div>
                      )}
                    </div>
                    <div className="p-2">
                      <p className="text-xs font-medium text-white truncate">{r.title}</p>
                      <p className="text-[10px] text-gray-500 mt-0.5">{r.year}{r.original_title ? ` · ${r.original_title}` : ''}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="flex gap-3 mt-4">
              <button onClick={() => { setShowManualSearch(false); setSearchResults([]) }}
                className="flex-1 py-2 bg-dark-700 hover:bg-dark-600 rounded text-sm text-gray-400">
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {showCoverPicker && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="bg-dark-800 border border-dark-600 rounded-xl p-5 w-full max-w-lg mx-4 shadow-2xl max-h-[80vh] overflow-y-auto">
            <h2 className="text-lg font-bold mb-3">更换封面</h2>
            <p className="text-xs text-gray-500 mb-3">选择封面或上传本地图片</p>
            <div className="grid grid-cols-3 gap-3 mb-4">
              {altCovers.map((c, i) => (
                <div key={i}
                  onClick={() => handleSelectCover(c.url)}
                  className="aspect-[2/3] bg-dark-700 rounded overflow-hidden border border-dark-600 hover:border-blue-500 cursor-pointer transition-colors"
                >
                  <img src={c.url} alt={c.source} className="w-full h-full object-cover" />
                </div>
              ))}
            </div>
            <div className="flex gap-3">
              <button onClick={handleUploadCover}
                className="flex-1 py-2 bg-dark-700 hover:bg-dark-600 rounded text-sm text-gray-400">
                上传本地图片
              </button>
              <button onClick={() => setShowCoverPicker(false)}
                className="flex-1 py-2 bg-dark-700 hover:bg-dark-600 rounded text-sm text-gray-400">
                取消
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
