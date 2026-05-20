import { Movie } from '../api'

interface Props {
  movie: Movie
  sourceName: string
}

export default function MovieInfoPanel({ movie, sourceName }: Props) {
  const comments = movie.javdb_comments || []
  const cast = movie.cast || []
  const crew = movie.crew || []

  return (
    <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
      <h3 className="text-sm font-semibold mb-3 text-gray-300">影片信息</h3>

      <div className="space-y-1.5 text-sm">
        {movie.title && (
          <div className="flex justify-between">
            <span className="text-gray-500 shrink-0">标题</span>
            <span className="text-gray-200 text-right ml-4">{movie.title}</span>
          </div>
        )}
        {movie.actress && (
          <div className="flex justify-between">
            <span className="text-gray-500 shrink-0">演员</span>
            <span className="text-gray-200 text-right ml-4">{movie.actress}</span>
          </div>
        )}
        {movie.director && (
          <div className="flex justify-between">
            <span className="text-gray-500 shrink-0">导演</span>
            <span className="text-gray-200 text-right ml-4">{movie.director}</span>
          </div>
        )}
        {movie.series && (
          <div className="flex justify-between">
            <span className="text-gray-500 shrink-0">系列</span>
            <span className="text-gray-200 text-right ml-4">{movie.series}</span>
          </div>
        )}
        {movie.studio && (
          <div className="flex justify-between">
            <span className="text-gray-500 shrink-0">片商</span>
            <span className="text-gray-200 text-right ml-4">{movie.studio}</span>
          </div>
        )}
        {movie.genre && (
          <div className="flex justify-between">
            <span className="text-gray-500 shrink-0">类型</span>
            <span className="text-gray-200 text-right ml-4">{movie.genre}</span>
          </div>
        )}
        {movie.dvd_id && (
          <div className="flex justify-between">
            <span className="text-gray-500 shrink-0">番号</span>
            <span className="text-gray-200 text-right ml-4">{movie.dvd_id}</span>
          </div>
        )}
        {movie.release_date && (
          <div className="flex justify-between">
            <span className="text-gray-500 shrink-0">发行日</span>
            <span className="text-gray-200 text-right ml-4">{movie.release_date}</span>
          </div>
        )}
        {movie.duration && (
          <div className="flex justify-between">
            <span className="text-gray-500 shrink-0">时长</span>
            <span className="text-gray-200 text-right ml-4">{movie.duration} 分钟</span>
          </div>
        )}
        {movie.javdb_score != null && movie.javdb_score > 0 && (
          <div className="flex justify-between">
            <span className="text-gray-500 shrink-0">评分</span>
            <span className="text-yellow-400 text-right ml-4">{movie.javdb_score.toFixed(1)} / 5.0</span>
          </div>
        )}
        {movie.javdb_likes != null && movie.javdb_likes > 0 && (
          <div className="flex justify-between">
            <span className="text-gray-500 shrink-0">票数</span>
            <span className="text-pink-400 text-right ml-4">{movie.javdb_likes.toLocaleString()}</span>
          </div>
        )}
      </div>

      {cast.length > 0 && (
        <div className="mt-3 pt-3 border-t border-dark-700">
          <p className="text-xs text-gray-500 mb-2">演员表</p>
          <div className="space-y-1">
            {cast.slice(0, 8).map((c, i) => (
              <div key={i} className="flex justify-between text-xs">
                <span className="text-gray-300">{c.name}</span>
                <span className="text-gray-500 ml-4 truncate">{c.character}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {crew.length > 0 && (
        <div className="mt-3 pt-3 border-t border-dark-700">
          <p className="text-xs text-gray-500 mb-2">制作团队</p>
          <div className="space-y-1">
            {crew.map((c, i) => (
              <div key={i} className="flex justify-between text-xs">
                <span className="text-gray-300">{c.name}</span>
                <span className="text-gray-500 ml-4">{c.job}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {movie.javdb_url && (
        <a
          href={movie.javdb_url}
          target="_blank"
          rel="noreferrer"
          className="inline-block mt-4 text-xs text-blue-400 hover:text-blue-300 transition-colors"
        >
          查看更多信息
        </a>
      )}

      {comments.length > 0 && (
        <div className="mt-4 pt-3 border-t border-dark-700">
          <p className="text-xs text-gray-500 mb-2">简介</p>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {comments.map((comment, i) => (
              <p key={i} className="text-xs text-gray-400 leading-relaxed bg-dark-700/50 p-2 rounded">
                {comment}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
