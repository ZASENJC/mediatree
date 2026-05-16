import { useEffect, useState, useRef, useCallback } from 'react'
import { api, SubtitleTrack } from '../api'

interface Props {
  src: string
  poster?: string
  movieId: number
  onWatched?: () => void
}

const POS_KEY = 'mediatree_pos_'
const SEEK_THRESH = 5
const WATCHED_AFTER = 60

function getSavedPos(movieId: number): number {
  try { return parseFloat(localStorage.getItem(POS_KEY + movieId) || '0') } catch { return 0 }
}
function savePos(movieId: number, pos: number) {
  try { localStorage.setItem(POS_KEY + movieId, String(pos)) } catch {}
}

export default function VideoPlayer({ src, poster, movieId, onWatched }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [tracks, setTracks] = useState<SubtitleTrack[]>([])
  const [activeTrack, setActiveTrack] = useState(-1)
  const [savedPos, setSavedPos] = useState(() => getSavedPos(movieId))
  const [showResume, setShowResume] = useState(false)
  const [copied, setCopied] = useState(false)
  const watchedRef = useRef(false)
  const lastPosRef = useRef(0)

  useEffect(() => { api.subtitleTracks(movieId).then(setTracks).catch(() => {}) }, [movieId])

  useEffect(() => {
    if (tracks.length > 0 && activeTrack < 0) {
      const chi = tracks.find(t => t.language === 'chi' || t.language === 'zh')
      if (chi) setActiveTrack(chi.index)
    }
  }, [tracks])

  useEffect(() => {
    if (savedPos > SEEK_THRESH) setShowResume(true)
  }, [savedPos])

  const handleLoaded = useCallback(() => {
    const v = videoRef.current
    if (!v) return
    if (savedPos > SEEK_THRESH) {
      v.currentTime = savedPos
    }
  }, [savedPos])

  const handleTimeUpdate = useCallback(() => {
    const v = videoRef.current
    if (!v) return
    lastPosRef.current = v.currentTime
    if (v.currentTime > 3) {
      savePos(movieId, v.currentTime)
    }
    if (!watchedRef.current && v.currentTime > WATCHED_AFTER) {
      watchedRef.current = true
      onWatched?.()
    }
  }, [movieId, onWatched])

  const handlePause = useCallback(() => {
    if (videoRef.current) savePos(movieId, videoRef.current.currentTime)
  }, [movieId])

  const handleSeekToSaved = () => {
    if (videoRef.current) {
      videoRef.current.currentTime = savedPos
      setShowResume(false)
    }
  }

  const copyStreamUrl = async () => {
    try {
      await navigator.clipboard.writeText(src)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      const input = document.createElement('input')
      input.value = src
      document.body.appendChild(input)
      input.select()
      document.execCommand('copy')
      document.body.removeChild(input)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const localPlayers = [
    { name: 'IINA', scheme: 'iina://weblink?url=' },
    { name: 'MPV', scheme: 'mpv://' },
    { name: 'PotPlayer', scheme: 'potplayer://' },
    { name: 'VLC', scheme: 'vlc://' },
  ]

  return (
    <div>
      <div className="bg-dark-950 rounded-lg overflow-hidden relative">
        <video
          ref={videoRef}
          key={src}
          controls
          preload="metadata"
          poster={poster}
          className="w-full aspect-video bg-black"
          style={{ maxHeight: '70vh' }}
          onLoadedMetadata={handleLoaded}
          onTimeUpdate={handleTimeUpdate}
          onPause={handlePause}
        >
          <source src={src} type="video/mp4" />
          {tracks.map((t) => (
            <track key={t.index} kind="subtitles" label={t.title || t.language}
              srcLang={t.language} src={api.subtitleUrl(movieId, t.index)}
              default={t.index === activeTrack} />
          ))}
        </video>
        {showResume && (
          <button
            onClick={handleSeekToSaved}
            className="absolute bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 bg-blue-600/90 hover:bg-blue-500 rounded-lg text-sm font-medium shadow-lg transition-colors z-10"
          >
            从上次位置继续 ({Math.floor(savedPos / 60)}:{(Math.floor(savedPos) % 60).toString().padStart(2, '0')})
          </button>
        )}
      </div>

      {tracks.length > 0 && (
        <div className="flex gap-1.5 mt-2 flex-wrap">
          {tracks.map((t) => (
            <button key={t.index} onClick={() => setActiveTrack(t.index)}
              className={`px-2 py-1 rounded text-xs transition-colors ${t.index === activeTrack ? 'bg-blue-600/30 text-blue-400 border border-blue-500/30' : 'bg-dark-800 text-gray-400 border border-dark-600 hover:bg-dark-700'}`}>
              {t.title || t.language}
            </button>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 mt-3 flex-wrap">
        <span className="text-xs text-gray-500 mr-1">本地播放:</span>
        {localPlayers.map(p => (
          <a
            key={p.name}
            href={`${p.scheme}${encodeURIComponent(src)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-2.5 py-1 bg-dark-700 hover:bg-dark-600 border border-dark-600 rounded text-xs text-gray-300 hover:text-white transition-colors"
          >
            {p.name}
          </a>
        ))}
        <button
          onClick={copyStreamUrl}
          className="px-2.5 py-1 bg-dark-700 hover:bg-dark-600 border border-dark-600 rounded text-xs text-gray-300 hover:text-white transition-colors"
        >
          {copied ? '已复制 ✓' : '复制链接'}
        </button>
      </div>
    </div>
  )
}
