import { useEffect, useState, useMemo, useRef, useCallback, useLayoutEffect, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import { useSearchParams, useNavigate, useLocation } from 'react-router-dom'
import { api, Movie, FolderNode, resolveApiUrl } from '../../api'
import { getExcluded } from '../../store'
import { getCached, setCache } from '../../cache'
import { restoreScrollPos } from '../../scroll'
import { MovieCard } from '../../components/MovieCard'
import SortDropdown from '../../components/SortDropdown'
import { showToast } from '../../toast'
import FolderTitle, { type FolderLogo } from './folderTitle'

import { LIBRARY_SORT_OPTIONS } from '../../constants/sortOptions'

type SortMode = 'name' | 'created_desc' | 'created_asc' | 'release_date_desc' | 'release_date_asc' | 'random'
const FOLDER_ENTRY_TRANSITION_MS = 520

type FolderTransitionState = {
  rect: {
    left: number
    top: number
    width: number
    height: number
  }
  coverSrc: string
  title: string
}

interface SeasonTab { name: string; path: string; count: number }

function cleanSeriesFolderLabel(label: string) {
  return label
    .replace(/\s*\[[^\]]*tmdbid[^\]]*\]\s*/ig, ' ')
    .replace(/\s*\([12]\d{3}\)\s*/g, ' ')
    .replace(/\s+/g, ' ')
    .trim() || label
}

function isSeasonLabel(label: string) {
  return /^(S|Season\s*|第)\s*\d{1,2}$/i.test(label)
}

