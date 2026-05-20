import type Artplayer from 'artplayer'
import SubtitlesOctopus, { SubtitlesOctopusOptions } from '@jellyfin/libass-wasm'
import workerUrl from '@jellyfin/libass-wasm/dist/js/subtitles-octopus-worker.js?url'
import wasmUrl from '@jellyfin/libass-wasm/dist/js/subtitles-octopus-worker.wasm?url'
import fallbackFontUrl from '@jellyfin/libass-wasm/dist/js/default.woff2?url'

const bundledCjkFallbackFontUrl = '/fonts/SourceHanSansCN-Bold.woff2'

type ArtplayerPlugin = (art: Artplayer) => Promise<{
  name: string
  instance: SubtitlesOctopus
  setVisible: (visible: boolean) => void
  destroy: () => void
}>

interface AssPluginOptions extends Omit<SubtitlesOctopusOptions, 'video' | 'workerUrl' | 'fallbackFont'> {
  fallbackFont?: string
}

function toAbsoluteUrl(url: string): string {
  if (/^(https?:)?\/\//i.test(url) || url.startsWith('blob:') || url.startsWith('data:')) return url
  return new URL(url, document.baseURI).toString()
}

async function loadWorker(): Promise<string> {
  const response = await fetch(workerUrl)
  const workerScript = await response.text()
  const patched = workerScript.replace(
    /wasmBinaryFile\s*=\s*"(subtitles-octopus-worker\.wasm)"/g,
    `wasmBinaryFile = "${toAbsoluteUrl(wasmUrl)}"`,
  )
  return URL.createObjectURL(new Blob([patched], { type: 'text/javascript' }))
}

export default function artplayerPluginAss(options: AssPluginOptions): ArtplayerPlugin {
  return async (art) => {
    const objectWorkerUrl = await loadWorker()
    const instance = new SubtitlesOctopus({
      renderMode: 'wasm-blend',
      targetFps: 30,
      ...options,
      workerUrl: objectWorkerUrl,
      fallbackFont: toAbsoluteUrl(options.fallbackFont || bundledCjkFallbackFontUrl || fallbackFontUrl),
      video: art.template.$video,
    })

    instance.canvasParent.className = 'artplayer-plugin-ass'
    instance.canvasParent.style.cssText = [
      'position:absolute',
      'inset:0',
      'width:100%',
      'height:100%',
      'user-select:none',
      'pointer-events:none',
      'z-index:20',
      'display:block',
    ].join(';')

    let destroyed = false

    const setVisible = (visible: boolean) => {
      if (!destroyed && instance.canvasParent) {
        instance.canvasParent.style.display = visible ? 'block' : 'none'
      }
    }

    const destroy = () => {
      if (destroyed) return
      destroyed = true
      try { instance.freeTrack() } catch (err) { console.warn('ASS subtitle freeTrack failed', err) }
      try { instance.dispose() } catch (err) { console.warn('ASS subtitle dispose failed', err) }
      try { instance.canvasParent?.remove() } catch {}
      URL.revokeObjectURL(objectWorkerUrl)
    }

    art.on('artplayer-plugin-ass:switch', (subtitleUrl) => {
      if (destroyed) return
      try {
        instance.freeTrack()
        instance.setTrackByUrl(String(subtitleUrl))
        setVisible(true)
      } catch (err) {
        console.error('ASS subtitle switch failed', err)
      }
    })
    art.on('artplayer-plugin-ass:visible', (visible) => setVisible(Boolean(visible)))
    art.on('artplayer-plugin-ass:destroy', destroy)
    art.on('subtitleOffset', (offset) => {
      if (!destroyed) instance.timeOffset = Number(offset || 0)
    })
    art.on('destroy', destroy)

    return {
      name: 'artplayerPluginAss',
      instance,
      setVisible,
      destroy,
    }
  }
}
