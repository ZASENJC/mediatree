import type { Movie } from '../api'

export type MovieCardCoverStrategy = 'auto' | 'episode-still-only' | 'episode-still-or-landscape'
export type MovieCardCoverKind = 'cover' | 'episode-still' | 'placeholder'

export interface MovieCardCoverState {
  kind: MovieCardCoverKind
  isEpisode: boolean
  hasEpisodeStill: boolean
  usesLandscape: boolean
}

export function resolveMovieCardImageSrc(url: string, version: string, sharedArtwork: boolean) {
  if (!version || sharedArtwork) return url
  return `${url}${url.includes('?') ? '&' : '?'}v=${encodeURIComponent(version)}`
}

type CoverMovie = Pick<Movie, 'tmdb_type' | 'tmdb_episode' | 'episode_number' | 'episode_still' | 'episode_still_local'>
type EpisodeTitleMovie = Pick<Movie, 'tmdb_season' | 'tmdb_episode' | 'episode_number' | 'episode_title' | 'title' | 'code'>

export function getMovieCardCover(movie: CoverMovie, strategy: MovieCardCoverStrategy = 'auto'): MovieCardCoverState {
  const isEpisode = movie.tmdb_type === 'tv' || movie.tmdb_episode != null || movie.episode_number != null
  const hasEpisodeStill = !!(isEpisode && (movie.episode_still || movie.episode_still_local))

  if (strategy === 'episode-still-only') {
    return {
      kind: hasEpisodeStill ? 'episode-still' : 'placeholder',
      isEpisode,
      hasEpisodeStill,
      usesLandscape: true,
    }
  }

  if (strategy === 'episode-still-or-landscape') {
    return {
      kind: hasEpisodeStill ? 'episode-still' : 'cover',
      isEpisode,
      hasEpisodeStill,
      usesLandscape: true,
    }
  }

  return {
    kind: hasEpisodeStill ? 'episode-still' : 'cover',
    isEpisode,
    hasEpisodeStill,
    usesLandscape: hasEpisodeStill,
  }
}

export function formatMovieCardEpisodePrefix(movie: EpisodeTitleMovie): string {
  const episodeNumber = movie.tmdb_episode ?? movie.episode_number
  if (episodeNumber == null) {
    return ''
  }

  const seasonPrefix = movie.tmdb_season != null
    ? `S${String(movie.tmdb_season).padStart(2, '0')}·`
    : ''
  return `${seasonPrefix}E${String(episodeNumber).padStart(2, '0')}`
}

export function formatMovieCardEpisodeTitle(movie: EpisodeTitleMovie): string {
  const prefix = formatMovieCardEpisodePrefix(movie)
  const title = movie.episode_title || movie.title || movie.code || ''
  if (!prefix || !title) {
    return prefix || title
  }
  return title.toLowerCase().includes(prefix.toLowerCase()) ? title : `${prefix} ${title}`
}
