export { api } from './api/endpoints'

export { clearCache } from './api/client'
export { getMediaTokenSync, ensureMediaToken, resolveApiUrl, resolveMediaUrl } from './api/mediaUrls'
export { getToken, setToken, getActiveLibrary, setActiveLibrary, getServerUrl, setServerUrl, getApiBase, isNativeApp } from './api/session'

export type {
  Category,
  Config,
  DockerHubLatestBaseline,
  ExternalAudioTrack,
  FolderNode,
  FolderSpecialsResponse,
  LatestSyncWarning,
  LibrarySetting,
  ManualScraperName,
  MediaRoot,
  Movie,
  ScrapeMediaType,
  ScrapeSearchResult,
  SubtitleTrack,
  UpdateCheckResult,
  UpdateInfo,
  UpdateStatus,
  VersionEntry,
} from './api/types'
