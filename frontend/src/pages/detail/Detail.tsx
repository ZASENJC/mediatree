import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api, Movie } from '../../api'
import VideoPlayer from '../../components/VideoPlayer'
import Lightbox from '../../components/Lightbox'
import { useTheater } from '../../theater'
import { specialMovieTitle } from '../../movieTitle'

type ThumbnailImage = { src: string; fallback?: string; alt: string }

function parentFolder(path?: string) {
  if (!path || !path.includes('/')) return ''
  return path.split('/').slice(0, -1).join('/')
}

function inferEpisodeNumber(movie: Movie) {
  if (movie.tmdb_episode != null) return movie.tmdb_episode
  if (movie.episode_number != null) return movie.episode_number
  const text = [
    movie.display_title,
    movie.episode_title,
    movie.code,
    movie.path.split('/').pop(),
  ].filter(Boolean).join(' ')
  const match = text.match(/[Ss]\d{1,2}\s*[Ee](\d{1,4})|(?:EP?|第)\s*0*(\d{1,4})\s*(?:集|話|话)?/i)
  const value = Number(match?.[1] || match?.[2] || 0)
  return value > 0 ? value : Number.MAX_SAFE_INTEGER
}

function sortEpisodes(items: Movie[]) {
  return [...items].sort((a, b) => {
    const seasonA = a.tmdb_season ?? 0
    const seasonB = b.tmdb_season ?? 0
    if (seasonA !== seasonB) return seasonA - seasonB
    const episodeA = inferEpisodeNumber(a)
    const episodeB = inferEpisodeNumber(b)
    if (episodeA !== episodeB) return episodeA - episodeB
    return (a.path || a.code).localeCompare(b.path || b.code, 'zh-CN')
  })
}

