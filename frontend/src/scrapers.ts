import type { ScraperInfo } from './api'

export const FALLBACK_SCRAPER_OPTIONS: ScraperInfo[] = [
  { name: 'auto', label: '自动', description: '自动判断刮削源', supported_media_types: [], requires_api_key: false, enabled: true, builtin: true },
  { name: 'tmdb_movie', label: 'TMDB 电影', description: 'TMDB movie scraper', supported_media_types: ['movie'], requires_api_key: true, enabled: true, builtin: true },
  { name: 'tmdb_tv', label: 'TMDB 剧集/番剧', description: 'TMDB TV scraper', supported_media_types: ['tv'], requires_api_key: true, enabled: true, builtin: true },
  { name: 'tmdb_collection', label: 'TMDB 合集', description: 'TMDB collection scraper', supported_media_types: ['collection'], requires_api_key: true, enabled: true, builtin: true },
  { name: 'bangumi', label: 'Bangumi', description: 'Bangumi scraper', supported_media_types: ['tv'], requires_api_key: false, enabled: true, builtin: true },
  { name: 'javdatabase', label: 'Javdatabase', description: 'Javdatabase scraper', supported_media_types: ['movie'], requires_api_key: false, enabled: true, builtin: true },
  { name: 'none', label: '不刮削', description: '只扫描本地文件，不联网刮削元数据', supported_media_types: [], requires_api_key: false, enabled: false, builtin: true },
]

function normalizeOptions(
  items: ScraperInfo[] | undefined,
  {
    allowJavdatabase = true,
    allowNone = false,
  }: {
    allowJavdatabase?: boolean
    allowNone?: boolean
  } = {},
): ScraperInfo[] {
  const source = items ?? FALLBACK_SCRAPER_OPTIONS
  const seen = new Set<string>()
  return source.filter(item => {
    const name = item.name
    if (name === 'none' && !allowNone) return false
    if (!item.enabled && !(allowNone && name === 'none')) return false
    if (!allowJavdatabase && name === 'javdatabase') return false
    if (!name || seen.has(name)) return false
    seen.add(name)
    return true
  })
}

export function normalizeScraperOptions(items?: ScraperInfo[], allowJavdatabase = true): ScraperInfo[] {
  return normalizeOptions(items, { allowJavdatabase })
}

export function normalizeLibraryScraperOptions(items?: ScraperInfo[]): ScraperInfo[] {
  return normalizeOptions(items, { allowNone: true })
}
