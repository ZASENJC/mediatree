import { useEffect, useState, useCallback, useMemo } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { api, Movie, FolderNode } from '../api'
import { getExcluded, setExcluded } from '../store'
import { getCached, setCache } from '../cache'
import { saveScrollPos } from '../scroll'
import { WatchedBadge } from '../components/WatchedBadge'
import SortDropdown from '../components/SortDropdown'

import { BROWSE_SORT_OPTIONS } from '../constants/sortOptions'

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

  const sortedFolders = useMemo(() => {
    const sortNodes = (nodes: FolderNode[]): FolderNode[] => {
      let sorted = [...nodes]
      if (sort === 'random') {
        sorted = sorted.sort(() => Math.random() - 0.5)
      } else if (sort === 'name' || sort === 'created_asc' || sort === 'release_date_asc') {
        sorted = sorted.sort((a, b) => a.name.localeCompare(b.name))
      } else {
        sorted = sorted.sort((a, b) => b.name.localeCompare(a.name))
      }
      return sorted.map(node => ({
        ...node,
        children: node.children ? sortNodes(node.children) : undefined,
      }))
    }
    return sortNodes(folders)
  }, [folders, sort])

  useEffect(() => {
    api.folders().then(data => setFolders(data.tree))
  }, [])

  useEffect(() => {
    setPage(0)
  }, [folder, actress, staff, sort, codeQuery])

  useEffect(() => {
    setLoading(true)
    const params: Record<string, string | number> = {
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
      {sortedFolders.length === 0 ? (
        <p className="text-xs text-gray-600 px-2">无文件夹</p>
      ) : (
        sortedFolders.map((node) => (
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
    <div className="space-y-5">
      <div className="glass-panel flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <button
              onClick={() => setMobileTreeOpen(true)}
              className="glass-button h-9 w-9 shrink-0 p-0 lg:hidden"
              aria-label="打开文件夹"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
                <path strokeLinecap="round" d="M4 7h16M4 12h16M4 17h16" />
              </svg>
            </button>
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-[0.24em] text-apple-blue/80">Browse</p>
              <h1 className="min-w-0 break-words text-2xl font-bold tracking-tight text-white sm:text-3xl">
                {staff ? `Staff: ${decodeURIComponent(staff)}` : actress ? `演员: ${decodeURIComponent(actress)}` : codeQuery ? `搜索: ${decodeURIComponent(codeQuery)}` : folder ? `浏览: ${decodeURIComponent(folder)}` : '全部影片'}
              </h1>
              <p className="mt-1 text-sm text-gray-500">共 {total} 部</p>
            </div>
          </div>
        </div>
        <SortDropdown options={BROWSE_SORT_OPTIONS} current={sort} onChange={handleSortChange} variant="menu" />
      </div>

      {mobileTreeOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-2xl" onClick={() => setMobileTreeOpen(false)} />
          <aside className="glass-modal absolute left-3 top-3 h-[calc(100%-1.5rem)] w-[82vw] max-w-xs overflow-hidden p-4">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-apple-blue/70">Folders</p>
                <h2 className="text-sm font-semibold text-white">文件夹</h2>
              </div>
              <button
                onClick={() => setMobileTreeOpen(false)}
                className="glass-button h-8 w-8 p-0 text-gray-300"
                aria-label="关闭文件夹"
              >
                ×
              </button>
            </div>
            {renderFolderTree()}
          </aside>
        </div>
      )}

      <div className="flex gap-5">
        <div className="hidden w-60 shrink-0 lg:block">
          <div className="glass-panel sticky top-20 p-4">
            <h3 className="mb-3 text-xs font-medium uppercase tracking-[0.24em] text-gray-500">文件夹</h3>
            {renderFolderTree()}
          </div>
        </div>

        <div className="min-w-0 flex-1">
          {loading ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 media-grid">
              {Array.from({ length: 12 }).map((_, i) => (
                <div key={i} className="aspect-[2/3] animate-pulse rounded-2xl border border-white/10 bg-white/[0.06] media-grid-card" />
              ))}
            </div>
          ) : movies.length === 0 ? (
            <div className="glass-panel py-20 text-center text-gray-500">
              <p className="mb-2 text-3xl font-light text-white/60">--</p>
              <p>没有找到影片</p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 media-grid">
                {movies.map((movie) => (
                  <div
                    key={movie.id}
                    onClick={() => { saveScrollPos(); navigate(`/detail/${movie.id}`) }}
                    className="glass-card apple-focus media-grid-card group cursor-pointer overflow-hidden"
                  >
                    <div className="relative aspect-[2/3] overflow-hidden bg-white/[0.04]">
                      <img
                        src={api.coverUrl(movie.id)}
                        alt={movie.code}
                        className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
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
                              <div className="absolute bottom-0 left-0 right-0 z-20 h-1 bg-white/15 backdrop-blur">
                                <div className="h-full rounded-r-full bg-apple-blue shadow-glow" style={{ width: `${progress}%` }} />
                              </div>
                            )}
                          </>
                        )
                      })()}
                      <div className="absolute inset-0 bg-gradient-to-t from-black via-black/35 to-transparent opacity-95" />
                      <div className="absolute bottom-0 left-0 right-0 min-w-0 p-3">
                        <p className="line-clamp-2 break-words text-sm font-semibold leading-snug text-white drop-shadow">
                          {getDisplayTitle(movie)}
                        </p>
                        <div className="mt-1 flex items-center gap-2 text-xs text-gray-400">
                          <span className="truncate">{movie.code}</span>
                          {movie.duration && <span className="shrink-0">{movie.duration}分</span>}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {totalPages > 1 && (
                <div className="mt-8 flex items-center justify-center gap-2">
                  <button
                    onClick={() => setPage(Math.max(0, page - 1))}
                    disabled={page === 0}
                    className="glass-button px-4 py-2 text-sm"
                  >
                    上一页
                  </button>
                  <span className="glass-chip px-3 py-2 text-sm text-gray-300">
                    {page + 1} / {totalPages}
                  </span>
                  <button
                    onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
                    disabled={page >= totalPages - 1}
                    className="glass-button px-4 py-2 text-sm"
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
        className={`group flex items-center gap-1 rounded-xl px-2 py-1 text-sm transition-all ${
          isSelected
            ? 'border border-apple-blue/30 bg-apple-blue/15 text-apple-blue shadow-glow'
            : 'text-gray-400 hover:bg-white/[0.08] hover:text-white'
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {hasChildren && (
          <span
            onClick={(e) => { e.stopPropagation(); setOpen(!open) }}
            className="w-4 shrink-0 cursor-pointer text-center text-[10px] text-gray-500 hover:text-white"
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
          className="h-3 w-3 shrink-0 cursor-pointer rounded accent-apple-blue"
        />
        <span
          onClick={() => onSelect(node.path)}
          className={`min-w-0 flex-1 cursor-pointer truncate ${included ? '' : 'opacity-40'}`}
        >
          {node.name}
        </span>
        {node.movie_count > 0 && (
          <span className="shrink-0 rounded-full bg-white/[0.08] px-1.5 py-0.5 text-[10px] text-gray-500">{node.movie_count}</span>
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
