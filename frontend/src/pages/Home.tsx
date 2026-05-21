import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, FolderNode, Movie } from '../api'
import { getExcluded, getUiPrefs } from '../store'
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
  const hideHomeTitleText = getUiPrefs().hideHomeTitleText

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
    } catch (err) {
      alert(`刮削失败：${err instanceof Error ? err.message : '请查看后端日志'}`)
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
    } catch (err) {
      alert(`替换失败：${err instanceof Error ? err.message : '请查看后端日志'}`)
    } finally {
      setFolderScrapeApplying(false)
    }
  }, [activeFolderPath, activeMediaRoot, load, folderScrapeApplying])

  const handleChangeFolderCover = useCallback(async () => {
    setFolderMenu(null)
    try {
      const movies = await api.movies({ folder: activeFolderPath, media_root: activeMediaRoot, limit: 1 })
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
  }, [activeFolderPath, activeMediaRoot])

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
      const data = await api.movies({ folder: activeFolderPath, media_root: activeMediaRoot, limit: 1 })
      if (!data.movies || data.movies.length === 0) { alert('目录下无影片'); return }
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
    <div className="space-y-5">
      <div className="glass-panel flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        {!hideHomeTitleText && (
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-apple-blue/80">Library</p>
            <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              {tab === 'recent' ? '最近观看' : '我的媒体库'}
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              {tab === 'recent' ? `共 ${recentTotal} 部` : `共 ${tree.length} 个目录`}
            </p>
          </div>
        )}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <div className="flex rounded-full border border-white/10 bg-white/[0.06] p-1 backdrop-blur-xl">
            <button onClick={() => setTab('library')}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-all ${tab === 'library' ? 'bg-apple-blue/80 text-white shadow-glow' : 'text-gray-400 hover:text-white'}`}>
              媒体库
            </button>
            <button onClick={() => setTab('recent')}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-all ${tab === 'recent' ? 'bg-apple-blue/80 text-white shadow-glow' : 'text-gray-400 hover:text-white'}`}>
              最近观看
            </button>
          </div>
          <SortDropdown options={sortOptions} current={sort} onChange={handleSort} />
        </div>
      </div>

      {tab === 'recent' ? (
        recentMovies.length === 0 ? (
          <div className="glass-panel py-20 text-center text-gray-500">
            <p className="mb-2 text-3xl font-light text-white/60">--</p>
            <p>还没有观看记录</p>
            <p className="mt-2 text-sm text-gray-600">点击"已看"标签即可记录观看</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7">
            {recentMovies.map((movie) => (
              <MovieCard key={movie.id} movie={movie} onUpdated={loadRecent} />
            ))}
          </div>
        )
      ) : (
        tree.length === 0 ? (
          <div className="glass-panel py-20 text-center text-gray-500">
            <p className="mb-2 text-3xl font-light text-white/60">--</p>
            <p className="text-lg text-white/70">未找到媒体文件</p>
            <p className="mt-2 text-sm">请配置 MEDIA_ROOT 或检查浏览页勾选状态</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7">
            {tree.map((node) => {
              const coverSrc = getCoverSrc(node.random_cover || node.cover)
              return (
                <div key={node.path}
                  onClick={() => goFolder(node.path, node.media_root)}
                  onContextMenu={(e) => handleFolderContextMenu(e, node)}
                  className="glass-card apple-focus group cursor-pointer overflow-hidden"
                >
                  <div className="relative aspect-[2/3] bg-white/[0.04]">
                    {coverSrc ? (
                      <img src={coverSrc} className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" alt={node.name} loading="lazy"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-4xl text-white/10" />
                    )}
                    <WatchedBadge watched={!!node.folder_watched} />
                    <div className="absolute inset-0 bg-gradient-to-t from-black via-black/35 to-transparent opacity-95" />
                    {!node.folder_watched && (node.progress_percent || 0) > 0 && (
                      <div className="absolute bottom-0 left-0 right-0 z-20 h-1 bg-white/15 backdrop-blur">
                        <div className="h-full rounded-r-full bg-apple-blue shadow-glow" style={{ width: `${node.progress_percent || 0}%` }} />
                      </div>
                    )}
                    <div className="absolute bottom-0 left-0 right-0 min-w-0 p-3">
                      <p className="line-clamp-2 break-words text-sm font-semibold leading-snug text-white drop-shadow">{node.display_title || node.name}</p>
                      <p className="mt-1 text-xs text-gray-400">{node.movie_count} 部</p>
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 backdrop-blur-xl">
          <div className="glass-modal max-h-[85vh] w-full max-w-3xl overflow-y-auto p-4 sm:p-5">
            <h2 className="mb-1 text-lg font-bold text-white">手动刮削目录: {activeFolderName}</h2>
            <p className="mb-4 text-xs text-gray-500">搜索关键词，选择结果应用到整个目录</p>
            <div className="mb-4 flex flex-col gap-2 sm:flex-row">
              <input type="text" value={folderScrapeQuery} onChange={e => { setFolderScrapeQuery(e.target.value); setFolderScrapeResults([]) }}
                onKeyDown={e => { if (e.key === 'Enter') handleFolderScrapeSearch() }}
                placeholder="搜索关键词" autoFocus
                className="glass-input flex-1 px-3 py-2 text-sm" />
              <select value={folderScrapeSrc} onChange={e => setFolderScrapeSrc(e.target.value)}
                className="glass-input px-3 py-2 text-sm text-gray-300">
                <option value="">自动</option>
                <option value="tmdb_movie">TMDB 电影</option>
                <option value="tmdb_tv">TMDB 剧集/番剧</option>
                <option value="bangumi">Bangumi</option>
                <option value="javdatabase">Javdatabase</option>
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
                    const bd = folderScrapeBackdrops.find(b => b.source_id === r.source_id && b.source === r.source)
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
                                api.changeFolderBackdrop(activeFolderPath, activeMediaRoot, bd.backdrop_url!).then(() => { alert('背景图已更新'); load() }).catch(() => alert('失败'))
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
        </div>
      )}

      {folderScrapeApplying && (
        <div className="fixed bottom-3 left-3 right-3 z-[60] rounded-3xl border border-white/10 bg-black/60 p-4 shadow-glass backdrop-blur-2xl sm:bottom-4 sm:left-auto sm:right-4 sm:w-72">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-white">正在应用刮削结果...</p>
              <p className="mt-1 text-xs text-gray-500">更新目录元数据和封面</p>
            </div>
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-apple-blue border-t-transparent" />
          </div>
        </div>
      )}

      {showFolderCover && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 backdrop-blur-xl">
          <div className="glass-modal max-h-[85vh] w-full max-w-3xl overflow-y-auto p-4 sm:p-5">
            <h2 className="mb-1 text-lg font-bold text-white">更换封面与背景: {activeFolderName}</h2>
            <p className="mb-4 text-xs text-gray-500">选择封面图或背景图应用到该目录下所有影片</p>

            {folderAltCovers.length > 0 && (
              <>
                <h3 className="mb-2 text-sm font-medium text-gray-400">封面图 (竖屏海报)</h3>
                <div className="mb-4 grid grid-cols-3 gap-3 sm:grid-cols-4">
                  {folderAltCovers.map((c, i) => (
                    <div key={i} onClick={() => handleSelectFolderCover(c.url)}
                      className="aspect-[2/3] cursor-pointer overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] transition-all hover:border-apple-blue/40 hover:shadow-glow">
                      <img src={c.url} alt={c.source} className="h-full w-full object-cover" />
                      <div className="p-1 text-center text-[9px] text-gray-500">{c.source}</div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {folderAltBackdrops.length > 0 && (
              <>
                <h3 className="mb-2 mt-4 text-sm font-medium text-gray-400">背景图 (横屏 Fanart)</h3>
                <div className="mb-4 grid grid-cols-2 gap-3">
                  {folderAltBackdrops.map((b, i) => (
                    <div key={i} onClick={() => {
                      api.changeFolderBackdrop(activeFolderPath, activeMediaRoot, b.url).then(() => { alert('背景图已更新'); load() }).catch(() => alert('失败'))
                    }}
                      className="aspect-video cursor-pointer overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] transition-all hover:border-apple-blue/40 hover:shadow-glow">
                      <img src={b.url} alt={b.source} className="h-full w-full object-cover" />
                      <div className="p-1 text-center text-[9px] text-gray-500">{b.source}</div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {folderAltCovers.length === 0 && folderAltBackdrops.length === 0 && (
              <p className="py-4 text-center text-sm text-gray-500">没有可用的封面或背景图</p>
            )}

            <div className="flex gap-3">
              <button onClick={() => setShowFolderCover(false)}
                className="glass-button flex-1 py-2 text-sm text-gray-300">取消</button>
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
