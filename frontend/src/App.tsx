import { useState, useCallback, useEffect, useLayoutEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom'
import { getActiveLibrary, setActiveLibrary, api, clearCache, MediaRoot, getToken, getMediaTokenSync } from './api'
import { getUiPrefs, setUiPrefs, getUpdateNotification } from './store'
import { useToastController } from './toast'
import { useTaskProgressController } from './taskProgress'
import { useTheater } from './theater'
import { useMediaGridMotion } from './hooks/useMediaGridMotion'
import Home from './pages/home'
import Browse from './pages/browse'
import FolderPage from './pages/folder'
import Detail from './pages/detail'
import Favorites from './pages/favorites'
import Settings from './pages/settings'
import Login from './pages/login'
import SetupWizard from './pages/setup'

const navItems = [
  { path: '/', label: '首页' },
  { path: '/browse', label: '浏览' },
  { path: '/favorites', label: '收藏' },
]

const TOPBAR_LIBRARY_LABEL_LIMIT = 5
const TOPBAR_LIBRARY_LABEL_PREFIX = 2

function formatTopbarLibraryLabel(label: string) {
  const normalized = label.trim()
  if (!normalized) return ''

  const chars = Array.from(normalized)
  if (chars.length <= TOPBAR_LIBRARY_LABEL_LIMIT) return normalized
  return `${chars.slice(0, TOPBAR_LIBRARY_LABEL_PREFIX).join('')}...`
}

export default function App() {
  const location = useLocation()
  const navigate = useNavigate()
  useMediaGridMotion()
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searchTotal, setSearchTotal] = useState(0)
  const [searchLoading, setSearchLoading] = useState(false)
  const [showLibraryModal, setShowLibraryModal] = useState(false)
  const [libraries, setLibraries] = useState<MediaRoot[]>([])
  const [activeLib, setActiveLib] = useState(getActiveLibrary())
  const [passwordTarget, setPasswordTarget] = useState<MediaRoot | null>(null)
  const [showSetup, setShowSetup] = useState(false)
  const [checkingSetup, setCheckingSetup] = useState(true)
  const [scanToast, setScanToast] = useState<{ visible: boolean; status: string; done: number; total: number }>({ visible: false, status: '', done: 0, total: 0 })
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false)
  const [desktopSearchOpen, setDesktopSearchOpen] = useState(false)
  const [hasUpdate, setHasUpdate] = useState(() => getUpdateNotification().available)
  const [topbarWheelDirection, setTopbarWheelDirection] = useState<'up' | 'down' | null>(null)
  const [topbarCompact, setTopbarCompact] = useState(false)
  const [topbarHovering, setTopbarHovering] = useState(false)
  const [topbarFocused, setTopbarFocused] = useState(false)
  const [, setMediaTokenVersion] = useState(0)
  const [checkingMediaToken, setCheckingMediaToken] = useState(() => Boolean(getToken()) && !getMediaTokenSync())
  const { theaterMode, setTheaterMode } = useTheater()
  const toasts = useToastController()
  const taskProgress = useTaskProgressController()
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const moreBtnRef = useRef<HTMLButtonElement | null>(null)
  const topbarLeftRef = useRef<HTMLDivElement | null>(null)
  const topbarRightRef = useRef<HTMLDivElement | null>(null)
  const desktopSearchRootRef = useRef<HTMLDivElement | null>(null)

  const currentLibraryLabel = (() => {
    if (!activeLib) return ''
    const parts = activeLib.split('/').filter(Boolean)
    return parts[parts.length - 1] || activeLib
  })()
  const currentLibraryDisplayLabel = formatTopbarLibraryLabel(currentLibraryLabel)

  const topbarOpenByInteraction = topbarHovering || desktopSearchOpen || mobileNavOpen || mobileSearchOpen || showLibraryModal
  const topbarShouldCompact = topbarWheelDirection === 'down' && !topbarOpenByInteraction

  const mountedRef = useRef(true)
  useEffect(() => { return () => { mountedRef.current = false } }, [])

  const measureExpandedTopbarGlass = useCallback((element: HTMLElement) => {
    if (typeof document === 'undefined' || !document.body) {
      return Math.ceil(Math.max(element.scrollWidth, element.getBoundingClientRect().width))
    }

    const host = document.createElement('div')
    host.className = 'mt-topbar is-expanded topbar-measure-host'
    const clone = element.cloneNode(true) as HTMLElement
    clone.style.removeProperty('--mt-topbar-expanded-width')
    clone.style.setProperty('inline-size', 'max-content')
    clone.style.setProperty('max-inline-size', 'none')
    clone.style.setProperty('transition', 'none')
    host.appendChild(clone)
    document.body.appendChild(host)
    const width = Math.ceil(Math.max(clone.scrollWidth, clone.getBoundingClientRect().width))
    host.remove()
    return width
  }, [])

  const measureTopbarGlass = useCallback(() => {
    ;[topbarLeftRef.current, topbarRightRef.current].forEach((element) => {
      if (!element) return
      const width = measureExpandedTopbarGlass(element)
      if (width > 0) element.style.setProperty('--mt-topbar-expanded-width', `${width}px`)
    })
  }, [measureExpandedTopbarGlass])

  const flushTopbarLayout = useCallback(() => {
    void topbarLeftRef.current?.offsetWidth
    void topbarRightRef.current?.offsetWidth
  }, [])

  const setTopbarWheelDirectionWithMeasure = useCallback((direction: 'up' | 'down' | null) => {
    if (direction === 'down') {
      setTopbarFocused(false)
      setDesktopSearchOpen(false)
      setSearchOpen(false)
      setMobileSearchOpen(false)
      if (!topbarCompact) measureTopbarGlass()
    }
    setTopbarWheelDirection(direction)
  }, [topbarCompact, measureTopbarGlass])

  useEffect(() => {
    const onWheel = (event: WheelEvent) => {
      if (event.deltaY > 0) {
        setTopbarWheelDirectionWithMeasure('down')
      } else if (event.deltaY < 0) {
        setTopbarWheelDirectionWithMeasure('up')
      }
    }

    window.addEventListener('wheel', onWheel, { passive: true })
    return () => {
      window.removeEventListener('wheel', onWheel)
    }
  }, [setTopbarWheelDirectionWithMeasure])

  useLayoutEffect(() => {
    if (typeof window === 'undefined') return
    let frame = 0
    let commitFrame = 0

    if (topbarShouldCompact) {
      if (topbarCompact) return
      measureTopbarGlass()
      flushTopbarLayout()
      frame = window.requestAnimationFrame(() => {
        commitFrame = window.requestAnimationFrame(() => {
          setTopbarCompact(true)
        })
      })
      return () => {
        if (frame) window.cancelAnimationFrame(frame)
        if (commitFrame) window.cancelAnimationFrame(commitFrame)
      }
    }

    setTopbarCompact(false)
    frame = window.requestAnimationFrame(measureTopbarGlass)
    return () => {
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [topbarShouldCompact, topbarCompact, measureTopbarGlass, flushTopbarLayout])

  useLayoutEffect(() => {
    if (topbarShouldCompact || topbarCompact || typeof window === 'undefined') return
    const frame = window.requestAnimationFrame(measureTopbarGlass)
    return () => window.cancelAnimationFrame(frame)
  }, [topbarShouldCompact, topbarCompact, measureTopbarGlass, currentLibraryDisplayLabel, libraries.length, location.pathname, hasUpdate, desktopSearchOpen])

  useEffect(() => {
    if (typeof window === 'undefined') return
    let frame = 0
    const onResize = () => {
      if (topbarCompact || frame) return
      frame = window.requestAnimationFrame(() => {
        frame = 0
        measureTopbarGlass()
      })
    }

    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [topbarCompact, measureTopbarGlass])

  const loadLibraries = useCallback(async () => {
    if (!getToken()) return
    try {
      const data = await api.mediaRoots()
      if (!mountedRef.current) return
      const items = data.items || []
      setLibraries(items)
      if (items.length > 1 && !getActiveLibrary()) {
        setShowLibraryModal(true)
      } else if (items.length >= 1 && !getActiveLibrary()) {
        const first = items[0]
        if (!first.locked) {
          setActiveLibrary(first.path)
          setActiveLib(first.path)
        }
      }
    } catch {}
  }, [])

  useEffect(() => { loadLibraries() }, [loadLibraries])
  useEffect(() => {
    if (!getToken()) {
      setCheckingMediaToken(false)
      return
    }
    api.ensureMediaToken()
      .then(() => {
        if (mountedRef.current) setMediaTokenVersion(v => v + 1)
      })
      .finally(() => {
        if (mountedRef.current) setCheckingMediaToken(false)
      })
      .catch(() => {})
  }, [])
  useEffect(() => {
    setMobileNavOpen(false)
    setMobileSearchOpen(false)
    setDesktopSearchOpen(false)
    setSearchOpen(false)
  }, [location.pathname])
  useEffect(() => {
    if (desktopSearchOpen) searchInputRef.current?.focus()
  }, [desktopSearchOpen])
  useEffect(() => {
    if (mobileSearchOpen) searchInputRef.current?.focus()
  }, [mobileSearchOpen])

  // 版本更新检查（每 15 分钟轮询）
  useEffect(() => {
    if (!getToken()) return
    const check = async () => {
      try {
        const result = await api.checkForUpdates()
        const { dismissed } = getUpdateNotification()
        const top = result.versions[0]
        if (result.has_update && top && top.version !== dismissed) {
          setHasUpdate(true)
          setUiPrefs({ ...getUiPrefs(), updateAvailable: true, lastUpdateCheck: Date.now() })
        } else if (!result.has_update) {
          setHasUpdate(false)
        }
      } catch {}
    }
    check()
    const t = setInterval(check, 15 * 60 * 1000)
    return () => clearInterval(t)
  }, [])

  // auto-search with debounce when typing
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([])
      setSearchTotal(0)
      setSearchOpen(false)
      return
    }
    const timer = setTimeout(async () => {
      setSearchLoading(true)
      setSearchOpen(true)
      try {
        const data = await api.search(searchQuery.trim())
        setSearchResults(data.movies)
        setSearchTotal(data.total)
      } catch {
        setSearchResults([])
        setSearchTotal(0)
      }
      setSearchLoading(false)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  useEffect(() => {
    if (!getToken()) {
      setShowSetup(false)
      setCheckingSetup(false)
      return
    }
    api.setupStatus().then(d => {
      if (d.needs_setup) setShowSetup(true)
      setCheckingSetup(false)
    }).catch(() => setCheckingSetup(false))
  }, [])

  // 离开详情页时自动退出剧院模式
  useEffect(() => {
    if (theaterMode && !location.pathname.startsWith('/detail/')) {
      setTheaterMode(false)
    }
  }, [location.pathname, theaterMode, setTheaterMode])

  const scanTimerRef = useRef(0)

  useEffect(() => {
    if (!getToken()) return
    let hadActive = false
    const poll = async () => {
      try {
        const data = await api.scanStatusAll()
        const roots = Object.values(data.roots || {})
        const active = roots.filter(r => ['scanning', 'scanned', 'scraping'].includes(r.status))
        if (active.length > 0) {
          hadActive = true
          const done = active.reduce((sum, r) => sum + (r.done || 0), 0)
          const total = active.reduce((sum, r) => sum + (r.total || 0), 0)
          const scanning = active.some(r => r.status === 'scanning' || r.status === 'scanned')
          setScanToast({ visible: true, status: scanning ? '正在扫描媒体库...' : '正在刮削媒体信息...', done, total })
        } else if (hadActive) {
          hadActive = false
          clearCache()
          setScanToast({ visible: true, status: '媒体库刮削完成', done: 1, total: 1 })
          window.setTimeout(() => setScanToast(t => ({ ...t, visible: false })), 4500)
        }
      } catch {}
      scanTimerRef.current = window.setTimeout(poll, 2500)
    }
    poll()
    return () => clearTimeout(scanTimerRef.current)
  }, [])

  const doSwitch = (libPath: string) => {
    setActiveLibrary(libPath)
    setActiveLib(libPath)
    clearCache()
    setShowLibraryModal(false)
    navigate('/')
  }

  const selectLibrary = (lib: MediaRoot) => {
    if (lib.locked) {
      setPasswordTarget(lib)
      return
    }
    doSwitch(lib.path)
  }

  const onPasswordOk = (libPath: string) => {
    setPasswordTarget(null)
    doSwitch(libPath)
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    setSearchLoading(true)
    setSearchOpen(true)
    try {
      const data = await api.search(searchQuery.trim())
      setSearchResults(data.movies)
      setSearchTotal(data.total)
    } catch {
      setSearchResults([])
      setSearchTotal(0)
    }
    setSearchLoading(false)
  }

  const openDesktopSearch = useCallback(() => {
    setDesktopSearchOpen(true)
    if (searchQuery.trim() || searchResults.length > 0) {
      setSearchOpen(true)
    }
  }, [searchQuery, searchResults.length])

  const closeDesktopSearch = useCallback(() => {
    setDesktopSearchOpen(false)
    setSearchOpen(false)
  }, [])

  useEffect(() => {
    if (!desktopSearchOpen) return

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target
      if (!(target instanceof Node)) return
      if (!desktopSearchRootRef.current?.contains(target)) closeDesktopSearch()
    }

    document.addEventListener('pointerdown', handlePointerDown, true)
    return () => document.removeEventListener('pointerdown', handlePointerDown, true)
  }, [desktopSearchOpen, closeDesktopSearch])

  const closeSearch = () => {
    closeDesktopSearch()
    setSearchOpen(false)
    setMobileSearchOpen(false)
  }

  const clearSearch = () => {
    setSearchQuery('')
    setSearchResults([])
  }

  const openMovieFromSearch = (movieId: number) => {
    navigate(`/detail/${movieId}`)
    closeSearch()
    clearSearch()
  }

  const renderSearchPanel = (className: string) => (
    searchOpen && (searchResults.length > 0 || searchLoading || (searchQuery && !searchLoading)) ? (
      <div className={className}>
        {searchResults.length > 0 && (
          <>
            <div className="border-b border-white/10 p-3 text-xs text-gray-400">
              找到 {searchTotal} 个结果
            </div>
            {searchResults.slice(0, 15).map((movie: any) => (
              <div
                key={movie.id}
                onClick={() => openMovieFromSearch(movie.id)}
                className="flex cursor-pointer items-center gap-3 rounded-2xl p-2 transition-colors hover:bg-white/10"
              >
                <img
                  src={api.coverUrl(movie.id)}
                  alt={movie.code}
                  className="h-14 w-10 shrink-0 rounded-lg bg-white/10 object-cover"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                />
                <div className="min-w-0">
                  <p className="truncate text-sm text-white">{movie.title || movie.code}</p>
                  <p className="text-xs text-gray-500">{movie.code}</p>
                  {movie.actress && (
                    <p className="truncate text-xs text-gray-600">{movie.actress}</p>
                  )}
                </div>
              </div>
            ))}
            {searchTotal > 15 && (
              <button
                onClick={() => {
                  navigate(`/browse?code=${encodeURIComponent(searchQuery)}`)
                  closeSearch()
                  clearSearch()
                }}
                className="w-full rounded-2xl border-t border-white/10 p-2 text-center text-xs text-apple-blue transition-colors hover:bg-white/10 hover:text-white"
              >
                查看全部 {searchTotal} 个结果
              </button>
            )}
          </>
        )}
        {searchLoading && (
          <div className="p-4 text-center text-sm text-gray-400">搜索中...</div>
        )}
        {!searchLoading && searchResults.length === 0 && searchQuery && (
          <div className="p-4 text-center text-sm text-gray-400">未找到结果</div>
        )}
      </div>
    ) : null
  )

  if (checkingSetup || checkingMediaToken) {
    return <div className="min-h-screen bg-aurora" />
  }

  if (!getToken()) {
    return (
      <Routes>
        <Route path="*" element={<Login onLogin={loadLibraries} />} />
      </Routes>
    )
  }

  if (showSetup) {
    return <SetupWizard onComplete={() => { setShowSetup(false); loadLibraries() }} />
  }

  if (location.pathname === '/login') {
    return (
      <Routes>
        <Route path="/login" element={<Login onLogin={loadLibraries} />} />
        <Route path="*" element={<Login onLogin={loadLibraries} />} />
      </Routes>
    )
  }

  return (
    <div className="mt-app-shell min-h-screen flex flex-col">
      {!theaterMode && (
      <header
        className={`mt-topbar sticky top-0 z-50 pt-6 sm:pt-9 ${topbarCompact ? 'is-compact' : 'is-expanded'}`}
        onPointerEnter={() => setTopbarHovering(true)}
        onPointerLeave={() => setTopbarHovering(false)}
        onFocusCapture={() => setTopbarFocused(true)}
        onBlurCapture={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
            setTopbarFocused(false)
          }
        }}
      >
        <div className="topbar-shell flex h-12 w-full min-w-0 items-center justify-between gap-2 transform-gpu sm:h-14 sm:gap-3">
          <div className="relative">
          <div ref={topbarLeftRef} className="flex min-w-0 items-center gap-1.5 liquid-glass topbar-glass topbar-left-glass px-3 py-1.5 sm:px-4 sm:py-2">
            <Link to="/" className="topbar-brand-link shrink-0 text-base font-semibold tracking-tight text-white transition-colors hover:text-white sm:text-lg">
              <img className="topbar-logo-mark" src="/site-logo.png" alt="" aria-hidden="true" />
              <span className="topbar-brand-text hidden min-[380px]:inline">MediaTree</span>
              <span className="topbar-brand-text min-[380px]:hidden">MT</span>
            </Link>
            <nav className="topbar-collapsible topbar-nav flex min-w-0 items-center justify-center gap-1 overflow-visible">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`shrink-0 rounded-full px-1.5 py-1.5 text-xs transition-all sm:px-3 sm:text-sm ${
                  item.path === '/favorites' ? 'hidden sm:inline-flex' : 'inline-flex'
                } ${
                  location.pathname === item.path
                    ? 'bg-white/18 text-white shadow-sm'
                    : 'text-white hover:bg-white/10'
                }`}
              >
                <span className="relative">
                  {item.label}
                </span>
              </Link>
            ))}
            <div className="relative shrink-0 sm:hidden">
              <button
                ref={moreBtnRef}
                onClick={() => setMobileNavOpen(v => !v)}
                className="rounded-full px-1.5 py-1.5 text-xs text-white transition-colors hover:bg-white/10 sm:px-2"
                aria-label="更多导航"
              >
                ···
              </button>
            </div>
            </nav>
          </div>
          {mobileNavOpen && (
            <>
              <div className="absolute right-0 top-full z-[70] mt-2 w-32 p-1 liquid-glass">
                {navItems.filter(item => item.path === '/favorites').map(item => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`block rounded-3xl px-3 py-2 text-sm transition-colors ${
                      location.pathname === item.path
                        ? 'bg-white/15 text-white'
                        : 'text-white hover:bg-white/10'
                    }`}
                  >
                    <span className="relative">
                      {item.label}
                    </span>
                  </Link>
                ))}
              </div>
              <div className="fixed inset-0 z-[60]" onClick={() => setMobileNavOpen(false)} />
            </>
          )}
        </div>
        <div ref={desktopSearchRootRef} className="relative shrink-0">
            <div ref={topbarRightRef} className="flex items-center justify-end gap-1.5 liquid-glass topbar-glass topbar-right-glass px-3 py-1.5 sm:gap-2 sm:px-4 sm:py-2">
            <div className="topbar-collapsible topbar-right-expanded flex items-center justify-end gap-1.5 sm:gap-2">
            {libraries.length > 1 && (
              <button
                type="button"
                onClick={() => setShowLibraryModal(true)}
                className="glass-button topbar-library-button h-8 max-w-9 gap-1.5 px-2 text-xs sm:max-w-none sm:px-3"
                title={currentLibraryLabel || '切换媒体库'}
              >
                <svg className="h-3 w-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                <span className="topbar-library-label hidden truncate sm:inline-block">{currentLibraryDisplayLabel || '库'}</span>
              </button>
            )}
            {currentLibraryLabel && libraries.length <= 1 && (
              <span className="glass-chip topbar-library-chip hidden max-w-32 truncate text-white sm:inline-flex" title={currentLibraryLabel}>
                <span className="topbar-library-label">{currentLibraryDisplayLabel}</span>
              </span>
            )}
            <form onSubmit={handleSearch} className={`topbar-search-form ${desktopSearchOpen ? 'is-open' : ''} hidden sm:flex`}>
              {desktopSearchOpen ? (
                <>
                  <input
                    ref={searchInputRef}
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onFocus={() => setSearchOpen(true)}
                    onKeyDown={(event) => {
                      if (event.key === 'Escape') closeDesktopSearch()
                    }}
                    placeholder="搜索..."
                    className="topbar-search-input glass-input"
                    aria-label="搜索"
                  />
                  <button
                    type="button"
                    onClick={closeDesktopSearch}
                    className="topbar-search-toggle topbar-icon-button"
                    aria-label="收起搜索"
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 6l12 12M18 6L6 18" />
                    </svg>
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={openDesktopSearch}
                  className="topbar-icon-button hidden sm:inline-flex"
                  aria-label="展开搜索"
                  title="展开搜索"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </button>
              )}
            </form>
            <button
              type="button"
              onClick={() => setMobileSearchOpen(v => !v)}
              className="rounded-full p-1.5 text-white transition-colors hover:bg-white/10 sm:p-2 sm:hidden"
              aria-label="搜索"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </button>
            <Link
              to="/settings"
              className={`topbar-icon-button relative inline-flex ${location.pathname === '/settings' ? 'bg-white/18 text-white shadow-sm' : ''}`}
              aria-label="设置"
              title="设置"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317a1.724 1.724 0 012.354 0l.9.9c.25.25.61.36.954.29l1.258-.252a1.724 1.724 0 012.012 1.238l.208 1.276c.056.346.276.642.58.807l1.184.64a1.724 1.724 0 01.708 2.299l-.536 1.1c-.155.319-.155.69 0 1.009l.536 1.1a1.724 1.724 0 01-.708 2.3l-1.184.64a1.724 1.724 0 00-.58.806l-.208 1.276a1.724 1.724 0 01-2.012 1.238l-1.258-.252a1.724 1.724 0 00-.954.29l-.9.9a1.724 1.724 0 01-2.354 0l-.9-.9a1.724 1.724 0 00-.954-.29l-1.258.252a1.724 1.724 0 01-2.012-1.238l-.208-1.276a1.724 1.724 0 00-.58-.806l-1.184-.64a1.724 1.724 0 01-.708-2.3l.536-1.1a1.724 1.724 0 000-1.009l-.536-1.1a1.724 1.724 0 01.708-2.299l1.184-.64c.304-.165.524-.46.58-.807l.208-1.276a1.724 1.724 0 012.012-1.238l1.258.252c.344.07.704-.04.954-.29l.9-.9z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              {hasUpdate && <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-red-500" />}
            </Link>
            <button
              onClick={() => api.logout()}
              className="topbar-round-button rounded-full text-white transition-colors hover:bg-red-500/10 hover:text-white"
              title="登出"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
            </div>
            <button
              type="button"
              onClick={() => {
                if (libraries.length > 1) setShowLibraryModal(true)
              }}
              className="topbar-compact-library-trigger"
              title={currentLibraryLabel || '切换媒体库'}
              aria-label="切换媒体库"
            >
              <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </button>
            </div>
            {renderSearchPanel('hidden sm:block absolute right-0 top-full z-50 mt-2 max-h-96 w-96 overflow-y-auto p-1 liquid-glass')}
          </div>
        </div>
        {mobileSearchOpen && (
          <form onSubmit={handleSearch} className="relative mt-2 w-full min-w-0 px-4 sm:hidden">
            <div className="relative">
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onFocus={() => setSearchOpen(true)}
              placeholder="搜索..."
              className="glass-input w-full py-2 pl-9 pr-3 text-sm"
            />
            <svg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            </div>
            {renderSearchPanel('absolute left-0 right-0 top-full z-50 mt-2 max-h-80 overflow-y-auto p-1 liquid-glass')}
          </form>
        )}
      </header>
      )}

      <main className={`flex-1 w-full min-h-0 ${theaterMode ? 'flex flex-col max-w-none mx-0 px-0 py-0' : 'mt-content mx-auto'}`}>
        <Routes key={activeLib}>
          <Route path="/" element={<Home />} />
          <Route path="/browse" element={<Browse />} />
          <Route path="/folder" element={<FolderPage />} />
          <Route path="/detail/:id" element={<Detail />} />
          <Route path="/favorites" element={<Favorites />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
        {searchOpen && (
          <div className="fixed inset-0 z-40" onClick={closeSearch} />
        )}
      </main>

      {showLibraryModal && (
        <LibraryModal
          libraries={libraries}
          activeLib={activeLib}
          onSelect={selectLibrary}
          onClose={() => setShowLibraryModal(false)}
        />
      )}

      {passwordTarget && (
        <PasswordModal
          target={passwordTarget}
          onOk={onPasswordOk}
          onCancel={() => setPasswordTarget(null)}
        />
      )}

      {scanToast.visible && createPortal(
        <ScanToast {...scanToast} />,
        document.body,
      )}
      {taskProgress.visible && createPortal(
        <ScanToast {...taskProgress} className="z-[80]" />,
        document.body,
      )}

      {toasts.length > 0 && createPortal(
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[90] flex flex-col gap-2">
          {toasts.map(t => (
            <div key={t.id} className="glass-popover px-4 py-2 text-sm text-white/90 animate-fade-in">
              {t.message}
            </div>
          ))}
        </div>,
        document.body,
      )}
    </div>
  )
}

