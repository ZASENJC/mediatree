export type ManualScraperName = 'auto' | 'tmdb_movie' | 'tmdb_tv' | 'tmdb_collection' | 'bangumi' | 'javdatabase' | (string & {})
export type ScrapeMediaType = 'movie' | 'tv' | 'collection' | (string & {})

export interface ScraperInfo {
  name: ManualScraperName
  label: string
  description: string
  supported_media_types: string[]
  requires_api_key: boolean
  enabled: boolean
  builtin: boolean
}

export interface ScraperPlugin {
  name: string
  version: string
  label: string
  description: string
  supported_media_types: string[]
  enabled: boolean
  builtin: boolean
  installed_at?: string
  updated_at?: string
  error?: string
}

export interface ScrapeSearchResult {
  source: string
  source_id: string
  media_type: ScrapeMediaType
  title: string
  original_title?: string
  year?: string
  poster_url?: string
  overview?: string
  scraper?: ManualScraperName
}

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
  url?: string
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
  video_count?: number
  cover?: string
  random_cover?: string
  backdrop?: string
  display_title?: string
  children?: FolderNode[]
  media_root?: string
  created_max?: string
  release_date_max?: string
  watched_count?: number
  folder_watched?: boolean
  progress_percent?: number
  tmdb_id?: number
  tmdb_type?: string
  special_count?: number
  show_specials?: boolean
}

export interface Movie {
  id: number
  path: string
  code: string
  title?: string
  original_title?: string
  overview?: string
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
  keywords?: string
  studios?: string
  tagline?: string
  status?: string
  content_rating?: string
  scraper_source?: string
  source_id?: string
  javdb_id?: string
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
  cast?: { name: string; character?: string; role?: string; profile_path?: string; person_id?: string; source?: string }[]
  crew?: { name: string; job: string; department?: string; profile_path?: string; person_id?: string; source?: string }[]
  playback_position?: number
  progress_percent?: number
  content_role?: 'main' | 'special' | string
  special_parent_levels?: string
}

export interface FolderSpecialsResponse {
  show_specials: boolean
  special_count: number
  movies: Movie[]
}

export interface Category {
  id: number
  name: string
  movie_ids: number[]
  created_at?: string
}

export interface Config {
  tmdb_access_token: string
  tmdb_configured: boolean
  media_root: string
  update_check_enabled: boolean
  update_check_interval_hours: number
}

export interface UpdateInfo {
  version: string
  runtime_version?: string
  current_source?: 'base' | 'app-package' | 'docker-image'
  base_version?: string
  effective_version?: string
  overlay_active?: boolean
  overlay_is_outdated?: boolean
  status_note?: string
}

export interface VersionEntry {
  version: string
  display_version: string
  name?: string
  published_at: string
  html_url: string
  body?: string
  source: 'github-release' | string
  update_type?: 'app-package' | 'docker-image-required'
  size?: number
  requires_image_update?: boolean
  required_image_version?: string
  reason?: string
}

export interface DockerHubLatestBaseline {
  version?: string
  display_version?: string
  published_at?: string
  html_url?: string
  source?: 'dockerhub-latest' | string
  status?: 'ok' | 'unknown' | string
  reason?: string
}

export interface LatestSyncWarning {
  type: 'dockerhub-latest-outdated' | string
  severity: 'warning' | string
  release_version: string
  release_display_version?: string
  release_published_at?: string
  dockerhub_latest_version?: string
  dockerhub_latest_updated_at?: string
  evidence?: 'version' | 'timestamp' | string
  message: string
  action: string
}

export interface UpdateCheckResult {
  current_version: string
  runtime_version?: string
  current_source?: 'base' | 'app-package' | 'docker-image'
  base_version?: string
  effective_version?: string
  overlay_active?: boolean
  overlay_is_outdated?: boolean
  status_note?: string
  has_update: boolean
  dockerhub_latest?: DockerHubLatestBaseline | null
  latest_sync_warning?: LatestSyncWarning | null
  versions: VersionEntry[]
}

export interface UpdateStatus {
  status: 'idle' | 'downloading' | 'verifying' | 'installing' | 'restarting' | 'success' | 'error'
  version: string
  downloaded: number
  total: number
  message: string
  update_type?: 'app-package' | 'docker-image' | ''
  logs?: string[]
  can_rollback?: boolean
  rollback_version?: string
  updated_at?: number
}
