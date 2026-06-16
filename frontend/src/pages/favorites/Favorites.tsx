import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, Movie } from '../../api'
import { saveScrollPos, restoreScrollPos } from '../../scroll'
import { WatchedBadge } from '../../components/WatchedBadge'
import SortDropdown from '../../components/SortDropdown'

import { FAVORITES_SORT_OPTIONS } from '../../constants/sortOptions'

type SortMode = 'name' | 'created_desc' | 'created_asc' | 'random'

export default function Favorites() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const sort = (searchParams.get('sort') || 'created_desc') as SortMode
  const [movies, setMovies] = useState<Movie[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.favorites(200, 0, sort).then((data) => {
      setMovies(data.movies)
      setTotal(data.total)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [sort])

  useEffect(() => { restoreScrollPos() }, [])

  const handleSort = (s: string) => {
    if (s === 'created_desc') setSearchParams({}, { replace: true })
    else setSearchParams({ sort: s }, { replace: true })
  }

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
          <p className="text-xs uppercase tracking-[0.24em] text-apple-pink/80">Library</p>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">我的收藏</h1>
          <p className="mt-1 text-sm text-gray-500">共 {total} 部</p>
        </div>
        <div className="flex items-center gap-1">
          <SortDropdown options={FAVORITES_SORT_OPTIONS} current={sort} onChange={handleSort} variant="menu" />
        </div>
      </div>

      {movies.length === 0 ? (
        <div className="glass-panel py-20 text-center text-gray-500">
          <p className="mb-2 text-3xl font-light text-white/60">--</p>
          <p>还没有收藏影片</p>
          <p className="mt-2 text-sm text-gray-600">在影片详情页点击收藏按钮即可添加</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 media-grid">
          {movies.map((movie) => (
            <div
              key={movie.id}
              onClick={() => { saveScrollPos(); navigate(`/detail/${movie.id}`) }}
              className="glass-card apple-focus media-grid-card group cursor-pointer overflow-hidden"
            >
              <div className="relative aspect-[2/3] bg-white/[0.04]">
                <img
                  src={api.coverUrl(movie.id)}
                  alt={movie.code}
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                  loading="lazy"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none'
                  }}
                />
                <WatchedBadge watched={!!(movie.tags || []).includes('watched')} />
                <div className="absolute right-2 top-2 z-10 flex flex-col items-end gap-1.5">
                  {movie.javdb_score != null && movie.javdb_score > 0 && (
                    <span className="rounded-full border border-apple-yellow/30 bg-black/45 px-2 py-0.5 text-xs font-semibold text-apple-yellow backdrop-blur-xl">
                      {movie.javdb_score.toFixed(1)}
                    </span>
                  )}
                  {movie.javdb_likes != null && movie.javdb_likes > 0 && (
                    <span className="rounded-full border border-apple-pink/30 bg-black/45 px-2 py-0.5 text-xs font-semibold text-apple-pink backdrop-blur-xl">
                      {movie.javdb_likes >= 1000 ? `${(movie.javdb_likes / 1000).toFixed(1)}k` : movie.javdb_likes}
                    </span>
                  )}
                </div>
                <div className="absolute inset-0 bg-gradient-to-t from-black via-black/35 to-transparent opacity-95" />
                <div className="absolute bottom-0 left-0 right-0 p-3">
                  <p className="truncate text-sm font-semibold text-white drop-shadow">{movie.title || movie.code}</p>
                  <p className="mt-0.5 text-xs text-gray-400">{movie.code}</p>
                </div>
                <button
                  onClick={async (e) => {
                    e.stopPropagation()
                    await api.removeTag(movie.id, 'favorite')
                    setMovies(prev => prev.filter(m => m.id !== movie.id))
                    setTotal(t => t - 1)
                  }}
                  className="absolute left-1/2 top-2 z-20 -translate-x-1/2 rounded-full border border-red-400/20 bg-red-500/15 px-2.5 py-1 text-[10px] text-red-200 opacity-0 backdrop-blur-xl transition-opacity hover:bg-red-500/25 group-hover:opacity-100"
                >
                  取消收藏
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