export default function Detail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { theaterMode } = useTheater()
  const [movie, setMovie] = useState<Movie | null>(null)
  const [loading, setLoading] = useState(true)
  const [episodes, setEpisodes] = useState<Movie[]>([])
  const [specialMovies, setSpecialMovies] = useState<Movie[]>([])
  const [specialCount, setSpecialCount] = useState(0)
  const [specialsExpanded, setSpecialsExpanded] = useState(false)
  const [lightboxIdx, setLightboxIdx] = useState(-1)
  const [infoExpanded, setInfoExpanded] = useState(false)

  // TMDB extended data
  const [posters, setPosters] = useState<any[]>([])
  const [videos, setVideos] = useState<any[]>([])
  const [reviews, setReviews] = useState<any[]>([])
  const [showAllReviews, setShowAllReviews] = useState(false)
  const [trailerKey, setTrailerKey] = useState<string | null>(null)
  const [tmdbDataLoaded, setTmdbDataLoaded] = useState(false)
  const thumbnailImages: ThumbnailImage[] = movie ? [
    ...(movie.episode_still ? [{ src: api.cachedCoverUrl(`ep_${movie.id}`), fallback: movie.episode_still, alt: '单集封面' }] : []),
    ...((movie.javdb_thumbnails || []).map((_, i) => ({ src: api.thumbnailUrl(movie.id, i), alt: `缩略图 ${i + 1}` }))),
  ] : []

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setEpisodes([])
    setSpecialMovies([])
    setSpecialCount(0)
    setSpecialsExpanded(false)
    setPosters([])
    setVideos([])
    setReviews([])
    setShowAllReviews(false)
    setTrailerKey(null)
    setTmdbDataLoaded(false)
    api.detail(Number(id)).then((data) => {
      setMovie(data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (!movie?.folder_levels) {
      setEpisodes([])
      return
    }
    let cancelled = false
    const loadEpisodes = async () => {
      const mediaRoot = movie.media_root || undefined
      const primary = await api.movies({ folder: movie.folder_levels, sort: 'name', limit: 2000, media_root: mediaRoot })
      let items = primary.movies || []
      const parent = parentFolder(movie.folder_levels)
      if (items.length <= 1 && parent) {
        const fallback = await api.movies({ folder: parent, sort: 'name', limit: 2000, media_root: mediaRoot })
        if ((fallback.movies || []).some(item => item.id === movie.id)) {
          items = fallback.movies || items
        }
      }
      if (!cancelled) setEpisodes(sortEpisodes(items))
    }
    loadEpisodes().catch(() => {
      if (!cancelled) setEpisodes([])
    })
    return () => { cancelled = true }
  }, [movie?.id, movie?.folder_levels, movie?.media_root])

  useEffect(() => {
    const specialFolder = movie?.content_role === 'special'
      ? (movie.special_parent_levels || parentFolder(movie.folder_levels))
      : movie?.folder_levels
    if (!specialFolder) {
      setSpecialMovies([])
      setSpecialCount(0)
      setSpecialsExpanded(false)
      return
    }
    let cancelled = false
    api.folderSpecials(specialFolder, movie?.media_root || undefined, true)
      .then((data) => {
        if (cancelled) return
        setSpecialCount(data.special_count || 0)
        setSpecialMovies(data.movies || [])
      })
      .catch(() => {
        if (cancelled) return
        setSpecialMovies([])
        setSpecialCount(0)
        setSpecialsExpanded(false)
      })
    return () => { cancelled = true }
  }, [movie?.id, movie?.folder_levels, movie?.media_root, movie?.content_role, movie?.special_parent_levels])

  // Load TMDB extended data when movie has tmdb_id
  useEffect(() => {
    if (movie?.content_role === 'special' || !movie?.tmdb_id || !movie?.tmdb_type || tmdbDataLoaded) return
    setTmdbDataLoaded(true)
    const mt = movie.tmdb_type
    const mid = movie.tmdb_id
    Promise.allSettled([
      api.tmdbImages(mid, mt),
      api.tmdbVideos(mid, mt),
      api.tmdbReviews(mid, mt),
    ]).then(([imgRes, vidRes, revRes]) => {
      if (imgRes.status === 'fulfilled' && imgRes.value) {
        setPosters(imgRes.value.posters?.slice(0, 20) || [])
      }
      if (vidRes.status === 'fulfilled' && vidRes.value) {
        setVideos(vidRes.value.results || [])
      }
      if (revRes.status === 'fulfilled' && revRes.value) {
        setReviews(revRes.value.results || [])
      }
    }).catch(() => {})
  }, [movie?.content_role, movie?.tmdb_id, movie?.tmdb_type, tmdbDataLoaded])

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
  const goStaff = (name: string, personId?: string) => {
    if (personId) {
      window.open(`https://www.themoviedb.org/person/${personId}`, '_blank')
      return
    }
    const p = new URLSearchParams()
    p.set('staff', name)
    if (movie.media_root) p.set('media_root', movie.media_root)
    navigate(`/browse?${p.toString()}`)
  }
  const cast = (movie.cast || []).filter(p => p.name)
  const crew = (movie.crew || []).filter(p => p.name)
  const isSpecial = movie.content_role === 'special'
  const captureContinueSnapshot = !isSpecial && !(movie.tmdb_type === 'tv' || movie.tmdb_episode != null || movie.episode_number != null)
  const displayTitle = isSpecial ? specialMovieTitle(movie) : (movie.title || movie.code)
  const isJavdatabase = !isSpecial && (movie.scraper_source === 'javdatabase' || Boolean(movie.javdb_id || movie.javdb_url))
  const castNames = cast.map(p => p.name).filter(Boolean)
  const performerText = isSpecial ? '' : (movie.actress || castNames.slice(0, 5).join(', '))
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

  const toggleSpecials = () => {
    setSpecialsExpanded(v => !v)
  }

  const coreMeta = [
    !isSpecial && movie.release_date ? { label: '发行日', value: movie.release_date } : null,
    movie.duration ? { label: '时长', value: `${movie.duration} 分钟` } : null,
    !isSpecial && movie.javdb_score != null && movie.javdb_score > 0 ? { label: '评分', value: movie.javdb_score.toFixed(1), tone: 'text-apple-yellow' } : null,
    !isSpecial && movie.javdb_likes != null && movie.javdb_likes > 0 ? { label: '喜欢', value: movie.javdb_likes.toLocaleString(), tone: 'text-apple-pink' } : null,
    !isSpecial && movie.tmdb_type === 'tv' && movie.tmdb_season != null
      ? { label: '季/集', value: `Season ${movie.tmdb_season}${movie.tmdb_episode != null ? ` · Episode ${movie.tmdb_episode}` : ''}` }
      : null,
  ].filter(Boolean) as { label: string; value: string; tone?: string }[]

  return (
    <div className={theaterMode ? 'flex-1 flex flex-col min-h-0' : 'space-y-5'}>
      {!theaterMode && (
        <button
          onClick={() => navigate(-1)}
          className="glass-button px-4 py-2 text-sm"
        >
          返回
        </button>
      )}

      <VideoPlayer src={api.streamUrl(movie.id)} poster={api.coverUrl(movie.id)} movieId={movie.id}
        title={displayTitle}
        episodes={episodes}
        captureContinueSnapshot={captureContinueSnapshot}
        onEpisodeSelect={(episode) => {
          if (episode.id !== movie.id) navigate(`/detail/${episode.id}`)
        }}
        onWatched={() => { if (!movie.tags?.includes('watched')) toggleTag('watched') }} />

      {!theaterMode && (<>
      <section className="glass-panel p-4 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0 flex-1">
            <p className="text-xs uppercase tracking-[0.24em] text-apple-blue/80">Now Playing</p>
            <h1 className="mt-1 break-words text-2xl font-bold tracking-tight text-white sm:text-4xl">
              {displayTitle}
            </h1>
            {!isSpecial && movie.original_title && movie.original_title !== movie.title && (
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

      {specialCount > 0 && (
        <section className="rounded-3xl bg-white/[0.04] px-4 py-3 shadow-glass backdrop-blur-2xl sm:px-6 sm:py-4">
          <button
            onClick={toggleSpecials}
            className={`${specialsExpanded ? 'mb-3' : ''} flex w-full items-center justify-between gap-4 text-left`}
          >
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-[0.24em] text-apple-pink/70">Specials</p>
              <h2 className="mt-0.5 truncate text-base font-semibold text-white sm:text-lg">花絮</h2>
            </div>
            <span className="shrink-0 rounded-full border border-white/10 bg-white/[0.08] px-3 py-1 text-xs text-gray-300 transition-all hover:border-apple-pink/40 hover:text-apple-pink">
              {specialsExpanded ? '收起' : '展开'}
            </span>
          </button>
          {specialsExpanded && specialMovies.length > 0 && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 media-grid">
              {specialMovies.map((item) => (
                <button
                  key={item.id}
                  onClick={() => { if (item.id !== movie.id) navigate(`/detail/${item.id}`) }}
                  className="apple-focus group overflow-hidden rounded-2xl border border-white/10 bg-white/[0.06] text-left transition-all hover:border-apple-pink/40 hover:bg-white/[0.09]"
                >
                  <div className="relative aspect-video bg-black/20">
                    <img
                      src={api.coverUrl(item.id)}
                      alt={item.title || item.code}
                      className="h-full w-full object-cover opacity-85 transition-transform duration-500 group-hover:scale-105"
                      loading="lazy"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                    />
                    <span className="absolute left-2 top-2 rounded-full border border-apple-pink/30 bg-black/45 px-2 py-0.5 text-[10px] font-semibold text-apple-pink backdrop-blur-xl">
                      花絮
                    </span>
                  </div>
                  <div className="p-3">
                    <p className="line-clamp-2 text-sm font-semibold text-white">{specialMovieTitle(item)}</p>
                    <p className="mt-1 truncate text-xs text-gray-500">{item.folder_levels}</p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>
      )}

      <section className="rounded-3xl bg-white/[0.04] px-4 py-3 shadow-glass backdrop-blur-2xl sm:px-6 sm:py-4">
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
            {(movie.episode_overview || movie.folder_levels) && (
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                {movie.episode_overview ? (
                  <div className="grid gap-4 lg:grid-cols-2">
                    <div>
                      <p className="mb-1.5 text-xs text-gray-500">集概述</p>
                      <p className="whitespace-pre-line text-sm leading-relaxed text-gray-300">{movie.episode_overview}</p>
                    </div>
                    <div className="space-y-3 text-sm lg:text-right">
                      {movie.folder_levels && (
                        <InfoLine label="目录" value={movie.folder_levels} />
                      )}
                    </div>
                  </div>
                ) : (
                  movie.folder_levels && (
                    <InfoLine label="目录" value={movie.folder_levels} />
                  )
                )}
              </div>
            )}

            {/* Poster Gallery */}
            {posters.length > 0 && (
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <h3 className="mb-3 text-sm font-semibold text-gray-200">海报画廊 <span className="ml-1 text-xs font-normal text-gray-500">{posters.length}</span></h3>
                <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin">
                  {posters.map((p, i) => (
                    <div key={i} className="apple-focus group shrink-0 cursor-pointer" onClick={async () => {
                      try { await api.changeCover(movie.id, p.url); setMovie(prev => prev ? { ...prev, cover_remote: p.url, cover_local: undefined } : null) } catch {}
                    }}>
                      <img
                        src={p.url}
                        alt={`poster-${i}`}
                        className="h-56 w-auto rounded-xl border border-white/10 object-cover transition-all group-hover:border-apple-blue/40"
                        loading="lazy"
                      />
                      {p.language && p.language !== 'null' && (
                        <p className="mt-1 text-center text-[10px] text-gray-500">{p.language.toUpperCase()}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Trailers */}
            {videos.filter((v: any) => v.type === 'Trailer').length > 0 && (
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <h3 className="mb-3 text-sm font-semibold text-gray-200">预告片</h3>
                <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin">
                  {videos.filter((v: any) => v.type === 'Trailer' || v.type === 'Teaser').map((v: any, i: number) => (
                    <div
                      key={i}
                      className="apple-focus shrink-0 cursor-pointer overflow-hidden rounded-xl border border-white/10 bg-black/15"
                      onClick={() => setTrailerKey(v.key)}
                    >
                      <div className="relative">
                        <img
                          src={`https://img.youtube.com/vi/${v.key}/mqdefault.jpg`}
                          alt={v.name}
                          className="h-28 w-48 object-cover"
                          loading="lazy"
                        />
                        <div className="absolute inset-0 flex items-center justify-center">
                          <div className="rounded-full bg-black/60 p-2 backdrop-blur-sm">
                            <svg className="h-6 w-6 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                          </div>
                        </div>
                      </div>
                      <div className="p-2">
                        <p className="text-xs text-gray-300 line-clamp-2">{v.name}</p>
                        <p className="mt-0.5 text-[10px] text-gray-500">{v.type}{v.official ? ' · 官方' : ''}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Trailer Modal */}
            {trailerKey && (
              <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 backdrop-blur-md" onClick={() => setTrailerKey(null)}>
                <div className="w-full max-w-4xl p-4" onClick={(e) => e.stopPropagation()}>
                  <div className="relative overflow-hidden rounded-2xl bg-black" style={{ paddingBottom: '56.25%' }}>
                    <iframe
                      src={`https://www.youtube.com/embed/${trailerKey}?autoplay=1`}
                      className="absolute inset-0 h-full w-full"
                      allow="autoplay; encrypted-media"
                      allowFullScreen
                    />
                  </div>
                  <button onClick={() => setTrailerKey(null)} className="glass-button mt-3 px-4 py-2 text-sm">关闭</button>
                </div>
              </div>
            )}

            {/* Reviews */}
            {reviews.length > 0 && (
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <h3 className="mb-3 text-sm font-semibold text-gray-200">用户评论 <span className="ml-1 text-xs font-normal text-gray-500">{reviews.length}</span></h3>
                <div className="space-y-3">
                  {(showAllReviews ? reviews : reviews.slice(0, 3)).map((r: any, i: number) => (
                    <div key={i} className="rounded-2xl border border-white/10 bg-black/15 p-3">
                      <div className="mb-2 flex items-center gap-2">
                        {r.author_details?.avatar_path ? (
                          <img
                            src={r.author_details.avatar_path.startsWith('/') ? `https://image.tmdb.org/t/p/w45${r.author_details.avatar_path}` : r.author_details.avatar_path}
                            className="h-6 w-6 rounded-full object-cover"
                            alt=""
                          />
                        ) : (
                          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-apple-blue/20 text-[10px] text-apple-blue">
                            {(r.author || '?')[0]}
                          </div>
                        )}
                        <div>
                          <p className="text-xs font-medium text-gray-200">{r.author || '匿名'}</p>
                          <p className="text-[10px] text-gray-500">{r.author_details?.rating ? `评分 ${r.author_details.rating} / 10` : ''}{r.created_at ? ` · ${r.created_at.slice(0, 10)}` : ''}</p>
                        </div>
                      </div>
                      <p className="text-xs leading-relaxed text-gray-400 line-clamp-5">{r.content?.slice(0, 500)}</p>
                    </div>
                  ))}
                </div>
                {reviews.length > 3 && (
                  <button
                    onClick={() => setShowAllReviews(v => !v)}
                    className="mt-3 rounded-full border border-white/10 bg-white/[0.08] px-3 py-1 text-xs text-gray-400 transition-all hover:text-apple-blue"
                  >
                    {showAllReviews ? '收起' : `查看全部 ${reviews.length} 条`}
                  </button>
                )}
              </div>
            )}

            {(cast.length > 0 || crew.length > 0) && (
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <h3 className="mb-3 text-sm font-semibold text-gray-200">Staff</h3>
                <div className="space-y-4">
                  {cast.length > 0 && (
                    <StaffGroup label="演员" items={cast.map(p => ({ name: p.name, sub: p.role || p.character, person_id: p.person_id, profile_path: p.profile_path }))} onClick={goStaff} />
                  )}
                  {directors.length > 0 && (
                    <StaffGroup label="导演" items={directors.map(p => ({ name: p.name, sub: p.job, person_id: p.person_id, profile_path: p.profile_path }))} onClick={goStaff} />
                  )}
                  {supervisors.length > 0 && (
                    <StaffGroup label="监督" items={supervisors.map(p => ({ name: p.name, sub: p.job, person_id: p.person_id, profile_path: p.profile_path }))} onClick={goStaff} />
                  )}
                  {writers.length > 0 && (
                    <StaffGroup label="编剧" items={writers.map(p => ({ name: p.name, sub: p.job, person_id: p.person_id, profile_path: p.profile_path }))} onClick={goStaff} />
                  )}
                  {studios.length > 0 && (
                    <StaffGroup label="制作" items={studios.map(p => ({ name: p.name, sub: p.job, person_id: p.person_id, profile_path: p.profile_path }))} onClick={goStaff} />
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      {thumbnailImages.length > 0 && (
        <section className="rounded-3xl bg-white/[0.04] px-4 py-3 shadow-glass backdrop-blur-2xl sm:px-6 sm:py-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-[0.24em] text-apple-blue/70">Thumbnails</p>
              <h3 className="mt-0.5 text-base font-semibold text-white sm:text-lg">缩略图</h3>
            </div>
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
      </>
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

function StaffGroup({ label, items, onClick }: { label: string; items: { name: string; sub?: string; person_id?: string; profile_path?: string }[]; onClick: (name: string, personId?: string) => void }) {
  return (
    <div>
      <div className="mb-2 text-xs text-gray-500">{label}</div>
      <div className="flex flex-wrap gap-2">
        {items.map((item, idx) => (
          <button
            key={`${item.name}-${idx}`}
            onClick={() => onClick(item.name, item.person_id)}
            className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.08] py-1 pl-1.5 pr-3 text-left text-xs text-gray-200 transition-all hover:border-apple-blue/40 hover:bg-apple-blue/10 hover:text-apple-blue"
            title={item.sub || item.name}
          >
            {item.profile_path ? (
              <img src={item.profile_path} alt={item.name} className="h-7 w-7 rounded-full object-cover" loading="lazy" referrerPolicy="no-referrer" crossOrigin="anonymous" />
            ) : (
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white/[0.12] text-[11px] text-gray-400">
                {item.name.charAt(0)}
              </span>
            )}
            <span>{item.name}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
