import type { Movie } from '../api'

type EpisodeMenuProps = {
  activeMovieId: number
  episodes: Movie[]
  open: boolean
  visible: boolean
  onClose: () => void
  onSelect?: (episode: Movie) => void
  onToggle: () => void
}

export function episodeLabel(movie: Movie) {
  const number = movie.tmdb_episode ?? movie.episode_number
  const prefix = number != null
    ? `${movie.tmdb_season != null ? `S${String(movie.tmdb_season).padStart(2, '0')}` : ''}E${String(number).padStart(2, '0')}`
    : ''
  const title = movie.episode_title || movie.display_title || movie.title || movie.code
  if (!prefix) return title
  return title.toLowerCase().includes(prefix.toLowerCase()) ? title : `${prefix} ${title}`
}

export function EpisodeMenu({
  activeMovieId,
  episodes,
  open,
  visible,
  onClose,
  onSelect,
  onToggle,
}: EpisodeMenuProps) {
  return (
    <div className={`episode-switcher absolute right-3 top-1/2 z-50 flex items-center justify-end sm:right-4 ${visible ? 'episode-switcher-visible' : ''}`}>
      {open && (
        <div className="player-episode-menu mr-2 max-h-[min(22rem,70dvh)] w-[min(18rem,calc(100vw-5rem))] overflow-hidden rounded-2xl">
          <div className="player-episode-menu-header flex items-center justify-between px-3 py-2">
            <p className="text-xs font-semibold">选集</p>
            <span className="player-episode-count text-[11px]">{episodes.length}</span>
          </div>
          <div className="max-h-[calc(min(22rem,70dvh)-2.5rem)] overflow-y-auto p-1.5">
            {episodes.map(episode => {
              const active = episode.id === activeMovieId
              const progress = Math.max(0, Math.min(100, episode.progress_percent || 0))
              return (
                <button
                  key={episode.id}
                  onClick={() => {
                    onClose()
                    if (!active) onSelect?.(episode)
                  }}
                  className={`mb-1 flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-left transition-all last:mb-0 ${
                    active ? 'player-episode-item-active' : 'player-episode-item'
                  }`}
                >
                  <span className={`h-2 w-2 shrink-0 rounded-full ${active ? 'player-episode-dot-active' : 'player-episode-dot'}`} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-xs font-medium">{episodeLabel(episode)}</span>
                    <span className="player-episode-meta mt-0.5 block truncate text-[11px]">
                      {episode.duration ? `${episode.duration}分` : episode.code}
                      {progress > 0 && progress < 90 ? ` · ${Math.round(progress)}%` : ''}
                    </span>
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      )}
      <button
        onClick={onToggle}
        className={`episode-switcher-button ${open ? 'episode-switcher-button-active' : ''}`}
        aria-label="选集"
        aria-expanded={open}
        title="选集"
      >
        <span className="sr-only">选集</span>
        <span className="episode-switcher-icon" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
      </button>
    </div>
  )
}
