import type { Movie } from './api'

export function fileStemFromPath(path?: string) {
  const name = (path || '').replace(/\\/g, '/').split('/').pop() || ''
  return name.replace(/\.[^.]+$/, '') || name
}

export function specialMovieTitle(movie: Movie) {
  return fileStemFromPath(movie.path)
    || movie.display_title
    || movie.title
    || movie.clean_title
    || movie.code
}
