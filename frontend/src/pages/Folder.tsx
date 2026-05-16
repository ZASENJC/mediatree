import { useEffect, useState, useMemo, useCallback } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { api, Movie, FolderNode } from '../api'
import { getExcluded } from '../store'
import { getCached, setCache, clearCache } from '../cache'
import { saveScrollPos, restoreScrollPos } from '../scroll'
import { MovieCard } from '../components/MovieCard'
import SortDropdown from '../components/SortDropdown'

type SortMode = 'name' | 'created_desc' | 'created_asc' | 'release_date_desc' | 'release_date_asc' | 'random'

const sortOptions = [
  { key: 'created_desc', label: '最近添加' },
  { key: 'created_asc', label: '最早添加' },
  { key: 'name', label: '名称' },
  { key: 'release_date_desc', label: '发行日期↓' },
  { key: 'release_date_asc', label: '发行日期↑' },
  { key: 'random', label: '随机' },
]

interface SeasonTab { name: string; path: string; count: number }

export default function FolderPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const folderPath = searchParams.get('path') || ''
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
    api.movies({ folder: folderPath, sort, limit: 2000 })
      .then((data) => {
        setAllMovies(data.movies)
        setCache(cacheKey, { movies: data.movies })
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [folderPath, sort])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    api.folders().then(data => {
      for (const node of data.tree) {
        if (node.path === folderPath) {
          if (node.display_title) setFolderDisplayTitle(node.display_title)
          if (node.backdrop) setFolderBackdrop(node.backdrop)
        }
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
      const m = allMovies.find(m => m.title && m.title !== m.code)
      return m?.title || folderLabel
    })()
  )

  const handleSort = (s: string) => {
    const p = new URLSearchParams(searchParams)
    p.set('path', folderPath)
    if (seasonFilter) p.set('season', seasonFilter)
    if (s !== 'created_desc') p.set('sort', s)
    else p.delete('sort')
    setSearchParams(p, { replace: true })
  }

  const selectSeason = (tabPath: string | null) => {
    const p = new URLSearchParams(searchParams)
    p.set('path', folderPath)
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
    <div>
      {folderBackdrop && (
        <div className="relative -mx-4 -mt-6 mb-6 h-[42vh] min-h-[240px] max-h-[550px] overflow-hidden bg-dark-950">
          <img
            src={folderBackdrop}
            alt=""
            className="w-full h-full object-cover brightness-[0.45]"
          />
          <div className="absolute bottom-0 left-0 right-0 h-2/3 bg-gradient-to-t from-dark-900 via-dark-900/60 to-transparent pointer-events-none" />
          <div className="absolute bottom-4 left-4 right-4">
            <button onClick={() => { saveScrollPos(); navigate('/') }}
              className="text-sm text-gray-400 hover:text-white transition-colors mb-1 block">
              ← 返回首页
            </button>
            <h1 className="text-2xl font-bold truncate text-white drop-shadow-lg">{showTitle}</h1>
            <p className="text-sm text-gray-400 mt-1">{movies.length} 部影片</p>
          </div>
        </div>
      )}

      {!folderBackdrop && (
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div>
            <button onClick={() => { saveScrollPos(); navigate('/') }}
              className="text-sm text-gray-400 hover:text-white transition-colors mb-1 block">
              ← 返回首页
            </button>
            <h1 className="text-2xl font-bold truncate">{showTitle}</h1>
            <p className="text-sm text-gray-500 mt-1">{movies.length} 部影片</p>
          </div>
          <SortDropdown options={sortOptions} current={sort} onChange={handleSort} />
        </div>
      )}

      {folderBackdrop && (
        <div className="flex items-center justify-end mb-4">
          <SortDropdown options={sortOptions} current={sort} onChange={handleSort} />
        </div>
      )}

      {seasonTabs.length > 0 && (
        <div className="flex items-center gap-1 mb-4 flex-wrap">
          <button
            onClick={() => selectSeason(null)}
            className={`px-3 py-1.5 rounded text-xs transition-colors ${
              !seasonFilter ? 'bg-blue-600 text-white' : 'bg-dark-700 text-gray-400 hover:text-white hover:bg-dark-600'
            }`}
          >
            全部 ({allMovies.length})
          </button>
          {seasonTabs.map(tab => (
            <button key={tab.path}
              onClick={() => selectSeason(tab.path)}
              className={`px-3 py-1.5 rounded text-xs transition-colors ${
                seasonFilter === tab.path ? 'bg-blue-600 text-white' : 'bg-dark-700 text-gray-400 hover:text-white hover:bg-dark-600'
              }`}
            >
              {tab.name} ({tab.count})
            </button>
          ))}
        </div>
      )}

      {movies.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <p className="text-2xl font-light mb-2">--</p>
          <p>此文件夹下没有影片</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-4">
          {movies.map((movie) => (
            <MovieCard key={movie.id} movie={movie} onUpdated={load} />
          ))}
        </div>
      )}
    </div>
  )
}
