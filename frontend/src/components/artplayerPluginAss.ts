import type Artplayer from 'artplayer'
import SubtitlesOctopus, { SubtitlesOctopusOptions } from '@jellyfin/libass-wasm'
import workerUrl from '@jellyfin/libass-wasm/dist/js/subtitles-octopus-worker.js?url'
import wasmUrl from '@jellyfin/libass-wasm/dist/js/subtitles-octopus-worker.wasm?url'
import fallbackFontUrl from '@jellyfin/libass-wasm/dist/js/default.woff2?url'

const bundledCjkFallbackFontUrl = '/fonts/SourceHanSansCN-Bold.woff2'

type ArtplayerPlugin = (art: Artplayer) => Promise<{
  name: string
  instance: SubtitlesOctopus | null
  setVisible: (visible: boolean) => void
  switch: (subtitleUrl: string, nextOptions?: Partial<AssPluginOptions>) => Promise<void>
  clear: () => void
  destroy: () => void
}>

interface AssPluginOptions extends Omit<SubtitlesOctopusOptions, 'video' | 'workerUrl' | 'fallbackFont'> {
  fallbackFont?: string
}

let _cachedObjectWorkerUrl: string | null = null
let _workerLoadPromise: Promise<string> | null = null

function toAbsoluteUrl(url: string): string {
  if (/^(https?:)?\/\//i.test(url) || url.startsWith('blob:') || url.startsWith('data:')) return url
  return new URL(url, document.baseURI).toString()
}

async function loadWorker(): Promise<string> {
  if (_cachedObjectWorkerUrl) return _cachedObjectWorkerUrl
  if (_workerLoadPromise) return _workerLoadPromise
  _workerLoadPromise = (async () => {
    const response = await fetch(workerUrl)
    const workerScript = await response.text()
    const patched = workerScript.replace(
      /wasmBinaryFile\s*=\s*"(subtitles-octopus-worker\.wasm)"/g,
      `wasmBinaryFile = "${toAbsoluteUrl(wasmUrl)}"`,
    )
    _cachedObjectWorkerUrl = URL.createObjectURL(new Blob([patched], { type: 'text/javascript' }))
    return _cachedObjectWorkerUrl
  })()
  return _workerLoadPromise
}

export default function artplayerPluginAss(options: AssPluginOptions): ArtplayerPlugin {
  return async (art) => {
    let current: { instance: SubtitlesOctopus; objectWorkerUrl: string } | null = null
    let destroyed = false
    let visible = true
    let switchSeq = 0

    const setVisible = (nextVisible: boolean) => {
      visible = Boolean(nextVisible)
      if (!destroyed && current?.instance.canvasParent) {
        current.instance.canvasParent.style.display = visible ? 'block' : 'none'
      }
    }

    const disposeCurrent = () => {
      if (!current) return
      const runtime = current
      current = null
      try { runtime.instance.freeTrack() } catch (err) { console.warn('ASS subtitle freeTrack failed', err) }
      try { runtime.instance.dispose() } catch (err) { console.warn('ASS subtitle dispose failed', err) }
      try { runtime.instance.canvasParent?.remove() } catch {}
      // Worker URL is cached globally, do not revoke
    }

    const switchTrack = async (subtitleUrl: string, nextOptions: Partial<AssPluginOptions> = {}) => {
      const seq = ++switchSeq
      disposeCurrent()
      if (destroyed || !subtitleUrl) return
      try {
        console.info('ASS plugin init', { subtitleUrl })
        const objectWorkerUrl = await loadWorker()
        if (destroyed || seq !== switchSeq) return
        const mergedOptions = { ...options, ...nextOptions }
        const instance = new SubtitlesOctopus({
          renderMode: 'wasm-blend',
          targetFps: 30,
          ...mergedOptions,
          subUrl: subtitleUrl,
          workerUrl: objectWorkerUrl,
          fallbackFont: toAbsoluteUrl(mergedOptions.fallbackFont || bundledCjkFallbackFontUrl || fallbackFontUrl),
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
          `display:${visible ? 'block' : 'none'}`,
        ].join(';')

        if (destroyed || seq !== switchSeq) {
          try { instance.dispose() } catch {}
          try { instance.canvasParent?.remove() } catch {}
          return
        }
        current = { instance, objectWorkerUrl }
      } catch (err) {
        console.error('ASS subtitle switch failed', err)
        throw err
      }
    }

    const clear = () => {
      switchSeq += 1
      console.info('ASS plugin destroy')
      disposeCurrent()
    }

    const destroy = () => {
      if (destroyed) return
      destroyed = true
      clear()
      art.off('artplayer-plugin-ass:switch', onSwitch)
      art.off('artplayer-plugin-ass:clear', onClear)
      art.off('artplayer-plugin-ass:visible', onVisible)
      art.off('artplayer-plugin-ass:destroy', destroy)
      art.off('subtitleOffset', onOffset)
      art.off('destroy', destroy)
    }

    const onSwitch = (subtitleUrl: unknown, nextOptions?: unknown) => {
      switchTrack(String(subtitleUrl || ''), (nextOptions || {}) as Partial<AssPluginOptions>).catch(() => {})
    }
    const onClear = () => clear()
    const onVisible = (nextVisible: unknown) => setVisible(Boolean(nextVisible))
    const onOffset = (offset: unknown) => {
      if (!destroyed && current) current.instance.timeOffset = Number(offset || 0)
    }

    art.on('artplayer-plugin-ass:switch', onSwitch)
    art.on('artplayer-plugin-ass:clear', onClear)
    art.on('artplayer-plugin-ass:visible', onVisible)
    art.on('artplayer-plugin-ass:destroy', destroy)
    art.on('subtitleOffset', onOffset)
    art.on('destroy', destroy)

    if (options.subUrl) {
      switchTrack(String(options.subUrl)).catch(() => {})
    }

    return {
      name: 'artplayerPluginAss',
      get instance() {
        return current?.instance || null
      },
      setVisible,
      switch: switchTrack,
      clear,
      destroy,
    }
  }
}
