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
  const [applying, setApplying] = useState(false)
  const [coverVersion, setCoverVersion] = useState(() => movie.updated_at || '')

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
  const versionSuffix = coverVersion ? `?v=${encodeURIComponent(coverVersion)}` : ''
  const coverSrc = (hasEpisodeStill
    ? api.episodeStillUrl(movie.id)
    : api.coverUrl(movie.id)) + versionSuffix
  const displayTitle = isEpisode
    ? `E${String(movie.tmdb_episode).padStart(2, '0')} ${movie.episode_title || movie.title || movie.code}`
    : (movie.title || movie.code)
  const watched = !!(movie.tags || []).includes('watched')
  const progressPercent = Math.max(0, Math.min(100, movie.progress_percent || 0))
  const showProgress = !watched && progressPercent > 0 && progressPercent < 90

  const handleRescrape = useCallback(async () => {
    try {
      await api.rescrapeMovie(movie.id)
      clearCache()
      setCoverVersion(String(Date.now()))
      onUpdated?.()
    } catch (err) {
      console.error('Rescrape failed for movie', movie.id, err)
      alert(`刮削失败：${err instanceof Error ? err.message : '请查看后端日志'}`)
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
    if (applying) return
    setApplying(true)
    try {
      await api.manualScrapeMovie(movie.id, result.title, result.source_id, result.media_type, result.source)
      clearCache()
      setCoverVersion(String(Date.now()))
      setShowManualSearch(false)
      setSearchResults([])
      setManualQuery('')
      onUpdated?.()
    } catch {
      console.error('Failed to apply scrape result')
    } finally {
      setApplying(false)
    }
  }, [movie.id, onUpdated, applying])

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
      setCoverVersion(String(Date.now()))
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
        setCoverVersion(String(Date.now()))
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
        className="glass-card apple-focus group cursor-pointer overflow-hidden"
      >
        <div className={`${hasEpisodeStill ? 'aspect-video' : 'aspect-[2/3]'} relative bg-white/[0.04]`}>
          <img
            src={coverSrc}
            alt={movie.code}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
            loading="lazy"
            onError={(e) => {
              const img = e.target as HTMLImageElement
              if (hasEpisodeStill) {
                img.src = api.coverUrl(movie.id) + versionSuffix
              } else {
                img.style.display = 'none'
              }
            }}
          />
          <WatchedBadge watched={watched} />

          <div className="absolute right-2 top-2 z-10 flex flex-col items-end gap-1.5">
            {movie.javdb_score != null && movie.javdb_score > 0 && (
              <span className="rounded-full border border-apple-yellow/30 bg-black/45 px-2 py-0.5 text-xs font-semibold text-apple-yellow shadow-sm backdrop-blur-xl">
                {movie.javdb_score.toFixed(1)}
              </span>
            )}
            {movie.javdb_likes != null && movie.javdb_likes > 0 && (
              <span className="rounded-full border border-apple-pink/30 bg-black/45 px-2 py-0.5 text-xs font-semibold text-apple-pink shadow-sm backdrop-blur-xl">
                {movie.javdb_likes >= 1000 ? `${(movie.javdb_likes / 1000).toFixed(1)}k` : movie.javdb_likes}
              </span>
            )}
          </div>

          {isEpisode && (
            <span className="absolute left-2 top-2 z-10 rounded-full border border-apple-blue/35 bg-apple-blue/70 px-2 py-0.5 text-[10px] font-semibold text-white shadow-glow backdrop-blur-xl">
              S{movie.tmdb_season}·E{movie.tmdb_episode}
            </span>
          )}

          <div className="absolute inset-0 bg-gradient-to-t from-black via-black/35 to-transparent opacity-95" />
          {showProgress && (
            <div className="absolute bottom-0 left-0 right-0 z-20 h-1 bg-white/15 backdrop-blur">
              <div className="h-full rounded-r-full bg-apple-blue shadow-glow" style={{ width: `${progressPercent}%` }} />
            </div>
          )}
          <div className="absolute bottom-0 left-0 right-0 min-w-0 p-3">
            <p className="line-clamp-2 break-words text-sm font-semibold leading-snug text-white drop-shadow">{displayTitle}</p>
            <p className="mt-0.5 truncate text-xs text-gray-400">{movie.code}</p>
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 backdrop-blur-xl">
          <div className="glass-modal w-full max-w-lg p-4 sm:p-5 max-h-[80vh] overflow-y-auto">
            <h2 className="mb-1 text-lg font-bold text-white">手动刮削</h2>
            <p className="mb-4 text-xs text-gray-500">输入搜索关键词，选择刮削器</p>
            <div className="mb-4 flex flex-col gap-2 sm:flex-row">
              <input
                type="text" value={manualQuery} onChange={e => { setManualQuery(e.target.value); setSearchResults([]) }}
                onKeyDown={e => { if (e.key === 'Enter') handleSearch() }}
                placeholder="搜索关键词" autoFocus
                className="glass-input flex-1 px-3 py-2 text-sm"
              />
              <select
                value={manualScraper} onChange={e => setManualScraper(e.target.value)}
                className="glass-input px-3 py-2 text-sm text-gray-300"
              >
                <option value="">自动</option>
                <option value="tmdb_movie">TMDB 电影</option>
                <option value="tmdb_tv">TMDB 剧集/番剧</option>
                <option value="bangumi">Bangumi</option>
                <option value="javdatabase">Javdatabase</option>
              </select>
              <button onClick={handleSearch} disabled={searching}
                className="glass-button-primary px-4 py-2 text-sm">
                {searching ? '搜索中...' : '搜索'}
              </button>
            </div>

            {searchResults.length > 0 && (
              <div className="grid max-h-[50vh] grid-cols-3 gap-3 overflow-y-auto">
                {searchResults.map((r, i) => (
                  <div key={i}
                    onClick={() => handleSelectSearchResult(r)}
                    className="glass-card cursor-pointer overflow-hidden transition-all hover:border-apple-blue/40 hover:shadow-glow"
                  >
                    <div className="aspect-[2/3] bg-white/[0.04]">
                      {r.poster_url ? (
                        <img src={r.poster_url} alt={r.title} className="h-full w-full object-cover" />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center p-2 text-center text-xs text-gray-600">{r.title}</div>
                      )}
                    </div>
                    <div className="p-2">
                      <p className="truncate text-xs font-medium text-white">{r.title}</p>
                      <p className="mt-0.5 text-[10px] text-gray-500">{r.year}{r.original_title ? ` · ${r.original_title}` : ''}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-4 flex gap-3">
              <button onClick={() => { setShowManualSearch(false); setSearchResults([]) }}
                className="glass-button flex-1 py-2 text-sm text-gray-300">
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {applying && (
        <div className="fixed bottom-3 left-3 right-3 z-[60] rounded-3xl border border-white/10 bg-black/60 p-4 shadow-glass backdrop-blur-2xl sm:bottom-4 sm:left-auto sm:right-4 sm:w-72">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-white">正在应用刮削结果...</p>
              <p className="mt-1 text-xs text-gray-500">更新元数据和封面缓存</p>
            </div>
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-apple-blue border-t-transparent" />
          </div>
        </div>
      )}

      {showCoverPicker && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 backdrop-blur-xl">
          <div className="glass-modal w-full max-w-lg p-4 sm:p-5 max-h-[80vh] overflow-y-auto">
            <h2 className="mb-1 text-lg font-bold text-white">更换封面</h2>
            <p className="mb-4 text-xs text-gray-500">选择封面或上传本地图片</p>
            <div className="mb-4 grid grid-cols-3 gap-3">
              {altCovers.map((c, i) => (
                <div key={i}
                  onClick={() => handleSelectCover(c.url)}
                  className="aspect-[2/3] cursor-pointer overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] transition-all hover:border-apple-blue/40 hover:shadow-glow"
                >
                  <img src={c.url} alt={c.source} className="h-full w-full object-cover" />
                </div>
              ))}
            </div>
            <div className="flex gap-3">
              <button onClick={handleUploadCover}
                className="glass-button flex-1 py-2 text-sm text-gray-300">
                上传本地图片
              </button>
              <button onClick={() => setShowCoverPicker(false)}
                className="glass-button flex-1 py-2 text-sm text-gray-300">
                取消
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
