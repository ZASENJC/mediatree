import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api, Movie } from '../api'
import VideoPlayer from '../components/VideoPlayer'
import MovieInfoPanel from '../components/MovieInfoPanel'
import Lightbox from '../components/Lightbox'

type ThumbnailImage = { src: string; fallback?: string; alt: string }

export default function Detail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [movie, setMovie] = useState<Movie | null>(null)
  const [loading, setLoading] = useState(true)
  const [lightboxIdx, setLightboxIdx] = useState(-1)
  const [infoExpanded, setInfoExpanded] = useState(false)
  const thumbnailImages: ThumbnailImage[] = movie ? [
    ...(movie.episode_still ? [{ src: api.cachedCoverUrl(`ep_${movie.id}`), fallback: movie.episode_still, alt: '单集封面' }] : []),
    ...((movie.javdb_thumbnails || []).map((_, i) => ({ src: api.thumbnailUrl(movie.id, i), alt: `缩略图 ${i + 1}` }))),
  ] : []

  useEffect(() => {
    if (!id) return
    api.detail(Number(id)).then((data) => {
      setMovie(data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="animate-pulse text-lg text-gray-400">加载中...</div>
      </div>
    )
  }

  if (!movie) {
    return (
      <div className="glass-panel py-20 text-center text-gray-500">
        <p className="mb-2 text-3xl font-light text-white/60">?</p>
        <p>影片未找到</p>
        <button onClick={() => navigate(-1)} className="glass-button mt-4 px-4 py-2 text-sm">
          返回
        </button>
      </div>
    )
  }

  const isFavorited = movie.tags?.includes('favorite')
  const goStaff = (name: string) => {
    const p = new URLSearchParams()
    p.set('staff', name)
    if (movie.media_root) p.set('media_root', movie.media_root)
    navigate(`/browse?${p.toString()}`)
  }
  const cast = (movie.cast || []).filter(p => p.name)
  const crew = (movie.crew || []).filter(p => p.name)
  const isJavdatabase = movie.scraper_source === 'javdatabase' || Boolean(movie.javdb_id || movie.javdb_url)
  const castNames = cast.map(p => p.name).filter(Boolean)
  const performerText = movie.actress || castNames.join(', ')
  const overview = movie.overview || movie.episode_overview || ''
  const crewByJob = (jobs: string[]) => crew.filter(p => jobs.some(j => (p.job || '').toLowerCase().includes(j.toLowerCase())))
  const directors = crewByJob(['director', '导演'])
  const supervisors = crewByJob(['supervisor', 'animation director', 'series director', '监督'])
  const writers = crewByJob(['writer', '脚本', '编剧'])
  const studios = crewByJob(['studio', '制作'])

  const toggleTag = async (tag: string) => {
    if (movie.tags?.includes(tag)) {
      await api.removeTag(movie.id, tag)
      setMovie(prev => prev ? { ...prev, tags: prev.tags?.filter(t => t !== tag) } : null)
    } else {
      await api.addTag(movie.id, tag)
      setMovie(prev => prev ? { ...prev, tags: [...(prev.tags || []), tag] } : null)
    }
  }

  const coreMeta = [
    movie.release_date ? { label: '发行日', value: movie.release_date } : null,
    movie.duration ? { label: '时长', value: `${movie.duration} 分钟` } : null,
    movie.javdb_score != null && movie.javdb_score > 0 ? { label: '评分', value: movie.javdb_score.toFixed(1), tone: 'text-apple-yellow' } : null,
    movie.javdb_likes != null && movie.javdb_likes > 0 ? { label: '喜欢', value: movie.javdb_likes.toLocaleString(), tone: 'text-apple-pink' } : null,
    movie.tmdb_type === 'tv' && movie.tmdb_season != null
      ? { label: '季/集', value: `Season ${movie.tmdb_season}${movie.tmdb_episode != null ? ` · Episode ${movie.tmdb_episode}` : ''}` }
      : null,
  ].filter(Boolean) as { label: string; value: string; tone?: string }[]

  return (
    <div className="space-y-5">
      <button
        onClick={() => navigate(-1)}
        className="glass-button px-4 py-2 text-sm"
      >
        返回
      </button>

      <div className="glass-panel overflow-hidden p-2">
        <VideoPlayer src={api.streamUrl(movie.id)} poster={api.coverUrl(movie.id)} movieId={movie.id}
          onWatched={() => { if (!movie.tags?.includes('watched')) toggleTag('watched') }} />
      </div>

      <section className="glass-panel p-4 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0 flex-1">
            <p className="text-xs uppercase tracking-[0.24em] text-apple-blue/80">Now Playing</p>
            <h1 className="mt-1 break-words text-2xl font-bold tracking-tight text-white sm:text-4xl">
              {movie.title || movie.code}
            </h1>
            {movie.original_title && movie.original_title !== movie.title && (
              <p className="mt-2 break-words text-sm text-gray-400">{movie.original_title}</p>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-gray-400">
              <span className="glass-chip font-mono text-gray-200">{movie.code}</span>
              {coreMeta.map(item => (
                <span key={item.label} className="glass-chip">
                  <span className="mr-1 text-gray-500">{item.label}</span>
                  <span className={item.tone || 'text-gray-200'}>{item.value}</span>
                </span>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => toggleTag('favorite')}
              className={`rounded-full border px-4 py-2 text-sm font-medium transition-all ${
                isFavorited
                  ? 'border-apple-yellow/40 bg-apple-yellow/20 text-apple-yellow shadow-glow'
                  : 'border-white/10 bg-white/[0.08] text-gray-300 hover:bg-white/[0.14] hover:text-apple-yellow'
              }`}
            >
              {isFavorited ? '已收藏' : '收藏'}
            </button>
            <button
              onClick={() => toggleTag('want_to_watch')}
              className={`rounded-full border px-4 py-2 text-sm transition-all ${
                movie.tags?.includes('want_to_watch')
                  ? 'border-apple-blue/40 bg-apple-blue/20 text-apple-blue shadow-glow'
                  : 'border-white/10 bg-white/[0.08] text-gray-300 hover:bg-white/[0.14] hover:text-white'
              }`}
            >
              {movie.tags?.includes('want_to_watch') ? '想看中' : '想看'}
            </button>
            <button
              onClick={() => toggleTag('watched')}
              className={`rounded-full border px-4 py-2 text-sm transition-all ${
                movie.tags?.includes('watched')
                  ? 'border-apple-mint/40 bg-apple-mint/20 text-apple-mint shadow-glow'
                  : 'border-white/10 bg-white/[0.08] text-gray-300 hover:bg-white/[0.14] hover:text-white'
              }`}
            >
              {movie.tags?.includes('watched') ? '已看' : '标为已看'}
            </button>
          </div>
        </div>

        {performerText && (
          <div className="mt-5 flex flex-wrap items-start gap-2 text-sm">
            <span className="shrink-0 text-gray-500">{isJavdatabase ? '女优' : '演员'}</span>
            <div className="flex min-w-0 flex-wrap gap-1.5">
              {performerText.split(/[,，、]/).map((name: string, i: number) => {
                const trimmed = name.trim()
                if (!trimmed) return null
                return (
                  <button
                    key={`${trimmed}-${i}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      goStaff(trimmed)
                    }}
                    className="rounded-full border border-white/10 bg-white/[0.08] px-2.5 py-1 text-xs text-gray-200 transition-all hover:border-apple-blue/40 hover:text-apple-blue"
                  >
                    {trimmed}
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </section>

      <section className="rounded-3xl border border-white/10 bg-white/[0.04] p-3 shadow-glass backdrop-blur-2xl sm:p-4">
        <button
          onClick={() => setInfoExpanded(v => !v)}
          className="flex w-full items-center justify-between gap-4 text-left"
        >
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.24em] text-apple-blue/70">Details</p>
            <h2 className="mt-0.5 truncate text-base font-semibold text-white sm:text-lg">影片信息</h2>
          </div>
          <span className="shrink-0 rounded-full border border-white/10 bg-white/[0.08] px-3 py-1 text-xs text-gray-300">
            {infoExpanded ? '收起' : '展开'}
          </span>
        </button>

        {infoExpanded && (
          <div className="mt-4 space-y-4 border-t border-white/10 pt-4">
            {(overview || movie.episode_title || movie.episode_overview || movie.folder_levels) && (
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <div className="grid gap-4 lg:grid-cols-3">
                  {overview && (
                    <div className="lg:col-span-2">
                      <p className="mb-1.5 text-xs text-gray-500">简介</p>
                      <p className="whitespace-pre-line text-sm leading-relaxed text-gray-300">{overview}</p>
                    </div>
                  )}
                  <div className="space-y-3 text-sm">
                    {movie.folder_levels && (
                      <InfoLine label="目录" value={movie.folder_levels} />
                    )}
                    {movie.episode_title && (
                      <InfoLine label="集标题" value={movie.episode_title} />
                    )}
                    {movie.episode_overview && movie.episode_overview !== overview && (
                      <InfoLine label="集概述" value={movie.episode_overview} />
                    )}
                  </div>
                </div>
              </div>
            )}

            <MovieInfoPanel movie={movie} compact={false} />

            {(cast.length > 0 || crew.length > 0) && (
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <h3 className="mb-3 text-sm font-semibold text-gray-200">Staff</h3>
                <div className="space-y-4">
                  {cast.length > 0 && (
                    <StaffGroup label="演员" items={cast.map(p => ({ name: p.name, sub: p.role || p.character }))} onClick={goStaff} />
                  )}
                  {directors.length > 0 && (
                    <StaffGroup label="导演" items={directors.map(p => ({ name: p.name, sub: p.job }))} onClick={goStaff} />
                  )}
                  {supervisors.length > 0 && (
                    <StaffGroup label="监督" items={supervisors.map(p => ({ name: p.name, sub: p.job }))} onClick={goStaff} />
                  )}
                  {writers.length > 0 && (
                    <StaffGroup label="编剧" items={writers.map(p => ({ name: p.name, sub: p.job }))} onClick={goStaff} />
                  )}
                  {studios.length > 0 && (
                    <StaffGroup label="制作" items={studios.map(p => ({ name: p.name, sub: p.job }))} onClick={goStaff} />
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      {thumbnailImages.length > 0 && (
        <section className="glass-panel p-4 sm:p-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-gray-300">缩略图</h3>
            <span className="glass-chip text-xs text-gray-400">{thumbnailImages.length}</span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8">
            {thumbnailImages.map((image, i) => (
              <div
                key={`${image.src}-${i}`}
                onClick={() => setLightboxIdx(i)}
                className="apple-focus block aspect-video cursor-pointer overflow-hidden rounded-2xl border border-white/10 bg-white/[0.06] transition-all hover:border-apple-blue/40"
              >
                <img
                  src={image.src}
                  alt={image.alt}
                  className="h-full w-full object-cover"
                  loading="lazy"
                  onError={(e) => {
                    if (image.fallback) (e.target as HTMLImageElement).src = image.fallback
                  }}
                />
              </div>
            ))}
          </div>
        </section>
      )}

      {lightboxIdx >= 0 && thumbnailImages.length > 0 && (
        <Lightbox
          images={thumbnailImages}
          index={lightboxIdx}
          onClose={() => setLightboxIdx(-1)}
          onPrev={() => setLightboxIdx(i => Math.max(0, i - 1))}
          onNext={() => setLightboxIdx(i => Math.min(thumbnailImages.length - 1, i + 1))}
        />
      )}
    </div>
  )
}

function InfoLine({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="mb-1 text-xs text-gray-500">{label}</p>
      <p className="break-words text-gray-300">{value}</p>
    </div>
  )
}

function StaffGroup({ label, items, onClick }: { label: string; items: { name: string; sub?: string }[]; onClick: (name: string) => void }) {
  return (
    <div>
      <div className="mb-2 text-xs text-gray-500">{label}</div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item, idx) => (
          <button
            key={`${item.name}-${idx}`}
            onClick={() => onClick(item.name)}
            className="rounded-full border border-white/10 bg-white/[0.08] px-2.5 py-1 text-left text-xs text-gray-200 transition-all hover:border-apple-blue/40 hover:bg-apple-blue/10 hover:text-apple-blue"
            title={item.sub || item.name}
          >
            {item.name}
          </button>
        ))}
      </div>
    </div>
  )
}
