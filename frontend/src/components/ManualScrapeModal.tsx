import { useState } from 'react'
import { api, type ManualScraperName, type ScrapeSearchResult } from '../api'
import { showToast } from '../toast'

export type ScrapeResult = ScrapeSearchResult

export interface BackdropResult {
  source_id: string
  source: string
  media_type?: string
  backdrop_url?: string
  poster_url?: string
}

interface ManualScrapeModalProps {
  title?: string
  initialQuery?: string
  mediaRoot?: string
  allowJavdatabase?: boolean
  /** 是否在结果卡片上显示"选背景"按钮 */
  showBackdropButton?: boolean
  /** 选择背景时的回调，接收背景图 URL */
  onSelectBackdrop?: (backdropUrl: string) => void
  /** 应用刮削回调 */
  onApply: (result: ScrapeResult) => Promise<void>
  onClose: () => void
}

const SCRAPER_OPTIONS: { value: ManualScraperName; label: string }[] = [
  { value: 'auto', label: '自动' },
  { value: 'tmdb_movie', label: 'TMDB 电影' },
  { value: 'tmdb_tv', label: 'TMDB 剧集/番剧' },
  { value: 'tmdb_collection', label: 'TMDB 合集' },
  { value: 'bangumi', label: 'Bangumi' },
  { value: 'javdatabase', label: 'Javdatabase' },
]

