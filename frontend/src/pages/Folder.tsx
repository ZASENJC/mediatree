import { useEffect, useState, useMemo, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { api, Movie, FolderNode } from '../api'
import { getExcluded } from '../store'
import { getCached, setCache } from '../cache'
import { saveScrollPos, restoreScrollPos } from '../scroll'
import { MovieCard } from '../components/MovieCard'
import SortDropdown from '../components/SortDropdown'

import { LIBRARY_SORT_OPTIONS } from '../constants/sortOptions'

type SortMode = 'name' | 'created_desc' | 'created_asc' | 'release_date_desc' | 'release_date_asc' | 'random'

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
  const folderPath = searchParams.get('path') || ''
  const mediaRoot = searchParams.get('media_root') || ''
  const seasonFilter = searchParams.get('season') || ''
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
  const [overviewModal, setOverviewModal] = useState(false)

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

  // Load backdrops from folder-scraped TMDB data
  useEffect(() => {
    if (!folderPath) return
    if (lastPath.current === folderPath + mediaRoot) return
    lastPath.current = folderPath + mediaRoot
    setBackdrops([])
    setBackdropIdx(0)
    api.folderBackdrops(folderPath, mediaRoot)
      .then(data => {
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
  const activeBackdrop = backdrops.length > 0 ? backdrops[backdropIdx]?.url : folderBackdrop
  const exitBackdrop = prevIdxRef.current >= 0 && backdrops.length > prevIdxRef.current ? backdrops[prevIdxRef.current]?.url : ''

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
    setSearchParams(p, { replace: true })
  }

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
      <div className="relative space-y-6">
      {activeBackdrop ? (
        <div className="relative -mt-5 min-h-[56vh] sm:-mt-7 sm:min-h-[62vh]"
          onMouseEnter={() => setBackdropHover(true)}
          onMouseLeave={() => setBackdropHover(false)}
        >
          <div className="absolute inset-x-[calc(50%-50vw)] -top-20 h-[calc(100%+10rem)] overflow-hidden">
            {/* Crossfade: exiting backdrop (animate-out) */}
            {exitBackdrop && (
              <img
                key={`exit-${fadeKey}`}
                src={exitBackdrop}
                alt=""
                className="pointer-events-none absolute inset-0 h-full w-full scale-[1.04] object-cover saturate-115 animate-backdrop-out [mask-image:linear-gradient(to_bottom,transparent_5%,black_15%,black_55%,rgba(0,0,0,0.82)_70%,rgba(0,0,0,0.45)_84%,rgba(0,0,0,0.08)_95%,transparent_100%)] [-webkit-mask-image:linear-gradient(to_bottom,transparent_5%,black_15%,black_55%,rgba(0,0,0,0.82)_70%,rgba(0,0,0,0.45)_84%,rgba(0,0,0,0.08)_95%,transparent_100%)]"
              />
            )}
            {/* Crossfade: entering backdrop (animate-in) */}
            <img
              key={`enter-${fadeKey}`}
              src={activeBackdrop}
              alt=""
              className="pointer-events-none absolute inset-0 h-full w-full scale-[1.04] object-cover saturate-115 animate-backdrop-in [mask-image:linear-gradient(to_bottom,transparent_5%,black_15%,black_55%,rgba(0,0,0,0.82)_70%,rgba(0,0,0,0.45)_84%,rgba(0,0,0,0.08)_95%,transparent_100%)] [-webkit-mask-image:linear-gradient(to_bottom,transparent_5%,black_15%,black_55%,rgba(0,0,0,0.82)_70%,rgba(0,0,0,0.45)_84%,rgba(0,0,0,0.08)_95%,transparent_100%)]"
            />
            {/* Fade overlay: top edge soft + bottom gradient to page bg */}
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_32%,rgba(3,4,10,0.12)_68%,transparent_100%),linear-gradient(180deg,rgba(3,4,10,0)_0%,rgba(3,4,10,0.04)_30%,rgba(3,4,10,0.15)_50%,rgba(3,4,10,0.4)_65%,rgba(3,4,10,0.7)_78%,rgba(3,4,10,0.94)_90%,transparent_100%)]" />
          </div>

          {/* Arrow controls — visible on hover only when multiple backdrops */}
          {backdrops.length > 1 && (
            <>
              <button
                onClick={(e) => { e.stopPropagation(); cycleTo((backdropIdxRef.current - 1 + backdrops.length) % backdrops.length) }}
                className={`absolute left-3 top-1/2 z-20 -translate-y-1/2 rounded-full bg-black/40 p-2 text-white/70 backdrop-blur transition-all hover:bg-black/60 hover:text-white sm:left-5 sm:p-2.5 ${
                  backdropHover ? 'opacity-100' : 'opacity-0'
                }`}
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); cycleTo((backdropIdxRef.current + 1) % backdrops.length) }}
                className={`absolute right-3 top-1/2 z-20 -translate-y-1/2 rounded-full bg-black/40 p-2 text-white/70 backdrop-blur transition-all hover:bg-black/60 hover:text-white sm:right-5 sm:p-2.5 ${
                  backdropHover ? 'opacity-100' : 'opacity-0'
                }`}
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
              </button>
            </>
          )}

          <div className="pointer-events-none absolute inset-x-0 bottom-0 p-4 pb-14 sm:p-7 sm:pb-24">
            <button onClick={() => { saveScrollPos(); navigate('/') }}
              className="pointer-events-auto glass-chip mb-4 text-sm text-gray-300 drop-shadow hover:text-white">
              返回首页
            </button>
            <p className="text-xs uppercase tracking-[0.28em] text-apple-blue/90 drop-shadow">Folder</p>
            <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
              <div className="min-w-0">
                <h1 className="max-w-4xl break-words text-3xl font-bold tracking-tight text-white drop-shadow-2xl sm:text-5xl">{showTitle}</h1>
                {folderOverviewText && (
                  <p className="mt-2 max-w-[320px] text-xs leading-relaxed text-gray-400/70 drop-shadow line-clamp-2">
                    {folderOverviewText.length > 46 ? folderOverviewText.slice(0, 46) : folderOverviewText}
                    {folderOverviewText.length > 46 && <span>… </span>}
                    <button
                      className="pointer-events-auto inline-flex items-center rounded-full border border-white/10 bg-white/[0.08] px-1.5 py-0 text-xs text-gray-400 hover:bg-white/[0.14] hover:text-white transition"
                      onClick={(e) => { e.stopPropagation(); setOverviewModal(true) }}
                    >更多</button>
                  </p>
                )}
                <p className="mt-2 text-xs text-gray-400/70 drop-shadow">
                  {[folderMetaMovie?.release_date?.slice(0, 4), folderMetaMovie?.content_rating, `${movies.length} 部影片`].filter(Boolean).join(' · ')}
                </p>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="glass-panel flex flex-wrap items-center justify-between gap-3 px-5 py-4">
          <div className="min-w-0">
            <button onClick={() => { saveScrollPos(); navigate('/') }}
              className="glass-chip mb-2 text-sm text-gray-400 hover:text-white">
              返回首页
            </button>
            <p className="text-xs uppercase tracking-[0.24em] text-apple-blue/80">Folder</p>
            <h1 className="break-words text-2xl font-bold tracking-tight text-white sm:text-3xl">{showTitle}</h1>
            {folderOverviewText && (
              <p className="mt-1.5 max-w-[320px] text-xs leading-relaxed text-gray-400 line-clamp-2">
                {folderOverviewText.length > 46 ? folderOverviewText.slice(0, 46) : folderOverviewText}
                {folderOverviewText.length > 46 && <span>… </span>}
                <button
                  className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.08] px-1.5 py-0 text-xs text-gray-400 hover:bg-white/[0.14] hover:text-white transition"
                  onClick={() => setOverviewModal(true)}
                >更多</button>
              </p>
            )}
            <p className="mt-1.5 text-xs text-gray-400">
              {[folderMetaMovie?.release_date?.slice(0, 4), folderMetaMovie?.content_rating, `${movies.length} 部影片`].filter(Boolean).join(' · ')}
            </p>
          </div>
        </div>
      )}

      <div className="flex justify-between items-start">
        {seasonTabs.length > 0 && (
        <div className="-mt-2 inline-flex flex-wrap items-center gap-2 rounded-3xl border border-white/15 bg-white/[0.08] p-2 shadow-[0_10px_34px_rgba(0,0,0,0.24),inset_0_1px_0_rgba(255,255,255,0.18)] backdrop-blur-xl backdrop-saturate-150">
          <button
            onClick={() => selectSeason(null)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium transition-all ${
              !seasonFilter ? 'bg-apple-blue/80 text-white shadow-glow' : 'text-gray-400 hover:bg-white/[0.08] hover:text-white'
            }`}
          >
            全部 ({allMovies.length})
          </button>
          {seasonTabs.map(tab => (
            <button key={tab.path}
              onClick={() => selectSeason(tab.path)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-all ${
                seasonFilter === tab.path ? 'bg-apple-blue/80 text-white shadow-glow' : 'text-gray-400 hover:bg-white/[0.08] hover:text-white'
              }`}
            >
              {tab.name} ({tab.count})
            </button>
          ))}
        </div>
        )}
        <SortDropdown options={LIBRARY_SORT_OPTIONS} current={sort} onChange={handleSort} />
      </div>

      {movies.length === 0 ? (
        <div className="glass-panel py-20 text-center text-gray-500">
          <p className="mb-2 text-3xl font-light text-white/60">--</p>
          <p>此文件夹下没有影片</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
          {movies.map((movie) => (
            <MovieCard key={movie.id} movie={movie} onUpdated={load} showBadges={false} />
          ))}
        </div>
      )}
    </div>
    </>
  )
}
