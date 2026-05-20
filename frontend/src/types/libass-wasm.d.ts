declare module '@jellyfin/libass-wasm' {
  export interface SubtitlesOctopusOptions {
    video?: HTMLVideoElement
    canvas?: HTMLCanvasElement
    subUrl?: string
    subContent?: string
    workerUrl?: string
    legacyWorkerUrl?: string
    fonts?: string[]
    availableFonts?: Record<string, string>
    fallbackFont?: string
    lazyFileLoading?: boolean
    timeOffset?: number
    onReady?: () => void
    onError?: (error: unknown) => void
    debug?: boolean
    renderMode?: 'js-blend' | 'wasm-blend' | 'lossy'
    targetFps?: number
    libassMemoryLimit?: number
    libassGlyphLimit?: number
    dropAllAnimations?: boolean
  }

  export default class SubtitlesOctopus {
    canvasParent: HTMLDivElement
    timeOffset: number
    constructor(options: SubtitlesOctopusOptions)
    setTrackByUrl(url: string): void
    setTrack(content: string): void
    freeTrack(): void
    dispose(): void
  }
}
