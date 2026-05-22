import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { CSSProperties } from 'react'
import Artplayer, { Option, Setting, SettingOption } from 'artplayer'
import { api, SubtitleTrack } from '../api'
import { getUiPrefs, setUiPrefs } from '../store'
import artplayerPluginAss from './artplayerPluginAss'
import VRVideoLayer, { VRMode } from './VRVideoLayer'

interface Props {
  src: string
  poster?: string
  movieId: number
  onWatched?: () => void
}

const POS_KEY = 'mediatree_pos_'
const WATCHED_AFTER = 60
const WATCHED_RATIO = 0.9
const SEEK_SMALL = 5
const POS_SAVE_INTERVAL = 5000
const BROWSER_UNSUPPORTED_AUDIO = new Set(['eac3', 'truehd', 'dts', 'dca', 'mlp'])
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

type SubtitleFont = { name: string; size: number; family: string }
type AssPluginController = {
  setVisible: (visible: boolean) => void
  switch: (subtitleUrl: string, nextOptions?: Record<string, unknown>) => Promise<void>
  clear: () => void
  destroy: () => void
}

Artplayer.PLAYBACK_RATE = [0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4]
Artplayer.SEEK_STEP = SEEK_SMALL
Artplayer.FAST_FORWARD_VALUE = 2
Artplayer.REMOVE_SRC_WHEN_DESTROY = true

function getSavedPos(movieId: number): number {
  try { return parseFloat(localStorage.getItem(POS_KEY + movieId) || '0') } catch { return 0 }
}

function savePos(movieId: number, pos: number) {
  try { localStorage.setItem(POS_KEY + movieId, String(pos)) } catch {}
}

function loadJson<T>(key: string, fallback: T): T {
  try { return JSON.parse(localStorage.getItem(key) || 'null') || fallback } catch { return fallback }
}

function saveJson(key: string, val: unknown) {
  try { localStorage.setItem(key, JSON.stringify(val)) } catch {}
}

