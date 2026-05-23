import { Movie } from '../api'
import { useState, useEffect, useRef } from 'react'
import { api } from '../api'

interface Props {
  movie: Movie
  sourceName?: string
  compact?: boolean
}

export default function MovieInfoPanel({ movie, compact = false }: Props) {
  const comments = movie.javdb_comments || []
  const visibleComments = compact ? comments.slice(0, 1) : comments
  const [releaseInfo, setReleaseInfo] = useState<{ countries: { country: string; date: string; cert: string }[]; cert: string } | null>(null)
  const releaseFetched = useRef(false)

  useEffect(() => {
    if (releaseFetched.current || !movie.tmdb_id || movie.tmdb_type !== 'movie') return
    releaseFetched.current = true
    api.releaseDates(movie.tmdb_id).then(data => {
      if (!data?.results?.length) return
      const countries: { country: string; date: string; cert: string }[] = []
      const priority = ['CN', 'US', 'JP', 'HK', 'TW', 'KR', 'GB', 'FR', 'DE']
      for (const r of data.results) {
        const code = r.iso_3166_1
        if (!code) continue
        const theatrical = r.release_dates?.find((d: any) => d.type === 3) || r.release_dates?.[0]
        if (theatrical?.release_date) {
          countries.push({ country: code, date: theatrical.release_date, cert: theatrical.certification || '' })
        }
      }
      countries.sort((a, b) => {
        const ai = priority.indexOf(a.country), bi = priority.indexOf(b.country)
        return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
      })
      const primaryCert = countries.find(c => c.cert)?.cert || ''
      setReleaseInfo({ countries: countries.slice(0, 8), cert: primaryCert })
    }).catch(() => {})
  }, [movie.tmdb_id, movie.tmdb_type])

  const rows = [
    movie.title ? { label: '标题', value: movie.title } : null,
    movie.actress ? { label: '演员', value: movie.actress } : null,
    movie.director ? { label: '导演', value: movie.director } : null,
    movie.series ? { label: '系列', value: movie.series } : null,
    movie.studio ? { label: '片商', value: movie.studio } : null,
    movie.genre ? { label: '类型', value: movie.genre } : null,
    movie.keywords ? { label: '关键词', value: movie.keywords } : null,
    movie.studios ? { label: '制片', value: movie.studios } : null,
    movie.tagline ? { label: '标语', value: movie.tagline } : null,
    movie.status ? { label: '状态', value: movie.status } : null,
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

      {movie.tagline && (
        <div className="mt-3 rounded-2xl border border-white/10 bg-black/15 px-4 py-2.5">
          <p className="text-xs italic text-apple-blue/80">"{movie.tagline}"</p>
        </div>
      )}

      {releaseInfo && releaseInfo.countries.length > 0 && (
        <div className="mt-3">
          <p className="mb-1.5 text-xs text-gray-500">上映信息</p>
          <div className="flex flex-wrap gap-1.5">
            {releaseInfo.countries.map(c => (
              <span key={c.country} className="glass-chip text-xs">
                <span className="text-gray-400">{c.country}</span>
                <span className="ml-1 text-gray-300">{c.date}</span>
                {c.cert && <span className="ml-1 text-apple-yellow/80">{c.cert}</span>}
              </span>
            ))}
          </div>
        </div>
      )}

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
