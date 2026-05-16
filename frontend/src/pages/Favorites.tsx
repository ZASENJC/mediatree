import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, Movie } from '../api'
import { saveScrollPos, restoreScrollPos } from '../scroll'
import { WatchedBadge } from '../components/WatchedBadge'
import SortDropdown from '../components/SortDropdown'

type SortMode = 'name' | 'created_desc' | 'created_asc' | 'random'

const sortOptions = [
  { key: 'created_desc', label: '最近添加' },
  { key: 'created_asc', label: '最早添加' },
  { key: 'name', label: '名称' },
  { key: 'random', label: '随机' },
]

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
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">我的收藏</h1>
          <p className="text-sm text-gray-500">共 {total} 部</p>
        </div>
        <div className="flex items-center gap-1">
          <SortDropdown options={sortOptions} current={sort} onChange={handleSort} />
        </div>
      </div>

      {movies.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <p className="text-2xl font-light mb-2">--</p>
          <p>还没有收藏影片</p>
          <p className="text-sm mt-2 text-gray-600">在影片详情页点击收藏按钮即可添加</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-4">
          {movies.map((movie) => (
            <div
              key={movie.id}
              onClick={() => { saveScrollPos(); navigate(`/detail/${movie.id}`) }}
              className="group cursor-pointer bg-dark-800 rounded-xl overflow-hidden border border-dark-700 hover:border-blue-500/40 transition-all hover:bg-dark-700/50"
            >
              <div className="aspect-[2/3] bg-dark-700 relative">
                <img
                  src={api.coverUrl(movie.id)}
                  alt={movie.code}
                  className="w-full h-full object-cover"
                  loading="lazy"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none'
                  }}
                />
                <WatchedBadge watched={!!(movie.tags || []).includes('watched')} />
                {movie.javdb_score != null && movie.javdb_score > 0 && (
                  <span className="absolute top-2 right-2 bg-dark-900/80 px-1.5 py-0.5 rounded text-xs text-yellow-400">
                    {movie.javdb_score.toFixed(1)}
                  </span>
                )}
                {movie.javdb_likes != null && movie.javdb_likes > 0 && (
                  <span className="absolute top-7 right-2 bg-dark-900/80 px-1.5 py-0.5 rounded text-xs text-pink-400">
                    {movie.javdb_likes >= 1000 ? `${(movie.javdb_likes / 1000).toFixed(1)}k` : movie.javdb_likes}
                  </span>
                )}
                <div className="absolute inset-0 bg-gradient-to-t from-dark-900 via-dark-900/30 to-transparent" />
                <div className="absolute bottom-0 left-0 right-0 p-3">
                  <p className="text-sm font-semibold text-white truncate">{movie.title || movie.code}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{movie.code}</p>
                </div>
                <button
                  onClick={async (e) => {
                    e.stopPropagation()
                    await api.removeTag(movie.id, 'favorite')
                    setMovies(prev => prev.filter(m => m.id !== movie.id))
                    setTotal(t => t - 1)
                  }}
                  className="absolute top-2 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity px-2 py-1 text-[10px] bg-red-500/20 text-red-400 rounded hover:bg-red-500/30"
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