function fmt(t: number) {
  if (!isFinite(t) || t < 0) return '0:00'
  const h = Math.floor(t / 3600)
  const m = Math.floor((t % 3600) / 60)
  const s = Math.floor(t % 60)
  return h > 0
    ? `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
    : `${m}:${s.toString().padStart(2, '0')}`
}

function localPlayerOrigin() {
  const url = new URL(window.location.href)
  if (url.hostname === '0.0.0.0' || url.hostname === '::' || url.hostname === '[::]') {
    url.hostname = '127.0.0.1'
  }
  return url.origin
}

function absoluteApiUrl(url: string) {
  return new URL(url, window.location.origin).toString()
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

async function fetchOffsetSubtitleBlob(baseUrl: string, offsetSeconds: number): Promise<string> {
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

function buildAssFontConfig(fonts: SubtitleFont[]) {
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

function isAssTrack(track: SubtitleTrack) {
  const codec = (track.codec || '').toLowerCase()
  const title = (track.title || '').toLowerCase()
  const name = (track.name || '').toLowerCase()
  return codec.includes('ass') || codec.includes('ssa') || title.endsWith('.ass') || title.endsWith('.ssa') || name.endsWith('.ass') || name.endsWith('.ssa')
}

function isTextTrack(track: SubtitleTrack) {
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

function subtitleLanguagePriority(track: SubtitleTrack) {
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

function trackLabel(track: SubtitleTrack) {
  if (track.source === 'external') {
    return track.name || track.title || track.codec || `Subtitle ${track.index}`
  }
  const source = '内嵌'
  const lang = track.language || '--'
  const title = track.title || track.codec || `Track ${track.index}`
  return `${source} ${lang} ${title}`
}

function sortSubtitleTracks(trackList: SubtitleTrack[]) {
  return [...trackList].filter(isTextTrack).sort((a, b) => {
    const sourceRank = (track: SubtitleTrack) => track.source === 'external' ? 0 : 1
    const bySource = sourceRank(a) - sourceRank(b)
    if (bySource) return bySource
    return a.index - b.index
  })
}

function getAssPlugin(art: Artplayer): AssPluginController | null {
  const plugin = art.plugins.artplayerPluginAss as AssPluginController | undefined
  return plugin || null
}

function htmlLabel(text: string) {
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

type GestureCleanup = () => void
type GestureHandler = (gesture: string) => void
type SeekPreviewHandler = (payload: { target: number; delta: number; duration: number } | null, commit?: boolean) => void

function bindGestureLayer(element: HTMLElement, isMobile: () => boolean, onGesture: GestureHandler, onSeekPreview: SeekPreviewHandler, getSeekState: () => { current: number; duration: number; playing: boolean; disabled: boolean }): GestureCleanup {
  let lastTap = { time: 0, x: 0, y: 0, zone: 'center' }
  let pointer = { id: -1, type: '', x: 0, y: 0, zone: 'center', down: false, longPressed: false }
  let seekGesture: null | { startX: number; startY: number; base: number; duration: number; playing: boolean; target: number } = null
  let timer = 0

  const zoneFor = (clientX: number) => {
    const rect = element.getBoundingClientRect()
    const x = clientX - rect.left
    if (x < rect.width / 3) return 'left'
    if (x > rect.width * 2 / 3) return 'right'
    return 'center'
  }
  const clearTimer = () => {
    window.clearTimeout(timer)
    timer = 0
  }
  const stopLongPress = () => {
    if (pointer.longPressed) {
      pointer.longPressed = false
      onGesture('speed-hold-end')
    }
  }
  const onPointerDown = (event: PointerEvent) => {
    if (event.pointerType === 'mouse' && event.button !== 0) return
    const zone = zoneFor(event.clientX)
    pointer = {
      id: event.pointerId,
      type: event.pointerType,
      x: event.clientX,
      y: event.clientY,
      zone,
      down: true,
      longPressed: false,
    }
    element.setPointerCapture?.(event.pointerId)
    clearTimer()
    const longPressEnabled = isMobile() || event.pointerType !== 'mouse' || zone !== 'center'
    if (longPressEnabled) {
      timer = window.setTimeout(() => {
        if (!pointer.down) return
        pointer.longPressed = true
        onGesture('speed-hold-start')
      }, 420)
    }
  }
  const onPointerMove = (event: PointerEvent) => {
    if (!pointer.down || pointer.id !== event.pointerId) return
    const dx = Math.abs(event.clientX - pointer.x)
    const dy = Math.abs(event.clientY - pointer.y)
    const touchLike = isMobile() || pointer.type !== 'mouse'
    if (touchLike && !pointer.longPressed) {
      if (seekGesture) {
        event.preventDefault()
        const rawDelta = event.clientX - seekGesture.startX
        const secondsPerPx = seekGesture.duration > 7200 ? 0.8 : seekGesture.duration > 3600 ? 0.5 : 0.3
        const delta = Math.round(rawDelta * secondsPerPx)
        const target = Math.max(0, Math.min(seekGesture.duration, seekGesture.base + delta))
        seekGesture.target = target
        onSeekPreview({ target, delta, duration: seekGesture.duration })
        return
      }
      if (dx > 20 && dx > dy * 1.35) {
        const state = getSeekState()
        if (!state.disabled && state.duration > 0 && isFinite(state.duration)) {
          clearTimer()
          seekGesture = {
            startX: pointer.x,
            startY: pointer.y,
            base: state.current,
            duration: state.duration,
            playing: state.playing,
            target: state.current,
          }
          event.preventDefault()
          onSeekPreview({ target: state.current, delta: 0, duration: state.duration })
          return
        }
      }
    }
    if ((dx > 28 || dy > 28) && !pointer.longPressed) clearTimer()
  }
  const onPointerUp = (event: PointerEvent) => {
    if (!pointer.down || pointer.id !== event.pointerId) return
    clearTimer()
    if (seekGesture) {
      const sg = seekGesture
      seekGesture = null
      pointer.down = false
      element.releasePointerCapture?.(event.pointerId)
      onSeekPreview({ target: sg.target, delta: Math.round(sg.target - sg.base), duration: sg.duration }, true)
      return
    }
    const state = pointer
    pointer.down = false
    element.releasePointerCapture?.(event.pointerId)
    if (state.longPressed) {
      stopLongPress()
      return
    }
    const dx = Math.abs(event.clientX - state.x)
    const dy = Math.abs(event.clientY - state.y)
    if (dx > 28 || dy > 28) return
    const touchLike = isMobile() || state.type !== 'mouse'
    if (!touchLike) {
      onGesture('tap')
      return
    }
    const now = Date.now()
    const samePlace = now - lastTap.time < 330
      && Math.abs(event.clientX - lastTap.x) < 28
      && Math.abs(event.clientY - lastTap.y) < 28
      && lastTap.zone === state.zone
    if (samePlace) {
      onGesture(`doubletap-${state.zone}`)
      lastTap = { time: 0, x: 0, y: 0, zone: state.zone }
      return
    }
    lastTap = { time: now, x: event.clientX, y: event.clientY, zone: state.zone }
  }
  const onPointerCancel = (event: PointerEvent) => {
    if (pointer.id !== event.pointerId) return
    clearTimer()
    pointer.down = false
    seekGesture = null
    onSeekPreview(null)
    stopLongPress()
  }

  element.addEventListener('pointerdown', onPointerDown)
  element.addEventListener('pointermove', onPointerMove)
  element.addEventListener('pointerup', onPointerUp)
  element.addEventListener('pointercancel', onPointerCancel)
  return () => {
    clearTimer()
    element.removeEventListener('pointerdown', onPointerDown)
    element.removeEventListener('pointermove', onPointerMove)
    element.removeEventListener('pointerup', onPointerUp)
    element.removeEventListener('pointercancel', onPointerCancel)
  }
}

type AmbientColor = { r: number; g: number; b: number } | null

const AMBIENT_SAMPLE_INTERVAL = 200
const AMBIENT_COLOR_THRESHOLD = 12

function useAmbientColor(
  artRef: { current: Artplayer | null },
  enabled: boolean,
): AmbientColor {
  const [color, setColor] = useState<AmbientColor>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const lastSampleAtRef = useRef(0)
  const lastColorRef = useRef({ r: 10, g: 10, b: 12 })
  const visibleRef = useRef(true)

  useEffect(() => {
    if (!enabled) {
      setColor(null)
      return
    }

    const handleVisibility = () => { visibleRef.current = !document.hidden }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [enabled])

  useEffect(() => {
    if (!enabled) return

    const sample = () => {
      if (!visibleRef.current) return
      const art = artRef.current
      const video = art?.video as HTMLVideoElement | undefined
      if (!video || video.paused || video.readyState < 2) return
      if (video.videoWidth === 0 || video.videoHeight === 0) return

      const now = Date.now()
      if (now - lastSampleAtRef.current < AMBIENT_SAMPLE_INTERVAL) return
      lastSampleAtRef.current = now

      try {
        if (!canvasRef.current) {
          canvasRef.current = document.createElement('canvas')
          canvasRef.current.width = 1
          canvasRef.current.height = 1
        }
        const ctx = canvasRef.current.getContext('2d', { willReadFrequently: true })
        if (!ctx) return
        ctx.drawImage(video, 0, 0, 1, 1)
        const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data
        const prev = lastColorRef.current
        if (
          Math.abs(r - prev.r) > AMBIENT_COLOR_THRESHOLD ||
          Math.abs(g - prev.g) > AMBIENT_COLOR_THRESHOLD ||
          Math.abs(b - prev.b) > AMBIENT_COLOR_THRESHOLD
        ) {
          const next = { r, g, b }
          lastColorRef.current = next
          setColor(next)
        }
      } catch {
        // cross-origin canvas pollution — silently skip
      }
    }

    let raf = 0
    const loop = () => { sample(); raf = requestAnimationFrame(loop) }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [enabled])

  return color
}

function usePlayerRect(
  wrapperRef: React.RefObject<HTMLDivElement | null>,
  enabled: boolean,
): DOMRect | null {
  const [rect, setRect] = useState<DOMRect | null>(null)

  useEffect(() => {
    if (!enabled) {
      setRect(null)
      return
    }
    const el = wrapperRef.current
    if (!el) return

    let raf = 0
    const update = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        setRect(el.getBoundingClientRect())
      })
    }

    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update, { passive: true })

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      window.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
    // wrapperRef is stable (from useRef)
  }, [enabled])

  return rect
}

export default function VideoPlayer({ src, poster, movieId, onWatched }: Props) {
  const artContainerRef = useRef<HTMLDivElement>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const artRef = useRef<Artplayer | null>(null)
  const gestureCleanupRef = useRef<GestureCleanup | null>(null)
  const watchedRef = useRef(false)
  const tracksRef = useRef<SubtitleTrack[]>([])
  const activeTrackRef = useRef(-1)
  const pendingAutoPlay = useRef(false)
  const loadSeekRef = useRef<number | null>(null)
  const useTranscodeRef = useRef(false)
  const transcodeStartRef = useRef(0)
  const currentTimeRef = useRef(0)
  const displayDurationRef = useRef(0)
  const playbackRateBeforeBoost = useRef(1)
  const keyHoldTimer = useRef(0)
  const keyBoosting = useRef(false)
  const isMobileRef = useRef(false)
  const streamSrcRef = useRef('')
  const currentAssModeRef = useRef(false)
  const subtitleVisibleRef = useRef(true)
  const artReadyRef = useRef(false)
  const mountedRef = useRef(true)
  const manualSubtitleOffRef = useRef(false)
  const subtitleTrackRequestRef = useRef(0)
  const subtitleSwitchRequestRef = useRef(0)
  const assPluginAddPromiseRef = useRef<Promise<unknown> | null>(null)
  const subtitleBlobUrlRef = useRef<string | null>(null)
  const resumeTimerRef = useRef(0)
  const progressSaveTimerRef = useRef(0)
  const lastProgressSaveAtRef = useRef(0)
  const switchUrlSeqRef = useRef(0)
  const lastPosSaveAtRef = useRef(0)

  const [resumePos, setResumePos] = useState(() => getSavedPos(movieId))
  const [showResume, setShowResume] = useState(() => false)
  const [seekOsd, setSeekOsd] = useState<{ target: number; delta: number; duration: number } | null>(null)
  const [tracks, setTracks] = useState<SubtitleTrack[]>([])
  const [activeTrack, setActiveTrack] = useState(-1)
  const [subtitleVisible, setSubtitleVisibleState] = useState(true)
  const [volume] = useState(() => loadJson('mediatree_vol', 1))
  const [useTranscode, setUseTranscodeState] = useState(false)
  const [transcodeMode, setTranscodeMode] = useState<'audio' | 'full'>('audio')
  const [transcodeStart, setTranscodeStartState] = useState(0)
  const [mediaDuration, setMediaDuration] = useState(0)
  const [videoError, setVideoError] = useState(false)
  const [linkCopied, setLinkCopied] = useState(false)
  const [unsupportedAudio, setUnsupportedAudio] = useState('')
  const [fontUrls, setFontUrls] = useState<string[]>(() => buildAssFontConfig([]).fonts)
  const [availableFonts, setAvailableFonts] = useState<Record<string, string>>(() => buildAssFontConfig([]).availableFonts)
  const [assFallbackFont, setAssFallbackFont] = useState(() => buildAssFontConfig([]).fallbackFont)
  const [artInstance, setArtInstance] = useState<Artplayer | null>(null)
  const [vrMode, setVrMode] = useState<VRMode>('off')
  const [videoAspect, setVideoAspect] = useState(16 / 9)
  const [ambientEnabled, setAmbientEnabled] = useState(() => getUiPrefs().ambientMode !== false)
  const streamUrl = useMemo(() => new URL(api.streamUrl(movieId), localPlayerOrigin()).toString(), [movieId])
  const streamSrc = useMemo(() => {
    if (!useTranscode) return src
    const sep = src.includes('?') ? '&' : '?'
    const mode = transcodeMode === 'full' ? 'full' : '1'
    return `${src}${sep}transcode=${mode}&start=${Math.max(0, transcodeStart).toFixed(3)}`
  }, [src, useTranscode, transcodeMode, transcodeStart])

  const displayDuration = mediaDuration || displayDurationRef.current
  const hasExternalSubtitles = tracks.some(t => t.source === 'external')
  const externalPlaylistUrl = new URL(api.externalPlaylistUrl(movieId), localPlayerOrigin()).toString()
  const localPlaybackUrl = hasExternalSubtitles ? externalPlaylistUrl : streamUrl
  const playerStyle = { '--mediatree-video-aspect': videoAspect } as CSSProperties

  const ambientColor = useAmbientColor(artRef, ambientEnabled && !useTranscode)
  const playerRect = usePlayerRect(wrapperRef, ambientEnabled)

  const toggleAmbient = useCallback(() => {
    setAmbientEnabled(prev => {
      const next = !prev
      const prefs = getUiPrefs()
      setUiPrefs({ ...prefs, ambientMode: next })
      return next
    })
  }, [])

  useEffect(() => {
    const el = document.getElementById('ambient-root')
    if (!el) return
    if (ambientColor && ambientEnabled) {
      el.style.setProperty('--ambient-r', String(ambientColor.r))
      el.style.setProperty('--ambient-g', String(ambientColor.g))
      el.style.setProperty('--ambient-b', String(ambientColor.b))
    } else {
      el.style.removeProperty('--ambient-r')
      el.style.removeProperty('--ambient-g')
      el.style.removeProperty('--ambient-b')
    }
  }, [ambientColor, ambientEnabled])

  const clearNativeSubtitle = useCallback((art: Artplayer) => {
    try { art.subtitle.show = false } catch {}
    try { art.template.$subtitle.innerHTML = '' } catch {}
    try {
      const track = art.template.$track as HTMLTrackElement | undefined
      if (track) {
        const oldSrc = track.src || ''
        if (oldSrc.startsWith('blob:')) URL.revokeObjectURL(oldSrc)
        track.removeAttribute('src')
        track.src = ''
        if (track.track) track.track.mode = 'disabled'
      }
    } catch (err) {
      console.warn('VideoPlayer: native subtitle cleanup failed', err)
    }
  }, [])

  const clearRenderedSubtitles = useCallback((art = artRef.current, cancelPending = true) => {
    if (cancelPending) subtitleSwitchRequestRef.current += 1
    if (!art) return
    try { getAssPlugin(art)?.clear() } catch (err) { console.warn('VideoPlayer: ASS subtitle cleanup failed', err) }
    try { art.emit('artplayer-plugin-ass:visible', false) } catch {}
    clearNativeSubtitle(art)
    currentAssModeRef.current = false
    if (subtitleBlobUrlRef.current) {
      URL.revokeObjectURL(subtitleBlobUrlRef.current)
      subtitleBlobUrlRef.current = null
    }
  }, [clearNativeSubtitle])

  useEffect(() => { useTranscodeRef.current = useTranscode }, [useTranscode])
  useEffect(() => { transcodeStartRef.current = transcodeStart }, [transcodeStart])
  useEffect(() => { displayDurationRef.current = mediaDuration || displayDurationRef.current }, [mediaDuration])
  useEffect(() => { tracksRef.current = tracks }, [tracks])
  useEffect(() => { activeTrackRef.current = activeTrack }, [activeTrack])
  useEffect(() => { subtitleVisibleRef.current = subtitleVisible }, [subtitleVisible])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      subtitleTrackRequestRef.current += 1
      subtitleSwitchRequestRef.current += 1
    }
  }, [])

  useEffect(() => {
    const saved = getSavedPos(movieId)
    setResumePos(saved)
    watchedRef.current = false
    subtitleTrackRequestRef.current += 1
    subtitleSwitchRequestRef.current += 1
    manualSubtitleOffRef.current = false
    artReadyRef.current = false
    tracksRef.current = []
    activeTrackRef.current = -1
    currentAssModeRef.current = false
    subtitleVisibleRef.current = true
    lastProgressSaveAtRef.current = 0
    lastPosSaveAtRef.current = 0
    setTracks([])
    setActiveTrack(-1)
    setSubtitleVisibleState(true)
    setShowResume(false)
    window.clearTimeout(resumeTimerRef.current)
    window.clearTimeout(progressSaveTimerRef.current)
    api.getProgress(movieId).then(progress => {
      const pos = Math.max(progress.position || 0, saved || 0)
      setResumePos(pos)
      const total = displayDurationRef.current || mediaDuration || 0
      const nearEnd = total > 0 && pos / total >= WATCHED_RATIO
      if (pos > 30 && !nearEnd) {
        setShowResume(true)
        resumeTimerRef.current = window.setTimeout(() => setShowResume(false), 5000)
      }
    }).catch(() => {
      if (saved > 30) {
        setShowResume(true)
        resumeTimerRef.current = window.setTimeout(() => setShowResume(false), 5000)
      }
    })
    try {
      const savedVr = localStorage.getItem(`mediatree_vr_${movieId}`) as VRMode | null
      setVrMode(savedVr && savedVr !== 'off' ? savedVr : 'off')
    } catch {
      setVrMode('off')
    }
    return () => {
      window.clearTimeout(resumeTimerRef.current)
      window.clearTimeout(progressSaveTimerRef.current)
    }
  }, [movieId])

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 640px), (pointer: coarse)')
    const update = () => { isMobileRef.current = mq.matches }
    update()
    mq.addEventListener?.('change', update)
    return () => mq.removeEventListener?.('change', update)
  }, [])

  useEffect(() => {
    api.mediaInfo(movieId).then(info => {
      if (info.duration && isFinite(info.duration)) {
        displayDurationRef.current = info.duration
        setMediaDuration(info.duration)
      }
      const audioCodec = (info.audio_codec || '').toLowerCase()
      setUnsupportedAudio(BROWSER_UNSUPPORTED_AUDIO.has(audioCodec) ? (info.audio_codec || 'unknown') : '')
    }).catch(() => {})
  }, [movieId])

  useEffect(() => {
    const initialConfig = buildAssFontConfig([])
    setFontUrls(initialConfig.fonts)
    setAvailableFonts(initialConfig.availableFonts)
    setAssFallbackFont(initialConfig.fallbackFont)
    let cancelled = false
    api.subtitleFonts().then(({ fonts }) => {
      if (cancelled) return
      const config = buildAssFontConfig(fonts)
      setFontUrls(config.fonts)
      setAvailableFonts(config.availableFonts)
      setAssFallbackFont(config.fallbackFont)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [])

  function chooseDefaultTrack(trackList: SubtitleTrack[]) {
    const sorted = sortSubtitleTracks(trackList)
    const external = sorted.filter(track => track.source === 'external' || track.is_external)
    const pool = external.length > 0 ? external : sorted
    return [...pool].sort((a, b) => {
      const byLanguage = subtitleLanguagePriority(a) - subtitleLanguagePriority(b)
      if (byLanguage) return byLanguage
      return sorted.indexOf(a) - sorted.indexOf(b)
    })[0]
  }

  useEffect(() => {
    const requestId = ++subtitleTrackRequestRef.current
    const abortController = new AbortController()
    api.subtitleTracks(movieId, abortController.signal)
      .then(trackList => {
        if (!mountedRef.current || requestId !== subtitleTrackRequestRef.current) return
        if (import.meta.env.DEV) console.info('VideoPlayer: subtitle tracks loaded', {
          movieId,
          total: trackList.length,
          external: trackList.filter(track => track.source === 'external' || track.is_external).length,
        })
        tracksRef.current = trackList
        setTracks(trackList)
        const selected = manualSubtitleOffRef.current ? undefined : chooseDefaultTrack(trackList)
        const selectedIndex = selected?.index ?? -1
        activeTrackRef.current = selectedIndex
        setActiveTrack(selectedIndex)
        const art = artRef.current
        if (art) art.setting.update(buildSubtitleSetting(trackList, selectedIndex))
        if (selectedIndex >= 0) {
          if (import.meta.env.DEV) console.info('VideoPlayer: selected default subtitle', {
            movieId,
            index: selectedIndex,
            language: selected?.language,
            format: selected?.format || selected?.codec,
            title: trackLabel(selected as SubtitleTrack),
          })
          applyActiveSubtitle(selectedIndex, trackList)
        } else if (artReadyRef.current) {
          clearRenderedSubtitles()
        }
      })
      .catch(err => {
        if (err?.name === 'AbortError') return
        console.error('VideoPlayer: track fetch error', err)
      })
    return () => {
      subtitleTrackRequestRef.current += 1
      abortController.abort()
    }
  }, [movieId])

  const notice = useCallback((message: string) => {
    const art = artRef.current
    if (art) art.notice.show = message
  }, [])

  const hideResumePrompt = useCallback(() => {
    window.clearTimeout(resumeTimerRef.current)
    setShowResume(false)
  }, [])

  const seekToTime = useCallback((time: number) => {
    const art = artRef.current
    if (!art) return
    const total = displayDurationRef.current || art.duration || 0
    const target = Math.max(0, total ? Math.min(total, time) : time)
    if (useTranscodeRef.current) {
      pendingAutoPlay.current = art.playing
      loadSeekRef.current = target
      currentTimeRef.current = target
      setTranscodeStartState(target)
    } else {
      art.currentTime = target
    }
    hideResumePrompt()
  }, [hideResumePrompt])

  const skipBack = useCallback((seconds: number) => {
    const art = artRef.current
    const base = useTranscodeRef.current ? currentTimeRef.current : (art?.currentTime || 0)
    seekToTime(Math.max(0, base - seconds))
    notice(`快退 ${seconds}s`)
  }, [notice, seekToTime])

  const skipForward = useCallback((seconds: number) => {
    const art = artRef.current
    const base = useTranscodeRef.current ? currentTimeRef.current : (art?.currentTime || 0)
    seekToTime(base + seconds)
    notice(`快进 ${seconds}s`)
  }, [notice, seekToTime])

  const togglePlay = useCallback(() => {
    const art = artRef.current
    if (!art) return
    art.toggle()
    notice(art.playing ? '播放' : '暂停')
  }, [notice])

  const startSpeedHold = useCallback(() => {
    const art = artRef.current
    if (!art || keyBoosting.current) return
    keyBoosting.current = true
    playbackRateBeforeBoost.current = art.playbackRate || 1
    art.playbackRate = 2
    if (!art.playing) art.play().catch(() => {})
    notice('2x')
  }, [notice])

  const stopSpeedHold = useCallback(() => {
    const art = artRef.current
    if (!art || !keyBoosting.current) return
    keyBoosting.current = false
    art.playbackRate = playbackRateBeforeBoost.current || 1
    notice(`${playbackRateBeforeBoost.current || 1}x`)
  }, [notice])

  const handleGesture = useCallback((gesture: string) => {
    switch (gesture) {
      case 'tap':
      case 'doubletap-center':
        togglePlay()
        break
      case 'doubletap-left':
        skipBack(SEEK_SMALL)
        break
      case 'doubletap-right':
        skipForward(SEEK_SMALL)
        break
      case 'speed-hold-start':
        startSpeedHold()
        break
      case 'speed-hold-end':
        stopSpeedHold()
        break
      default:
        break
    }
  }, [skipBack, skipForward, startSpeedHold, stopSpeedHold, togglePlay])

  const handleSeekPreview = useCallback((payload: { target: number; delta: number; duration: number } | null, commit?: boolean) => {
    if (!payload) {
      setSeekOsd(null)
      return
    }
    setSeekOsd(payload)
    hideResumePrompt()
    if (commit) {
      const wasPlaying = artRef.current?.playing
      seekToTime(payload.target)
      window.setTimeout(() => {
        if (wasPlaying) artRef.current?.play().catch(() => {})
      }, 0)
      window.setTimeout(() => setSeekOsd(null), 450)
    }
  }, [hideResumePrompt, seekToTime])

  const getSeekState = useCallback(() => {
    const art = artRef.current
    const duration = displayDurationRef.current || art?.duration || 0
    return {
      current: useTranscodeRef.current ? currentTimeRef.current : (art?.currentTime || 0),
      duration,
      playing: !!art?.playing,
      disabled: useTranscodeRef.current || !duration || !isFinite(duration),
    }
  }, [])

  const setTranscode = useCallback((enabled: boolean, mode: 'audio' | 'full' = 'audio') => {
    const art = artRef.current
    const target = currentTimeRef.current || art?.currentTime || 0
    pendingAutoPlay.current = !!art?.playing
    loadSeekRef.current = target
    if (art && enabled !== useTranscodeRef.current) {
      art.pause()
      art.reset()
    }
    setVideoError(false)
    setTranscodeMode(mode)
    setTranscodeStartState(enabled ? target : 0)
    setUseTranscodeState(enabled)
  }, [])

  const startTranscode = useCallback((mode: 'audio' | 'full' = 'audio') => {
    pendingAutoPlay.current = true
    setTranscode(true, mode)
  }, [setTranscode])

  const setVr = useCallback((mode: VRMode) => {
    setVrMode(mode)
    try { localStorage.setItem(`mediatree_vr_${movieId}`, mode) } catch {}
  }, [movieId])

  const copyStreamUrl = useCallback(async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(localPlaybackUrl)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = localPlaybackUrl
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.focus()
        textarea.select()
        document.execCommand('copy')
        textarea.remove()
      }
      setLinkCopied(true)
      setTimeout(() => setLinkCopied(false), 2000)
    } catch (err) {
      console.error('Copy stream url failed', err)
    }
  }, [localPlaybackUrl])

  const openMpv = useCallback(() => {
    const ua = navigator.userAgent || ''
    const href = /Android/i.test(ua)
      ? `intent:${localPlaybackUrl}#Intent;action=android.intent.action.VIEW;type=video/*;package=is.xyz.mpv;end`
      : `mpv://play/${encodeURIComponent(localPlaybackUrl)}`
    window.location.href = href
  }, [localPlaybackUrl])

  const setSubtitleVisible = useCallback((visible: boolean, art = artRef.current, manual = false) => {
    subtitleVisibleRef.current = visible
    setSubtitleVisibleState(visible)
    if (manual) manualSubtitleOffRef.current = !visible
    if (!art) return
    if (!visible) {
      clearRenderedSubtitles(art)
      return
    }
    manualSubtitleOffRef.current = false
    if (currentAssModeRef.current) {
      art.subtitle.show = false
      getAssPlugin(art)?.setVisible(visible)
      art.emit('artplayer-plugin-ass:visible', visible)
    } else {
      art.subtitle.show = visible
    }
  }, [clearRenderedSubtitles])

  const activateSubtitleTrack = useCallback(async (art: Artplayer, track: SubtitleTrack) => {
    const requestId = ++subtitleSwitchRequestRef.current
    const label = trackLabel(track)
    const url = absoluteApiUrl(track.url || api.subtitleUrl(movieId, track.index))
    const isCurrentRequest = () => (
      mountedRef.current
      && artRef.current === art
      && !art.isDestroy
      && artReadyRef.current
      && subtitleSwitchRequestRef.current === requestId
      && activeTrackRef.current === track.index
    )
    if (import.meta.env.DEV) console.info('VideoPlayer: switching subtitle', {
      movieId,
      index: track.index,
      format: track.format || track.codec,
      language: track.language,
      source: track.source || (track.is_external ? 'external' : 'embedded'),
    })
    setActiveTrack(track.index)
    activeTrackRef.current = track.index
    manualSubtitleOffRef.current = false
    if (!artReadyRef.current) return label

    if (isAssTrack(track)) {
      try {
        clearNativeSubtitle(art)
        let plugin = getAssPlugin(art)
        if (!plugin) {
          if (!assPluginAddPromiseRef.current) {
            assPluginAddPromiseRef.current = art.plugins.add(artplayerPluginAss({
              fonts: fontUrls,
              availableFonts,
              fallbackFont: assFallbackFont,
              timeOffset: useTranscodeRef.current ? transcodeStartRef.current : 0,
            })).finally(() => {
              assPluginAddPromiseRef.current = null
            })
          }
          await assPluginAddPromiseRef.current
          plugin = getAssPlugin(art)
        }
        if (!plugin || !isCurrentRequest()) return label
        await plugin.switch(url, {
          fonts: fontUrls,
          availableFonts,
          fallbackFont: assFallbackFont,
          timeOffset: useTranscodeRef.current ? transcodeStartRef.current : 0,
        })
        if (!isCurrentRequest()) {
          plugin.clear()
          return label
        }
        currentAssModeRef.current = true
        art.subtitle.show = false
        art.emit('subtitleOffset', useTranscodeRef.current ? transcodeStartRef.current : 0)
        plugin.setVisible(subtitleVisibleRef.current)
        if (import.meta.env.DEV) console.info('VideoPlayer: ASS subtitle switch complete', { movieId, index: track.index })
        return label
      } catch (assError) {
        if (import.meta.env.DEV) console.warn('VideoPlayer: ASS plugin failed, falling back to native subtitle', {
          movieId, index: track.index, error: assError,
        })
        // Fall through to native subtitle rendering below
      }
    }

    currentAssModeRef.current = false
    getAssPlugin(art)?.clear()
    art.emit('artplayer-plugin-ass:visible', false)
    clearNativeSubtitle(art)

    let subtitleUrl = url
    let subtitleType = 'vtt'
    const offset = useTranscodeRef.current ? transcodeStartRef.current : 0
    if (offset > 0 && !isAssTrack(track)) {
      try {
        if (subtitleBlobUrlRef.current) {
          URL.revokeObjectURL(subtitleBlobUrlRef.current)
          subtitleBlobUrlRef.current = null
        }
        const blobUrl = await fetchOffsetSubtitleBlob(url, offset)
        if (isCurrentRequest()) {
          subtitleUrl = blobUrl
          subtitleBlobUrlRef.current = blobUrl
        } else {
          URL.revokeObjectURL(blobUrl)
          return label
        }
      } catch (offsetErr) {
        console.warn('VideoPlayer: subtitle offset fetch failed, using original timestamps', offsetErr)
      }
    }

    await art.subtitle.switch(subtitleUrl, {
      name: label,
      type: subtitleType,
      encoding: 'utf-8',
      style: {
        color: '#fff',
        fontSize: isMobileRef.current ? '18px' : '26px',
        textShadow: '0 2px 4px #000, 0 0 2px #000',
      },
    })
    if (!isCurrentRequest()) {
      clearNativeSubtitle(art)
      return label
    }
    art.subtitle.show = subtitleVisibleRef.current
    if (import.meta.env.DEV) console.info('VideoPlayer: ArtPlayer subtitle switch complete', { movieId, index: track.index, url })
    return label
  }, [availableFonts, assFallbackFont, clearNativeSubtitle, fontUrls, movieId])

  const buildSubtitleSetting = useCallback((trackList: SubtitleTrack[], selectedIndex: number): Setting => {
    const textTracks = sortSubtitleTracks(trackList)
    const selectedTrack = textTracks.find(track => track.index === selectedIndex)
    const visible = subtitleVisibleRef.current
    const tooltip = selectedTrack ? (visible ? trackLabel(selectedTrack) : '隐藏') : '关闭'

    const innerMenu: Setting[] = [
      {
        html: '显示字幕',
        name: 'setting_subtitle_display',
        tooltip: visible && selectedTrack ? '开' : '关',
        switch: visible && Boolean(selectedTrack),
        onSwitch: function (item: SettingOption) {
          const nextVisible = !item.switch
          item.tooltip = nextVisible ? '开' : '关'
          if (nextVisible) {
            manualSubtitleOffRef.current = false
            subtitleVisibleRef.current = true
            setSubtitleVisibleState(true)
            const target = textTracks.find(track => track.index === activeTrackRef.current) || chooseDefaultTrack(textTracks)
            if (target) {
              activeTrackRef.current = target.index
              setActiveTrack(target.index)
              activateSubtitleTrack(this, target).catch(err => console.error('VideoPlayer: subtitle activation failed', err))
            } else {
              setSubtitleVisible(true, this)
            }
          } else {
            manualSubtitleOffRef.current = true
            setSubtitleVisible(false, this, true)
          }
          const menu = this.setting.find('setting_subtitle')
          const tooltipTrack = textTracks.find(track => track.index === activeTrackRef.current) || chooseDefaultTrack(textTracks)
          if (menu) menu.tooltip = nextVisible ? (tooltipTrack ? trackLabel(tooltipTrack) : '开') : '关闭'
          return nextVisible
        },
      },
      {
        html: '无字幕',
        name: 'subtitle-off',
        default: selectedIndex < 0,
      },
    ]

    for (const track of textTracks) {
      const label = trackLabel(track)
      const subtitleUrl = absoluteApiUrl(api.subtitleUrl(movieId, track.index))
      innerMenu.push({
        html: htmlLabel(label),
        name: `subtitle-${track.index}`,
        url: subtitleUrl,
        track,
        default: track.index === selectedIndex,
      })
    }

    return {
      html: '字幕',
      name: 'setting_subtitle',
      tooltip,
      selector: innerMenu,
      onSelect: async function (item: SettingOption) {
        if (item.name === 'setting_subtitle_display') return item.tooltip
        if (item.name === 'subtitle-off') {
          manualSubtitleOffRef.current = true
          activeTrackRef.current = -1
          setActiveTrack(-1)
          currentAssModeRef.current = false
          setSubtitleVisible(false, this, true)
          return '关'
        }
        const selectedTrack = item.track as SubtitleTrack | undefined
        if (!selectedTrack) return item.tooltip
        manualSubtitleOffRef.current = false
        subtitleVisibleRef.current = true
        setSubtitleVisibleState(true)
        const label = await activateSubtitleTrack(this, selectedTrack)
        const switcher = innerMenu.find(item => item.name === 'setting_subtitle_display')
        if (switcher) {
          switcher.switch = true
          switcher.tooltip = '开'
        }
        return label
      },
    }
  }, [activateSubtitleTrack, movieId, setSubtitleVisible])

  const applyActiveSubtitle = useCallback((index: number, trackList = tracksRef.current) => {
    const art = artRef.current
    if (!art) return
    const resolvedIndex = index >= 0 ? index : -1
    activeTrackRef.current = resolvedIndex
    setActiveTrack(resolvedIndex)
    art.setting.update(buildSubtitleSetting(trackList, resolvedIndex))
    if (!artReadyRef.current) return
    if (manualSubtitleOffRef.current) {
      clearRenderedSubtitles(art)
      return
    }
    const track = trackList.find(track => track.index === resolvedIndex && isTextTrack(track))
    if (!track) {
      clearRenderedSubtitles(art)
      return
    }
    activateSubtitleTrack(art, track).then(label => {
      if (!mountedRef.current || activeTrackRef.current !== track.index) return
      art.setting.update(buildSubtitleSetting(trackList, track.index))
      const menu = art.setting.find('setting_subtitle')
      if (menu) menu.tooltip = subtitleVisibleRef.current ? label : '隐藏'
    }).catch(err => console.error('VideoPlayer: subtitle activation failed', err))
  }, [activateSubtitleTrack, buildSubtitleSetting, clearRenderedSubtitles])

  useEffect(() => {
    if (!artContainerRef.current) return
    const option: Option = {
      container: artContainerRef.current,
      url: streamSrc,
      poster: poster || '',
      volume,
      autoplay: false,
      autoSize: false,
      autoMini: false,
      loop: false,
      flip: true,
      playbackRate: true,
      aspectRatio: true,
      screenshot: true,
      setting: true,
      hotkey: false,
      pip: true,
      mutex: true,
      fullscreen: true,
      fullscreenWeb: true,
      subtitleOffset: true,
      miniProgressBar: true,
      playsInline: true,
      lock: true,
      gesture: false,
      fastForward: false,
      autoOrientation: true,
      airplay: true,
      theme: '#00a4dc',
      subtitle: {
        url: '',
        type: 'vtt',
        style: {
          color: '#fff',
          fontSize: '26px',
          textShadow: '0 2px 4px #000, 0 0 2px #000',
        },
      },
      layers: [
        {
          name: 'mediatree-gesture',
          html: '<div class="mediatree-art-gesture-layer"></div>',
          mounted: (layer) => {
            const target = layer.firstElementChild as HTMLElement | null
            if (target) {
              gestureCleanupRef.current?.()
              gestureCleanupRef.current = bindGestureLayer(target, () => isMobileRef.current, handleGesture, handleSeekPreview, getSeekState)
            }
          },
        },
      ],
      settings: [
        {
          html: '转码',
          name: 'setting_transcode',
          tooltip: '关',
          selector: [
            {
              html: '关闭',
              name: 'transcode-off',
              default: true,
              onSelect: function () {
                setTranscode(false)
                return '关'
              },
            },
            {
              html: '音频转码',
              name: 'transcode-audio',
              onSelect: function () {
                startTranscode('audio')
                return '音频'
              },
            },
            {
              html: '完整转码',
              name: 'transcode-full',
              onSelect: function () {
                startTranscode('full')
                return '完整'
              },
            },
          ],
        },
        buildSubtitleSetting(tracksRef.current, activeTrackRef.current),
        {
          html: 'VR',
          name: 'setting_vr',
          tooltip: vrMode === 'off' ? '关' : vrMode,
          selector: [
            { html: '关闭', name: 'vr-off', default: vrMode === 'off', onSelect: function () { setVr('off'); return '关' } },
            { html: '360°', name: 'vr-360', default: vrMode === '360', onSelect: function () { setVr('360'); return '360°' } },
            { html: '180°', name: 'vr-180', default: vrMode === '180', onSelect: function () { setVr('180'); return '180°' } },
            { html: 'SBS 360°', name: 'vr-sbs360', default: vrMode === 'sbs360', onSelect: function () { setVr('sbs360'); return 'SBS 360°' } },
            { html: 'TB 360°', name: 'vr-tb360', default: vrMode === 'tb360', onSelect: function () { setVr('tb360'); return 'TB 360°' } },
            { html: 'SBS 180°', name: 'vr-sbs180', default: vrMode === 'sbs180', onSelect: function () { setVr('sbs180'); return 'SBS 180°' } },
            { html: 'TB 180°', name: 'vr-tb180', default: vrMode === 'tb180', onSelect: function () { setVr('tb180'); return 'TB 180°' } },
          ],
        },
      ],
      moreVideoAttr: {
        preload: 'metadata',
        crossOrigin: 'anonymous',
        playsInline: true,
      },
    }

    const art = new Artplayer(option)
    artRef.current = art
    setArtInstance(art)
    streamSrcRef.current = streamSrc

    art.on('ready', () => {
      artReadyRef.current = true
      if (!useTranscodeRef.current && resumePos > 5) {
        art.currentTime = resumePos
      }
      applyActiveSubtitle(activeTrackRef.current)
    })
    art.on('video:loadedmetadata', () => {
      const video = art.video
      const naturalWidth = video?.videoWidth || 0
      const naturalHeight = video?.videoHeight || 0
      if (naturalWidth > 0 && naturalHeight > 0) {
        setVideoAspect(Math.max(4 / 5, Math.min(21 / 9, naturalWidth / naturalHeight)))
      }
      const loadedDuration = isFinite(art.duration) && art.duration > 0 ? art.duration : 0
      const total = useTranscodeRef.current ? (displayDurationRef.current || loadedDuration) : loadedDuration
      if (total) {
        displayDurationRef.current = total
        setMediaDuration(prev => prev || total)
        if (resumePos > 0 && resumePos / total >= WATCHED_RATIO) hideResumePrompt()
      }
      if (useTranscodeRef.current) {
        currentTimeRef.current = transcodeStartRef.current
        if (pendingAutoPlay.current) {
          pendingAutoPlay.current = false
          art.play().catch(() => {})
        }
      } else {
        const target = loadSeekRef.current ?? resumePos
        if (target > 5) art.currentTime = target
        loadSeekRef.current = null
      }
    })
    art.on('video:timeupdate', () => {
      const virtualTime = useTranscodeRef.current ? transcodeStartRef.current + art.currentTime : art.currentTime
      currentTimeRef.current = virtualTime
      const now = Date.now()
      if (virtualTime > 3 && (!lastPosSaveAtRef.current || now - lastPosSaveAtRef.current >= POS_SAVE_INTERVAL)) {
        lastPosSaveAtRef.current = now
        savePos(movieId, virtualTime)
      }
      hideResumePrompt()
      if (virtualTime > 0 && (!lastProgressSaveAtRef.current || now - lastProgressSaveAtRef.current >= 15000)) {
        lastProgressSaveAtRef.current = now
        api.saveProgress(movieId, virtualTime, displayDurationRef.current || art.duration || undefined).catch(err => {
          console.error('VideoPlayer: progress save failed', err)
        })
      }
      const total = displayDurationRef.current || art.duration || 0
      if (!watchedRef.current && total > 0 && virtualTime / total >= WATCHED_RATIO) {
        watchedRef.current = true
        api.saveProgress(movieId, virtualTime, total, true).catch(() => {})
        onWatched?.()
      }
    })
    art.on('video:play', hideResumePrompt)
    art.on('video:pause', () => {
      const pos = currentTimeRef.current || art.currentTime || 0
      savePos(movieId, pos)
      api.saveProgress(movieId, pos, displayDurationRef.current || art.duration || undefined, true).catch(() => {})
    })
    art.on('video:ended', () => {
      savePos(movieId, 0)
      api.saveProgress(movieId, displayDurationRef.current || art.duration || currentTimeRef.current, displayDurationRef.current || art.duration || undefined, true).catch(() => {})
      onWatched?.()
    })
    art.on('video:volumechange', () => {
      if (!art.muted) saveJson('mediatree_vol', art.volume)
    })
    art.on('video:error', () => setVideoError(true))
    art.on('seek', (_currentTime, requestedTime) => {
      if (!useTranscodeRef.current) return
      const virtualNow = currentTimeRef.current
      if (Math.abs(requestedTime - virtualNow) > 2) {
        pendingAutoPlay.current = art.playing
        loadSeekRef.current = requestedTime
        setTranscodeStartState(requestedTime)
      }
    })

    return () => {
      const pos = currentTimeRef.current || art.currentTime || 0
      const total = displayDurationRef.current || art.duration || undefined
      if (pos > 0) {
        api.saveProgress(movieId, pos, total, true).catch(err => {
          console.error('VideoPlayer: final progress save failed', err)
        })
      }
      if (import.meta.env.DEV) console.info('VideoPlayer cleanup: destroying ArtPlayer and subtitle resources')
      artReadyRef.current = false
      subtitleSwitchRequestRef.current += 1
      window.clearTimeout(progressSaveTimerRef.current)
      window.clearTimeout(resumeTimerRef.current)
      window.clearTimeout(keyHoldTimer.current)
      gestureCleanupRef.current?.()
      gestureCleanupRef.current = null
      clearRenderedSubtitles(art)
      try { art.emit('artplayer-plugin-ass:destroy') } catch {}
      try { art.pause() } catch {}
      try { art.destroy() } catch (err) { console.warn('VideoPlayer: ArtPlayer destroy failed', err) }
      try {
        artContainerRef.current?.querySelectorAll('.artplayer-plugin-ass, .JASSUB, canvas[data-mediatree-subtitle="ass"]').forEach(node => node.remove())
      } catch {}
      document.body.classList.remove('artplayer-fullscreen-web', 'art-fullscreen-web')
      document.documentElement.classList.remove('artplayer-fullscreen-web', 'art-fullscreen-web')
      document.body.style.overflow = ''
      document.documentElement.style.overflow = ''
      document.body.style.touchAction = ''
      document.documentElement.style.touchAction = ''
      artRef.current = null
      setArtInstance(null)
    }
  }, [movieId])

  useEffect(() => {
    const art = artRef.current
    if (!art || streamSrcRef.current === streamSrc) return
    const seq = ++switchUrlSeqRef.current
    const wasPlaying = pendingAutoPlay.current || art.playing
    streamSrcRef.current = streamSrc
    setVideoError(false)
    clearRenderedSubtitles(art)
    art.pause()
    art.switchUrl(streamSrc).then(() => {
      if (switchUrlSeqRef.current !== seq) return
      try {
        art.emit('subtitleOffset', useTranscodeRef.current ? transcodeStartRef.current : 0)
        applyActiveSubtitle(activeTrackRef.current)
      } catch (err) {
        console.error('VideoPlayer: subtitle reload after source switch failed', err)
      }
      if (wasPlaying) art.play().catch(() => {})
    }).catch(err => {
      if (switchUrlSeqRef.current !== seq) return
      console.error('ArtPlayer switchUrl failed', err)
      setVideoError(true)
    })
  }, [streamSrc])

  useEffect(() => {
    const art = artRef.current
    if (!art || !artReadyRef.current || manualSubtitleOffRef.current) return
    const track = tracksRef.current.find(track => track.index === activeTrackRef.current)
    if (track && isAssTrack(track)) applyActiveSubtitle(track.index)
  }, [fontUrls, availableFonts, assFallbackFont])

  useEffect(() => {
    const art = artRef.current
    if (!art) return
    const item = art.setting.find('setting_vr')
    if (item) {
      item.tooltip = vrMode === 'off' ? '关' : vrMode
      art.setting.update(item)
    }
  }, [vrMode])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const art = artRef.current
      if (!art) return
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return
      switch (event.key) {
        case ' ':
        case 'k':
          event.preventDefault()
          togglePlay()
          break
        case 'ArrowLeft':
          event.preventDefault()
          if (!event.repeat) {
            skipBack(SEEK_SMALL)
            clearTimeout(keyHoldTimer.current)
            keyHoldTimer.current = window.setTimeout(startSpeedHold, 380)
          }
          break
        case 'ArrowRight':
          event.preventDefault()
          if (!event.repeat) {
            skipForward(SEEK_SMALL)
            clearTimeout(keyHoldTimer.current)
            keyHoldTimer.current = window.setTimeout(startSpeedHold, 380)
          }
          break
        case 'ArrowUp':
          event.preventDefault()
          art.volume = Math.min(1, art.volume + 0.05)
          break
        case 'ArrowDown':
          event.preventDefault()
          art.volume = Math.max(0, art.volume - 0.05)
          break
        case 'f':
          event.preventDefault()
          art.fullscreen = !art.fullscreen
          break
        case 'm':
          event.preventDefault()
          art.muted = !art.muted
          break
        default:
          break
      }
    }
    const onKeyUp = (event: KeyboardEvent) => {
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        clearTimeout(keyHoldTimer.current)
        stopSpeedHold()
      }
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('keyup', onKeyUp)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('keyup', onKeyUp)
      clearTimeout(keyHoldTimer.current)
    }
  }, [skipBack, skipForward, startSpeedHold, stopSpeedHold, togglePlay])

  function handleResume() {
    const art = artRef.current
    if (!art) return
    if (useTranscodeRef.current) {
      pendingAutoPlay.current = true
      setTranscodeStartState(resumePos)
    } else {
      art.currentTime = resumePos
      art.play().catch(() => {})
    }
    hideResumePrompt()
  }

  return (
    <>
      {ambientEnabled && playerRect && createPortal(
        <div
          className="ambient-glow"
          style={{
            left: playerRect.left + playerRect.width / 2,
            top: playerRect.top + playerRect.height / 2,
            width: playerRect.width * 3,
            height: playerRect.height * 3,
          }}
        />,
        document.getElementById('ambient-root')!,
      )}
      <div ref={wrapperRef} className="relative mx-auto w-full max-w-[calc((100vh-11rem)*var(--mediatree-video-aspect))] transition-all duration-300" style={playerStyle}>
        <div className="relative z-[1] overflow-hidden rounded-3xl border border-white/10 bg-black shadow-glass">
        <div ref={artContainerRef} className="mediatree-artplayer w-full" />
        <VRVideoLayer art={artInstance} mode={vrMode} />

        {seekOsd && (
          <div className="glass-popover absolute left-1/2 top-1/2 z-40 -translate-x-1/2 -translate-y-1/2 px-4 py-2 text-sm font-semibold text-white">
            {seekOsd.delta >= 0 ? '+' : '-'}{fmt(Math.abs(seekOsd.delta))} &nbsp; {fmt(seekOsd.target)} / {fmt(seekOsd.duration)}
          </div>
        )}

        {showResume && (
          <div className="absolute bottom-[20%] left-1/2 z-30 flex -translate-x-1/2 items-center overflow-hidden rounded-full border border-apple-blue/35 bg-apple-blue/75 text-sm font-semibold text-white shadow-glow backdrop-blur-2xl">
            <button onClick={handleResume} className="px-5 py-3 transition-all hover:bg-white/10">
              从上次位置继续 ({fmt(resumePos)})
            </button>
            <button onClick={hideResumePrompt} className="border-l border-white/20 px-3 py-3 text-white/80 hover:bg-white/10" aria-label="关闭继续播放提示">
              ×
            </button>
          </div>
        )}

        {unsupportedAudio && !useTranscode && !videoError && (
          <div className="absolute left-3 right-3 top-3 z-30 rounded-2xl border border-amber-400/25 bg-black/55 px-3 py-2 shadow-glass backdrop-blur-2xl">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="text-xs font-medium text-amber-200">当前音频编码 {unsupportedAudio.toUpperCase()} 可能无声</p>
                <p className="mt-0.5 text-[11px] text-gray-400">直传不会占用转码资源；需要声音时再手动开启音频转码或外部播放器。</p>
              </div>
              <div className="flex shrink-0 gap-1.5">
                <button onClick={() => startTranscode('audio')} className="rounded-full border border-amber-400/30 bg-amber-500/20 px-2.5 py-1 text-xs text-amber-100 transition-all hover:bg-amber-500/30">
                  音频转码
                </button>
                <button onClick={openMpv} className="rounded-full border border-white/10 bg-white/[0.08] px-2.5 py-1 text-xs text-gray-200 transition-all hover:bg-white/[0.14] hover:text-white">
                  MPV
                </button>
              </div>
            </div>
          </div>
        )}

        {videoError && (
          <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/70 p-4 backdrop-blur-xl">
            <div className="glass-modal max-w-sm p-5 text-center">
              <p className="mb-2 font-semibold text-white">该视频解码失败</p>
              <p className="mb-4 text-xs text-gray-400">浏览器不支持此视频的音视频编码</p>
              <div className="flex flex-col justify-center gap-2 sm:flex-row">
                <button onClick={() => startTranscode('audio')} className="glass-button-primary px-4 py-2 text-sm">
                  音频转码播放
                </button>
                <button onClick={() => startTranscode('full')} className="glass-button px-4 py-2 text-sm">
                  完整转码
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="mt-2 flex items-center gap-2 overflow-x-auto pb-1">
        <span className="shrink-0 text-[11px] text-gray-500">本地播放:</span>
        <a href={`iina://weblink?url=${encodeURIComponent(localPlaybackUrl)}`} target="_blank" rel="noopener noreferrer" className="shrink-0 rounded-full border border-white/10 bg-white/[0.08] px-2.5 py-1 text-xs text-gray-300 backdrop-blur-xl transition-all hover:bg-white/[0.14] hover:text-white">
          IINA
        </a>
        <button onClick={openMpv} className="shrink-0 rounded-full border border-white/10 bg-white/[0.08] px-2.5 py-1 text-xs text-gray-300 backdrop-blur-xl transition-all hover:bg-white/[0.14] hover:text-white">
          MPV
        </button>
        <button onClick={copyStreamUrl} className="shrink-0 rounded-full border border-white/10 bg-white/[0.08] px-2.5 py-1 text-xs text-gray-300 backdrop-blur-xl transition-all hover:bg-white/[0.14] hover:text-white">
          {linkCopied ? '已复制' : '复制链接'}
        </button>
        {hasExternalSubtitles && (
          <a href={externalPlaylistUrl} className="shrink-0 rounded-full border border-white/10 bg-white/[0.08] px-2.5 py-1 text-xs text-gray-300 backdrop-blur-xl transition-all hover:bg-white/[0.14] hover:text-white">
            字幕播放列表
          </a>
        )}
        <button onClick={toggleAmbient} className={`shrink-0 rounded-full border px-2.5 py-1 text-xs backdrop-blur-xl transition-all ${ambientEnabled ? 'border-apple-blue/30 bg-apple-blue/15 text-apple-blue' : 'border-white/10 bg-white/[0.08] text-gray-300 hover:bg-white/[0.14] hover:text-white'}`} title="剧院光效">
          光效
        </button>
        {useTranscode && (
          <span className="shrink-0 rounded-full border border-amber-400/20 bg-amber-500/10 px-2.5 py-1 text-xs text-amber-200 backdrop-blur-xl">
            {transcodeMode === 'full' ? '完整转码' : '音频转码'} · {fmt(currentTimeRef.current || transcodeStart)}
          </span>
        )}
      </div>
      </div>
    </>
  )
}
