import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { CSSProperties } from 'react'
import Artplayer, { Option, Setting, SettingOption } from 'artplayer'
import { api, type Movie, type SubtitleTrack, resolveMediaUrl } from '../api'
import { getUiPrefs, setUiPrefs } from '../store'
import artplayerPluginAss from './artplayerPluginAss'
import VRVideoLayer, { VRMode } from './VRVideoLayer'
import { useTheater } from '../theater'
import { EpisodeMenu, episodeLabel } from '../player/EpisodeMenu'
import { bindGestureLayer, type GestureCleanup, type SeekPreviewPayload } from '../player/gesture'
import { useAmbientColor, usePlayerRect, useTheaterPlayerSize } from '../player/useAmbientColor'
import { usePlaybackTitle } from '../player/usePlaybackTitle'
import {
  buildAssFontConfig,
  fetchOffsetSubtitleBlob,
  getAssPlugin,
  htmlLabel,
  isAssTrack,
  isTextTrack,
  sortSubtitleTracks,
  subtitleLanguagePriority,
  trackLabel,
} from '../player/subtitles'

interface Props {
  src: string
  poster?: string
  movieId: number
  title?: string
  episodes?: Movie[]
  onEpisodeSelect?: (episode: Movie) => void
  onWatched?: () => void
}

const POS_KEY = 'mediatree_pos_'
const WATCHED_AFTER = 60
const WATCHED_RATIO = 0.9
const SEEK_SMALL = 5
const POS_SAVE_INTERVAL = 5000
const AUTO_TRANSCODE_AUDIO = new Set(['ac3'])
const BROWSER_UNSUPPORTED_AUDIO = new Set([...AUTO_TRANSCODE_AUDIO, 'eac3', 'truehd', 'dts', 'dca', 'mlp'])

Artplayer.PLAYBACK_RATE = [0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4]
Artplayer.SEEK_STEP = SEEK_SMALL
Artplayer.FAST_FORWARD_VALUE = 2
Artplayer.CONTROL_HIDE_TIME = 5000
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
  return new URL(resolveMediaUrl(url), window.location.origin).toString()
}

