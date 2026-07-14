import { useState, useCallback, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { api, Movie, type ManualScraperName, type ScrapeSearchResult, type ScraperInfo } from '../api'
import { saveScrollPos } from '../scroll'
import { showToast } from '../toast'
import { showTaskProgress, hideTaskProgress } from '../taskProgress'
import { WatchedBadge } from './WatchedBadge'
import ContextMenu, { ContextMenuItem } from './ContextMenu'
import EditModal from './EditModal'
import { clearCache } from '../cache'
import CoverPickerModal from './CoverPickerModal'
import { specialMovieTitle } from '../movieTitle'
import { normalizeScraperOptions } from '../scrapers'
import { formatMovieCardEpisodePrefix, formatMovieCardEpisodeTitle, getMovieCardCover, resolveMovieCardImageSrc, type MovieCardCoverStrategy } from './movieCardCover'

interface MovieCardProps {
  movie: Movie
  onUpdated?: () => void
  showBadges?: boolean
  hideTitle?: boolean
  adaptiveCover?: boolean
  coverStrategy?: MovieCardCoverStrategy
  landscapeFallbackSrc?: string
}

export function MovieCard({ movie, onUpdated, showBadges = true, hideTitle = false, adaptiveCover = false, coverStrategy = 'auto', landscapeFallbackSrc }: MovieCardProps) {
  const navigate = useNavigate()
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null)
  const [showEdit, setShowEdit] = useState(false)
  const [showManualSearch, setShowManualSearch] = useState(false)
  const [manualQuery, setManualQuery] = useState('')
  const [manualScraper, setManualScraper] = useState<ManualScraperName>('auto')
  const [showCoverPicker, setShowCoverPicker] = useState(false)
  const [altCovers, setAltCovers] = useState<{ url: string; source: string; width?: number; height?: number; language?: string; vote_count?: number }[]>([])
  const [searchResults, setSearchResults] = useState<ScrapeSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [applying, setApplying] = useState(false)
  const [coverVersion, setCoverVersion] = useState(() => movie.updated_at || '')
  const [coverLoadFailed, setCoverLoadFailed] = useState(false)
  const prevMovieId = useRef(movie.id)
  const [hovered, setHovered] = useState(false)
  const [libraryScrapers, setLibraryScrapers] = useState<Record<string, string>>({})
  const [scraperOptions, setScraperOptions] = useState<ScraperInfo[]>(normalizeScraperOptions(undefined, false))

  useEffect(() => {
    if (prevMovieId.current !== movie.id) {
      prevMovieId.current = movie.id
      setCoverVersion(movie.updated_at || '')
      setCoverLoadFailed(false)
    }
  }, [movie.id, movie.updated_at])
  useEffect(() => {
    setCoverLoadFailed(false)
  }, [coverStrategy, landscapeFallbackSrc])
  useEffect(() => {
    api.mediaRoots().then(data => {
      const scrapers: Record<string, string> = {}
      ;(data.items || []).forEach(item => { scrapers[item.path] = item.scraper || 'auto' })
      setLibraryScrapers(scrapers)
    }).catch(() => {})
    api.scrapers()
      .then(data => setScraperOptions(normalizeScraperOptions(data.items, false)))
      .catch(() => setScraperOptions(normalizeScraperOptions(undefined, false)))
  }, [])
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

  const coverState = getMovieCardCover(movie, coverStrategy)
  const isEpisode = coverState.isEpisode
  const isSpecial = movie.content_role === 'special'
  const episodePrefix = formatMovieCardEpisodePrefix(movie)
  const displayEpisodeTitle = formatMovieCardEpisodeTitle(movie)
  const landscapeCoverSrc = landscapeFallbackSrc || api.coverUrl(movie.id)
  const usesSharedLandscapeCover = coverStrategy === 'episode-still-or-landscape' && Boolean(landscapeFallbackSrc)
  const coverSrc = coverState.kind === 'episode-still'
    ? api.episodeStillUrl(movie.id)
    : coverStrategy === 'episode-still-or-landscape'
    ? landscapeCoverSrc
    : api.coverUrl(movie.id)
  const resolvedCoverSrc = resolveMovieCardImageSrc(
    coverSrc,
    coverVersion,
    usesSharedLandscapeCover && coverState.kind !== 'episode-still',
  )
  const coverPlaceholder = '暂无单集海报'
  const displayTitle = isSpecial
    ? specialMovieTitle(movie)
    : isEpisode
    ? displayEpisodeTitle
    : (movie.title || movie.code)
  const watched = localWatched !== null ? localWatched : (movie.tags || []).includes('watched')
  const progressPercent = Math.max(0, Math.min(100, movie.progress_percent || 0))
  const showProgress = !watched && progressPercent > 0 && progressPercent < 90
  const movieLibraryScraper = movie.media_root ? libraryScrapers[movie.media_root] : undefined
  const canUseJavdatabase = movieLibraryScraper === 'javdatabase'
  const manualScraperOptions = normalizeScraperOptions(scraperOptions, canUseJavdatabase)

  const checkTmdbConfig = useCallback(async (scraperName: string = manualScraper) => {
    try {
      const cfg = await api.getConfig()
      const normalizedScraper = scraperName === 'tmdb' ? 'tmdb_movie' : (scraperName || 'auto')
      if (!cfg.tmdb_configured && (normalizedScraper === 'auto' || normalizedScraper.startsWith('tmdb'))) {
        showToast('TMDB 读访问令牌未配置，刮削可能失败，请在设置中填写令牌')
      }
    } catch {}
  }, [manualScraper])

  const handleRescrape = useCallback(async () => {
    try {
      const librarySettings = await api.librarySettings().catch(() => [])
      const libraryScraper = librarySettings.find(item => item.media_root === movie.media_root)?.scraper || 'auto'
      await checkTmdbConfig(libraryScraper)
      await api.rescrapeMovie(movie.id)
      clearCache()
      setCoverVersion(String(Date.now()))
      onUpdated?.()
    } catch (err) {
      console.error('Rescrape failed for movie', movie.id, err)
      showToast(`刮削失败：${err instanceof Error ? err.message : '请查看后端日志'}`)
    }
  }, [movie.id, movie.media_root, onUpdated, checkTmdbConfig])

  const handleSearch = useCallback(async () => {
    const query = manualQuery.trim()
    if (!query) return
    await checkTmdbConfig()
    setSearching(true)
    try {
      const data = await api.searchScrape(query, manualScraper, movie.media_root || '')
      setSearchResults((data.results || []).map(result => ({
        ...result,
        scraper: result.scraper || manualScraper,
      })))
      if ((data.results || []).length === 0) {
        showToast('没有找到匹配结果')
      }
    } catch (err) {
      console.error('Search scrape failed', err)
      showToast(`搜索失败：${err instanceof Error ? err.message : '请查看后端日志'}`)
    } finally {
      setSearching(false)
    }
  }, [manualQuery, manualScraper, movie.media_root, checkTmdbConfig])

  const handleSelectSearchResult = useCallback(async (result: ScrapeSearchResult) => {
    if (applying) return
    setApplying(true)
    showTaskProgress({ status: '正在刮削媒体信息...' })
    try {
      await api.manualScrapeMovie(movie.id, result.title, result.source_id, result.media_type, result.scraper || manualScraper || result.source)
      clearCache()
      setCoverVersion(String(Date.now()))
      setShowManualSearch(false)
      setSearchResults([])
      setManualQuery('')
      showTaskProgress({ status: '刮削完成', done: 1, total: 1 })
      window.setTimeout(() => hideTaskProgress(), 3500)
      onUpdated?.()
    } catch {
      hideTaskProgress()
      console.error('Failed to apply scrape result')
    } finally {
      setApplying(false)
    }
  }, [movie.id, onUpdated, applying, manualScraper])

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
    ...(!isSpecial ? [
      { label: '重新刮削', onClick: handleRescrape },
      { label: '手动刮削', onClick: () => setShowManualSearch(true) },
    ] : []),
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
        className="glass-card apple-focus media-grid-card group cursor-pointer overflow-hidden"
      >
        <div className={`${adaptiveCover ? 'min-h-40 overflow-hidden' : (coverState.usesLandscape ? 'aspect-video' : 'aspect-[2/3]')} relative bg-white/[0.04]`}>
          {coverState.kind === 'placeholder' || (coverStrategy !== 'auto' && coverLoadFailed) ? (
            <div className="flex h-full w-full items-center justify-center bg-[linear-gradient(135deg,rgba(255,255,255,0.08),rgba(255,255,255,0.02))] p-3 text-center text-xs font-medium text-white/30">
              {coverPlaceholder}
            </div>
          ) : (
            <img
              src={resolvedCoverSrc}
              alt={movie.code}
              className={`${adaptiveCover ? 'h-auto' : 'h-full'} w-full object-cover transition-transform duration-500 group-hover:scale-105`}
              loading="lazy"
              onError={(e) => {
                const img = e.target as HTMLImageElement
                if (coverStrategy !== 'episode-still-only' && coverState.kind === 'episode-still') {
                  const fallbackSrc = resolveMovieCardImageSrc(
                    coverStrategy === 'episode-still-or-landscape'
                      ? landscapeCoverSrc
                      : api.coverUrl(movie.id),
                    coverVersion,
                    usesSharedLandscapeCover,
                  )
                  if (img.getAttribute('src') !== fallbackSrc) {
                    img.src = fallbackSrc
                    return
                  }
                  setCoverLoadFailed(true)
                } else {
                  setCoverLoadFailed(true)
                }
              }}
            />
          )}
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

          {showBadges && isEpisode && episodePrefix && (
            <span className="absolute left-2 top-2 z-10 rounded-full border border-apple-blue/35 bg-apple-blue/70 px-2 py-0.5 text-[10px] font-semibold text-white shadow-glow backdrop-blur-xl">
              {episodePrefix}
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
            <p className="mt-0.5 truncate text-xs text-gray-400">{isSpecial ? '花絮' : movie.code}</p>
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

      {showManualSearch && createPortal(
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4 backdrop-blur-2xl">
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
                value={manualScraper} onChange={e => setManualScraper(e.target.value as ManualScraperName)}
                className="glass-input px-3 py-2 text-sm text-gray-300"
              >
                {manualScraperOptions.map(option => (
                  <option key={option.name} value={option.name}>{option.label}</option>
                ))}
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
        </div>,
        document.body,
      )}

      {applying && (
        <div className="fixed bottom-3 left-3 right-3 z-[60] rounded-3xl bg-black/60 p-4 shadow-glass backdrop-blur-2xl sm:bottom-4 sm:left-auto sm:right-4 sm:w-72">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-white">正在应用刮削结果...</p>
              <p className="mt-1 text-xs text-gray-500">更新元数据和封面缓存</p>
            </div>
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-apple-blue border-t-transparent" />
          </div>
        </div>
      )}

      {showCoverPicker && createPortal(
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4 backdrop-blur-2xl">
          <CoverPickerModal
            covers={altCovers}
            onSelectCover={handleSelectCover}
            onUpload={handleUploadCover}
            onClose={() => setShowCoverPicker(false)}
          />
        </div>,
        document.body,
      )}
    </>
  )
}
