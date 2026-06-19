import { useEffect, useState, useCallback, useRef, useLayoutEffect, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom'
import { api, FolderNode, Movie, resolveMediaUrl, type ManualScraperName, type ScrapeSearchResult, type ScraperInfo } from '../../api'
import { getExcluded, getUiPrefs } from '../../store'
import { saveScrollPos, restoreScrollPos } from '../../scroll'
import { showToast } from '../../toast'
import { showTaskProgress, hideTaskProgress } from '../../taskProgress'
import { clearCache } from '../../cache'
import SortDropdown from '../../components/SortDropdown'
import ContextMenu, { ContextMenuItem } from '../../components/ContextMenu'
import EditModal from '../../components/EditModal'
import CoverPickerModal from '../../components/CoverPickerModal'
import { normalizeScraperOptions } from '../../scrapers'

function encodeMediaPath(path: string): string {
  return path.split('/').map(encodeURIComponent).join('/')
}

function getCoverSrc(cover: string | null | undefined, version?: number): string | null {
  if (!cover) return null
  let url: string
  if (cover.startsWith('http://') || cover.startsWith('https://')) url = cover
  else if (cover.startsWith('/api/')) url = resolveMediaUrl(cover)
  else url = resolveMediaUrl(`/api/media/${encodeMediaPath(cover)}`)
  if (version !== undefined) url += `${url.includes('?') ? '&' : '?'}v=${version}`
  return url
}

type SortMode = 'name' | 'created_desc' | 'created_asc' | 'release_date_desc' | 'release_date_asc' | 'random'
const HOME_RETURN_TRANSITION_MS = 520
const HOME_OPENING_ANIMATION_MS = 1680
const HOME_OPENING_MAX_ITEMS = 48

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

const sortOptions = [
  { key: 'created_desc', label: '最近添加' },
  { key: 'created_asc', label: '最早添加' },
  { key: 'name', label: '名称' },
  { key: 'release_date_desc', label: '发行日期新到旧' },
  { key: 'release_date_asc', label: '发行日期旧到新' },
  { key: 'random', label: '随机' },
]

function scraperMayNeedTmdb(scraper?: string): boolean {
  const normalized = scraper === 'tmdb' ? 'tmdb_movie' : (scraper || 'auto')
  return normalized === 'auto' || normalized.startsWith('tmdb')
}

function sortMovies(movies: Movie[], sort: SortMode): Movie[] {
  const sorted = [...movies]
  const toTime = (value?: string) => value ? new Date(value).getTime() || 0 : 0
  const titleOf = (movie: Movie) => movie.display_title || movie.clean_title || movie.title || movie.code || ''

  if (sort === 'name') {
    sorted.sort((a, b) => titleOf(a).localeCompare(titleOf(b), 'zh-CN'))
  } else if (sort === 'created_desc') {
    sorted.sort((a, b) => toTime(b.created_at) - toTime(a.created_at))
  } else if (sort === 'created_asc') {
    sorted.sort((a, b) => toTime(a.created_at) - toTime(b.created_at))
  } else if (sort === 'release_date_desc') {
    sorted.sort((a, b) => toTime(b.release_date) - toTime(a.release_date))
  } else if (sort === 'release_date_asc') {
    sorted.sort((a, b) => toTime(a.release_date) - toTime(b.release_date))
  } else if (sort === 'random') {
    for (let i = sorted.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [sorted[i], sorted[j]] = [sorted[j], sorted[i]]
    }
  }

  return sorted
}

function getHomeFolderCount(node: FolderNode): number {
  return node.video_count ?? node.movie_count
}

function getFolderLocalKey(node: FolderNode): string {
  return `${node.media_root || ''}::${node.path}`
}

function getYearFromDate(value?: string): string {
  return value?.match(/^(\d{4})/)?.[1] || ''
}

function getYearFromText(value?: string): string {
  const match = value?.match(/(?:^|[^\d])((?:18|19|20)\d{2})(?!\d)/)
  return match?.[1] || ''
}

function getHomeFolderYear(node: FolderNode): string {
  return (
    getYearFromDate(node.release_date_max)
    || getYearFromText(node.display_title)
    || getYearFromText(node.name)
    || getYearFromDate(node.created_max)
  )
}

function getHomeFolderTitle(node: FolderNode, showSourceName?: boolean): string {
  return showSourceName ? node.name : (node.display_title || node.name)
}

function getHomeFolderWatchState(node: FolderNode, watchedOverride?: boolean) {
  const totalCount = getHomeFolderCount(node)
  const watchedCount = watchedOverride === true
    ? totalCount
    : watchedOverride === false
    ? 0
    : Math.max(0, node.watched_count || 0)
  const watchedByCount = totalCount > 0 && watchedCount >= totalCount
  const watched = watchedOverride ?? (!!node.folder_watched || watchedByCount)
  return {
    watched,
    unwatchedCount: watched ? 0 : Math.max(0, totalCount - watchedCount),
  }
}

function getHomeContinueCoverKind(movie: Movie): 'episode-still' | 'continue-snapshot' {
  const isEpisode = movie.tmdb_type === 'tv' || movie.tmdb_episode != null || movie.episode_number != null
  if (isEpisode) return 'episode-still'
  return 'continue-snapshot'
}

function getHomeContinueCoverSrc(movie: Movie): string {
  const coverKind = getHomeContinueCoverKind(movie)
  if (coverKind === 'episode-still') return api.episodeStillUrl(movie.id)
  if (coverKind === 'continue-snapshot') return api.continueCoverUrl(movie.id)
  return api.coverUrl(movie.id)
}

function getHomeContinueTitle(movie: Movie): string {
  return movie.display_title || movie.title || movie.clean_title || movie.code
}

function getHomeContinueSubtitle(movie: Movie): string {
  const episodeNumber = movie.tmdb_episode ?? movie.episode_number
  if (episodeNumber != null) {
    const seasonPrefix = movie.tmdb_season != null ? `S${movie.tmdb_season}:` : ''
    const episodePrefix = `${seasonPrefix}E${episodeNumber}`
    return movie.episode_title ? `${episodePrefix} - ${movie.episode_title}` : episodePrefix
  }
  const year = getYearFromDate(movie.release_date)
  return year || movie.code
}

function CheckIcon({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

export default function Home() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const location = useLocation()
  const initialHomeReturnTransitionRef = useRef<FolderTransitionState | null>(
    (location.state as { homeReturnTransition?: FolderTransitionState } | null)?.homeReturnTransition || null,
  )
  const initialHomeReturnTransition = initialHomeReturnTransitionRef.current
  const sort = (searchParams.get('sort') || 'created_desc') as SortMode
  const continueStripRef = useRef<HTMLDivElement>(null)
  const homeReturnStartedRef = useRef(false)
  const homeOpeningStartedRef = useRef(false)

  const [tree, setTree] = useState<FolderNode[]>([])
  const [libraryScrapers, setLibraryScrapers] = useState<Record<string, string>>({})
  const [scraperOptions, setScraperOptions] = useState<ScraperInfo[]>(normalizeScraperOptions(undefined, false))
  const [recentMovies, setRecentMovies] = useState<Movie[]>([])
  const [libraryLoading, setLibraryLoading] = useState(true)
  const [recentLoading, setRecentLoading] = useState(true)
  const [folderMenu, setFolderMenu] = useState<{ x: number; y: number; mediaRoot: string; folderPath: string; folderName: string } | null>(null)
  const [activeFolderPath, setActiveFolderPath] = useState('')
  const [activeMediaRoot, setActiveMediaRoot] = useState('')
  const [activeFolderName, setActiveFolderName] = useState('')
  const [activeFolderSpecialCount, setActiveFolderSpecialCount] = useState(0)
  const [activeFolderShowSpecials, setActiveFolderShowSpecials] = useState(false)
  const hideHomeTitleText = getUiPrefs().hideHomeTitleText
  const showSourceName = getUiPrefs().showSourceName

  const [folderWatched, setFolderWatched] = useState<Record<string, boolean>>({})

  const handleToggleFolderWatched = async (e: React.MouseEvent, node: FolderNode) => {
    e.stopPropagation()
    const key = getFolderLocalKey(node)
    const current = folderWatched[key] ?? !!node.folder_watched
    const newVal = !current
    setFolderWatched(prev => ({ ...prev, [key]: newVal }))
    try {
      await api.setFolderWatched(node.path, node.media_root || '', newVal)
      clearCache()
    } catch {
      setFolderWatched(prev => ({ ...prev, [key]: current }))
    }
  }

  const [showFolderScrape, setShowFolderScrape] = useState(false)
  const [folderScrapeQuery, setFolderScrapeQuery] = useState('')
  const [folderScrapeSrc, setFolderScrapeSrc] = useState<ManualScraperName>('auto')
  const [folderScrapeResults, setFolderScrapeResults] = useState<ScrapeSearchResult[]>([])
  const [folderScrapeBackdrops, setFolderScrapeBackdrops] = useState<{ source_id: string; source: string; media_type?: string; backdrop_url?: string; poster_url?: string }[]>([])
  const [folderScrapeSearching, setFolderScrapeSearching] = useState(false)
  const [folderScrapeApplying, setFolderScrapeApplying] = useState(false)

  const [showFolderCover, setShowFolderCover] = useState(false)
  const [folderAltCovers, setFolderAltCovers] = useState<{ url: string; source: string }[]>([])
  const [folderAltBackdrops, setFolderAltBackdrops] = useState<{ url: string; source: string }[]>([])
  const [folderCoverVersion, setFolderCoverVersion] = useState(0)
  const [showFolderBackdrop, setShowFolderBackdrop] = useState(false)

  const [showFolderEdit, setShowFolderEdit] = useState(false)
  const [editFolderMovie, setEditFolderMovie] = useState<Movie | null>(null)
  const [homeReturnTransition, setHomeReturnTransition] = useState<FolderTransitionState | null>(null)
  const [homeReturning, setHomeReturning] = useState(false)
  const [homeOpening, setHomeOpening] = useState(false)
  const activeFolderUsesJavdatabase = libraryScrapers[activeMediaRoot] === 'javdatabase'
  const folderScraperOptions = normalizeScraperOptions(scraperOptions, activeFolderUsesJavdatabase)

  const load = useCallback(() => {
    setLibraryLoading(true)
    api.folders().then((data) => {
      const ex = getExcluded()
      const relevant = data.tree.filter(n => getHomeFolderCount(n) > 0 && !ex.has(n.path))
      let filtered = relevant
      if (sort === 'name') {
        filtered.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
      } else if (sort === 'created_desc') {
        filtered.sort((a, b) => (b.created_max || '').localeCompare(a.created_max || ''))
      } else if (sort === 'created_asc') {
        filtered.sort((a, b) => (a.created_max || '').localeCompare(b.created_max || ''))
      } else if (sort === 'release_date_desc') {
        const toTs = (d?: string) => d ? new Date(d).getTime() : 0
        filtered.sort((a, b) => toTs(b.release_date_max) - toTs(a.release_date_max))
      } else if (sort === 'release_date_asc') {
        const toTs = (d?: string) => d ? new Date(d).getTime() : 0
        filtered.sort((a, b) => toTs(a.release_date_max) - toTs(b.release_date_max))
      } else if (sort === 'random') {
        for (let i = filtered.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          [filtered[i], filtered[j]] = [filtered[j], filtered[i]]
        }
      }
      setTree(filtered)
    }).catch(() => {}).finally(() => setLibraryLoading(false))
    api.mediaRoots().then(data => {
      const scrapers: Record<string, string> = {}
      ;(data.items || []).forEach(item => { scrapers[item.path] = item.scraper || 'auto' })
      setLibraryScrapers(scrapers)
    }).catch(() => {})
    api.scrapers()
      .then(data => setScraperOptions(normalizeScraperOptions(data.items, false)))
      .catch(() => setScraperOptions(normalizeScraperOptions(undefined, false)))
  }, [sort])

  const loadRecent = useCallback(() => {
    setRecentLoading(true)
    api.getRecentWatched(200).then((data) => {
      setRecentMovies(sortMovies(data.movies, sort))
    }).catch(() => {}).finally(() => setRecentLoading(false))
  }, [sort])

  useEffect(() => {
    load()
    loadRecent()
  }, [load, loadRecent])
  useEffect(() => { restoreScrollPos() }, [])
  useLayoutEffect(() => {
    if (!initialHomeReturnTransition) return
    if (libraryLoading || recentLoading || homeReturnStartedRef.current) return
    homeReturnStartedRef.current = true
    setHomeReturnTransition(initialHomeReturnTransition)
    setHomeReturning(true)
    navigate({ pathname: location.pathname, search: location.search, hash: location.hash }, { replace: true, state: null })
    const clearReturningTimer = window.setTimeout(() => setHomeReturning(false), HOME_RETURN_TRANSITION_MS)
    const clearTransitionTimer = window.setTimeout(() => setHomeReturnTransition(null), HOME_RETURN_TRANSITION_MS)
    return () => {
      window.clearTimeout(clearReturningTimer)
      window.clearTimeout(clearTransitionTimer)
    }
  }, [initialHomeReturnTransition, libraryLoading, recentLoading])
  useEffect(() => {
    if (initialHomeReturnTransition || libraryLoading || recentLoading || homeOpeningStartedRef.current) return
    homeOpeningStartedRef.current = true
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    setHomeOpening(true)
    const timer = window.setTimeout(() => setHomeOpening(false), HOME_OPENING_ANIMATION_MS)
    return () => window.clearTimeout(timer)
  }, [initialHomeReturnTransition, libraryLoading, recentLoading])

  const handleSort = (s: string) => {
    setSearchParams({ sort: s }, { replace: true })
  }

  const goFolder = (e: React.MouseEvent<HTMLDivElement>, node: FolderNode, coverSrc: string | null) => {
    const p = new URLSearchParams()
    p.set('path', node.path)
    if (node.media_root) p.set('media_root', node.media_root)
    saveScrollPos()

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (prefersReducedMotion || !coverSrc) {
      navigate(`/folder?${p.toString()}`)
      return
    }

    const sourceCover = e.currentTarget.querySelector('.home-poster-cover') as HTMLElement | null
    const rect = sourceCover?.getBoundingClientRect()
    if (!rect || rect.width <= 0 || rect.height <= 0) {
      navigate(`/folder?${p.toString()}`)
      return
    }

    const folderTransition: FolderTransitionState = {
      rect: {
        left: rect.left,
        top: rect.top,
        width: rect.width,
        height: rect.height,
      },
      coverSrc,
      title: node.name,
    }
    navigate(`/folder?${p.toString()}`, { state: { folderTransition } })
  }

  const goMovie = (movieId: number) => {
    saveScrollPos()
    navigate(`/detail/${movieId}`)
  }

  const scrollContinue = (direction: -1 | 1) => {
    const el = continueStripRef.current
    if (!el) return
    el.scrollBy({ left: direction * Math.max(320, el.clientWidth * 0.72), behavior: 'smooth' })
  }

  const handleFolderContextMenu = (e: React.MouseEvent, node: FolderNode) => {
    e.preventDefault()
    setActiveFolderPath(node.path)
    setActiveMediaRoot(node.media_root || '')
    setActiveFolderName(node.name)
    setActiveFolderSpecialCount(node.special_count || 0)
    setActiveFolderShowSpecials(Boolean(node.show_specials))
    setFolderMenu({
      x: e.clientX, y: e.clientY,
      mediaRoot: node.media_root || '', folderPath: node.path, folderName: node.name,
    })
  }

  const handleRescanFolder = useCallback(async () => {
    clearCache()
    try {
      const [cfg, librarySettings] = await Promise.all([
        api.getConfig(),
        api.librarySettings().catch(() => []),
      ])
      const libraryScraper = librarySettings.find(item => item.media_root === activeMediaRoot)?.scraper || 'auto'
      if (!cfg.tmdb_configured && scraperMayNeedTmdb(libraryScraper)) {
        showToast('TMDB 读访问令牌未配置，刮削可能失败，请在设置中填写令牌')
      }
      await api.rescrapeFolder(activeFolderPath, activeMediaRoot)
      showToast('刮削任务已触发')
      setFolderMenu(null)
      load()
    } catch (err) {
      showToast(`刮削失败：${err instanceof Error ? err.message : '请查看后端日志'}`)
    }
  }, [activeFolderPath, activeMediaRoot, load])

  const handleManualScrapeFolder = useCallback(() => {
    setFolderScrapeQuery(activeFolderName || '')
    setFolderScrapeSrc('auto')
    setFolderScrapeResults([])
    setShowFolderScrape(true)
    setFolderMenu(null)
  }, [activeFolderName])

  const handleFolderScrapeSearch = useCallback(async () => {
    const query = folderScrapeQuery.trim()
    if (!query) return
    try {
      const cfg = await api.getConfig()
      if (!cfg.tmdb_configured && (folderScrapeSrc === 'auto' || folderScrapeSrc.startsWith('tmdb'))) {
        showToast('TMDB 读访问令牌未配置，刮削可能失败，请在设置中填写令牌')
      }
    } catch {}
    setFolderScrapeSearching(true)
    try {
      const data = await api.searchScrape(query, folderScrapeSrc, activeMediaRoot)
      const results = (data.results || []).map(result => ({
        ...result,
        scraper: result.scraper || folderScrapeSrc,
      }))
      setFolderScrapeResults(results)
      if (results.length === 0) {
        showToast('没有找到匹配结果')
      } else {
        api.fetchSearchBackdrops(results).then(bd => {
          setFolderScrapeBackdrops(bd.backdrops || [])
        }).catch(() => {})
      }
    } catch (err) {
      console.error('Search scrape failed', err)
      showToast(`搜索失败：${err instanceof Error ? err.message : '请查看后端日志'}`)
    } finally {
      setFolderScrapeSearching(false)
    }
  }, [folderScrapeQuery, folderScrapeSrc, activeMediaRoot])

  const handleSelectFolderScrapeResult = useCallback(async (result: ScrapeSearchResult) => {
    if (folderScrapeApplying) return
    setFolderScrapeApplying(true)
    showTaskProgress({ status: '正在刮削媒体信息...' })
    try {
      clearCache()
      const res = await api.applyFolderScrape(activeFolderPath, activeMediaRoot, result.source_id, result.source, result.media_type)
      if (res.ok) {
        showToast(`已应用: ${res.title}`)
        setShowFolderScrape(false)
        setFolderScrapeResults([])
        setFolderScrapeQuery('')
        showTaskProgress({ status: '刮削完成', done: 1, total: 1 })
        window.setTimeout(() => hideTaskProgress(), 3500)
        await load()
      } else {
        hideTaskProgress()
        showToast('应用失败')
      }
    } catch (err) {
      hideTaskProgress()
      showToast(`替换失败：${err instanceof Error ? err.message : '请查看后端日志'}`)
    } finally {
      setFolderScrapeApplying(false)
    }
  }, [activeFolderPath, activeMediaRoot, load, folderScrapeApplying])

  const handleChangeFolderCover = useCallback(async () => {
    setFolderMenu(null)
    try {
      const movies = await api.movies({ folder: activeFolderPath, media_root: activeMediaRoot, limit: 1 })
      if (!movies.movies || movies.movies.length === 0) { showToast('目录下无影片'); return }
      const movieId = movies.movies[0].id
      const data = await api.getAlternativeCovers(movieId)
      const covers = data.covers || []
      setFolderAltCovers(covers)
      const detailResults = covers.map(c => ({ source_id: '', source: c.source, poster_url: c.url }))
      api.fetchSearchBackdrops(detailResults.filter(r => r.source !== 'local')).then(bd => {
        const backdrops = (bd.backdrops || []).filter(b => b.backdrop_url).map(b => ({ url: b.backdrop_url!, source: b.source }))
        setFolderAltBackdrops(backdrops)
      }).catch(() => {})
      setShowFolderCover(true)
    } catch {
      console.error('Load covers failed')
    }
  }, [activeFolderPath, activeMediaRoot])

  const handleSelectFolderCover = useCallback(async (url: string) => {
    try {
      await api.changeFolderCover(activeFolderPath, activeMediaRoot, url)
      clearCache()
      // Directly re-fetch folders to bypass all caches
      const data = await api.folders()
      const ex = getExcluded()
      let filtered = data.tree.filter(n => getHomeFolderCount(n) > 0 && !ex.has(n.path))
      if (sort === 'name') {
        filtered.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
      } else if (sort === 'created_desc') {
        filtered.sort((a, b) => (b.created_max || '').localeCompare(a.created_max || ''))
      } else if (sort === 'created_asc') {
        filtered.sort((a, b) => (a.created_max || '').localeCompare(b.created_max || ''))
      } else if (sort === 'release_date_desc') {
        const toTs = (d?: string) => d ? new Date(d).getTime() : 0
        filtered.sort((a, b) => toTs(b.release_date_max) - toTs(a.release_date_max))
      } else if (sort === 'release_date_asc') {
        const toTs = (d?: string) => d ? new Date(d).getTime() : 0
        filtered.sort((a, b) => toTs(a.release_date_max) - toTs(b.release_date_max))
      } else if (sort === 'random') {
        for (let i = filtered.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          [filtered[i], filtered[j]] = [filtered[j], filtered[i]]
        }
      }
      setTree(filtered)
      setFolderCoverVersion(v => v + 1)
      setShowFolderCover(false)
      showToast('封面已更新')
    } catch (err) {
      console.error('[cover] change failed:', err)
      showToast('操作失败')
    }
  }, [activeFolderPath, activeMediaRoot, sort])

  const handleEditFolder = useCallback(async () => {
    setFolderMenu(null)
    try {
      const data = await api.movies({ folder: activeFolderPath, media_root: activeMediaRoot, limit: 1 })
      if (!data.movies || data.movies.length === 0) { showToast('目录下无影片'); return }
      setEditFolderMovie(data.movies[0])
      setShowFolderEdit(true)
    } catch {
      console.error('Load movie for edit failed')
    }
  }, [activeFolderPath, activeMediaRoot])

  const handleFolderEditSave = useCallback(async (fields: Record<string, any>) => {
    clearCache()
    try {
      await api.editFolder(activeFolderPath, activeMediaRoot, fields)
    } catch {
      throw new Error('Edit failed')
    }
  }, [activeFolderPath, activeMediaRoot])

  const handleDeleteFolder = useCallback(async () => {
    if (!confirm(`确定要删除目录 "${activeFolderName}" 下的所有影片？\n此操作不可撤销。`)) return
    try {
      clearCache()
      await api.deleteFolder(activeFolderPath, activeMediaRoot)
      showToast('已删除')
      load()
    } catch {
      showToast('删除失败')
    }
  }, [activeFolderName, activeFolderPath, activeMediaRoot, load])

  const handleToggleFolderSpecials = useCallback(async () => {
    if (!activeFolderSpecialCount) return
    const next = !activeFolderShowSpecials
    try {
      await api.setFolderSpecials(activeFolderPath, activeMediaRoot, next)
      setActiveFolderShowSpecials(next)
      setFolderMenu(null)
      showToast(next ? '已显示花絮' : '已隐藏花絮')
      await load()
    } catch {
      showToast('花絮显示设置失败')
    }
  }, [activeFolderPath, activeMediaRoot, activeFolderShowSpecials, activeFolderSpecialCount, load])

  const folderMenuItems: ContextMenuItem[] = [
    { label: '重新刮削', onClick: handleRescanFolder },
    { label: '手动刮削', onClick: handleManualScrapeFolder },
    { label: '更换封面', onClick: handleChangeFolderCover },
    { label: '编辑信息', onClick: handleEditFolder },
    ...(activeFolderSpecialCount > 0 ? [{
      label: activeFolderShowSpecials ? `隐藏花絮 (${activeFolderSpecialCount})` : `显示花絮 (${activeFolderSpecialCount})`,
      onClick: handleToggleFolderSpecials,
    }] : []),
    { label: '删除', danger: true, onClick: handleDeleteFolder },
  ]

  if (libraryLoading || recentLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-pulse text-gray-400 text-lg">加载中...</div>
      </div>
    )
  }

  return (
    <div className={`home-page ${homeReturning ? 'is-home-returning' : ''} ${homeOpening ? 'is-home-opening' : ''}`}>
      {recentMovies.length > 0 && (
        <>
          <section className="home-section">
            <div className="home-section-header home-continue-header">
              <h2 className="home-section-title">继续观看</h2>
              <div className="home-scroll-actions" aria-label="继续观看滚动控制">
                <button type="button" className="home-scroll-button" aria-label="向左滚动继续观看" onClick={() => scrollContinue(-1)}>
                  <span className="home-scroll-icon" aria-hidden="true">‹</span>
                </button>
                <button type="button" className="home-scroll-button" aria-label="向右滚动继续观看" onClick={() => scrollContinue(1)}>
                  <span className="home-scroll-icon" aria-hidden="true">›</span>
                </button>
              </div>
            </div>
            <div ref={continueStripRef} className="home-continue-strip">
              {recentMovies.map((movie, index) => (
                <article
                  key={movie.id}
                  className="home-continue-item"
                  onClick={() => goMovie(movie.id)}
                  style={{ '--home-opening-index': Math.min(index, HOME_OPENING_MAX_ITEMS) } as CSSProperties}
                >
                  <div className="home-continue-cover">
                    <div className="home-continue-cover-placeholder">暂无继续观看封面</div>
                    <img
                      src={getHomeContinueCoverSrc(movie)}
                      alt={getHomeContinueTitle(movie)}
                      loading="lazy"
                      onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
                    />
                    <div className="home-continue-cover-shade" />
                    <div className="home-continue-progress-track" aria-hidden="true">
                      <div
                        className="home-continue-progress-bar"
                        style={{ width: `${Math.max(0, Math.min(100, movie.progress_percent || 0))}%` }}
                      />
                    </div>
                  </div>
                  <div className="home-continue-meta">
                    <p className="home-continue-title">{getHomeContinueTitle(movie)}</p>
                    <p className="home-continue-subtitle">{getHomeContinueSubtitle(movie)}</p>
                  </div>
                </article>
              ))}
            </div>
          </section>
          <div className="home-section-separator" aria-hidden="true" />
        </>
      )}

      <section className="home-section home-library-section">
        <div className="home-section-header home-library-header">
          <SortDropdown options={sortOptions} current={sort} onChange={handleSort} variant="menu" size="heading" />
        </div>

        {tree.length === 0 ? (
          <div className="glass-panel py-20 text-center text-gray-500">
            <p className="mb-2 text-3xl font-light text-white/60">--</p>
            <p className="text-lg text-white/70">未找到媒体文件</p>
            <p className="mt-2 text-sm">请配置 MEDIA_ROOT 或检查浏览页勾选状态</p>
          </div>
        ) : (
          <div className="home-poster-grid media-grid">
            {tree.map((node, index) => {
              const coverSrc = getCoverSrc(node.random_cover || node.cover, folderCoverVersion)
              const localKey = getFolderLocalKey(node)
              const watchState = getHomeFolderWatchState(node, folderWatched[localKey])
              const yearText = getHomeFolderYear(node)
              const titleText = getHomeFolderTitle(node, showSourceName)
              return (
                <div key={node.path}
                  onClick={(e) => goFolder(e, node, coverSrc)}
                  onContextMenu={(e) => handleFolderContextMenu(e, node)}
                  className="home-poster-card media-grid-card group cursor-pointer"
                  style={{ '--home-opening-index': Math.min(index, HOME_OPENING_MAX_ITEMS) } as CSSProperties}
                >
                  <div className="home-poster-cover relative aspect-[2/3] bg-white/[0.04]">
                    {coverSrc ? (
                      <img src={coverSrc} className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" alt={node.name} loading="lazy"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-4xl text-white/10" />
                    )}
                    <span
                      className={`home-poster-watch-status absolute right-2 top-2 z-20 flex h-7 min-w-7 items-center justify-center rounded-full px-2 text-xs font-bold shadow-lg backdrop-blur-xl ${
                        watchState.watched
                          ? 'border border-apple-mint/40 bg-apple-mint/85 text-white'
                          : 'border border-apple-blue/35 bg-apple-blue/85 text-white'
                      }`}
                      title={watchState.watched ? '已看完' : `未观看 ${watchState.unwatchedCount} 集`}
                    >
                      {watchState.watched ? <CheckIcon className="h-3.5 w-3.5" /> : (watchState.unwatchedCount > 99 ? '99+' : watchState.unwatchedCount)}
                    </span>
                    <button
                      onClick={(e) => handleToggleFolderWatched(e, node)}
                      className={`home-poster-watched-action absolute bottom-2 right-2 z-30 flex h-8 w-8 items-center justify-center rounded-full shadow-lg backdrop-blur-xl transition-all ${
                        watchState.watched
                          ? 'border border-apple-mint/50 bg-apple-mint/85 text-white'
                          : 'border border-white/20 bg-black/55 text-white/80 hover:border-apple-mint/45 hover:bg-apple-mint/85 hover:text-white'
                      }`}
                      title={watchState.watched ? '取消已看' : '标记已看'}
                      aria-label={watchState.watched ? '取消已看' : '标记已看'}
                    >
                      <CheckIcon className="h-4 w-4" />
                    </button>
                  </div>
                  {!hideHomeTitleText && (
                    <div className="home-poster-meta min-w-0 text-center">
                      <p className="home-poster-title line-clamp-2 break-words text-sm font-medium leading-snug text-white/90">{titleText}</p>
                      <p className="home-poster-year mt-1 truncate text-xs text-gray-500">{yearText || '年份未知'}</p>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </section>

      {folderMenu && (
        <ContextMenu x={folderMenu.x} y={folderMenu.y} items={folderMenuItems}
          onClose={() => setFolderMenu(null)} />
      )}

      {homeReturnTransition && createPortal(
        <div
          className="home-folder-transition"
          aria-hidden="true"
          style={{
            '--home-folder-transition-left': `${homeReturnTransition.rect.left}px`,
            '--home-folder-transition-top': `${homeReturnTransition.rect.top}px`,
            '--home-folder-transition-width': `${homeReturnTransition.rect.width}px`,
            '--home-folder-transition-height': `${homeReturnTransition.rect.height}px`,
          } as CSSProperties}
        >
          <img
            src={homeReturnTransition.coverSrc}
            alt={homeReturnTransition.title}
            className="home-folder-transition-image"
          />
        </div>,
        document.body,
      )}

      {showFolderScrape && createPortal(
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4 backdrop-blur-2xl">
          <div className="glass-modal max-h-[85vh] w-full max-w-3xl overflow-y-auto p-4 sm:p-5">
            <h2 className="mb-1 text-lg font-bold text-white">手动刮削目录: {activeFolderName}</h2>
            <p className="mb-4 text-xs text-gray-500">搜索关键词，选择结果应用到整个目录</p>
            <div className="mb-4 flex flex-col gap-2 sm:flex-row">
              <input type="text" value={folderScrapeQuery} onChange={e => { setFolderScrapeQuery(e.target.value); setFolderScrapeResults([]) }}
                onKeyDown={e => { if (e.key === 'Enter') handleFolderScrapeSearch() }}
                placeholder="搜索关键词" autoFocus
                className="glass-input flex-1 px-3 py-2 text-sm" />
              <select value={folderScrapeSrc} onChange={e => setFolderScrapeSrc(e.target.value as ManualScraperName)}
                className="glass-input px-3 py-2 text-sm text-gray-300">
                {folderScraperOptions.map(option => (
                  <option key={option.name} value={option.name}>{option.label}</option>
                ))}
              </select>
              <button onClick={handleFolderScrapeSearch} disabled={folderScrapeSearching}
                className="glass-button-primary px-4 py-2 text-sm">
                {folderScrapeSearching ? '搜索中...' : '搜索'}
              </button>
            </div>
            {folderScrapeResults.length > 0 && (
              <>
                <p className="mb-2 text-xs text-gray-500">共 {folderScrapeResults.length} 个结果，点击应用元数据，长按/右键查看封面和背景图可选</p>
                <div className="grid max-h-[50vh] grid-cols-2 gap-3 overflow-y-auto sm:grid-cols-3">
                  {folderScrapeResults.map((r, i) => {
                    const bd = folderScrapeBackdrops.find(b => b.source_id === r.source_id && b.source === r.source && (b.media_type || '') === (r.media_type || ''))
                    return (
                      <div key={i} className="glass-card overflow-hidden transition-all hover:border-apple-blue/40 hover:shadow-glow">
                        <div className="aspect-[2/3] cursor-pointer bg-white/[0.04]"
                          onClick={() => handleSelectFolderScrapeResult(r)}>
                          {r.poster_url ? (
                            <img src={r.poster_url} alt={r.title} className="h-full w-full object-cover" />
                          ) : (
                            <div className="flex h-full w-full items-center justify-center p-2 text-center text-xs text-gray-600">{r.title}</div>
                          )}
                        </div>
                        <div className="p-2">
                          <p className="truncate text-xs font-medium text-white">{r.title}</p>
                          <p className="mt-0.5 text-[10px] text-gray-500">
                            <span className={`inline-block rounded-full border px-1.5 py-0.5 text-[9px] ${r.source === 'tmdb' ? 'border-apple-blue/25 bg-apple-blue/15 text-apple-blue' : r.source === 'bangumi' ? 'border-apple-pink/25 bg-apple-pink/15 text-apple-pink' : 'border-apple-mint/25 bg-apple-mint/15 text-apple-mint'}`}>
                              {r.source}
                            </span>
                            {' '}{r.year}{r.original_title ? ` · ${r.original_title}` : ''}
                          </p>
                          <div className="mt-1.5 flex gap-1">
                            <a href="#" onClick={e => { e.preventDefault(); e.stopPropagation(); handleSelectFolderScrapeResult(r) }}
                              className="flex-1 rounded-full border border-apple-blue/20 bg-apple-blue/10 px-1 py-0.5 text-center text-[10px] text-apple-blue hover:bg-apple-blue/20">应用</a>
                            {bd?.backdrop_url && (
                              <a href="#" onClick={e => { e.preventDefault(); e.stopPropagation();
                                api.changeFolderBackdrop(activeFolderPath, activeMediaRoot, bd.backdrop_url!).then(() => { showToast('背景图已更新'); load() }).catch(() => showToast('失败'))
                              }}
                                className="rounded-full border border-white/10 bg-white/[0.08] px-1.5 py-0.5 text-[10px] text-gray-400 hover:text-white">选背景</a>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </>
            )}
            <div className="mt-4 flex gap-3">
              <button onClick={() => { setShowFolderScrape(false); setFolderScrapeResults([]) }}
                className="glass-button flex-1 py-2 text-sm text-gray-300">取消</button>
            </div>
          </div>
        </div>,
        document.body,
      )}

      {folderScrapeApplying && (
        <div className="fixed bottom-3 left-3 right-3 z-[60] rounded-3xl bg-black/60 p-4 shadow-glass backdrop-blur-2xl sm:bottom-4 sm:left-auto sm:right-4 sm:w-72">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-white">正在应用刮削结果...</p>
              <p className="mt-1 text-xs text-gray-500">更新目录元数据和封面</p>
            </div>
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-apple-blue border-t-transparent" />
          </div>
        </div>
      )}

      {showFolderCover && createPortal(
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4 backdrop-blur-2xl">
          <CoverPickerModal
            title={`更换封面与背景: ${activeFolderName}`}
            subtitle="选择封面图或背景图应用到该目录下所有影片"
            covers={folderAltCovers}
            backdrops={folderAltBackdrops}
            onSelectCover={handleSelectFolderCover}
            onSelectBackdrop={(url) => {
              api.changeFolderBackdrop(activeFolderPath, activeMediaRoot, url)
                .then(() => { showToast('背景图已更新'); setFolderCoverVersion(v => v + 1); setShowFolderCover(false); load() })
                .catch(() => showToast('失败'))
            }}
            onClose={() => setShowFolderCover(false)}
          />
        </div>,
        document.body,
      )}

      {showFolderEdit && editFolderMovie && (
        <EditModal movie={editFolderMovie}
          onClose={() => setShowFolderEdit(false)}
          onSaved={() => { setShowFolderEdit(false); load() }}
          onSave={handleFolderEditSave} />
      )}
    </div>
  )
}