export default function VideoPlayer({ src, poster, movieId, title, episodes = [], onEpisodeSelect, onWatched }: Props) {
  const artContainerRef = useRef<HTMLDivElement>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const playerFrameRef = useRef<HTMLDivElement>(null)
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
  const autoTranscodedAudioRef = useRef('')
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
  const [episodeMenuOpen, setEpisodeMenuOpen] = useState(false)
  const [playerChromeVisible, setPlayerChromeVisible] = useState(true)
  const [unsupportedAudio, setUnsupportedAudio] = useState('')
  const [transcodePromptDismissed, setTranscodePromptDismissed] = useState(false)
  const [autoTranscodeAudio, setAutoTranscodeAudio] = useState('')
  const [fontUrls, setFontUrls] = useState<string[]>(() => buildAssFontConfig([]).fonts)
  const [availableFonts, setAvailableFonts] = useState<Record<string, string>>(() => buildAssFontConfig([]).availableFonts)
  const [assFallbackFont, setAssFallbackFont] = useState(() => buildAssFontConfig([]).fallbackFont)
  const [artInstance, setArtInstance] = useState<Artplayer | null>(null)
  const [vrMode, setVrMode] = useState<VRMode>('off')
  const [videoAspect, setVideoAspect] = useState(16 / 9)
  const [ambientEnabled, setAmbientEnabled] = useState(() => getUiPrefs().ambientMode !== false)
  const { theaterMode, setTheaterMode } = useTheater()
  const theaterModeRef = useRef(theaterMode)
  const previousTheaterModeRef = useRef(theaterMode)
  theaterModeRef.current = theaterMode
  const [theaterTransition, setTheaterTransition] = useState<'enter' | 'exit' | null>(null)
  const streamUrl = useMemo(() => new URL(api.streamUrl(movieId), localPlayerOrigin()).toString(), [movieId])
  const streamSrc = useMemo(() => {
    if (!useTranscode) return src
    const sep = src.includes('?') ? '&' : '?'
    const mode = transcodeMode === 'full' ? 'full' : '1'
    return `${src}${sep}transcode=${mode}&start=${Math.max(0, transcodeStart).toFixed(3)}`
  }, [src, useTranscode, transcodeMode, transcodeStart])

  const displayDuration = mediaDuration || displayDurationRef.current
  const selectableEpisodes = episodes.length > 1 ? episodes : []
  const activeEpisodeTitle = useMemo(() => {
    const active = episodes.find(episode => episode.id === movieId)
    return active ? episodeLabel(active) : ''
  }, [episodes, movieId])
  const currentPlaybackTitle = (activeEpisodeTitle || title || '').trim()
  const hasExternalSubtitles = tracks.some(t => t.source === 'external')
  const externalPlaylistUrl = new URL(api.externalPlaylistUrl(movieId), localPlayerOrigin()).toString()
  const localPlaybackUrl = hasExternalSubtitles ? externalPlaylistUrl : streamUrl
  const playerStyle = { '--mediatree-video-aspect': videoAspect } as CSSProperties
  const theaterSize = useTheaterPlayerSize(wrapperRef, theaterMode, videoAspect)
  const theaterFrameStyle = theaterSize ? {
    width: `${theaterSize.width}px`,
    height: `${theaterSize.height}px`,
  } as CSSProperties : undefined

  const effectiveAmbient = ambientEnabled || theaterMode
  const ambientColor = useAmbientColor(artRef, effectiveAmbient && !useTranscode)
  const playerRect = usePlayerRect(playerFrameRef, effectiveAmbient)
  const {
    restoringDocumentTitleRef,
    restoreDocumentTitle,
    showPausedDocumentTitle,
    showPlayingDocumentTitle,
  } = usePlaybackTitle(currentPlaybackTitle, artRef)

  const toggleAmbient = useCallback(() => {
    setAmbientEnabled(prev => {
      const next = !prev
      const prefs = getUiPrefs()
      setUiPrefs({ ...prefs, ambientMode: next })
      return next
    })
  }, [])

  const showPlayerChrome = useCallback(() => {
    const art = artRef.current
    if (!art || art.isDestroy) return
    art.controls.show = true
  }, [])

  const hidePlayerChrome = useCallback(() => {
    const art = artRef.current
    if (art && !art.isDestroy) {
      art.setting.show = false
      art.contextmenu.show = false
      art.info.show = false
      art.controls.show = false
    } else {
      setPlayerChromeVisible(false)
    }
    setEpisodeMenuOpen(false)
  }, [])

  useEffect(() => {
    const el = document.getElementById('ambient-root')
    if (!el) return
    if (ambientColor && effectiveAmbient) {
      el.style.setProperty('--ambient-r', String(ambientColor.r))
      el.style.setProperty('--ambient-g', String(ambientColor.g))
      el.style.setProperty('--ambient-b', String(ambientColor.b))
    } else {
      el.style.removeProperty('--ambient-r')
      el.style.removeProperty('--ambient-g')
      el.style.removeProperty('--ambient-b')
    }
  }, [ambientColor, effectiveAmbient])

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
    setEpisodeMenuOpen(false)
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
    autoTranscodedAudioRef.current = ''
    setTracks([])
    setActiveTrack(-1)
    setSubtitleVisibleState(true)
    setAutoTranscodeAudio('')
    setUnsupportedAudio('')
    setTranscodePromptDismissed(false)
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
    let cancelled = false
    api.mediaInfo(movieId).then(info => {
      if (cancelled) return
      if (info.duration && isFinite(info.duration)) {
        displayDurationRef.current = info.duration
        setMediaDuration(info.duration)
      }
      const audioCodec = (info.audio_codec || '').toLowerCase()
      setUnsupportedAudio(BROWSER_UNSUPPORTED_AUDIO.has(audioCodec) ? (info.audio_codec || 'unknown') : '')
      setAutoTranscodeAudio(AUTO_TRANSCODE_AUDIO.has(audioCodec) ? audioCodec : '')
    }).catch(() => {})
    return () => { cancelled = true }
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

  const hideTranscodePrompt = useCallback(() => {
    setTranscodePromptDismissed(true)
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

  const handleSeekPreview = useCallback((payload: SeekPreviewPayload | null, commit?: boolean) => {
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

  useEffect(() => {
    if (!autoTranscodeAudio || useTranscodeRef.current) return
    const autoKey = `${movieId}:${autoTranscodeAudio}`
    if (autoTranscodedAudioRef.current === autoKey) return
    autoTranscodedAudioRef.current = autoKey
    startTranscode('audio')
  }, [autoTranscodeAudio, movieId, startTranscode])

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
      miniProgressBar: false,
      playsInline: true,
      lock: true,
      gesture: false,
      fastForward: false,
      autoOrientation: true,
      airplay: true,
      controls: [
        {
          name: 'theater',
          position: 'right',
          index: 10,
          tooltip: '影院模式',
          html: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="14" rx="2"/><path d="M7 21h10"/><path d="M12 17v4"/></svg>`,
          click: function (_component: unknown, _event: Event) {
            setTheaterMode(!theaterModeRef.current)
          },
        },
      ],
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
    restoringDocumentTitleRef.current = false
    artRef.current = art
    setArtInstance(art)
    setPlayerChromeVisible(true)
    streamSrcRef.current = streamSrc

    const syncPlayerChrome = (visible: boolean) => {
      setPlayerChromeVisible(visible)
      if (!visible) setEpisodeMenuOpen(false)
    }
    const exitTheaterAfterFullscreen = (fullscreen: boolean) => {
      if (!fullscreen && theaterModeRef.current) {
        setTheaterMode(false)
      }
    }

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
    art.on('control', syncPlayerChrome)
    art.on('video:timeupdate', () => {
      const virtualTime = useTranscodeRef.current ? transcodeStartRef.current + art.currentTime : art.currentTime
      currentTimeRef.current = virtualTime
      if (art.playing && virtualTime > 0) hideTranscodePrompt()
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
    art.on('video:playing', () => {
      showPlayingDocumentTitle()
      hideTranscodePrompt()
    })
    art.on('video:play', () => {
      showPlayingDocumentTitle()
      hideResumePrompt()
    })
    art.on('fullscreen', exitTheaterAfterFullscreen)
    art.on('fullscreenWeb', exitTheaterAfterFullscreen)
    art.on('video:pause', () => {
      if (!restoringDocumentTitleRef.current) showPausedDocumentTitle()
      const pos = currentTimeRef.current || art.currentTime || 0
      savePos(movieId, pos)
      api.saveProgress(movieId, pos, displayDurationRef.current || art.duration || undefined, true).catch(() => {})
    })
    art.on('video:ended', () => {
      if (!restoringDocumentTitleRef.current) showPausedDocumentTitle()
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
      restoringDocumentTitleRef.current = true
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
      restoreDocumentTitle()
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
      setPlayerChromeVisible(true)
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
      const target = event.target
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        (target instanceof HTMLElement && target.isContentEditable)
      ) return
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
        case 't':
        case 'T':
          if (event.metaKey || event.ctrlKey || event.altKey) return
          event.preventDefault()
          setTheaterMode(!theaterModeRef.current)
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
  }, [setTheaterMode, skipBack, skipForward, startSpeedHold, stopSpeedHold, togglePlay])

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

  // ESC 键退出剧院模式（仅当不在浏览器原生全屏时）
  useEffect(() => {
    if (!theaterMode) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !document.fullscreenElement) {
        setTheaterMode(false)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [theaterMode, setTheaterMode])

  useEffect(() => {
    if (previousTheaterModeRef.current === theaterMode) return
    previousTheaterModeRef.current = theaterMode
    setTheaterTransition(theaterMode ? 'enter' : 'exit')
    const timer = window.setTimeout(() => setTheaterTransition(null), 260)
    return () => window.clearTimeout(timer)
  }, [theaterMode])

  // 剧院模式尺寸变化后触发 ArtPlayer 重新计算内部画布、字幕和控件布局。
  useEffect(() => {
    const art = artRef.current
    if (!art || art.isDestroy) return
    const timer = setTimeout(() => {
      window.dispatchEvent(new Event('resize'))
    }, 150)
    return () => clearTimeout(timer)
  }, [theaterMode, theaterSize?.width, theaterSize?.height])

  return (
    <>
      {effectiveAmbient && playerRect && createPortal(
        <div
          className={`ambient-glow ${theaterMode ? 'theater-ambient-glow' : ''}`}
          style={{
            left: playerRect.left + playerRect.width / 2,
            top: playerRect.top + playerRect.height / 2,
            width: playerRect.width * (theaterMode ? 5 : 3),
            height: playerRect.height * (theaterMode ? 5 : 3),
          }}
        />,
        document.getElementById('ambient-root')!,
      )}
      <div ref={wrapperRef}
        className={theaterMode ? 'theater-player-wrapper' : 'relative mx-auto w-full transition-all duration-300'}
        style={playerStyle}>
        <div
          ref={playerFrameRef}
          className={`mediatree-player-frame theater-player-frame relative z-[1] overflow-hidden rounded-3xl ${theaterTransition ? `theater-player-frame-${theaterTransition}` : ''}`}
          style={theaterMode ? theaterFrameStyle : undefined}
          onMouseMove={showPlayerChrome}
          onMouseEnter={showPlayerChrome}
          onMouseLeave={hidePlayerChrome}
        >
        <div ref={artContainerRef} className="mediatree-artplayer w-full" />
        <VRVideoLayer art={artInstance} mode={vrMode} />

        {selectableEpisodes.length > 0 && (
          <EpisodeMenu
            activeMovieId={movieId}
            episodes={selectableEpisodes}
            open={episodeMenuOpen}
            visible={playerChromeVisible}
            onClose={() => setEpisodeMenuOpen(false)}
            onSelect={onEpisodeSelect}
            onToggle={() => setEpisodeMenuOpen(open => !open)}
          />
        )}

        {seekOsd && (
          <div className="player-osd absolute left-1/2 top-1/2 z-40 -translate-x-1/2 -translate-y-1/2 rounded-2xl px-4 py-2 text-sm font-semibold">
            {seekOsd.delta >= 0 ? '+' : '-'}{fmt(Math.abs(seekOsd.delta))} &nbsp; {fmt(seekOsd.target)} / {fmt(seekOsd.duration)}
          </div>
        )}

        {showResume && (
          <div className="player-resume-prompt absolute bottom-[20%] left-1/2 z-30 flex -translate-x-1/2 items-center overflow-hidden rounded-full text-sm font-semibold">
            <button onClick={handleResume} className="player-resume-action border-0 px-5 py-3 transition-all">
              从上次位置继续 ({fmt(resumePos)})
            </button>
            <button onClick={hideResumePrompt} className="player-resume-dismiss border-y-0 border-r-0 px-3 py-3" aria-label="关闭继续播放提示">
              ×
            </button>
          </div>
        )}

        {unsupportedAudio && !useTranscode && !videoError && !transcodePromptDismissed && (
          <div className="player-warning absolute left-3 right-3 top-3 z-30 rounded-2xl px-3 py-2">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="player-warning-title text-xs font-medium">当前音频编码 {unsupportedAudio.toUpperCase()} 可能无声</p>
                <p className="player-warning-body mt-0.5 text-[11px]">直传不会占用转码资源；需要声音时再手动开启音频转码或外部播放器。</p>
              </div>
              <div className="flex shrink-0 gap-1.5">
                <button onClick={() => startTranscode('audio')} className="player-warning-action rounded-full px-2.5 py-1 text-xs transition-all">
                  音频转码
                </button>
                <button onClick={openMpv} className="player-action-chip rounded-full px-2.5 py-1 text-xs transition-all">
                  MPV
                </button>
              </div>
            </div>
          </div>
        )}

        {videoError && (
          <div className="player-error-overlay absolute inset-0 z-30 flex items-center justify-center p-4">
            <div className="player-modal max-w-sm rounded-3xl p-5 text-center">
              <p className="mb-2 font-semibold">该视频解码失败</p>
              <p className="player-modal-muted mb-4 text-xs">浏览器不支持此视频的音视频编码</p>
              <div className="flex flex-col justify-center gap-2 sm:flex-row">
                <button onClick={() => startTranscode('audio')} className="player-modal-primary rounded-full px-4 py-2 text-sm font-semibold transition-all">
                  音频转码播放
                </button>
                <button onClick={() => startTranscode('full')} className="player-modal-secondary rounded-full px-4 py-2 text-sm font-medium transition-all">
                  完整转码
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {!theaterMode && (
      <div className="mt-5 flex items-center justify-center gap-2 overflow-x-auto pb-1">
        <a href={`iina://weblink?url=${encodeURIComponent(localPlaybackUrl)}`} target="_blank" rel="noopener noreferrer" className="player-action-chip shrink-0 rounded-full px-2.5 py-1 text-xs transition-all">
          IINA
        </a>
        <button onClick={openMpv} className="player-action-chip shrink-0 rounded-full px-2.5 py-1 text-xs transition-all">
          MPV
        </button>
        <button onClick={copyStreamUrl} className="player-action-chip shrink-0 rounded-full px-2.5 py-1 text-xs transition-all">
          {linkCopied ? '已复制' : '复制链接'}
        </button>
        <button onClick={toggleAmbient} className={`shrink-0 rounded-full px-2.5 py-1 text-xs transition-all ${ambientEnabled ? 'player-action-chip-active' : 'player-action-chip'}`} title="剧院光效">
          光效
        </button>
        {useTranscode && (
          <span className="player-transcode-chip shrink-0 rounded-full px-2.5 py-1 text-xs">
            {transcodeMode === 'full' ? '完整转码' : '音频转码'} · {fmt(currentTimeRef.current || transcodeStart)}
          </span>
        )}
      </div>
      )}
      </div>
    </>
  )
}
