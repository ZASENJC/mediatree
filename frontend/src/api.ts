import { getCached, setCache, clearCache } from './cache'

const BASE = '/api'
let memoryToken = ''
let memoryActiveLibrary = ''

function getToken(): string {
  try {
    const stored = localStorage.getItem('mediatree_token') || ''
    if (stored) memoryToken = stored
    return stored || memoryToken
  } catch {
    return memoryToken
  }
}
function setToken(t: string) {
  memoryToken = t
  try { localStorage.setItem('mediatree_token', t) } catch {}
}

function getActiveLibrary(): string {
  try {
    const stored = localStorage.getItem('mediatree_library') || ''
    if (stored) memoryActiveLibrary = stored
    return stored || memoryActiveLibrary
  } catch {
    return memoryActiveLibrary
  }
}
function setActiveLibrary(lib: string) {
  memoryActiveLibrary = lib
  try { localStorage.setItem('mediatree_library', lib) } catch {}
}

async function request<T>(url: string, options?: RequestInit, cacheKey?: string): Promise<T> {
  if (cacheKey) {
    const cached = getCached<T>(cacheKey)
    if (cached !== null) return cached
  }
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string> || {}),
  }
  const token = getToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const res = await fetch(`${BASE}${url}`, { ...options, headers })
  if (res.status === 401) {
    setToken('')
    if (window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  const data = await res.json()
  if (cacheKey) setCache(cacheKey, data)
  return data
}

function libParam(): string {
  const lib = getActiveLibrary()
  return lib ? `&media_root=${encodeURIComponent(lib)}` : ''
}

export const api = {
  authStatus: () => request<{ need_auth: boolean }>('/auth/status'),

  login: (username: string, password: string) =>
    request<{ token: string; ok: boolean }>('/auth/login', {
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

  saveProgress: (id: number, position: number, duration?: number, stopped?: boolean) =>
    request<{ ok: boolean; played: boolean; progress_percent: number }>(`/progress/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ position, duration, stopped }),
    }),

  streamUrl: (id: number) => `${BASE}/stream/${id}`,

  externalPlaylistUrl: (id: number) => `${BASE}/external-play/${id}.m3u`,

  coverUrl: (id: number) => `${BASE}/cover/${id}`,

  thumbnailUrl: (id: number, index: number) => `${BASE}/thumbnail/${id}/${index}`,

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

  deleteMovie: (movieId: number) =>
    request(`/movies/${movieId}`, { method: 'DELETE' }),

  getConfig: () => request<Config>('/config', undefined, 'config'),

  updateConfig: (data: Partial<Config>) =>
    request('/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
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

  subtitleTracks: (movieId: number) => request<SubtitleTrack[]>(`/subtitle-tracks/${movieId}`),

  subtitleUrl: (movieId: number, trackIndex: number) => `${BASE}/subtitle/${movieId}/${trackIndex}`,

  subtitleContent: async (movieId: number, trackIndex: number) => {
    const headers: Record<string, string> = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    const res = await fetch(`${BASE}/subtitle-content/${movieId}/${trackIndex}`, { headers })
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
    const res = await fetch(`${BASE}/subtitle-fonts/upload`, { method: 'POST', headers, body: formData })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  deleteFont: (name: string) => request<{ ok: boolean }>(`/subtitle-fonts/${encodeURIComponent(name)}`, { method: 'DELETE' }),

  defaultSubtitleFontUrl: () => `${BASE}/subtitle-fonts/default`,

  fontUrl: (name: string) => `${BASE}/subtitle-fonts/${name.split('/').map(encodeURIComponent).join('/')}`,

  cachedCoverUrl: (cacheKey: string) => `${BASE}/cached-cover/${cacheKey}`,

  episodeStillUrl: (movieId: number) => `${BASE}/episode-still/${movieId}`,

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

  backupUrl: (type: 'core' | 'full') => `${BASE}/backup?backup_type=${type}`,

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

  searchScrape: (query: string, scraper?: string) =>
    request<{ results: { source: string; source_id: string; media_type: string; title: string; original_title: string; year: string; poster_url?: string; overview: string }[] }>('/search-scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, scraper: scraper || 'tmdb_movie' }),
    }),

  rescrapeFolderManual: (folder: string, mediaRoot: string, query: string, scraper?: string) =>
    request<{ ok: boolean; source: string; title: string }>('/rescrape-folder-manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder, media_root: mediaRoot, query, scraper: scraper || '' }),
    }),

  applyFolderScrape: (folder: string, mediaRoot: string, sourceId: string, source: string, mediaType: string) =>
    request<{ ok: boolean; source: string; title: string; affected?: number }>('/apply-folder-scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder, media_root: mediaRoot, source_id: sourceId, source, media_type: mediaType }),
    }),

  fetchSearchBackdrops: (results: any[]) =>
    request<{ backdrops: { source_id: string; source: string; backdrop_url?: string; poster_url?: string }[] }>('/search-backdrops', {
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

  manualScrapeMovie: (movieId: number, query: string, sourceId?: string, mediaType?: string, scraper?: string) =>
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
    return fetch(`${BASE}/movies/${movieId}/cover`, { method: 'POST', headers, body: formData }).then(r => r.json())
  },

  editMovie: (movieId: number, data: Partial<Pick<Movie, 'title' | 'code' | 'actress' | 'release_date' | 'duration'>>) =>
    request<{ ok: boolean }>(`/movies/${movieId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  changePassword: (oldUsername: string, oldPassword: string, newUsername: string, newPassword: string) =>
    request<{ ok: boolean }>('/auth/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_username: oldUsername, old_password: oldPassword, new_username: newUsername, new_password: newPassword }),
    }),

  getPlugins: () => request<{ plugins: Plugin[] }>('/plugins/list'),

  uploadPlugin: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const headers: Record<string, string> = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    const res = await fetch(`${BASE}/plugins/upload`, { method: 'POST', headers, body: formData })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  deletePlugin: (name: string) => request<{ ok: boolean }>(`/plugins/${encodeURIComponent(name)}`, { method: 'DELETE' }),

  logout: () => { setToken(''); setActiveLibrary(''); clearCache(); window.location.href = '/login' },
}

export { getToken, setToken, getActiveLibrary, setActiveLibrary, clearCache }

export interface LibrarySetting {
  media_root: string
  scraper: string
  tmdb_key: string
  password_hash?: string
  enabled: number
}

export interface MediaRoot {
  path: string
  label: string
  movie_count: number
  locked?: boolean
  scraper?: string
}

export interface SubtitleTrack {
  index: number
  stream_index: number
  codec: string
  language: string
  title: string
  name?: string
  source?: string
  path?: string
  format?: string
  is_external?: boolean
  web_supported?: boolean
}

export interface ExternalAudioTrack {
  path: string
  name: string
  source?: string
  language?: string
  codec?: string
  format?: string
  title?: string
  is_external?: boolean
}

export interface FolderNode {
  name: string
  path: string
  is_leaf: boolean
  movie_count: number
  cover?: string
  random_cover?: string
  backdrop?: string
  display_title?: string
  children?: FolderNode[]
  media_root?: string
  created_max?: string
  watched_count?: number
  folder_watched?: boolean
  progress_percent?: number
}

export interface Movie {
  id: number
  path: string
  code: string
  title?: string
  actress?: string
  director?: string
  series?: string
  studio?: string
  genre?: string
  dvd_id?: string
  release_date?: string
  duration?: number
  cover_local?: string
  cover_remote?: string
  fanart_local?: string
  javdb_url?: string
  javdb_score?: number
  javdb_likes?: number
  javdb_thumbnails?: string[]
  javdb_comments?: string[]
  folder_levels?: string
  tags?: string[]
  media_root?: string
  created_at?: string
  updated_at?: string
  tmdb_id?: number
  tmdb_type?: string
  tmdb_season?: number
  tmdb_episode?: number
  episode_title?: string
  episode_overview?: string
  episode_still?: string
  episode_still_local?: string
  clean_title?: string
  episode_number?: number
  episode_label?: string
  display_title?: string
  external_audio_tracks?: ExternalAudioTrack[]
  cast?: { name: string; character?: string; role?: string; profile_path?: string; source?: string }[]
  crew?: { name: string; job: string; department?: string; profile_path?: string; source?: string }[]
  playback_position?: number
  progress_percent?: number
}

export interface Category {
  id: number
  name: string
  movie_ids: number[]
  created_at?: string
}

export interface Config {
  javdb_enabled: boolean
  javdb_cache_hours: number
  javdb_request_interval: number
  tmdb_cache_hours: number
  bangumi_cache_hours: number
  tmdb_api_key: string
  tmdb_access_token: string
  media_root: string
}

export interface Plugin {
  name: string
  label: string
  description: string
  builtin: boolean
  enabled: boolean
  file?: string
}
