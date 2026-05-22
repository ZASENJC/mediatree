import { useEffect, useRef } from 'react'
import type Artplayer from 'artplayer'

export type VRMode = 'off' | '360' | '180' | 'sbs360' | 'tb360' | 'sbs180' | 'tb180'

interface Props {
  art: Artplayer | null
  mode: VRMode
}

let _threeCache: typeof import('three') | null = null
let _threeLoadPromise: Promise<typeof import('three')> | null = null

function loadThree(): Promise<typeof import('three')> {
  if (_threeCache) return Promise.resolve(_threeCache)
  if (!_threeLoadPromise) {
    _threeLoadPromise = import('three').then(m => { _threeCache = m; return m })
  }
  return _threeLoadPromise
}

function stereoConfig(mode: VRMode): { repeat: [number, number]; offset: [number, number] } {
  if (mode.startsWith('sbs')) return { repeat: [0.5, 1], offset: [0, 0] }
  if (mode.startsWith('tb')) return { repeat: [1, 0.5], offset: [0, 0] }
  return { repeat: [1, 1], offset: [0, 0] }
}

export default function VRVideoLayer({ art, mode }: Props) {
  const hostRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const host = hostRef.current
    const video = art?.template?.$video as HTMLVideoElement | undefined
    if (!host || !video || mode === 'off') return

    let disposed = false
    let renderer: any
    let scene: any
    let camera: any
    let texture: any
    let mesh: any
    let raf = 0
    let dragging = false
    let lastX = 0
    let lastY = 0
    let lon = 0
    let lat = 0
    let fov = 75

    const cleanupFns: Array<() => void> = []

    loadThree().then((THREE) => {
      if (disposed || !hostRef.current) return
      scene = new THREE.Scene()
      camera = new THREE.PerspectiveCamera(fov, host.clientWidth / Math.max(1, host.clientHeight), 1, 1100)
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
      renderer.setSize(host.clientWidth, host.clientHeight)
      host.appendChild(renderer.domElement)

      texture = new THREE.VideoTexture(video)
      texture.colorSpace = THREE.SRGBColorSpace
      texture.minFilter = THREE.LinearFilter
      texture.magFilter = THREE.LinearFilter

      const sc = stereoConfig(mode)
      texture.repeat.set(...sc.repeat)
      texture.offset.set(...sc.offset)

      const is180 = mode.includes('180')
      const geometry = is180
        ? new THREE.SphereGeometry(500, 64, 32, 0, Math.PI)
        : new THREE.SphereGeometry(500, 64, 32)
      geometry.scale(-1, 1, 1)
      const material = new THREE.MeshBasicMaterial({ map: texture })
      mesh = new THREE.Mesh(geometry, material)
      scene.add(mesh)

      const resize = () => {
        if (!renderer || !camera || !hostRef.current) return
        const w = hostRef.current.clientWidth
        const h = Math.max(1, hostRef.current.clientHeight)
        camera.aspect = w / h
        camera.updateProjectionMatrix()
        renderer.setSize(w, h)
      }
      const render = () => {
        if (disposed) return
        lat = Math.max(-85, Math.min(85, lat))
        const phi = THREE.MathUtils.degToRad(90 - lat)
        const theta = THREE.MathUtils.degToRad(lon)
        camera.lookAt(
          500 * Math.sin(phi) * Math.cos(theta),
          500 * Math.cos(phi),
          500 * Math.sin(phi) * Math.sin(theta),
        )
        renderer.render(scene, camera)
        raf = requestAnimationFrame(render)
      }
      const pointerDown = (event: PointerEvent) => {
        dragging = true
        lastX = event.clientX
        lastY = event.clientY
        ;(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId)
      }
      const pointerMove = (event: PointerEvent) => {
        if (!dragging) return
        lon -= (event.clientX - lastX) * 0.12
        lat += (event.clientY - lastY) * 0.12
        lastX = event.clientX
        lastY = event.clientY
      }
      const pointerUp = (event: PointerEvent) => {
        dragging = false
        ;(event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId)
      }
      const wheel = (event: WheelEvent) => {
        event.preventDefault()
        fov = Math.max(35, Math.min(100, fov + event.deltaY * 0.03))
        camera.fov = fov
        camera.updateProjectionMatrix()
      }

      host.addEventListener('pointerdown', pointerDown)
      host.addEventListener('pointermove', pointerMove)
      host.addEventListener('pointerup', pointerUp)
      host.addEventListener('pointercancel', pointerUp)
      host.addEventListener('wheel', wheel, { passive: false })
      window.addEventListener('resize', resize)

      const ro = new ResizeObserver(resize)
      ro.observe(host)

      cleanupFns.push(() => {
        host.removeEventListener('pointerdown', pointerDown)
        host.removeEventListener('pointermove', pointerMove)
        host.removeEventListener('pointerup', pointerUp)
        host.removeEventListener('pointercancel', pointerUp)
        host.removeEventListener('wheel', wheel)
        window.removeEventListener('resize', resize)
        ro.disconnect()
      })
      resize()
      render()
    })

    video.classList.add('mediatree-vr-video-hidden')

    return () => {
      disposed = true
      cancelAnimationFrame(raf)
      cleanupFns.forEach(fn => fn())
      video.classList.remove('mediatree-vr-video-hidden')
      if (mesh) {
        mesh.geometry?.dispose?.()
        mesh.material?.dispose?.()
      }
      texture?.dispose?.()
      renderer?.dispose?.()
      if (renderer?.domElement?.parentElement) renderer.domElement.parentElement.removeChild(renderer.domElement)
    }
  }, [art, mode])

  if (mode === 'off') return null

  return (
    <div ref={hostRef} className="mediatree-vr-layer">
      <div className="mediatree-vr-hint">拖拽旋转视角 · 滚轮缩放 · VR 退出</div>
    </div>
  )
}
