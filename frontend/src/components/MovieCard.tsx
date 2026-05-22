import { useState, useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, Movie } from '../api'
import { saveScrollPos } from '../scroll'
import { showToast } from '../toast'
import { WatchedBadge } from './WatchedBadge'
import ContextMenu, { ContextMenuItem } from './ContextMenu'
import EditModal from './EditModal'
import ManualScrapeModal from './ManualScrapeModal'
import CoverPickerModal from './CoverPickerModal'
import { clearCache } from '../cache'

interface MovieCardProps {
  movie: Movie
  onUpdated?: () => void
  showBadges?: boolean
  hideTitle?: boolean
}

export function MovieCard({ movie, onUpdated, showBadges = true, hideTitle = false }: MovieCardProps) {
  const navigate = useNavigate()
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null)
  const [showEdit, setShowEdit] = useState(false)
  const [showManualSearch, setShowManualSearch] = useState(false)
  const [showCoverPicker, setShowCoverPicker] = useState(false)
  const [altCovers, setAltCovers] = useState<{ url: string; source: string }[]>([])
  const [coverVersion, setCoverVersion] = useState(() => movie.updated_at || '')
  const prevMovieId = useRef(movie.id)
  const [hovered, setHovered] = useState(false)

  useEffect(() => {
    if (prevMovieId.current !== movie.id) {
      prevMovieId.current = movie.id
      setCoverVersion(movie.updated_at || '')
    }
  }, [movie.id, movie.updated_at])
  const [localWatched, setLocalWatched] = useState<boolean | null>(null)

  const goDetail = () => {
    saveScrollPos()
    navigate(`/detail/${movie.id}`)
  }

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault()
    setContextMenu({ x: e.clientX, y: e.clientY })
  }

  const handleToggleWatched = useCallback(async (e: React.MouseEvent) => {
    e.stopPropagation()
    const hasWatched = (movie.tags || []).includes('watched')
    const newWatched = !hasWatched
    setLocalWatched(newWatched)
    try {
      if (hasWatched) {
        await api.removeTag(movie.id, 'watched')
      } else {
        await api.addTag(movie.id, 'watched')
      }
      clearCache()
    } catch {
      setLocalWatched(null)
    }
  }, [movie.id, movie.tags])

  const isEpisode = movie.tmdb_type === 'tv' && movie.tmdb_episode != null
  const hasEpisodeStill = !!(isEpisode && movie.episode_still)
  const versionSuffix = coverVersion ? `?v=${encodeURIComponent(coverVersion)}` : ''
  const coverSrc = (hasEpisodeStill
    ? api.episodeStillUrl(movie.id)
    : api.coverUrl(movie.id)) + versionSuffix
  const displayTitle = isEpisode
    ? `E${String(movie.tmdb_episode).padStart(2, '0')} ${movie.episode_title || movie.title || movie.code}`
    : (movie.title || movie.code)
  const watched = localWatched !== null ? localWatched : (movie.tags || []).includes('watched')
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
      showToast(`刮削失败：${err instanceof Error ? err.message : '请查看后端日志'}`)
    }
  }, [movie.id, onUpdated])

  const handleLoadAltCovers = useCallback(async () => {
    try {
      const data = await api.getAlternativeCovers(movie.id)
      if (!data.covers || data.covers.length === 0) {
        showToast('没有找到备用封面')
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
      showToast('删除失败，请检查权限')
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
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
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

          {hovered && (
            <button
              onClick={handleToggleWatched}
              className={`absolute right-2 top-2 z-20 flex h-8 w-8 items-center justify-center rounded-full shadow-lg backdrop-blur-xl transition-all ${
                watched
                  ? 'border border-apple-mint/40 bg-apple-mint/80 text-white'
                  : 'border border-white/20 bg-black/50 text-white/70 hover:bg-apple-mint/80 hover:text-white hover:border-apple-mint/40'
              }`}
              title={watched ? '取消已看' : '标记已看'}
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </button>
          )}

          {showBadges && (
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
          )}

          {showBadges && isEpisode && (
            <span className="absolute left-2 top-2 z-10 rounded-full border border-apple-blue/35 bg-apple-blue/70 px-2 py-0.5 text-[10px] font-semibold text-white shadow-glow backdrop-blur-xl">
              S{movie.tmdb_season}·E{movie.tmdb_episode}
            </span>
          )}

          {!hideTitle && (
          <>
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
          </>
          )}
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
        <ManualScrapeModal
          title="手动刮削"
          initialQuery={movie.title || movie.code || ''}
          onApply={async (result) => {
            await api.manualScrapeMovie(movie.id, result.title, result.source_id, result.media_type, result.source)
            clearCache()
            setCoverVersion(String(Date.now()))
            setShowManualSearch(false)
            onUpdated?.()
          }}
          onClose={() => setShowManualSearch(false)}
        />
      )}

      {showCoverPicker && (
        <CoverPickerModal
          title="更换封面"
          covers={altCovers}
          onSelectCover={async (url) => {
            await api.changeCover(movie.id, url)
            clearCache()
            setCoverVersion(String(Date.now()))
            setShowCoverPicker(false)
            onUpdated?.()
          }}
          onUpload={handleUploadCover}
          onClose={() => setShowCoverPicker(false)}
        />
      )}
    </>
  )
}