export default function FolderPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const location = useLocation()
  const initialFolderTransitionRef = useRef<FolderTransitionState | null>(
    (location.state as { folderTransition?: FolderTransitionState } | null)?.folderTransition || null,
  )
  const initialFolderTransition = initialFolderTransitionRef.current
  const folderPath = searchParams.get('path') || ''
  const mediaRoot = searchParams.get('media_root') || ''
  const seasonFilter = searchParams.get('season') || ''
  const specialsSelected = searchParams.get('specials') === '1'
  const sort = (searchParams.get('sort') || 'created_desc') as SortMode
  const folderLabel = (() => {
    try { return decodeURIComponent(folderPath).split('/').pop() || folderPath }
    catch { return folderPath }
  })()

  const [movies, setMovies] = useState<Movie[]>([])
  const [allMovies, setAllMovies] = useState<Movie[]>([])
  const [loading, setLoading] = useState(true)
  const [folderDisplayTitle, setFolderDisplayTitle] = useState('')
  const [folderBackdrop, setFolderBackdrop] = useState('')
  const [folderLogos, setFolderLogos] = useState<FolderLogo[]>([])
  const [overviewModal, setOverviewModal] = useState(false)
  const [specialMovies, setSpecialMovies] = useState<Movie[]>([])
  const [specialCount, setSpecialCount] = useState(0)
  const [showSpecials, setShowSpecials] = useState(false)
  const [specialsLoading, setSpecialsLoading] = useState(false)
  const [specialsToggling, setSpecialsToggling] = useState(false)
  const [folderTransition, setFolderTransition] = useState<FolderTransitionState | null>(null)
  const [folderEntering, setFolderEntering] = useState(false)
  const [folderEntryBackdropKey, setFolderEntryBackdropKey] = useState<number | null>(null)
  const folderEntryStartedRef = useRef(false)

  // ─── Backdrop Carousel (powered by folder-scraped TMDB data) ───
  const [backdrops, setBackdrops] = useState<{ url: string; width: number; height: number }[]>([])
  const [backdropIdx, setBackdropIdx] = useState(0)
  const [backdropHover, setBackdropHover] = useState(false)
  const backdropTimer = useRef<ReturnType<typeof setInterval> | null>(null)
  const lastPath = useRef('')
  // Crossfade: animate-out the previous image, animate-in the new one
  const prevIdxRef = useRef(-1)
  const [fadeKey, setFadeKey] = useState(0)
  const backdropIdxRef = useRef(0)
  useEffect(() => { backdropIdxRef.current = backdropIdx }, [backdropIdx])

  const load = useCallback(() => {
    setLoading(true)
    const cacheKey = `movies_folder_${folderPath}_${sort}`
    const cached = getCached<{ movies: Movie[] }>(cacheKey)
    if (cached) {
      setAllMovies(cached.movies)
      setLoading(false)
      return
    }
    api.movies({ folder: folderPath, sort, limit: 2000, media_root: mediaRoot || undefined })
      .then((data) => {
        setAllMovies(data.movies)
        setCache(cacheKey, { movies: data.movies })
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [folderPath, sort, mediaRoot])

  useEffect(() => { load() }, [load])

  const specialFolderPath = folderPath
  const loadSpecials = useCallback(() => {
    if (!specialFolderPath) return
    setSpecialsLoading(true)
    api.folderSpecials(specialFolderPath, mediaRoot || undefined)
      .then((data) => {
        setShowSpecials(Boolean(data.show_specials))
        setSpecialCount(data.special_count || 0)
        setSpecialMovies(data.movies || [])
      })
      .catch(() => {
        setSpecialCount(0)
        setSpecialMovies([])
      })
      .finally(() => setSpecialsLoading(false))
  }, [specialFolderPath, mediaRoot])

  useEffect(() => { loadSpecials() }, [loadSpecials])

  useEffect(() => {
    api.folders().then(data => {
      const findNode = (nodes: FolderNode[]): FolderNode | undefined => {
        for (const node of nodes) {
          if (node.path === folderPath) return node
          const found = node.children ? findNode(node.children) : undefined
          if (found) return found
        }
        return undefined
      }
      const node = findNode(data.tree)
      if (node) {
        if (node.display_title) setFolderDisplayTitle(node.display_title)
        if (node.backdrop) setFolderBackdrop(node.backdrop)
      }
    }).catch(() => {})
  }, [folderPath])

  // Load backdrop and title logo artwork from folder-scraped TMDB data
  useEffect(() => {
    if (!folderPath) return
    if (lastPath.current === folderPath + mediaRoot) return
    lastPath.current = folderPath + mediaRoot
    setBackdrops([])
    setFolderLogos([])
    setBackdropIdx(0)
    api.folderBackdrops(folderPath, mediaRoot)
      .then(data => {
        setFolderLogos(data?.logos || [])
        if (data?.backdrops?.length) {
          setBackdrops(data.backdrops.slice(0, 10))
          prevIdxRef.current = -1
          setFadeKey(k => k + 1)
        }
      }).catch(() => {})
  }, [folderPath, mediaRoot])

  const cycleTo = useCallback((nextIdx: number) => {
    if (!backdrops.length) return
    prevIdxRef.current = backdropIdxRef.current
    setFadeKey(k => k + 1)
    setBackdropIdx(nextIdx)
  }, [backdrops.length])

  // Auto-rotate backdrops every 20s
  useEffect(() => {
    if (backdrops.length <= 1) return
    backdropTimer.current = setInterval(() => {
      cycleTo((backdropIdxRef.current + 1) % backdrops.length)
    }, 20000)
    return () => { if (backdropTimer.current) clearInterval(backdropTimer.current) }
  }, [backdrops.length, cycleTo])

  // Determine which backdrop source to use
  const activeBackdrop = resolveApiUrl(backdrops.length > 0 ? backdrops[backdropIdx]?.url : folderBackdrop)
  const episodeFallbackBackdrop = resolveApiUrl(backdrops[0]?.url || folderBackdrop)
  const exitBackdrop = resolveApiUrl(prevIdxRef.current >= 0 && backdrops.length > prevIdxRef.current ? backdrops[prevIdxRef.current]?.url : '')

  useEffect(() => {
    const ex = getExcluded()
    let filtered = allMovies
    if (ex.size > 0) {
      filtered = allMovies.filter(m => {
        const levels = m.folder_levels || ''
        return ![...ex].some(ef => levels === ef || levels.startsWith(ef + '/'))
      })
    }
    if (seasonFilter) {
      filtered = filtered.filter(m => {
        const levels = m.folder_levels || ''
        return levels === seasonFilter || levels.startsWith(seasonFilter + '/')
      })
    }
    setMovies(filtered)
  }, [allMovies, seasonFilter])

  useEffect(() => { restoreScrollPos() }, [])
  useLayoutEffect(() => {
    if (!initialFolderTransition) return
    if (loading || folderEntryStartedRef.current) return
    folderEntryStartedRef.current = true
    setFolderEntryBackdropKey(activeBackdrop ? fadeKey : null)
    setFolderTransition(initialFolderTransition)
    setFolderEntering(true)
    navigate({ pathname: location.pathname, search: location.search, hash: location.hash }, { replace: true, state: null })
    const clearEnteringTimer = window.setTimeout(() => setFolderEntering(false), FOLDER_ENTRY_TRANSITION_MS)
    const clearTransitionTimer = window.setTimeout(() => setFolderTransition(null), FOLDER_ENTRY_TRANSITION_MS)
    return () => {
      window.clearTimeout(clearEnteringTimer)
      window.clearTimeout(clearTransitionTimer)
    }
  }, [initialFolderTransition, loading])

  useEffect(() => {
    if (!folderEntering || !activeBackdrop) return
    setFolderEntryBackdropKey(fadeKey)
  }, [activeBackdrop, fadeKey, folderEntering])

  const seasonTabs = useMemo(() => {
    const seen = new Set<string>()
    const tabs: SeasonTab[] = []
    for (const m of allMovies) {
      const levels = m.folder_levels || ''
      if (levels === folderPath) continue
      const rel = levels.startsWith(folderPath + '/') ? levels.slice(folderPath.length + 1) : ''
      const top = rel.split('/')[0]
      if (!top || seen.has(top)) continue
      seen.add(top)
      const count = allMovies.filter(m2 => {
        const l = m2.folder_levels || ''
        return l === `${folderPath}/${top}` || l.startsWith(`${folderPath}/${top}/`)
      }).length
      tabs.push({ name: top, path: `${folderPath}/${top}`, count })
    }
    return tabs
  }, [allMovies, folderPath])

  const showTitle = folderDisplayTitle || (
    (() => {
      const allEpisodes = allMovies.length > 0 && allMovies.every(m => m.tmdb_type === 'tv' && m.tmdb_episode != null)
      if (allEpisodes && !isSeasonLabel(folderLabel)) return cleanSeriesFolderLabel(folderLabel)
      const m = allMovies.find(m => (
        m.title
        && m.title !== m.code
        && !(m.tmdb_type === 'tv' && m.tmdb_episode != null && m.episode_title && m.title === m.episode_title)
      ))
      return m?.title || folderLabel
    })()
  )

  const folderInfoMovie = useMemo(() => {
    if (allMovies.length === 0) return null
    const titleMovie = allMovies.find(m => m.title === showTitle && m.overview)
    if (titleMovie) return titleMovie
    const m = allMovies.find(m => m.overview)
    return m || null
  }, [allMovies, showTitle])
  const folderOverviewText = folderInfoMovie?.overview || ''

  // Same logic as folder-backdrops backend: find the "representative" movie
  // Prefer one with tmdb_id + metadata over bare overview-only matches
  const folderMetaMovie = useMemo(() => {
    if (allMovies.length === 0) return null
    const m = allMovies.find(m => m.tmdb_id != null && (m.release_date || m.content_rating))
    if (m) return m
    const m2 = allMovies.find(m => m.release_date || m.content_rating)
    return m2 || null
  }, [allMovies])

  const handleSort = (s: string) => {
    const p = new URLSearchParams(searchParams)
    p.set('path', folderPath)
    if (mediaRoot) p.set('media_root', mediaRoot)
    if (seasonFilter) p.set('season', seasonFilter)
    if (specialsSelected) p.set('specials', '1')
    if (s !== 'created_desc') p.set('sort', s)
    else p.delete('sort')
    setSearchParams(p, { replace: true })
  }

  const selectSeason = (tabPath: string | null) => {
    const p = new URLSearchParams(searchParams)
    p.set('path', folderPath)
    if (mediaRoot) p.set('media_root', mediaRoot)
    if (sort !== 'created_desc') p.set('sort', sort)
    if (tabPath) p.set('season', tabPath)
    else p.delete('season')
    p.delete('specials')
    setSearchParams(p, { replace: true })
  }

  const enableSpecials = useCallback(async () => {
    if (specialsToggling) return
    if (showSpecials || !specialFolderPath) return
    setSpecialsToggling(true)
    try {
      const data = await api.setFolderSpecials(specialFolderPath, mediaRoot || undefined, true)
      setShowSpecials(Boolean(data.show_specials))
      setSpecialCount(data.special_count || 0)
      setSpecialMovies(data.movies || [])
      showToast('已显示花絮')
    } catch {
      showToast('花絮加载失败')
    } finally {
      setSpecialsToggling(false)
    }
  }, [mediaRoot, showSpecials, specialFolderPath, specialsToggling])

  const selectSpecials = () => {
    const p = new URLSearchParams(searchParams)
    p.set('path', folderPath)
    if (mediaRoot) p.set('media_root', mediaRoot)
    if (sort !== 'created_desc') p.set('sort', sort)
    p.delete('season')
    p.set('specials', '1')
    setSearchParams(p, { replace: true })
    if (!showSpecials) void enableSpecials()
  }

  useEffect(() => {
    if (specialsSelected && specialCount > 0 && !showSpecials) {
      void enableSpecials()
    }
  }, [enableSpecials, showSpecials, specialCount, specialsSelected])

  const displayedMovies = specialsSelected ? specialMovies : movies
  const displayedMoviesLoading = specialsSelected && (specialsLoading || (specialsToggling && !showSpecials))
  const displayedEmptyText = specialsSelected ? '此文件夹下没有花絮' : '此文件夹下没有影片'
  const displayedCountText = specialsSelected ? `${specialCount} 个花絮` : `${movies.length} 部影片`
  const backdropImageClass = 'pointer-events-none absolute inset-0 h-full w-full object-cover object-center saturate-115'
  const useFolderEntryBackdropImage = folderEntering || (folderEntryBackdropKey === fadeKey && Boolean(activeBackdrop))

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-pulse text-gray-400 text-lg">加载中...</div>
      </div>
    )
  }

  return (
    <>
      {overviewModal && folderInfoMovie && createPortal(
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 backdrop-blur-2xl" onClick={() => setOverviewModal(false)}>
          <div className="glass-modal mx-4 max-h-[80vh] max-w-2xl overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-semibold text-white">影片信息</h3>
              <button onClick={() => setOverviewModal(false)} className="rounded-full p-1 text-gray-400 transition hover:bg-white/10 hover:text-white">&times;</button>
            </div>
            <h4 className="text-lg font-bold text-white mb-3">{folderInfoMovie.title || showTitle}</h4>
            {(folderInfoMovie.release_date || folderInfoMovie.duration != null || folderInfoMovie.genre || folderInfoMovie.director) && (
              <div className="flex flex-wrap gap-x-4 gap-y-1 mb-4 text-sm text-gray-400">
                {folderInfoMovie.release_date && <span>{folderInfoMovie.release_date}</span>}
                {folderInfoMovie.duration != null && <span>{Math.floor(folderInfoMovie.duration / 60) > 0 ? `${Math.floor(folderInfoMovie.duration / 60)} 小时 ${folderInfoMovie.duration % 60} 分` : `${folderInfoMovie.duration} 分`}</span>}
                {folderInfoMovie.genre && <span>{folderInfoMovie.genre}</span>}
                {folderInfoMovie.director && <span>导演：{folderInfoMovie.director}</span>}
              </div>
            )}
            {folderOverviewText && (
              <>
                <hr className="mb-4 border-white/10" />
                <h5 className="text-sm font-medium text-gray-500 mb-2">简介</h5>
                <p className="whitespace-pre-line text-sm leading-relaxed text-gray-300">{folderOverviewText}</p>
              </>
            )}
          </div>
        </div>,
        document.body,
      )}
      <div className={`folder-page ${folderEntering ? 'is-folder-entering' : ''} relative z-0 space-y-6`}>
      {activeBackdrop && (
        <div className="folder-backdrop-layer pointer-events-none fixed inset-0 -z-10 overflow-hidden">
          {exitBackdrop && (
            <img
              key={`exit-${fadeKey}`}
              src={exitBackdrop}
              alt=""
              className={`${backdropImageClass} animate-backdrop-out`}
            />
          )}
          <img
            key={`enter-${fadeKey}`}
            src={activeBackdrop}
            alt=""
            className={`${backdropImageClass} ${useFolderEntryBackdropImage ? 'folder-entry-backdrop-image' : 'animate-backdrop-in'}`}
          />
          <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,transparent_0%,transparent_58%,rgba(3,4,10,0.72)_100%)]" />
        </div>
      )}
      <div className="folder-content-layer">
      {activeBackdrop ? (
        <div
          className="relative -mt-5 min-h-[calc(100dvh-5.5rem)] sm:-mt-7 sm:min-h-[calc(100dvh-6.75rem)]"
          onMouseEnter={() => setBackdropHover(true)}
          onMouseLeave={() => setBackdropHover(false)}
        >
          {/* Arrow controls — visible on hover only when multiple backdrops */}
          {backdrops.length > 1 && (
            <>
              <button
                aria-label="上一张背景图"
                onClick={(e) => { e.stopPropagation(); cycleTo((backdropIdxRef.current - 1 + backdrops.length) % backdrops.length) }}
                className={`absolute left-3 top-1/2 z-20 -translate-y-1/2 p-2 text-white/70 drop-shadow-[0_2px_8px_rgba(0,0,0,0.9)] transition-[color,opacity,transform] hover:scale-110 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 sm:left-5 sm:p-2.5 ${
                  backdropHover ? 'opacity-100' : 'opacity-0'
                }`}
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
              </button>
              <button
                aria-label="下一张背景图"
                onClick={(e) => { e.stopPropagation(); cycleTo((backdropIdxRef.current + 1) % backdrops.length) }}
                className={`absolute right-3 top-1/2 z-20 -translate-y-1/2 p-2 text-white/70 drop-shadow-[0_2px_8px_rgba(0,0,0,0.9)] transition-[color,opacity,transform] hover:scale-110 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 sm:right-5 sm:p-2.5 ${
                  backdropHover ? 'opacity-100' : 'opacity-0'
                }`}
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
              </button>
            </>
          )}

          <div className="pointer-events-none absolute inset-x-0 bottom-0 p-4 pb-16 sm:p-7 sm:pb-24">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div className="min-w-0">
                <FolderTitle title={showTitle} logos={folderLogos} hasBackdrop />
                {folderOverviewText && (
                  <p className="mt-4 max-w-[320px] text-xs leading-relaxed text-gray-400/70 drop-shadow line-clamp-2">
                    {folderOverviewText.length > 46 ? folderOverviewText.slice(0, 46) : folderOverviewText}
                    {folderOverviewText.length > 46 && <span>… </span>}
                    <button
                      className="pointer-events-auto inline-flex items-center rounded-full border border-white/10 bg-white/[0.08] px-1.5 py-0 text-[10px] text-gray-400 hover:bg-white/[0.14] hover:text-white transition"
                      onClick={(e) => { e.stopPropagation(); setOverviewModal(true) }}
                    >更多</button>
                  </p>
                )}
                <p className="mt-2 text-xs text-gray-400/70 drop-shadow">
                  {[folderMetaMovie?.release_date?.slice(0, 4), folderMetaMovie?.content_rating, displayedCountText].filter(Boolean).join(' · ')}
                </p>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="glass-panel flex flex-wrap items-center justify-between gap-3 px-5 py-4">
          <div className="min-w-0">
            <FolderTitle title={showTitle} logos={folderLogos} hasBackdrop={false} />
            {folderOverviewText && (
              <p className="mt-3 max-w-[320px] text-xs leading-relaxed text-gray-400 line-clamp-2">
                {folderOverviewText.length > 46 ? folderOverviewText.slice(0, 46) : folderOverviewText}
                {folderOverviewText.length > 46 && <span>… </span>}
                <button
                  className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.08] px-1.5 py-0 text-[10px] text-gray-400 hover:bg-white/[0.14] hover:text-white transition"
                  onClick={() => setOverviewModal(true)}
                >更多</button>
              </p>
            )}
            <p className="mt-1.5 text-xs text-gray-400">
              {[folderMetaMovie?.release_date?.slice(0, 4), folderMetaMovie?.content_rating, displayedCountText].filter(Boolean).join(' · ')}
            </p>
          </div>
        </div>
      )}

      <div className="flex flex-col items-start gap-3 sm:flex-row sm:justify-between">
        {(seasonTabs.length > 0 || specialCount > 0) && (
        <div className="-mt-2 inline-flex max-w-full min-w-0 flex-wrap items-center gap-2 rounded-3xl bg-white/[0.08] p-2 shadow-[0_10px_34px_rgba(0,0,0,0.24),inset_0_1px_0_rgba(255,255,255,0.18)] backdrop-blur-xl backdrop-saturate-150 sm:max-w-[calc(100%_-_9rem)]">
          <button
            onClick={() => selectSeason(null)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium transition-all ${
              !seasonFilter && !specialsSelected ? 'bg-apple-blue/80 text-white shadow-glow' : 'text-white/80 hover:bg-white/[0.08] hover:text-white'
            }`}
          >
            全部 ({allMovies.length})
          </button>
          {seasonTabs.map(tab => (
            <button key={tab.path}
              onClick={() => selectSeason(tab.path)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-all ${
                seasonFilter === tab.path ? 'bg-apple-blue/80 text-white shadow-glow' : 'text-white/80 hover:bg-white/[0.08] hover:text-white'
              }`}
            >
              {tab.name} ({tab.count})
            </button>
          ))}
          {specialCount > 0 && (
            <button
              onClick={selectSpecials}
              disabled={specialsToggling && specialsSelected}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-all disabled:cursor-wait disabled:opacity-70 ${
                specialsSelected ? 'bg-apple-pink/80 text-white shadow-glow' : 'text-white/80 hover:bg-apple-pink/10 hover:text-white'
              }`}
            >
              {specialsToggling && specialsSelected ? '花絮加载中...' : `花絮 (${specialCount})`}
            </button>
          )}
        </div>
        )}
        <div className="shrink-0">
          <SortDropdown options={LIBRARY_SORT_OPTIONS} current={sort} onChange={handleSort} variant="menu" />
        </div>
      </div>

      <div className="folder-episode-section">
        {displayedMoviesLoading ? (
          <div className="glass-panel py-20 text-center text-gray-500">
            <div className="mx-auto mb-3 h-6 w-6 animate-spin rounded-full border-2 border-apple-pink border-t-transparent" />
            <p>花絮加载中...</p>
          </div>
        ) : displayedMovies.length === 0 ? (
          <div className="glass-panel py-20 text-center text-gray-500">
            <p className="mb-2 text-3xl font-light text-white/60">--</p>
            <p>{displayedEmptyText}</p>
          </div>
        ) : (
          <div className="folder-episode-grid media-grid">
            {displayedMovies.map((movie) => (
              <MovieCard
                key={movie.id}
                movie={movie}
                onUpdated={specialsSelected ? loadSpecials : load}
                showBadges={false}
                coverStrategy="episode-still-or-landscape"
                landscapeFallbackSrc={episodeFallbackBackdrop}
              />
            ))}
          </div>
        )}
      </div>
      </div>
    </div>
      {folderTransition && createPortal(
        <div
          className="home-folder-transition"
          aria-hidden="true"
          style={{
            '--home-folder-transition-left': `${folderTransition.rect.left}px`,
            '--home-folder-transition-top': `${folderTransition.rect.top}px`,
            '--home-folder-transition-width': `${folderTransition.rect.width}px`,
            '--home-folder-transition-height': `${folderTransition.rect.height}px`,
          } as CSSProperties}
        >
          <img
            src={folderTransition.coverSrc}
            alt={folderTransition.title}
            className="home-folder-transition-image"
          />
        </div>,
        document.body,
      )}
    </>
  )
}
