import type Artplayer from 'artplayer'
import { api, resolveMediaUrl, type SubtitleTrack } from '../api'

const BUNDLED_CJK_FALLBACK_FONT = '/fonts/SourceHanSansCN-Bold.woff2'
const CJK_FONT_RE = /source\s*han|noto\s*sans\s*cjk|noto\s*serif\s*cjk|noto.*cjk|wenquanyi|wqy|pingfang|hiragino|yu\s*gothic|meiryo|simhei|simsun|yahei|microsoft\s*yahei|思源|宋体|黑体|微软雅黑|蘋方|苹方|ヒラギノ|游ゴシック|メイリオ/i
const ASS_CJK_FONT_ALIASES = [
  'source han sans cn', 'source han sans sc', 'source han sans',
  'noto sans cjk sc', 'noto sans cjk jp', 'noto sans cjk kr', 'noto sans sc',
  'noto serif cjk sc', 'microsoft yahei', 'microsoft jhenghei',
  'simhei', 'simsun', 'nsimsun', 'simkai', 'kaiti', 'fangsong',
  'wenquanyi micro hei', 'wenquanyi zen hei', 'pingfang sc', 'pingfang tc',
  'hiragino sans gb', 'hiragino kaku gothic pro', 'yu gothic', 'meiryo',
  'arial unicode ms', '宋体', '新宋体', '黑体', '微软雅黑', '微軟雅黑',
  '楷体', '仿宋', '华文黑体', '蘋方', '苹方', 'ヒラギノ角ゴ', '游ゴシック', 'メイリオ',
]

export type SubtitleFont = { name: string; size: number; family: string }

type AssPluginController = {
  setVisible: (visible: boolean) => void
  switch: (subtitleUrl: string, nextOptions?: Record<string, unknown>) => Promise<void>
  clear: () => void
  destroy: () => void
}

function absoluteApiUrl(url: string) {
  return new URL(resolveMediaUrl(url), window.location.origin).toString()
}

function bundledCjkFontUrl() {
  return new URL(BUNDLED_CJK_FALLBACK_FONT, window.location.origin).toString()
}

function parseVttTimestamp(ts: string): number {
  const parts = ts.split(':')
  if (parts.length === 3) {
    return parseFloat(parts[0]) * 3600 + parseFloat(parts[1]) * 60 + parseFloat(parts[2])
  }
  if (parts.length === 2) {
    return parseFloat(parts[0]) * 60 + parseFloat(parts[1])
  }
  return parseFloat(parts[0]) || 0
}

