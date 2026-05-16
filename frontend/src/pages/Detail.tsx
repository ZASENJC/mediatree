import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api, Movie, Config } from '../api'
import VideoPlayer from '../components/VideoPlayer'
import MovieInfoPanel from '../components/MovieInfoPanel'
import Lightbox from '../components/Lightbox'

export default function Detail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [movie, setMovie] = useState<Movie | null>(null)
  const [loading, setLoading] = useState(true)
  const [sourceName, setSourceName] = useState('Javdatabase')
  const [lightboxIdx, setLightboxIdx] = useState(-1)

  useEffect(() => {
    if (!id) return
    api.detail(Number(id)).then((data) => {
      setMovie(data)
      setLoading(false)
    }).catch(() => setLoading(false))
    api.getConfig().then(c => setSourceName(c.javdb_enabled ? 'Javdatabase' : 'Online')).catch(() => {})
  }, [id])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-pulse text-gray-400 text-lg">加载中...</div>
      </div>
    )
  }

  if (!movie) {
    return (
      <div className="text-center py-20 text-gray-500">
        <p className="text-6xl mb-4 text-dark-600">?</p>
        <p>影片未找到</p>
        <button onClick={() => navigate(-1)} className="mt-4 px-4 py-2 bg-dark-700 rounded-lg text-sm">
          返回
        </button>
      </div>
    )
  }

  const isFavorited = movie.tags?.includes('favorite')

  const toggleTag = async (tag: string) => {
    if (movie.tags?.includes(tag)) {
      await api.removeTag(movie.id, tag)
      setMovie(prev => prev ? { ...prev, tags: prev.tags?.filter(t => t !== tag) } : null)
    } else {
      await api.addTag(movie.id, tag)
      setMovie(prev => prev ? { ...prev, tags: [...(prev.tags || []), tag] } : null)
    }
  }

  return (
    <div>
      <button
        onClick={() => navigate(-1)}
        className="mb-4 px-4 py-2 bg-dark-700 hover:bg-dark-600 rounded-lg text-sm transition-colors"
      >
        ← 返回
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <VideoPlayer src={api.streamUrl(movie.id)} poster={api.coverUrl(movie.id)} movieId={movie.id}
            onWatched={() => { if (!movie.tags?.includes('watched')) toggleTag('watched') }} />

          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={() => toggleTag('favorite')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                isFavorited
                  ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                  : 'bg-dark-700 text-gray-400 hover:text-yellow-400 hover:bg-dark-600'
              }`}
            >
              {isFavorited ? '[已收藏]' : '收藏'}
            </button>
            <button
              onClick={() => toggleTag('want_to_watch')}
              className={`px-3 py-2 rounded-lg text-sm transition-colors ${
                movie.tags?.includes('want_to_watch')
                  ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                  : 'bg-dark-700 text-gray-400 hover:text-white'
              }`}
            >
              {movie.tags?.includes('want_to_watch') ? '[想看]' : '想看'}
            </button>
            <button
              onClick={() => toggleTag('watched')}
              className={`px-3 py-2 rounded-lg text-sm transition-colors ${
                movie.tags?.includes('watched')
                  ? 'bg-green-600/20 text-green-400 border border-green-500/30'
                  : 'bg-dark-700 text-gray-400 hover:text-white'
              }`}
            >
              {movie.tags?.includes('watched') ? '[已看]' : '已看'}
            </button>
          </div>

          {movie.javdb_thumbnails && (movie.javdb_thumbnails || []).length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold text-gray-400 mb-3">缩略图 ({(movie.javdb_thumbnails || []).length})</h3>
              <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 gap-2">
                {(movie.javdb_thumbnails || []).map((_, i) => (
                  <div
                    key={i}
                    onClick={() => setLightboxIdx(i)}
                    className="block aspect-video bg-dark-800 rounded overflow-hidden hover:ring-2 ring-blue-500 cursor-pointer transition-all"
                  >
                    <img
                      src={api.thumbnailUrl(movie.id, i)}
                      alt={`缩略图 ${i + 1}`}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div>
            <h2 className="text-xl font-bold">{movie.title || movie.code}</h2>
            <p className="text-sm text-gray-400 mt-1">{movie.code}</p>
          </div>

          <div className="space-y-2 text-sm">
            {movie.actress && (
              <div className="flex gap-2">
                <span className="text-gray-500 shrink-0">演员:</span>
                <span>
                  {movie.actress.split(/[,，、]/).map((name: string, i: number, arr: string[]) => (
                    <span key={i}>
                      <span
                        onClick={(e) => {
                          e.stopPropagation()
                          navigate(`/browse?actress=${encodeURIComponent(name.trim())}`)
                        }}
                        className="text-blue-400 hover:text-blue-300 cursor-pointer hover:underline"
                      >
                        {name.trim()}
                      </span>
                      {i < arr.length - 1 && <span className="text-gray-600">, </span>}
                    </span>
                  ))}
                </span>
              </div>
            )}
            {movie.release_date && (
              <div className="flex gap-2">
                <span className="text-gray-500 shrink-0">发行日:</span>
                <span>{movie.release_date}</span>
              </div>
            )}
            {movie.duration && (
              <div className="flex gap-2">
                <span className="text-gray-500 shrink-0">时长:</span>
                <span>{movie.duration} 分钟</span>
              </div>
            )}
            {movie.javdb_score != null && movie.javdb_score > 0 && (
              <div className="flex gap-2">
                <span className="text-gray-500 shrink-0">评分:</span>
                <span className="text-yellow-400 font-semibold">{movie.javdb_score.toFixed(1)}</span>
              </div>
            )}
            {movie.javdb_likes != null && movie.javdb_likes > 0 && (
              <div className="flex gap-2">
                <span className="text-gray-500 shrink-0">喜欢:</span>
                <span className="text-pink-400">like {movie.javdb_likes.toLocaleString()}</span>
              </div>
            )}
            {movie.folder_levels && (
              <div className="flex gap-2">
                <span className="text-gray-500 shrink-0">目录:</span>
                <span className="text-gray-400 text-xs">{movie.folder_levels}</span>
              </div>
            )}
            {movie.tmdb_type === 'tv' && movie.tmdb_season != null && (
              <div className="flex gap-2">
                <span className="text-gray-500 shrink-0">季/集:</span>
                <span>Season {movie.tmdb_season}{movie.tmdb_episode != null ? ` · Episode ${movie.tmdb_episode}` : ''}</span>
              </div>
            )}
            {movie.episode_title && (
              <div className="flex gap-2">
                <span className="text-gray-500 shrink-0">集标题:</span>
                <span className="font-medium">{movie.episode_title}</span>
              </div>
            )}
            {movie.episode_overview && (
              <div className="flex gap-2">
                <span className="text-gray-500 shrink-0">集概述:</span>
                <span className="text-gray-300 text-xs leading-relaxed">{movie.episode_overview}</span>
              </div>
            )}
            {movie.episode_still && (
              <div className="mt-2">
                <img src={api.cachedCoverUrl(`ep_${movie.id}`)} alt="Episode still"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = movie.episode_still!
                  }}
                  className="w-full rounded-lg" />
              </div>
            )}
          </div>

          <MovieInfoPanel movie={movie} sourceName={sourceName} />
        </div>
      </div>

      {lightboxIdx >= 0 && movie?.javdb_thumbnails && (
        <Lightbox
          images={(movie.javdb_thumbnails || []).map((_, i) => api.thumbnailUrl(movie.id, i))}
          index={lightboxIdx}
          onClose={() => setLightboxIdx(-1)}
          onPrev={() => setLightboxIdx(i => Math.max(0, i - 1))}
          onNext={() => setLightboxIdx(i => Math.min((movie.javdb_thumbnails || []).length - 1, i + 1))}
        />
      )}
    </div>
  )
}