function ScanToast({ status, done, total, className = '' }: { status: string; done: number; total: number; className?: string }) {
  const pct = total > 0 ? Math.max(4, Math.min(100, (done / total) * 100)) : 100
  const complete = status.includes('完成')
  const indeterminate = total <= 0 && !complete
  return (
    <div className={`fixed bottom-3 left-3 right-3 z-50 rounded-3xl border border-white/10 bg-black/60 p-4 shadow-glass backdrop-blur-2xl sm:bottom-4 sm:left-auto sm:right-4 sm:w-80 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className={`text-sm font-medium ${complete ? 'text-green-300' : 'text-white'}`}>{status}</p>
          {!complete && total > 0 && <p className="mt-1 text-xs text-gray-500">{done}/{total}</p>}
        </div>
        {!complete && <div className="h-4 w-4 animate-spin rounded-full border-2 border-apple-blue border-t-transparent" />}
      </div>
      {!complete && (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
          {indeterminate ? (
            <div className="h-full w-1/3 rounded-full bg-apple-blue animate-indeterminate-bar" />
          ) : (
            <div className="h-full rounded-full bg-apple-blue transition-all duration-500" style={{ width: `${pct}%` }} />
          )}
        </div>
      )}
    </div>
  )
}

function LibraryModal({ libraries, activeLib, onSelect, onClose }: {
  libraries: MediaRoot[]
  activeLib: string
  onSelect: (lib: MediaRoot) => void
  onClose: () => void
}) {
  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4 backdrop-blur-2xl">
      <div className="glass-modal w-full max-w-sm p-6">
        <h2 className="mb-1 text-lg font-bold">切换媒体库</h2>
        <p className="mb-4 text-xs text-gray-500">选择要浏览的媒体库</p>
        <div className="space-y-2">
          {libraries.map((lib) => (
            <button
              key={lib.path}
              onClick={() => onSelect(lib)}
              className={`w-full rounded-2xl border px-3 py-2.5 text-left transition-all ${
                lib.path === activeLib
                  ? 'border-apple-blue/40 bg-apple-blue/15 text-apple-blue'
                  : 'border-white/10 bg-white/[0.06] text-gray-300 hover:border-white/20 hover:bg-white/[0.1]'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-1.5 text-sm font-medium">
                  {lib.locked && (
                    <svg className="h-3 w-3 text-apple-yellow" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                    </svg>
                  )}
                  {lib.label}
                </span>
                {lib.movie_count > 0 && (
                  <span className="text-xs text-gray-500">{lib.movie_count} 部</span>
                )}
              </div>
            </button>
          ))}
        </div>
        <button
          onClick={onClose}
          className="mt-4 w-full rounded-full py-2 text-sm text-gray-500 transition-colors hover:bg-white/10 hover:text-white"
        >
          取消
        </button>
      </div>
    </div>,
    document.body,
  )
}

