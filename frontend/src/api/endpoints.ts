import { clearCache, request } from './client'
import { appendMediaToken, ensureMediaToken, resolveApiUrl, resolveMediaUrl } from './mediaUrls'
import { clearActiveLibrary, getActiveLibrary, getApiBase, getToken, setToken } from './session'
import type {
  Category,
  Config,
  ExternalAudioTrack,
  FolderNode,
  FolderSpecialsResponse,
  LibrarySetting,
  MediaRoot,
  Movie,
  ScrapeMediaType,
  ScrapeSearchResult,
  ScraperInfo,
  ScraperPlugin,
  SubtitleTrack,
  UpdateCheckResult,
  UpdateInfo,
  UpdateStatus,
} from './types'

export const api = {
  authStatus: () => request<{ need_auth: boolean; auth_configured: boolean }>('/auth/status'),

  login: (username: string, password: string) =>
    request<{ token: string; ok: boolean }>('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    }),

  setupAuth: (username: string, password: string) =>
    request<{ token: string; ok: boolean }>('/auth/setup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    }),

  health: () => request<{ status: string }>('/health'),

  scan: (mediaRoot?: string) => {
    clearCache()
    const lib = mediaRoot || getActiveLibrary()
    const url = lib ? `/scan?media_root=${encodeURIComponent(lib)}` : '/scan'
    return request<{ total: number; codes: string[] }>(url)
  },

  folders: () => {
    const lib = getActiveLibrary()
    const cacheKey = `folders_${lib}`
    const url = `/folders${lib ? `?media_root=${encodeURIComponent(lib)}` : ''}`
    return request<{ tree: FolderNode[] }>(url, undefined, cacheKey)
  },

  search: (q: string, field?: string) => {
    const lib = getActiveLibrary()
    const url = `/search?q=${encodeURIComponent(q)}${field ? `&field=${encodeURIComponent(field)}` : ''}${lib ? `&media_root=${encodeURIComponent(lib)}` : ''}`
    return request<{ movies: Movie[]; total: number }>(url)
  },

  movies: (params?: {
    folder?: string
    tag?: string
    code?: string
    actress?: string
    staff?: string
    category_id?: number
    sort?: string
    limit?: number
    offset?: number
    media_root?: string
  }) => {
    const qs = new URLSearchParams()
    if (params?.folder) qs.set('folder', params.folder)
    if (params?.tag) qs.set('tag', params.tag)
    if (params?.code) qs.set('code', params.code)
    if (params?.actress) qs.set('actress', params.actress)
    if (params?.staff) qs.set('staff', params.staff)
    if (params?.category_id) qs.set('category_id', String(params.category_id))
    if (params?.sort) qs.set('sort', params.sort)
    if (params?.limit) qs.set('limit', String(params.limit))
    if (params?.offset) qs.set('offset', String(params.offset))
    const lib = params?.media_root || getActiveLibrary()
    if (lib) qs.set('media_root', lib)
    return request<{ movies: Movie[]; total: number }>(`/movies?${qs}`)
  },

  favorites: (limit?: number, offset?: number, sort?: string) => {
    const qs = new URLSearchParams()
    if (limit) qs.set('limit', String(limit))
    if (offset) qs.set('offset', String(offset))
    if (sort) qs.set('sort', sort)
    const lib = getActiveLibrary()
    if (lib) qs.set('media_root', lib)
    return request<{ movies: Movie[]; total: number }>(`/favorites?${qs}`)
  },

  detail: (id: number) => request<Movie>(`/detail/${id}`, undefined, `detail_${id}`),

  mediaInfo: (id: number) => request<{ duration: number; video_codec: string; audio_codec: string; audio_channels?: number; container: string; external_audio_tracks?: ExternalAudioTrack[] }>(`/media-info/${id}`),

  getProgress: (id: number) => request<{ position: number; played: boolean; progress_percent: number }>(`/progress/${id}`),

  saveProgress: (id: number, position: number, duration?: number, stopped?: boolean, snapshot?: boolean) =>
    request<{ ok: boolean; played: boolean; progress_percent: number }>(`/progress/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ position, duration, stopped, snapshot }),
      keepalive: !!snapshot,
    }),

  ensureMediaToken,

  streamUrl: (id: number) => appendMediaToken(`${getApiBase()}/stream/${id}`),

  externalPlaylistUrl: (id: number) => appendMediaToken(`${getApiBase()}/external-play/${id}.m3u`),

  coverUrl: (id: number) => appendMediaToken(`${getApiBase()}/cover/${id}`),

  continueCoverUrl: (id: number) => appendMediaToken(`${getApiBase()}/continue-cover/${id}`),

  resetContinueCover: (id: number) =>
    request<{ ok: boolean }>(`/continue-cover-reset/${id}`, { method: 'POST' }),

  thumbnailUrl: (id: number, index: number) => appendMediaToken(`${getApiBase()}/thumbnail/${id}/${index}`),

  categories: () => request<Category[]>('/categories'),

  createCategory: (data: { name: string; movie_ids?: number[] }) =>
    request<Category>('/categories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  updateCategory: (id: number, data: { name?: string; movie_ids?: number[] }) =>
    request<Category>(`/categories/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  deleteCategory: (id: number) => request(`/categories/${id}`, { method: 'DELETE' }),

  addTag: (movieId: number, tag: string) =>
    request(`/movies/${movieId}/tags`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tag }),
    }),

  removeTag: (movieId: number, tag: string) =>
    request(`/movies/${movieId}/tags/${encodeURIComponent(tag)}`, {
      method: 'DELETE',
    }),

  setFolderWatched: (folder: string, mediaRoot: string, watched: boolean) =>
    request('/folder/watched', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder, media_root: mediaRoot, watched }),
    }),

  folderSpecials: (folder: string, mediaRoot?: string, includeMovies = false) => {
    const lib = mediaRoot || getActiveLibrary()
    const include = includeMovies ? '&include_movies=1' : ''
    return request<FolderSpecialsResponse>(
      `/folder/specials?folder=${encodeURIComponent(folder)}&media_root=${encodeURIComponent(lib)}${include}`
    )
  },

  setFolderSpecials: (folder: string, mediaRoot: string | undefined, showSpecials: boolean) =>
    request<FolderSpecialsResponse>('/folder/specials', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder, media_root: mediaRoot || getActiveLibrary(), show_specials: showSpecials }),
    }).then(result => {
      clearCache()
      return result
    }),

  deleteMovie: (movieId: number) =>
    request(`/movies/${movieId}`, { method: 'DELETE' }),

  getConfig: () => request<Config>('/config', undefined, 'config'),

  updateConfig: (data: Partial<Config>) =>
    request('/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(result => {
      clearCache('config')
      return result
    }),

  mediaRoots: () => request<{ items: MediaRoot[] }>('/media-roots', undefined, 'media_roots'),

  libraryPasswords: () => request<{ media_root: string }[]>('/library-passwords'),

  setLibraryPassword: (media_root: string, password: string) =>
    request<{ ok: boolean }>('/library-passwords', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ media_root, password }),
    }),

  verifyLibrary: (media_root: string, password: string) =>
    request<{ ok: boolean }>('/library-verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ media_root, password }),
    }),

  setupStatus: () => request<{ needs_setup: boolean; roots: string[] }>('/setup/status'),

  setupSave: (libraries: any[], tmdbAccessToken?: string) =>
    request<{ ok: boolean; scan_started?: boolean }>('/setup/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ libraries, tmdb_access_token: tmdbAccessToken || '' }),
    }),

  librarySettings: () => request<LibrarySetting[]>('/library-settings'),

  saveLibrarySetting: (data: Partial<LibrarySetting> & { media_root: string }) =>
    request<{ ok: boolean }>('/library-settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  scrapers: () => request<{ items: ScraperInfo[] }>('/scrapers', undefined, 'scrapers'),

  scraperPlugins: () => request<{ items: ScraperPlugin[] }>('/scraper-plugins'),

  installScraperPlugin: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await request<{ ok: boolean; plugin: ScraperPlugin }>('/scraper-plugins/install', {
      method: 'POST',
      body: formData,
    })
    clearCache('scrapers')
    return res
  },

  enableScraperPlugin: (name: string) =>
    request<{ ok: boolean; plugin: ScraperPlugin }>(`/scraper-plugins/${encodeURIComponent(name)}/enable`, { method: 'POST' })
      .then(result => {
        clearCache('scrapers')
        return result
      }),

  disableScraperPlugin: (name: string) =>
    request<{ ok: boolean; plugin: ScraperPlugin }>(`/scraper-plugins/${encodeURIComponent(name)}/disable`, { method: 'POST' })
      .then(result => {
        clearCache('scrapers')
        return result
      }),

  deleteScraperPlugin: (name: string) =>
    request<{ ok: boolean }>(`/scraper-plugins/${encodeURIComponent(name)}`, { method: 'DELETE' })
      .then(result => {
        clearCache('scrapers')
        return result
      }),

  subtitleTracks: (movieId: number, signal?: AbortSignal) => request<SubtitleTrack[]>(`/subtitle-tracks/${movieId}`, signal ? { signal } : undefined),

  subtitleUrl: (movieId: number, trackIndex: number) => appendMediaToken(`${getApiBase()}/subtitle/${movieId}/${trackIndex}`),

  subtitleContent: async (movieId: number, trackIndex: number) => {
    const headers: Record<string, string> = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    const res = await fetch(`${getApiBase()}/subtitle-content/${movieId}/${trackIndex}`, { headers })
    if (!res.ok) throw new Error(await res.text())
    return res.text()
  },

  subtitleFonts: () => request<{ fonts: { name: string; size: number; family: string }[] }>('/subtitle-fonts'),

  uploadFont: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const headers: Record<string, string> = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    const res = await fetch(`${getApiBase()}/subtitle-fonts/upload`, { method: 'POST', headers, body: formData })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  deleteFont: (name: string) => request<{ ok: boolean }>(`/subtitle-fonts/${encodeURIComponent(name)}`, { method: 'DELETE' }),

  defaultSubtitleFontUrl: () => `${getApiBase()}/subtitle-fonts/default`,

  fontUrl: (name: string) => `${getApiBase()}/subtitle-fonts/${name.split('/').map(encodeURIComponent).join('/')}`,

  cachedCoverUrl: (cacheKey: string) => `${getApiBase()}/cached-cover/${cacheKey}`,

  episodeStillUrl: (movieId: number) => appendMediaToken(`${getApiBase()}/episode-still/${movieId}`),

  scanStatus: (mediaRoot: string) =>
    request<{ media_root?: string; status: string; done: number; total: number; roots?: Record<string, any> }>(
      `/scan/status?media_root=${encodeURIComponent(mediaRoot)}`
    ),

  scanStatusAll: () =>
    request<{ roots: Record<string, { status: string; done: number; total: number }> }>('/scan/status'),

  scanLog: (mediaRoot: string, lines: number = 100) =>
    request<{ lines: string[]; total: number }>(
      `/scan/log?media_root=${encodeURIComponent(mediaRoot)}&lines=${lines}`
    ),

  clearLibrary: (mediaRoot: string) =>
    request('/library/clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ media_root: mediaRoot }),
    }),

  backupUrl: (type: 'core' | 'full') => `${getApiBase()}/backup?backup_type=${type}`,

  getRecentWatched: (limit?: number, offset?: number) => {
    const qs = new URLSearchParams()
    if (limit) qs.set('limit', String(limit))
    if (offset) qs.set('offset', String(offset))
    const lib = getActiveLibrary()
    if (lib) qs.set('media_root', lib)
    return request<{ movies: Movie[]; total: number }>(`/recent-watched?${qs}`)
  },

  rescrapeMovie: (movieId: number) =>
    request<{ ok: boolean; source: string; title: string }>(`/movies/${movieId}/rescrape`, { method: 'POST' }),

  rescrapeFolder: (folder: string, mediaRoot: string) =>
    request<{ ok: boolean; rescraped: number; total: number }>('/rescrape-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder, media_root: mediaRoot }),
    }),

  searchScrape: (query: string, scraper?: string, mediaRoot?: string) =>
    request<{ results: ScrapeSearchResult[] }>('/search-scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, scraper: scraper || 'tmdb_movie', media_root: mediaRoot || getActiveLibrary() }),
    }),

  rescrapeFolderManual: (folder: string, mediaRoot: string, query: string, scraper?: string) =>
    request<{ ok: boolean; source: string; title: string }>('/rescrape-folder-manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder, media_root: mediaRoot, query, scraper: scraper || '' }),
    }),

  applyFolderScrape: (folder: string, mediaRoot: string, sourceId: string, source: string, mediaType: ScrapeMediaType) =>
    request<{ ok: boolean; source: string; title: string; affected?: number }>('/apply-folder-scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder, media_root: mediaRoot, source_id: sourceId, source, media_type: mediaType }),
    }),

  fetchSearchBackdrops: (results: any[]) =>
    request<{ backdrops: { source_id: string; source: string; media_type?: string; backdrop_url?: string; poster_url?: string }[] }>('/search-backdrops', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ results }),
    }),

  changeFolderBackdrop: (folder: string, mediaRoot: string, url: string) =>
    request<{ ok: boolean }>('/folder/backdrop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder, media_root: mediaRoot, url }),
    }),

  changeFolderCover: (folder: string, mediaRoot: string, url: string) =>
    request<{ ok: boolean }>('/folder/cover', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder, media_root: mediaRoot, url }),
    }),

  editFolder: (folder: string, mediaRoot: string, fields: Record<string, any>) =>
    request<{ ok: boolean }>('/folder/edit', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder, media_root: mediaRoot, fields }),
    }),

  deleteFolder: (folder: string, mediaRoot: string) =>
    request<{ ok: boolean; deleted: number }>('/folder/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder, media_root: mediaRoot }),
    }),

  manualScrapeMovie: (movieId: number, query: string, sourceId?: string, mediaType?: ScrapeMediaType, scraper?: string) =>
    request<{ ok: boolean; source: string; title: string }>(`/movies/${movieId}/manual-scrape`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, source_id: sourceId, media_type: mediaType, scraper }),
    }),

  getAlternativeCovers: (movieId: number) =>
    request<{ covers: { url: string; source: string }[] }>(`/movies/${movieId}/alternative-covers`),

  changeCover: (movieId: number, urlOrFile: string | File) => {
    if (typeof urlOrFile === 'string') {
      return request<{ ok: boolean; cover_local?: string; cover_remote?: string }>(`/movies/${movieId}/cover`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: urlOrFile }),
      })
    }
    const formData = new FormData()
    formData.append('file', urlOrFile)
    const headers: Record<string, string> = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    return fetch(`${getApiBase()}/movies/${movieId}/cover`, { method: 'POST', headers, body: formData }).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json()
    })
  },

  // ─── TMDB Extended API ───

  folderBackdrops: (path: string, mediaRoot: string) =>
    request<{
      backdrops: { url: string; width: number; height: number }[]
      logos: { url: string; width: number; height: number; language: string | null }[]
    }>(`/folder-backdrops?path=${encodeURIComponent(path)}&media_root=${encodeURIComponent(mediaRoot)}`, undefined, `folder_backdrops_${path}_${mediaRoot}`),

  tmdbImages: (tmdbId: number, mediaType: string) =>
    request<{ posters: { url: string; width: number; height: number; language: string; vote_count: number; vote_average: number }[]; backdrops: { url: string; width: number; height: number; language: string }[]; logos: { url: string; width: number; height: number; language: string }[] }>(`/tmdb-images/${tmdbId}?media_type=${encodeURIComponent(mediaType)}`, undefined, `tmdb_images_${tmdbId}_${mediaType}`),

  tmdbVideos: (tmdbId: number, mediaType: string) =>
    request<{ results: { key: string; name: string; site: string; type: string; size: number; official: boolean; published_at: string }[] }>(`/tmdb-videos/${tmdbId}?media_type=${encodeURIComponent(mediaType)}`, undefined, `tmdb_videos_${tmdbId}_${mediaType}`),

  personDetail: (personId: number) =>
    request<{ id: number; name: string; biography: string; birthday: string; deathday: string; place_of_birth: string; homepage: string; profile_path: string; known_for_department: string; imdb_id: string; facebook_id: string; instagram_id: string; twitter_id: string }>(`/person/${personId}`, undefined, `person_${personId}`),

  personCredits: (personId: number) =>
    request<{ cast: { id: number; title: string; media_type: string; character: string; job: string; release_date: string; poster_url: string; vote_average: number; overview: string }[]; crew: { id: number; title: string; media_type: string; character: string; job: string; release_date: string; poster_url: string; vote_average: number; overview: string }[] }>(`/person/${personId}/credits`, undefined, `person_credits_${personId}`),

  personImages: (personId: number) =>
    request<{ profiles: { url: string; width: number; height: number; vote_count: number }[] }>(`/person-images/${personId}`, undefined, `person_images_${personId}`),

  tmdbReviews: (tmdbId: number, mediaType: string, page: number = 1) =>
    request<{ results: { id: string; author: string; author_details: any; content: string; created_at: string; url: string }[]; page: number; total_pages: number; total_results: number }>(`/tmdb-reviews/${tmdbId}?media_type=${encodeURIComponent(mediaType)}&page=${page}`, undefined, `tmdb_reviews_${tmdbId}_${mediaType}_${page}`),

  tmdbKeywords: (tmdbId: number, mediaType: string) =>
    request<{ keywords: { id: number; name: string }[] }>(`/tmdb-keywords/${tmdbId}?media_type=${encodeURIComponent(mediaType)}`, undefined, `tmdb_keywords_${tmdbId}_${mediaType}`),

  releaseDates: (tmdbId: number) =>
    request<{ results: { iso_3166_1: string; release_dates: { certification: string; release_date: string; type: number; note: string }[] }[] }>(`/release-dates/${tmdbId}`, undefined, `release_dates_${tmdbId}`),

  seasonImages: (seriesId: number, seasonNum: number) =>
    request<{ posters: { url: string; width: number; height: number; language: string; vote_count: number; vote_average: number }[] }>(`/season-images/${seriesId}/${seasonNum}`, undefined, `season_images_${seriesId}_${seasonNum}`),

  episodeImages: (seriesId: number, seasonNum: number, epNum: number) =>
    request<{ stills: { url: string; width: number; height: number; vote_count: number; vote_average: number }[] }>(`/episode-images/${seriesId}/${seasonNum}/${epNum}`, undefined, `episode_images_${seriesId}_${seasonNum}_${epNum}`),

  editMovie: (movieId: number, data: Partial<Pick<Movie, 'title' | 'code' | 'actress' | 'release_date' | 'duration'>>) =>
    request<{ ok: boolean }>(`/movies/${movieId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  getVersion: () =>
    request<UpdateInfo>('/version'),

  checkForUpdates: (includeRegistrySync = false) =>
    request<UpdateCheckResult>(`/update/check${includeRegistrySync ? '?include_registry_sync=true' : ''}`),

  performUpdate: (version: string, mode: 'auto' | 'app-package' | 'docker-image' = 'auto') =>
    request<{ ok: boolean; message?: string; version?: string; error?: string }>('/update/perform', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version, mode }),
    }),

  updateStatus: () =>
    request<UpdateStatus>('/update/status'),

  rollbackUpdate: () =>
    request<{ ok: boolean; message?: string; version?: string }>('/update/rollback', {
      method: 'POST',
    }),

  getChangelog: (version: string) =>
    request<{ version: string; body: string }>(`/update/changelog?version=${encodeURIComponent(version)}`),

  changePassword: (oldUsername: string, oldPassword: string, newUsername: string, newPassword: string) =>
    request<{ ok: boolean }>('/auth/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_username: oldUsername, old_password: oldPassword, new_username: newUsername, new_password: newPassword }),
    }),

  resolveUrl: resolveApiUrl,
  resolveMediaUrl,

  logout: () => { setToken(''); clearActiveLibrary(); clearCache(); window.location.href = '/login?logout=1' },
}