export default function ManualScrapeModal({
  title,
  initialQuery = '',
  mediaRoot,
  allowJavdatabase = false,
  showBackdropButton = false,
  onSelectBackdrop,
  onApply,
  onClose,
}: ManualScrapeModalProps) {
  const [query, setQuery] = useState(initialQuery)
  const [scraper, setScraper] = useState<ManualScraperName>('auto')
  const [results, setResults] = useState<ScrapeResult[]>([])
  const [backdrops, setBackdrops] = useState<BackdropResult[]>([])
  const [searching, setSearching] = useState(false)
  const [applying, setApplying] = useState(false)

  const handleSearch = async () => {
    const trimmedQuery = query.trim()
    if (!trimmedQuery) return
    setSearching(true)
    try {
      const data = await api.searchScrape(trimmedQuery, scraper, mediaRoot)
      const found = (data.results || []).map(result => ({
        ...result,
        scraper: result.scraper || scraper,
      }))
      setResults(found)
      if (found.length === 0) {
        showToast('没有找到匹配结果')
      } else {
        api.fetchSearchBackdrops(found).then(bd => {
          setBackdrops(bd.backdrops || [])
        }).catch(() => {})
      }
    } catch (err) {
      console.error('Search scrape failed', err)
      showToast(`搜索失败：${err instanceof Error ? err.message : '请查看后端日志'}`)
    } finally {
      setSearching(false)
    }
  }

  const handleApply = async (result: ScrapeResult) => {
    if (applying) return
    setApplying(true)
    try {
      await onApply(result)
      onClose()
    } catch (err) {
      showToast(`应用失败：${err instanceof Error ? err.message : '请查看后端日志'}`)
    } finally {
      setApplying(false)
    }
  }

  const backdropsBySource = new Map<string, BackdropResult>()
  backdrops.forEach(b => backdropsBySource.set(`${b.source_id}-${b.source}-${b.media_type || ''}`, b))

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4 backdrop-blur-2xl">
      <div className="glass-modal max-h-[85vh] w-full max-w-3xl overflow-y-auto p-4 sm:p-5">
        <h2 className="mb-1 text-lg font-bold text-white">
          {title || '手动刮削'}
        </h2>
        <p className="mb-4 text-xs text-gray-500">输入搜索关键词，选择结果应用到当前影片</p>
        <div className="mb-4 flex flex-col gap-2 sm:flex-row">
          <input
            type="text"
            value={query}
            onChange={e => { setQuery(e.target.value); setResults([]) }}
            onKeyDown={e => { if (e.key === 'Enter') handleSearch() }}
            placeholder="搜索关键词"
            autoFocus
            className="glass-input flex-1 px-3 py-2 text-sm"
          />
          <select
            value={scraper}
            onChange={e => setScraper(e.target.value as ManualScraperName)}
            className="glass-input px-3 py-2 text-sm text-gray-300"
          >
            {SCRAPER_OPTIONS.filter(o => allowJavdatabase || o.value !== 'javdatabase').map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <button
            onClick={handleSearch}
            disabled={searching}
            className="glass-button-primary px-4 py-2 text-sm"
          >
            {searching ? '搜索中...' : '搜索'}
          </button>
        </div>
        {results.length > 0 && (
          <>
            <p className="mb-2 text-xs text-gray-500">
              共 {results.length} 个结果，点击应用元数据
              {showBackdropButton ? '，右键或点击按钮选择背景图' : ''}
            </p>
            <div className="grid max-h-[50vh] grid-cols-2 gap-3 overflow-y-auto sm:grid-cols-3">
              {results.map((r, i) => {
                const bdKey = `${r.source_id}-${r.source}-${r.media_type || ''}`
                const bd = backdropsBySource.get(bdKey)
                return (
                  <div key={i} className="glass-card overflow-hidden transition-all hover:border-apple-blue/40 hover:shadow-glow">
                    <div
                      className="aspect-[2/3] cursor-pointer bg-white/[0.04]"
                      onClick={() => handleApply(r)}
                    >
                      {r.poster_url ? (
                        <img src={r.poster_url} alt={r.title} className="h-full w-full object-cover" />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center p-2 text-center text-xs text-gray-600">
                          {r.title}
                        </div>
                      )}
                    </div>
                    <div className="p-2">
                      <p className="truncate text-xs font-medium text-white">{r.title}</p>
                      <p className="mt-0.5 text-[10px] text-gray-500">
                        <span className={`inline-block rounded-full border px-1.5 py-0.5 text-[9px] ${
                          r.source === 'tmdb' ? 'border-apple-blue/25 bg-apple-blue/15 text-apple-blue'
                          : r.source === 'bangumi' ? 'border-apple-pink/25 bg-apple-pink/15 text-apple-pink'
                          : 'border-apple-mint/25 bg-apple-mint/15 text-apple-mint'
                        }`}>
                          {r.source}
                        </span>
                        {' '}{r.year}{r.original_title ? ` · ${r.original_title}` : ''}
                      </p>
                      <div className="mt-1.5 flex gap-1">
                        <button
                          onClick={e => { e.stopPropagation(); handleApply(r) }}
                          className="flex-1 rounded-full border border-apple-blue/20 bg-apple-blue/10 px-1 py-0.5 text-center text-[10px] text-apple-blue hover:bg-apple-blue/20"
                        >
                          应用
                        </button>
                        {showBackdropButton && onSelectBackdrop && bd?.backdrop_url && (
                          <button
                            onClick={e => { e.stopPropagation(); onSelectBackdrop(bd.backdrop_url!) }}
                            className="rounded-full border border-white/10 bg-white/[0.08] px-1.5 py-0.5 text-[10px] text-gray-400 hover:text-white"
                          >
                            选背景
                          </button>
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
          <button
            onClick={onClose}
            className="glass-button flex-1 py-2 text-sm text-gray-300"
          >
            取消
          </button>
        </div>
      </div>

      {applying && (
        <div className="fixed bottom-3 left-3 right-3 z-[60] rounded-3xl border border-white/10 bg-black/60 p-4 shadow-glass backdrop-blur-2xl sm:bottom-4 sm:left-auto sm:right-4 sm:w-72">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-white">正在应用刮削结果...</p>
              <p className="mt-1 text-xs text-gray-500">更新元数据和封面缓存</p>
            </div>
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-apple-blue border-t-transparent" />
          </div>
        </div>
      )}
    </div>
  )
}
