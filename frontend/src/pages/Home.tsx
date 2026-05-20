import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, FolderNode, Movie } from '../api'
import { getExcluded } from '../store'
import { saveScrollPos, restoreScrollPos } from '../scroll'
import { getCached, setCache, clearCache } from '../cache'
import SortDropdown from '../components/SortDropdown'
import { MovieCard } from '../components/MovieCard'
import ContextMenu, { ContextMenuItem } from '../components/ContextMenu'
import EditModal from '../components/EditModal'
import { WatchedBadge } from '../components/WatchedBadge'

function encodeMediaPath(path: string): string {
  return path.split('/').map(encodeURIComponent).join('/')
}

function getCoverSrc(cover: string | null | undefined): string | null {
  if (!cover) return null
  if (cover.startsWith('http://') || cover.startsWith('https://')) return cover
  if (cover.startsWith('/api/')) return cover
  return `/api/media/${encodeMediaPath(cover)}`
}

type SortMode = 'name' | 'created_desc' | 'created_asc' | 'release_date_desc' | 'release_date_asc' | 'random'

const sortOptions = [
  { key: 'created_desc', label: '最近添加' },
  { key: 'created_asc', label: '最早添加' },
  { key: 'name', label: '名称' },
  { key: 'release_date_desc', label: '发行日期新到旧' },
  { key: 'release_date_asc', label: '发行日期旧到新' },
  { key: 'random', label: '随机' },
]

