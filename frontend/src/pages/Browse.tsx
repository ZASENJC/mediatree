import { useEffect, useState, useCallback } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { api, Movie, FolderNode } from '../api'
import { getExcluded, setExcluded } from '../store'
import { getCached, setCache } from '../cache'
import { saveScrollPos, restoreScrollPos } from '../scroll'
import { WatchedBadge } from '../components/WatchedBadge'
import SortDropdown from '../components/SortDropdown'

const sortOptions = [
  { key: 'created_desc', label: '最近添加' },
  { key: 'created_asc', label: '最早添加' },
  { key: 'name', label: '文件夹名称' },
  { key: 'release_date_desc', label: '发行日期新到旧' },
  { key: 'release_date_asc', label: '发行日期旧到新' },
  { key: 'random', label: '随机排列' },
]

export default function Browse() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const initFolder = searchParams.get('folder') || ''
  const initActress = searchParams.get('actress') || ''
  const initStaff = searchParams.get('staff') || ''
  const initCode = searchParams.get('code') || ''
  const initMediaRoot = searchParams.get('media_root') || ''
  const sort = searchParams.get('sort') || 'created_desc'

  const [movies, setMovies] = useState<Movie[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [folder, setFolder] = useState(initFolder)
  const [actress, setActress] = useState(initActress)
  const [staff, setStaff] = useState(initStaff)
  const [codeQuery, setCodeQuery] = useState(initCode)
  const [folders, setFolders] = useState<FolderNode[]>([])
  const [excluded, setExcludedState] = useState<Set<string>>(getExcluded())
  const [mobileTreeOpen, setMobileTreeOpen] = useState(false)
  const pageSize = 48

  useEffect(() => {
    api.folders().then(data => setFolders(data.tree))
  }, [])

  useEffect(() => { restoreScrollPos() }, [])

  useEffect(() => {
    setPage(0)
  }, [folder, actress, staff, sort, codeQuery])

  useEffect(() => {
    setLoading(true)
    const params: any = {
      sort,
      limit: pageSize,
      offset: page * pageSize,
    }
    if (folder) params.folder = folder
    if (actress) params.actress = actress
    if (staff) params.staff = staff
    if (codeQuery) params.code = codeQuery
    if (initMediaRoot) params.media_root = initMediaRoot

    const cacheKey = `movies_${JSON.stringify(params)}`
    const cached = getCached<{ movies: Movie[]; total: number }>(cacheKey)
    if (cached) {
      setMovies(cached.movies)
      setTotal(cached.total)
      setLoading(false)
      return
    }

    api.movies(params).then((data) => {
      setMovies(data.movies)
      setTotal(data.total)
      setCache(cacheKey, data)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [folder, actress, staff, page, sort, codeQuery])

  const toggleExclude = useCallback((path: string) => {
    setExcludedState(prev => {
      const n = new Set(prev)
      if (n.has(path)) n.delete(path)
      else n.add(path)
      setExcluded(n)
      return n
    })
  }, [])

  const totalPages = Math.ceil(total / pageSize)

  const getDisplayTitle = (movie: Movie) => {
    if (movie.title && movie.title !== movie.code) return movie.title
    try {
      const parts = movie.path.split('/')
      const filename = parts[parts.length - 1]
      const stem = filename.replace(/\.[^/.]+$/, '')
      return stem || movie.code
    } catch {
      return movie.code
    }
  }

  const handleSortChange = (key: string) => {
    const p = new URLSearchParams(searchParams)
    if (key === 'created_desc') p.delete('sort')
    else p.set('sort', key)
    if (folder) p.set('folder', folder)
    if (actress) p.set('actress', actress)
    if (staff) p.set('staff', staff)
    if (codeQuery) p.set('code', codeQuery)
    setSearchParams(p, { replace: true })
  }

  const handleFolderSelect = (path: string) => {
    setFolder(path)
    setMobileTreeOpen(false)
    const p = new URLSearchParams()
    if (path) p.set('folder', path)
    if (sort !== 'created_desc') p.set('sort', sort)
    setSearchParams(p, { replace: true })
  }

  const renderFolderTree = () => (
    <div className="space-y-0.5 max-h-[65vh] overflow-y-auto pr-1">
      {folders.length === 0 ? (
        <p className="text-xs text-gray-600 px-2">无文件夹</p>
      ) : (
        folders.map((node) => (
          <TreeItem
            key={node.path}
            node={node}
            selectedPath={folder}
            onSelect={handleFolderSelect}
            excluded={excluded}
            onToggleExclude={toggleExclude}
            depth={0}
          />
        ))
      )}
    </div>
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 min-w-0">
            <button
              onClick={() => setMobileTreeOpen(true)}
              className="lg:hidden w-9 h-9 flex items-center justify-center rounded-lg bg-dark-700 border border-dark-600 text-gray-300 hover:text-white hover:bg-dark-600 transition-colors shrink-0"
              aria-label="打开文件夹"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
                <path strokeLinecap="round" d="M4 7h16M4 12h16M4 17h16" />
              </svg>
            </button>
            <h1 className="text-xl sm:text-2xl font-bold break-words min-w-0">
              {staff ? `Staff: ${decodeURIComponent(staff)}` : actress ? `演员: ${decodeURIComponent(actress)}` : codeQuery ? `搜索: ${decodeURIComponent(codeQuery)}` : folder ? `浏览: ${decodeURIComponent(folder)}` : '全部影片'}
            </h1>
          </div>
          <p className="text-sm text-gray-500 mt-1">共 {total} 部</p>
        </div>
        <SortDropdown options={sortOptions} current={sort} onChange={handleSortChange} />
      </div>

      {mobileTreeOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileTreeOpen(false)} />
          <aside className="absolute left-0 top-0 h-full w-[82vw] max-w-xs bg-dark-900 border-r border-dark-600 shadow-2xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-300">文件夹</h2>
              <button
                onClick={() => setMobileTreeOpen(false)}
                className="w-8 h-8 rounded-lg bg-dark-700 text-gray-400 hover:text-white"
                aria-label="关闭文件夹"
              >
                ×
              </button>
            </div>
            {renderFolderTree()}
          </aside>
        </div>
      )}

      <div className="flex gap-6">
        <div className="w-56 shrink-0 hidden lg:block">
          <div className="sticky top-20">
            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">文件夹</h3>
            {renderFolderTree()}
          </div>
        </div>

        <div className="flex-1 min-w-0">
          {loading ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-3">
              {Array.from({ length: 12 }).map((_, i) => (
                <div key={i} className="aspect-[2/3] bg-dark-800 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : movies.length === 0 ? (
            <div className="text-center py-20 text-gray-500">
              <p className="text-2xl font-light mb-2">--</p>
              <p>没有找到影片</p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-3">
                {movies.map((movie) => (
                  <div
                    key={movie.id}
                    onClick={() => { saveScrollPos(); navigate(`/detail/${movie.id}`) }}
                    className="group cursor-pointer bg-dark-800 rounded-lg overflow-hidden border border-dark-700 hover:border-blue-500/40 transition-all hover:bg-dark-700/50"
                  >
                    <div className="aspect-[2/3] bg-dark-700 relative overflow-hidden group/thumb">
                      <img
                        src={api.coverUrl(movie.id)}
                        alt={movie.code}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        loading="lazy"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = 'none'
                        }}
                      />
                      {(() => {
                        const watched = !!(movie.tags || []).includes('watched')
                        const progress = Math.max(0, Math.min(100, movie.progress_percent || 0))
                        return (
                          <>
                            <WatchedBadge watched={watched} />
                            {!watched && progress > 0 && progress < 90 && (
                              <div className="absolute bottom-0 left-0 right-0 z-20 h-1.5 bg-black/50">
                                <div className="h-full bg-blue-500" style={{ width: `${progress}%` }} />
                              </div>
                            )}
                          </>
                        )
                      })()}
                      <div className="absolute inset-0 bg-gradient-to-t from-dark-900 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                      <div className="absolute inset-0 flex items-center justify-center p-2 pointer-events-none opacity-0 group-hover:opacity-100">
                        <span className="text-xs text-gray-400 text-center line-clamp-3 break-all">{getDisplayTitle(movie)}</span>
                      </div>
                    </div>
                    <div className="p-2.5 min-w-0">
                      <p className="text-xs font-medium text-white leading-tight break-words line-clamp-2">
                        {getDisplayTitle(movie)}
                      </p>
                      <div className="flex items-center gap-2 mt-1 text-[10px] text-gray-500">
                        <span>{movie.code}</span>
                        {movie.duration && <span>{movie.duration}分</span>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {totalPages > 1 && (
                <div className="flex justify-center items-center gap-2 mt-8">
                  <button
                    onClick={() => setPage(Math.max(0, page - 1))}
                    disabled={page === 0}
                    className="px-4 py-2 bg-dark-700 rounded-lg text-sm disabled:opacity-30 hover:bg-dark-600 transition-colors"
                  >
                    上一页
                  </button>
                  <span className="text-sm text-gray-400 px-3">
                    {page + 1} / {totalPages}
                  </span>
                  <button
                    onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
                    disabled={page >= totalPages - 1}
                    className="px-4 py-2 bg-dark-700 rounded-lg text-sm disabled:opacity-30 hover:bg-dark-600 transition-colors"
                  >
                    下一页
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function TreeItem({ node, selectedPath, onSelect, excluded, onToggleExclude, depth }: {
  node: FolderNode
  selectedPath: string
  onSelect: (path: string) => void
  excluded: Set<string>
  onToggleExclude: (path: string) => void
  depth: number
}) {
  const [open, setOpen] = useState(depth < 2)
  const hasChildren = node.children && node.children.length > 0
  const isSelected = selectedPath === node.path
  const included = !excluded.has(node.path)

  return (
    <div>
      <div
        className={`flex items-center gap-1 px-2 py-1 rounded-lg text-sm transition-colors group ${
          isSelected
            ? 'bg-blue-600/20 text-blue-400'
            : 'text-gray-400 hover:bg-dark-800'
        }`}
        style={{ paddingLeft: `${depth * 16 + 4}px` }}
      >
        {hasChildren && (
          <span
            onClick={(e) => { e.stopPropagation(); setOpen(!open) }}
            className="text-[10px] w-4 text-center shrink-0 cursor-pointer hover:text-white"
          >
            {open ? '\u25BC' : '\u25B6'}
          </span>
        )}
        {!hasChildren && <span className="w-4 shrink-0" />}
        <input
          type="checkbox"
          checked={included}
          onChange={(e) => {
            e.stopPropagation()
            onToggleExclude(node.path)
          }}
          className="w-3 h-3 shrink-0 rounded accent-blue-600 cursor-pointer"
        />
        <span
          onClick={() => onSelect(node.path)}
          className={`truncate flex-1 cursor-pointer ${included ? '' : 'opacity-40'}`}
        >
          {node.name}
        </span>
        {node.movie_count > 0 && (
          <span className="text-[10px] text-gray-600 shrink-0">{node.movie_count}</span>
        )}
      </div>
      {open && hasChildren && node.children!.map((child) => (
        <TreeItem
          key={child.path + (child.name || '')}
          node={child}
          selectedPath={selectedPath}
          onSelect={onSelect}
          excluded={excluded}
          onToggleExclude={onToggleExclude}
          depth={depth + 1}
        />
      ))}
    </div>
  )
}
