import { useCallback, useEffect, useRef } from 'react'
import type Artplayer from 'artplayer'

const SITE_TITLE = 'MediaTree'

function playbackDocumentTitle(title?: string, state: 'playing' | 'paused' = 'paused') {
  const trimmed = (title || '').trim()
  const icon = state === 'playing' ? '▶' : '⏸'
  return trimmed ? `${icon} ${trimmed} - ${SITE_TITLE}` : SITE_TITLE
}

export function usePlaybackTitle(
  currentPlaybackTitle: string,
  artRef: { current: Artplayer | null },
) {
  const documentTitleBeforePlaybackRef = useRef('')
  const playbackTitleActiveRef = useRef(false)
  const playingDocumentTitleRef = useRef(SITE_TITLE)
  const pausedDocumentTitleRef = useRef(SITE_TITLE)
  const restoringDocumentTitleRef = useRef(false)

  const ensureDocumentTitleBaseline = useCallback(() => {
    if (!playbackTitleActiveRef.current) {
      documentTitleBeforePlaybackRef.current = document.title || SITE_TITLE
      playbackTitleActiveRef.current = true
    }
  }, [])

  const showPlayingDocumentTitle = useCallback(() => {
    ensureDocumentTitleBaseline()
    document.title = playingDocumentTitleRef.current
  }, [ensureDocumentTitleBaseline])

  const showPausedDocumentTitle = useCallback(() => {
    ensureDocumentTitleBaseline()
    document.title = pausedDocumentTitleRef.current
  }, [ensureDocumentTitleBaseline])

  const restoreDocumentTitle = useCallback(() => {
    if (!playbackTitleActiveRef.current) return
    document.title = documentTitleBeforePlaybackRef.current || SITE_TITLE
    playbackTitleActiveRef.current = false
  }, [])

  useEffect(() => {
    playingDocumentTitleRef.current = playbackDocumentTitle(currentPlaybackTitle, 'playing')
    pausedDocumentTitleRef.current = playbackDocumentTitle(currentPlaybackTitle, 'paused')
    if (artRef.current?.playing) {
      showPlayingDocumentTitle()
    } else {
      showPausedDocumentTitle()
    }
  }, [artRef, currentPlaybackTitle, showPausedDocumentTitle, showPlayingDocumentTitle])

  return {
    restoringDocumentTitleRef,
    restoreDocumentTitle,
    showPausedDocumentTitle,
    showPlayingDocumentTitle,
  }
}