export default function Home() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const sort = (searchParams.get('sort') || 'created_desc') as SortMode
  const tab = searchParams.get('tab') || 'library'

  const [tree, setTree] = useState<FolderNode[]>([])
  const [recentMovies, setRecentMovies] = useState<Movie[]>([])
  const [recentTotal, setRecentTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [folderMenu, setFolderMenu] = useState<{ x: number; y: number; mediaRoot: string; folderPath: string; folderName: string } | null>(null)
  const [activeFolderPath, setActiveFolderPath] = useState('')
  const [activeMediaRoot, setActiveMediaRoot] = useState('')
  const [activeFolderName, setActiveFolderName] = useState('')

  const [showFolderScrape, setShowFolderScrape] = useState(false)
  const [folderScrapeQuery, setFolderScrapeQuery] = useState('')
  const [folderScrapeSrc, setFolderScrapeSrc] = useState('')
  const [folderScrapeResults, setFolderScrapeResults] = useState<any[]>([])
  const [folderScrapeBackdrops, setFolderScrapeBackdrops] = useState<any[]>([])
  const [folderScrapeSearching, setFolderScrapeSearching] = useState(false)
  const [folderScrapeApplying, setFolderScrapeApplying] = useState(false)

  const [showFolderCover, setShowFolderCover] = useState(false)
  const [folderAltCovers, setFolderAltCovers] = useState<{ url: string; source: string }[]>([])
  const [folderAltBackdrops, setFolderAltBackdrops] = useState<{ url: string; source: string }[]>([])
  const [showFolderBackdrop, setShowFolderBackdrop] = useState(false)

  const [showFolderEdit, setShowFolderEdit] = useState(false)
  const [editFolderMovie, setEditFolderMovie] = useState<Movie | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    api.folders().then((data) => {
      const ex = getExcluded()
      let filtered = data.tree.filter(n => n.movie_count > 0 && !ex.has(n.path))
      if (sort === 'name') {
        filtered.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
      } else if (sort === 'created_desc') {
        filtered.sort((a, b) => (b.created_max || '').localeCompare(a.created_max || ''))
      } else if (sort === 'created_asc') {
        filtered.sort((a, b) => (a.created_max || '').localeCompare(b.created_max || ''))
      } else if (sort === 'release_date_desc') {
        filtered.sort((a, b) => (b.created_max || '').localeCompare(a.created_max || ''))
      } else if (sort === 'release_date_asc') {
        filtered.sort((a, b) => (a.created_max || '').localeCompare(b.created_max || ''))
      } else if (sort === 'random') {
        for (let i = filtered.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          [filtered[i], filtered[j]] = [filtered[j], filtered[i]]
        }
      }
      setTree(filtered)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [sort])

  const loadRecent = useCallback(() => {
    setLoading(true)
    api.getRecentWatched(200).then((data) => {
      setRecentMovies(data.movies)
      setRecentTotal(data.total)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (tab === 'recent') loadRecent()
    else load()
  }, [load, loadRecent, tab])
  useEffect(() => { restoreScrollPos() }, [])

  const handleSort = (s: string) => {
    setSearchParams({ tab, sort: s }, { replace: true })
  }

  const setTab = (t: string) => {
    setSearchParams({ tab: t }, { replace: true })
  }

  const goFolder = (path: string, mediaRoot?: string) => {
    saveScrollPos()
    const p = new URLSearchParams()
    p.set('path', path)
    if (mediaRoot) p.set('media_root', mediaRoot)
    navigate(`/folder?${p.toString()}`)
  }

  const handleFolderContextMenu = (e: React.MouseEvent, node: FolderNode) => {
    e.preventDefault()
    setActiveFolderPath(node.path)
    setActiveMediaRoot(node.media_root || '')
    setActiveFolderName(node.name)
    setFolderMenu({
      x: e.clientX, y: e.clientY,
      mediaRoot: node.media_root || '', folderPath: node.path, folderName: node.name,
    })
  }

  const handleRescanFolder = useCallback(async () => {
    clearCache()
    try {
      await api.rescrapeFolder(activeFolderPath, activeMediaRoot)
      alert('刮削任务已触发')
      setFolderMenu(null)
      load()
    } catch {
      alert('刮削失败，请检查刮削器配置')
    }
  }, [activeFolderPath, activeMediaRoot, load])

  const handleManualScrapeFolder = useCallback(() => {
    setFolderScrapeQuery(activeFolderName || '')
    setFolderScrapeSrc('')
    setFolderScrapeResults([])
    setShowFolderScrape(true)
    setFolderMenu(null)
  }, [activeFolderName])

  const handleFolderScrapeSearch = useCallback(async () => {
    if (!folderScrapeQuery.trim()) return
    setFolderScrapeSearching(true)
    try {
      const data = await api.searchScrape(folderScrapeQuery.trim(), folderScrapeSrc || undefined)
      const results = data.results || []
      setFolderScrapeResults(results)
      if (results.length === 0) {
        alert('没有找到匹配结果')
      } else {
        api.fetchSearchBackdrops(results).then(bd => {
          setFolderScrapeBackdrops(bd.backdrops || [])
        }).catch(() => {})
      }
    } catch {
      console.error('Search scrape failed')
    }
    setFolderScrapeSearching(false)
  }, [folderScrapeQuery, folderScrapeSrc])

  const handleSelectFolderScrapeResult = useCallback(async (result: any) => {
    if (folderScrapeApplying) return
    setFolderScrapeApplying(true)
    try {
      clearCache()
      const res = await api.applyFolderScrape(activeFolderPath, activeMediaRoot, result.source_id, result.source, result.media_type)
      if (res.ok) {
        alert(`已应用: ${res.title}`)
        setShowFolderScrape(false)
        setFolderScrapeResults([])
        setFolderScrapeQuery('')
        await load()
      } else {
        alert('应用失败')
      }
    } catch {
      alert('替换失败，请检查刮削器配置')
    } finally {
      setFolderScrapeApplying(false)
    }
  }, [activeFolderPath, activeMediaRoot, load, folderScrapeApplying])

  const handleChangeFolderCover = useCallback(async () => {
    setFolderMenu(null)
    try {
      const movies = await api.movies({ folder: activeFolderPath, limit: 1 })
      if (!movies.movies || movies.movies.length === 0) { alert('目录下无影片'); return }
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
  }, [activeFolderPath])

  const handleSelectFolderCover = useCallback(async (url: string) => {
    try {
      clearCache()
      await api.changeFolderCover(activeFolderPath, activeMediaRoot, url)
      alert('封面已更新')
      load()
    } catch {
      console.error('Change folder cover failed')
    }
  }, [activeFolderPath, activeMediaRoot, load])

  const handleEditFolder = useCallback(async () => {
    setFolderMenu(null)
    try {
      const data = await api.movies({ folder: activeFolderPath, limit: 1 })
      if (!data.movies || data.movies.length === 0) { alert('目录下无影片'); return }
      setEditFolderMovie(data.movies[0])
      setShowFolderEdit(true)
    } catch {
      console.error('Load movie for edit failed')
    }
  }, [activeFolderPath])

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
      alert('已删除')
      load()
    } catch {
      alert('删除失败')
    }
  }, [activeFolderName, activeFolderPath, activeMediaRoot, load])

  const folderMenuItems: ContextMenuItem[] = [
    { label: '重新刮削', onClick: handleRescanFolder },
    { label: '手动刮削', onClick: handleManualScrapeFolder },
    { label: '更换封面', onClick: handleChangeFolderCover },
    { label: '编辑信息', onClick: handleEditFolder },
    { label: '删除', danger: true, onClick: handleDeleteFolder },
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-pulse text-gray-400 text-lg">加载中...</div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div className="flex items-center gap-3 sm:gap-4">
          <button onClick={() => setTab('library')}
            className={`text-base sm:text-lg font-bold transition-colors ${tab === 'recent' ? 'text-gray-500 hover:text-gray-300' : 'text-white'}`}>
            我的媒体库
          </button>
          <button onClick={() => setTab('recent')}
            className={`text-base sm:text-lg font-bold transition-colors ${tab === 'library' ? 'text-gray-500 hover:text-gray-300' : 'text-white'}`}>
            最近观看
          </button>
        </div>
        <SortDropdown options={sortOptions} current={sort} onChange={handleSort} />
      </div>

      {tab === 'recent' ? (
        recentMovies.length === 0 ? (
          <div className="text-center py-20 text-gray-500">
            <p className="text-2xl font-light mb-2">--</p>
            <p>还没有观看记录</p>
            <p className="text-sm mt-2 text-gray-600">点击"已看"标签即可记录观看</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-3 sm:gap-4">
            {recentMovies.map((movie) => (
              <MovieCard key={movie.id} movie={movie} onUpdated={loadRecent} />
            ))}
          </div>
        )
      ) : (
        tree.length === 0 ? (
          <div className="text-center py-20 text-gray-500">
            <p className="text-2xl font-light mb-2">--</p>
            <p className="text-lg">未找到媒体文件</p>
            <p className="text-sm mt-2">请配置 MEDIA_ROOT 或检查浏览页勾选状态</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-3 sm:gap-4">
            {tree.map((node) => {
              const coverSrc = getCoverSrc(node.random_cover || node.cover)
              return (
                <div key={node.path}
                  onClick={() => goFolder(node.path, node.media_root)}
                  onContextMenu={(e) => handleFolderContextMenu(e, node)}
                  className="group cursor-pointer bg-dark-800 rounded-lg overflow-hidden border border-dark-700 hover:border-blue-500/40 transition-all hover:bg-dark-700/50"
                >
                  <div className="aspect-[2/3] bg-dark-700 relative">
                    {coverSrc ? (
                      <img src={coverSrc} className="w-full h-full object-cover" alt={node.name} loading="lazy"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-4xl text-dark-500" />
                    )}
                    <WatchedBadge watched={!!node.folder_watched} />
                    <div className="absolute inset-0 bg-gradient-to-t from-dark-900 via-dark-900/30 to-transparent" />
                    {!node.folder_watched && (node.progress_percent || 0) > 0 && (
                      <div className="absolute bottom-0 left-0 right-0 z-20 h-1.5 bg-black/50">
                        <div className="h-full bg-blue-500" style={{ width: `${node.progress_percent || 0}%` }} />
                      </div>
                    )}
                    <div className="absolute bottom-0 left-0 right-0 p-3 min-w-0">
                      <p className="text-sm font-semibold text-white leading-snug break-words line-clamp-2">{node.display_title || node.name}</p>
                      <p className="text-xs text-gray-400 mt-1">{node.movie_count} 部</p>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )
      )}

      {folderMenu && (
        <ContextMenu x={folderMenu.x} y={folderMenu.y} items={folderMenuItems}
          onClose={() => setFolderMenu(null)} />
      )}

      {showFolderScrape && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="bg-dark-800 border border-dark-600 rounded-lg p-4 sm:p-5 w-full max-w-3xl mx-4 shadow-2xl max-h-[85vh] overflow-y-auto">
            <h2 className="text-lg font-bold mb-3">手动刮削目录: {activeFolderName}</h2>
            <p className="text-xs text-gray-500 mb-3">搜索关键词，选择结果应用到整个目录</p>
            <div className="flex flex-col sm:flex-row gap-2 mb-3">
              <input type="text" value={folderScrapeQuery} onChange={e => { setFolderScrapeQuery(e.target.value); setFolderScrapeResults([]) }}
                onKeyDown={e => { if (e.key === 'Enter') handleFolderScrapeSearch() }}
                placeholder="搜索关键词" autoFocus
                className="flex-1 px-3 py-2 bg-dark-700 border border-dark-600 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500" />
              <select value={folderScrapeSrc} onChange={e => setFolderScrapeSrc(e.target.value)}
                className="px-3 py-2 bg-dark-700 border border-dark-600 rounded-lg text-sm text-gray-300 focus:outline-none focus:border-blue-500">
                <option value="">自动</option>
                <option value="tmdb_movie">TMDB 电影</option>
                <option value="tmdb_tv">TMDB 剧集/番剧</option>
                <option value="bangumi">Bangumi</option>
                <option value="javdatabase">Javdatabase</option>
              </select>
              <button onClick={handleFolderScrapeSearch} disabled={folderScrapeSearching}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm">
                {folderScrapeSearching ? '搜索中...' : '搜索'}
              </button>
            </div>
            {folderScrapeResults.length > 0 && (
              <>
                <p className="text-xs text-gray-500 mb-2">共 {folderScrapeResults.length} 个结果，点击应用元数据，长按/右键查看封面和背景图可选</p>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-h-[50vh] overflow-y-auto">
                  {folderScrapeResults.map((r, i) => {
                    const bd = folderScrapeBackdrops.find(b => b.source_id === r.source_id && b.source === r.source)
                    return (
                      <div key={i} className="bg-dark-700 rounded-lg overflow-hidden border border-dark-600 hover:border-blue-500 transition-colors">
                        <div className="aspect-[2/3] bg-dark-800 cursor-pointer"
                          onClick={() => handleSelectFolderScrapeResult(r)}>
                          {r.poster_url ? (
                            <img src={r.poster_url} alt={r.title} className="w-full h-full object-cover" />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center text-xs text-gray-600 p-2 text-center">{r.title}</div>
                          )}
                        </div>
                        <div className="p-2">
                          <p className="text-xs font-medium text-white truncate">{r.title}</p>
                          <p className="text-[10px] text-gray-500 mt-0.5">
                            <span className={`inline-block px-1 py-0.5 rounded-md text-[9px] ${r.source === 'tmdb' ? 'bg-blue-600/30 text-blue-300' : r.source === 'bangumi' ? 'bg-pink-600/30 text-pink-300' : 'bg-green-600/30 text-green-300'}`}>
                              {r.source}
                            </span>
                            {' '}{r.year}{r.original_title ? ` · ${r.original_title}` : ''}
                          </p>
                          <div className="flex gap-1 mt-1.5">
                            <a href="#" onClick={e => { e.preventDefault(); e.stopPropagation(); handleSelectFolderScrapeResult(r) }}
                              className="flex-1 text-center px-1 py-0.5 bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 rounded-lg text-[10px]">应用</a>
                            {bd?.backdrop_url && (
                              <a href="#" onClick={e => { e.preventDefault(); e.stopPropagation();
                                api.changeFolderBackdrop(activeFolderPath, activeMediaRoot, bd.backdrop_url!).then(() => { alert('背景图已更新'); load() }).catch(() => alert('失败'))
                              }}
                                className="px-1 py-0.5 bg-dark-600 text-gray-400 hover:text-white rounded-lg text-[10px]">选背景</a>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </>
            )}
            <div className="flex gap-3 mt-4">
              <button onClick={() => { setShowFolderScrape(false); setFolderScrapeResults([]) }}
                className="flex-1 py-2 bg-dark-700 hover:bg-dark-600 rounded-lg text-sm text-gray-400">取消</button>
            </div>
          </div>
        </div>
      )}

      {folderScrapeApplying && (
        <div className="fixed left-3 right-3 bottom-3 sm:left-auto sm:right-4 sm:bottom-4 z-[60] sm:w-64 rounded-lg border border-dark-600 bg-dark-800/95 shadow-2xl p-4 backdrop-blur">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-white">正在应用刮削结果...</p>
              <p className="text-xs text-gray-500 mt-1">更新目录元数据和封面</p>
            </div>
            <div className="w-4 h-4 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />
          </div>
        </div>
      )}

      {showFolderCover && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="bg-dark-800 border border-dark-600 rounded-lg p-4 sm:p-5 w-full max-w-3xl mx-4 shadow-2xl max-h-[85vh] overflow-y-auto">
            <h2 className="text-lg font-bold mb-3">更换封面与背景: {activeFolderName}</h2>
            <p className="text-xs text-gray-500 mb-3">选择封面图或背景图应用到该目录下所有影片</p>

            {folderAltCovers.length > 0 && (
              <>
                <h3 className="text-sm font-medium text-gray-400 mb-2">封面图 (竖屏海报)</h3>
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-3 mb-4">
                  {folderAltCovers.map((c, i) => (
                    <div key={i} onClick={() => handleSelectFolderCover(c.url)}
                      className="aspect-[2/3] bg-dark-700 rounded-lg overflow-hidden border border-dark-600 hover:border-blue-500 cursor-pointer transition-colors">
                      <img src={c.url} alt={c.source} className="w-full h-full object-cover" />
                      <div className="p-1 text-[9px] text-gray-500 text-center">{c.source}</div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {folderAltBackdrops.length > 0 && (
              <>
                <h3 className="text-sm font-medium text-gray-400 mb-2 mt-4">背景图 (横屏 Fanart)</h3>
                <div className="grid grid-cols-2 gap-3 mb-4">
                  {folderAltBackdrops.map((b, i) => (
                    <div key={i} onClick={() => {
                      api.changeFolderBackdrop(activeFolderPath, activeMediaRoot, b.url).then(() => { alert('背景图已更新'); load() }).catch(() => alert('失败'))
                    }}
                      className="aspect-video bg-dark-700 rounded-lg overflow-hidden border border-dark-600 hover:border-blue-500 cursor-pointer transition-colors">
                      <img src={b.url} alt={b.source} className="w-full h-full object-cover" />
                      <div className="p-1 text-[9px] text-gray-500 text-center">{b.source}</div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {folderAltCovers.length === 0 && folderAltBackdrops.length === 0 && (
              <p className="text-sm text-gray-500 text-center py-4">没有可用的封面或背景图</p>
            )}

            <div className="flex gap-3">
              <button onClick={() => setShowFolderCover(false)}
                className="flex-1 py-2 bg-dark-700 hover:bg-dark-600 rounded-lg text-sm text-gray-400">取消</button>
            </div>
          </div>
        </div>
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
