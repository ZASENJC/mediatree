import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, FolderNode, Movie } from '../api'
import { getExcluded, getUiPrefs } from '../store'
import { saveScrollPos, restoreScrollPos } from '../scroll'
import { showToast } from '../toast'
import { clearCache } from '../cache'
import SortDropdown from '../components/SortDropdown'
import { MovieCard } from '../components/MovieCard'
import ContextMenu, { ContextMenuItem } from '../components/ContextMenu'
import EditModal, { type EditFields } from '../components/EditModal'
import { WatchedBadge } from '../components/WatchedBadge'
import ManualScrapeModal from '../components/ManualScrapeModal'
import CoverPickerModal from '../components/CoverPickerModal'

function encodeMediaPath(path: string): string {
  return path.split('/').map(encodeURIComponent).join('/')
}

function getCoverSrc(cover: string | null | undefined): string | null {
  if (!cover) return null
  if (cover.startsWith('http://') || cover.startsWith('https://')) return cover
  if (cover.startsWith('/api/')) return cover
  return `/api/media/${encodeMediaPath(cover)}`
}

import { LIBRARY_SORT_OPTIONS } from '../constants/sortOptions'

type SortMode = 'name' | 'created_desc' | 'created_asc' | 'release_date_desc' | 'release_date_asc' | 'random'

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

  const [hoveredFolder, setHoveredFolder] = useState<string | null>(null)
  const [folderWatched, setFolderWatched] = useState<Record<string, boolean>>({})

  const handleToggleFolderWatched = async (e: React.MouseEvent, node: FolderNode) => {
    e.stopPropagation()
    const current = folderWatched[node.path] ?? !!node.folder_watched
    const newVal = !current
    setFolderWatched(prev => ({ ...prev, [node.path]: newVal }))
    try {
      await api.setFolderWatched(node.path, node.media_root || '', newVal)
      clearCache()
    } catch {
      setFolderWatched(prev => ({ ...prev, [node.path]: current }))
    }
  }

  const [showFolderScrape, setShowFolderScrape] = useState(false)
  const [showFolderCover, setShowFolderCover] = useState(false)
  const [folderAltCovers, setFolderAltCovers] = useState<{ url: string; source: string }[]>([])
  const [folderAltBackdrops, setFolderAltBackdrops] = useState<{ url: string; source: string }[]>([])
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
      showToast('刮削任务已触发')
      setFolderMenu(null)
      load()
    } catch (err) {
      showToast(`刮削失败：${err instanceof Error ? err.message : '请查看后端日志'}`)
    }
  }, [activeFolderPath, activeMediaRoot, load])

  const handleManualScrapeFolder = useCallback(() => {
    setShowFolderScrape(true)
    setFolderMenu(null)
  }, [])

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
    } catch (err) {
      console.error('Load covers failed', err)
    }
  }, [activeFolderPath, activeMediaRoot])

  const handleSelectFolderCover = useCallback(async (url: string) => {
    try {
      clearCache()
      await api.changeFolderCover(activeFolderPath, activeMediaRoot, url)
      showToast('封面已更新')
      load()
    } catch (err) {
      console.error('Change folder cover failed', err)
    }
  }, [activeFolderPath, activeMediaRoot, load])

  const handleEditFolder = useCallback(async () => {
    setFolderMenu(null)
    try {
      const data = await api.movies({ folder: activeFolderPath, media_root: activeMediaRoot, limit: 1 })
      if (!data.movies || data.movies.length === 0) { showToast('目录下无影片'); return }
      setEditFolderMovie(data.movies[0])
      setShowFolderEdit(true)
    } catch (err) {
      console.error('Load movie for edit failed', err)
    }
  }, [activeFolderPath, activeMediaRoot])

  const handleFolderEditSave = useCallback(async (fields: EditFields) => {
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
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-apple-blue/80">Library</p>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            {tab === 'recent' ? '最近观看' : '我的媒体库'}
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            {tab === 'recent' ? `共 ${recentTotal} 部` : `共 ${tree.length} 个目录`}
          </p>
        </div>
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
          <SortDropdown options={LIBRARY_SORT_OPTIONS} current={sort} onChange={handleSort} />
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
              <MovieCard key={movie.id} movie={movie} onUpdated={loadRecent} hideTitle={hideHomeTitleText} />
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
                  onMouseEnter={() => setHoveredFolder(node.path)}
                  onMouseLeave={() => setHoveredFolder(null)}
                  className="glass-card apple-focus group cursor-pointer overflow-hidden"
                >
                  <div className="relative aspect-[2/3] bg-white/[0.04]">
                    {coverSrc ? (
                      <img src={coverSrc} className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" alt={node.name} loading="lazy"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-4xl text-white/10" />
                    )}
                    <WatchedBadge watched={folderWatched[node.path] ?? !!node.folder_watched} />
                    {hoveredFolder === node.path && (
                      <button
                        onClick={(e) => handleToggleFolderWatched(e, node)}
                        className={`absolute right-2 top-2 z-20 flex h-8 w-8 items-center justify-center rounded-full shadow-lg backdrop-blur-xl transition-all ${
                          (folderWatched[node.path] ?? !!node.folder_watched)
                            ? 'border border-apple-mint/40 bg-apple-mint/80 text-white'
                            : 'border border-white/20 bg-black/50 text-white/70 hover:bg-apple-mint/80 hover:text-white hover:border-apple-mint/40'
                        }`}
                        title={(folderWatched[node.path] ?? !!node.folder_watched) ? '取消已看' : '标记已看'}
                      >
                        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      </button>
                    )}
                    {!hideHomeTitleText && (
                    <>
                    <div className="absolute inset-0 bg-gradient-to-t from-black via-black/35 to-transparent opacity-95" />
                    {!(folderWatched[node.path] ?? !!node.folder_watched) && (node.progress_percent || 0) > 0 && (
                      <div className="absolute bottom-0 left-0 right-0 z-20 h-1 bg-white/15 backdrop-blur">
                        <div className="h-full rounded-r-full bg-apple-blue shadow-glow" style={{ width: `${node.progress_percent || 0}%` }} />
                      </div>
                    )}
                    <div className="absolute bottom-0 left-0 right-0 min-w-0 p-3">
                      <p className="line-clamp-2 break-words text-sm font-semibold leading-snug text-white drop-shadow">{node.display_title || node.name}</p>
                      <p className="mt-1 text-xs text-gray-400">{node.movie_count} 部</p>
                    </div>
                    </>
                    )}
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
        <ManualScrapeModal
          title={`手动刮削目录: ${activeFolderName}`}
          initialQuery={activeFolderName || ''}
          showBackdropButton={true}
          onApply={async (result) => {
            clearCache()
            const res = await api.applyFolderScrape(activeFolderPath, activeMediaRoot, result.source_id, result.source, result.media_type)
            if (res.ok) {
              showToast(`已应用: ${res.title}`)
              setShowFolderScrape(false)
              await load()
            } else {
              throw new Error('应用失败')
            }
          }}
          onSelectBackdrop={(backdropUrl) => {
            api.changeFolderBackdrop(activeFolderPath, activeMediaRoot, backdropUrl).then(() => {
              showToast('背景图已更新')
              load()
            }).catch(() => showToast('失败'))
          }}
          onClose={() => setShowFolderScrape(false)}
        />
      )}

      {showFolderCover && (
        <CoverPickerModal
          title={`更换封面与背景: ${activeFolderName}`}
          covers={folderAltCovers}
          backdrops={folderAltBackdrops}
          onSelectCover={async (url) => {
            clearCache()
            await api.changeFolderCover(activeFolderPath, activeMediaRoot, url)
            showToast('封面已更新')
            load()
          }}
          onSelectBackdrop={(url) => {
            api.changeFolderBackdrop(activeFolderPath, activeMediaRoot, url).then(() => {
              showToast('背景图已更新')
              load()
            }).catch(() => showToast('失败'))
          }}
          onClose={() => setShowFolderCover(false)}
        />
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