function PasswordModal({ target, onOk, onCancel }: {
  target: MediaRoot
  onOk: (path: string) => void
  onCancel: () => void
}) {
  const [pwd, setPwd] = useState('')
  const [error, setError] = useState('')
  const [checking, setChecking] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!pwd) return
    setChecking(true)
    setError('')
    try {
      const res = await api.verifyLibrary(target.path, pwd)
      if (res.ok) {
        onOk(target.path)
      } else {
        setError('密码错误')
      }
    } catch {
      setError('验证失败')
    }
    setChecking(false)
  }

  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4 backdrop-blur-2xl">
      <div className="glass-modal w-full max-w-xs p-6">
        <div className="mb-4 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl border border-apple-yellow/30 bg-apple-yellow/10">
            <svg className="h-6 w-6 text-apple-yellow" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
            </svg>
          </div>
          <h2 className="text-lg font-bold">{target.label}</h2>
          <p className="mt-1 text-xs text-gray-500">此媒体库已加密，请输入密码</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="password"
            value={pwd}
            onChange={e => setPwd(e.target.value)}
            placeholder="输入密码"
            autoFocus
            className="glass-input w-full px-3 py-2 text-sm"
          />
          {error && <p className="text-xs text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={checking}
            className="glass-button-primary w-full"
          >
            {checking ? '验证中...' : '确认'}
          </button>
          <button type="button" onClick={onCancel} className="w-full rounded-full py-2 text-sm text-gray-400 transition-colors hover:bg-white/10 hover:text-white">
            取消
          </button>
        </form>
      </div>
    </div>,
    document.body,
  )
}