function formatVttTimestamp(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600)
  const m = Math.floor((totalSeconds % 3600) / 60)
  const s = totalSeconds % 60
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toFixed(3).padStart(7, '0')}`
}

function offsetVttTimestamps(vtt: string, offsetSeconds: number): string {
  if (Math.abs(offsetSeconds) < 0.001) return vtt
  return vtt.replace(
    /(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})/g,
    (_match, start, end) => {
      const newStart = formatVttTimestamp(Math.max(0, parseVttTimestamp(start) - offsetSeconds))
      const newEnd = formatVttTimestamp(Math.max(0, parseVttTimestamp(end) - offsetSeconds))
      return `${newStart} --> ${newEnd}`
    }
  )
}

export async function fetchOffsetSubtitleBlob(baseUrl: string, offsetSeconds: number): Promise<string> {
  const response = await fetch(baseUrl)
  const text = await response.text()
  const adjusted = offsetVttTimestamps(text, offsetSeconds)
  const blob = new Blob([adjusted], { type: 'text/vtt' })
  return URL.createObjectURL(blob)
}

function normalizeAssFontName(name: string) {
  return name.trim().replace(/^@/, '').toLowerCase()
}

function addFontAlias(map: Record<string, string>, name: string | undefined, url: string, overwrite = false) {
  if (!name) return
  const key = normalizeAssFontName(name)
  if (!key) return
  if (overwrite || !map[key]) map[key] = url
}

function fontStem(name: string) {
  const base = name.split('/').pop() || name
  return base.replace(/\.(ttf|otf|ttc|woff2?|collection)$/i, '')
}

function isCjkFont(font: SubtitleFont) {
  return CJK_FONT_RE.test(font.family || '') || CJK_FONT_RE.test(font.name || '')
}

export function buildAssFontConfig(fonts: SubtitleFont[]) {
  const bundledFallback = bundledCjkFontUrl()
  const map: Record<string, string> = {}
  const urls = new Set<string>([bundledFallback])
  const uploadedCjkFont = fonts.find(font => !font.name.startsWith('system/') && isCjkFont(font) && /\.(ttf|otf|woff2?)$/i.test(font.name))
  const fallbackFont = uploadedCjkFont ? absoluteApiUrl(api.fontUrl(uploadedCjkFont.name)) : bundledFallback

  fonts.forEach(font => {
    const url = absoluteApiUrl(api.fontUrl(font.name))
    if (!font.name.startsWith('system/')) urls.add(url)
    addFontAlias(map, font.family, url)
    addFontAlias(map, fontStem(font.name), url)
  })
  ASS_CJK_FONT_ALIASES.forEach(name => addFontAlias(map, name, fallbackFont, true))
  addFontAlias(map, 'SourceHanSansCN-Bold', bundledFallback, true)
  addFontAlias(map, 'Source Han Sans CN', bundledFallback, true)

  return {
    fonts: Array.from(urls),
    availableFonts: map,
    fallbackFont,
  }
}

export function isAssTrack(track: SubtitleTrack) {
  const codec = (track.codec || '').toLowerCase()
  const title = (track.title || '').toLowerCase()
  const name = (track.name || '').toLowerCase()
  return codec.includes('ass') || codec.includes('ssa') || title.endsWith('.ass') || title.endsWith('.ssa') || name.endsWith('.ass') || name.endsWith('.ssa')
}

export function isTextTrack(track: SubtitleTrack) {
  const codec = (track.codec || '').toLowerCase()
  const title = (track.title || '').toLowerCase()
  const name = (track.name || '').toLowerCase()
  if (track.web_supported === false) return false
  if (track.source === 'external') {
    return ['ass', 'ssa', 'srt', 'vtt'].includes(codec)
      || /\.(ass|ssa|srt|vtt)$/i.test(title)
      || /\.(ass|ssa|srt|vtt)$/i.test(name)
  }
  return ['ass', 'ssa', 'srt', 'subrip', 'webvtt', 'vtt', 'mov_text'].includes(codec)
}

export function subtitleLanguagePriority(track: SubtitleTrack) {
  const language = (track.language || '').toLowerCase()
  const label = `${track.title || ''} ${track.name || ''}`.toLowerCase()
  const hasToken = (token: string) => new RegExp(`(^|[\\s._-])${token}($|[\\s._-])`, 'i').test(label)
  if (language === 'zh' || language === 'chi') return 0
  if (language === 'chs' || hasToken('chs')) return 1
  if (language === 'cht' || hasToken('cht')) return 2
  if (language === 'sc' || hasToken('sc')) return 3
  if (language === 'tc' || hasToken('tc')) return 4
  if (language === 'zh-cn' || language === 'zh-hans' || /zh[\s._-]?cn|zh[\s._-]?hans/.test(label)) return 5
  if (language === 'zh-tw' || language === 'zh-hant' || /zh[\s._-]?tw|zh[\s._-]?hant/.test(label)) return 6
  if (/chinese|中文|简体|繁体/.test(label)) return 7
  return 100
}

export function trackLabel(track: SubtitleTrack) {
  if (track.source === 'external') {
    return track.name || track.title || track.codec || `Subtitle ${track.index}`
  }
  const source = '内嵌'
  const lang = track.language || '--'
  const title = track.title || track.codec || `Track ${track.index}`
  return `${source} ${lang} ${title}`
}

export function sortSubtitleTracks(trackList: SubtitleTrack[]) {
  return [...trackList].filter(isTextTrack).sort((a, b) => {
    const sourceRank = (track: SubtitleTrack) => track.source === 'external' ? 0 : 1
    const bySource = sourceRank(a) - sourceRank(b)
    if (bySource) return bySource
    return a.index - b.index
  })
}

export function getAssPlugin(art: Artplayer): AssPluginController | null {
  const plugin = art.plugins.artplayerPluginAss as AssPluginController | undefined
  return plugin || null
}

export function htmlLabel(text: string) {
  const span = document.createElement('span')
  span.title = text
  span.textContent = text
  span.style.cssText = [
    'display:-webkit-box',
    'max-width:210px',
    'overflow:hidden',
    'text-overflow:ellipsis',
    '-webkit-line-clamp:2',
    '-webkit-box-orient:vertical',
    'white-space:normal',
    'word-break:break-word',
    'font-size:12px',
    'line-height:1.35',
  ].join(';')
  return span
}
