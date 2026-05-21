import { useEffect, useState, useMemo, useCallback } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { api, Movie, FolderNode } from '../api'
import { getExcluded } from '../store'
import { getCached, setCache } from '../cache'
import { saveScrollPos, restoreScrollPos } from '../scroll'
import { MovieCard } from '../components/MovieCard'
import SortDropdown from '../components/SortDropdown'

type SortMode = 'name' | 'created_desc' | 'created_asc' | 'release_date_desc' | 'release_date_asc' | 'random'

const sortOptions = [
  { key: 'created_desc', label: '最近添加' },
  { key: 'created_asc', label: '最早添加' },
  { key: 'name', label: '名称' },
  { key: 'release_date_desc', label: '发行日期新到旧' },
  { key: 'release_date_asc', label: '发行日期旧到新' },
  { key: 'random', label: '随机' },
]

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
    <div className="relative space-y-6">
      {folderBackdrop ? (
        <div className="relative -mt-5 min-h-[56vh] sm:-mt-7 sm:min-h-[62vh]">
          <div className="pointer-events-none absolute inset-x-[calc(50%-50vw)] -top-20 h-[calc(100%+7rem)] overflow-hidden">
            <img
              src={folderBackdrop}
              alt=""
              className="h-full w-full scale-[1.04] object-cover opacity-80 saturate-115 [mask-image:radial-gradient(ellipse_at_center,black_40%,rgba(0,0,0,0.9)_58%,rgba(0,0,0,0.42)_78%,transparent_100%)] [-webkit-mask-image:radial-gradient(ellipse_at_center,black_40%,rgba(0,0,0,0.9)_58%,rgba(0,0,0,0.42)_78%,transparent_100%)]"
            />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_36%,rgba(3,4,10,0.18)_72%,transparent_100%),linear-gradient(180deg,transparent_0%,rgba(3,4,10,0.08)_35%,rgba(3,4,10,0.25)_55%,rgba(3,4,10,0.6)_75%,rgba(3,4,10,0.95)_100%)]" />
          </div>
          <div className="absolute inset-x-0 bottom-0 p-4 sm:p-7">
            <button onClick={() => { saveScrollPos(); navigate('/') }}
              className="glass-chip mb-4 text-sm text-gray-300 drop-shadow hover:text-white">
              返回首页
            </button>
            <p className="text-xs uppercase tracking-[0.28em] text-apple-blue/90 drop-shadow">Folder</p>
            <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
              <div className="min-w-0">
                <h1 className="max-w-4xl break-words text-3xl font-bold tracking-tight text-white drop-shadow-2xl sm:text-5xl">{showTitle}</h1>
                <p className="mt-3 text-sm text-gray-300 drop-shadow">{movies.length} 部影片</p>
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
            <p className="mt-1 text-sm text-gray-500">{movies.length} 部影片</p>
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
        <SortDropdown options={sortOptions} current={sort} onChange={handleSort} />
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
  )
}
