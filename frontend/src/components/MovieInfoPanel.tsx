import { Movie } from '../api'

interface Props {
  movie: Movie
  sourceName?: string
  compact?: boolean
}

export default function MovieInfoPanel({ movie, compact = false }: Props) {
  const comments = movie.javdb_comments || []
  const visibleComments = compact ? comments.slice(0, 1) : comments

  const rows = [
    movie.title ? { label: '标题', value: movie.title } : null,
    movie.actress ? { label: '演员', value: movie.actress } : null,
    movie.director ? { label: '导演', value: movie.director } : null,
    movie.series ? { label: '系列', value: movie.series } : null,
    movie.studio ? { label: '片商', value: movie.studio } : null,
    movie.genre ? { label: '类型', value: movie.genre } : null,
    movie.dvd_id ? { label: '番号', value: movie.dvd_id } : null,
    movie.release_date ? { label: '发行日', value: movie.release_date } : null,
    movie.duration ? { label: '时长', value: `${movie.duration} 分钟` } : null,
    movie.javdb_score != null && movie.javdb_score > 0 ? { label: '评分', value: `${movie.javdb_score.toFixed(1)} / 5.0`, tone: 'text-apple-yellow' } : null,
    movie.javdb_likes != null && movie.javdb_likes > 0 ? { label: '票数', value: movie.javdb_likes.toLocaleString(), tone: 'text-apple-pink' } : null,
  ].filter(Boolean) as { label: string; value: string; tone?: string }[]

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
      <h3 className="mb-3 text-sm font-semibold text-gray-200">影片信息</h3>

      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {rows.map(row => (
          <div key={row.label} className="rounded-2xl border border-white/10 bg-black/15 px-3 py-2">
            <p className="mb-1 text-xs text-gray-500">{row.label}</p>
            <p className={`break-words text-sm ${row.tone || 'text-gray-200'}`}>{row.value}</p>
          </div>
        ))}
      </div>

      {movie.javdb_url && (
        <a
          href={movie.javdb_url}
          target="_blank"
          rel="noreferrer"
          className="mt-4 inline-flex rounded-full border border-apple-blue/25 bg-apple-blue/10 px-3 py-1.5 text-xs text-apple-blue transition-all hover:bg-apple-blue/20"
        >
          查看更多信息
        </a>
      )}

      {visibleComments.length > 0 && (
        <div className="mt-4 border-t border-white/10 pt-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <p className="text-xs text-gray-500">简介</p>
            {compact && comments.length > visibleComments.length && (
              <span className="text-xs text-gray-600">+{comments.length - visibleComments.length}</span>
            )}
          </div>
          <div className={`space-y-2 ${compact ? 'max-h-48 overflow-hidden' : ''}`}>
            {visibleComments.map((comment, i) => (
              <p key={i} className="rounded-2xl border border-white/10 bg-black/15 p-3 text-xs leading-relaxed text-gray-400">
                {comment}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
