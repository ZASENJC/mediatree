import { useState, useCallback, useEffect, useRef } from 'react'
import { Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom'
import { getActiveLibrary, setActiveLibrary, api, clearCache, MediaRoot } from './api'
import { useToastController } from './toast'
import { useSearch } from './hooks/useSearch'
import ScanToast from './components/ScanToast'
import LibraryModal from './components/LibraryModal'
import PasswordModal from './components/PasswordModal'
import ErrorBoundary from './components/ErrorBoundary'
import Home from './pages/Home'
import Browse from './pages/Browse'
import FolderPage from './pages/Folder'
import Detail from './pages/Detail'
import Favorites from './pages/Favorites'
import Settings from './pages/Settings'
import Login from './pages/Login'
import SetupWizard from './pages/SetupWizard'

const navItems = [
  { path: '/', label: '首页' },
  { path: '/browse', label: '浏览' },
  { path: '/favorites', label: '收藏' },
  { path: '/settings', label: '设置' },
]

export default function App() {
  const location = useLocation()
  const navigate = useNavigate()
  const { searchQuery, setSearchQuery, searchResults, searchTotal, searchLoading, searchOpen, closeSearch, clearSearch } = useSearch()
  const [showLibraryModal, setShowLibraryModal] = useState(false)
  const [libraries, setLibraries] = useState<MediaRoot[]>([])
  const [activeLib, setActiveLib] = useState(getActiveLibrary())
  const [passwordTarget, setPasswordTarget] = useState<MediaRoot | null>(null)
  const [showSetup, setShowSetup] = useState(false)
  const [checkingSetup, setCheckingSetup] = useState(true)
  const [scanToast, setScanToast] = useState<{ visible: boolean; status: string; done: number; total: number }>({ visible: false, status: '', done: 0, total: 0 })
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false)
  const toasts = useToastController()
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const moreBtnRef = useRef<HTMLButtonElement | null>(null)

  const currentLibraryLabel = (() => {
    if (!activeLib) return ''
    const parts = activeLib.split('/').filter(Boolean)
    return parts[parts.length - 1] || activeLib
  })()

  const mountedRef = useRef(true)
  useEffect(() => { return () => { mountedRef.current = false } }, [])

  const loadLibraries = useCallback(async () => {
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
    setMobileNavOpen(false)
    setMobileSearchOpen(false)
  }, [location.pathname])
  useEffect(() => {
    if (mobileSearchOpen) searchInputRef.current?.focus()
  }, [mobileSearchOpen])

  useEffect(() => {
    api.setupStatus().then(d => {
      if (d.needs_setup) setShowSetup(true)
      setCheckingSetup(false)
    }).catch(() => setCheckingSetup(false))
  }, [])

  const scanTimerRef = useRef(0)

  useEffect(() => {
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
            {searchResults.slice(0, 15).map((movie) => (
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

  if (checkingSetup) {
    return <div className="min-h-screen bg-aurora" />
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
    <ErrorBoundary>
      <div className="min-h-screen flex flex-col">
        <header className="sticky top-0 z-50 pt-2 sm:pt-3">
          <div className="mx-auto flex h-12 max-w-7xl items-center justify-between gap-2 px-4 sm:px-6 transform-gpu sm:h-14 sm:gap-3">
            <div className="relative">
            <div className="flex min-w-0 items-center gap-2 rounded-3xl border border-white/15 bg-white/[0.08] pl-3 pr-3 py-1.5 shadow-[0_10px_34px_rgba(0,0,0,0.24),inset_0_1px_0_rgba(255,255,255,0.18)] backdrop-blur-xl backdrop-saturate-150 sm:pl-4 sm:pr-4 sm:py-2">
              <Link to="/" className="shrink-0 text-base font-semibold tracking-tight text-white transition-colors hover:text-apple-blue sm:text-lg">
                <span className="hidden min-[380px]:inline">MediaTree</span>
                <span className="min-[380px]:hidden">MT</span>
              </Link>
              <nav className="flex min-w-0 items-center justify-center gap-1 overflow-visible">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`shrink-0 rounded-full px-1.5 py-1.5 text-xs transition-all sm:px-3 sm:text-sm ${
                    item.path === '/favorites' || item.path === '/settings' ? 'hidden sm:inline-flex' : 'inline-flex'
                  } ${
                    location.pathname === item.path
                      ? 'bg-white/18 text-white shadow-sm'
                      : 'text-gray-400 hover:bg-white/10 hover:text-white'
                  }`}
                >
                  <span>{item.label}</span>
                </Link>
              ))}
              <div className="relative shrink-0 sm:hidden">
                <button
                  ref={moreBtnRef}
                  onClick={() => setMobileNavOpen(v => !v)}
                  className="rounded-full px-1.5 py-1.5 text-xs text-gray-400 transition-colors hover:bg-white/10 hover:text-white sm:px-2"
                  aria-label="更多导航"
                >
                  ···
                </button>
              </div>
              </nav>
            </div>
            {mobileNavOpen && (
              <>
                <div className="absolute right-0 top-full z-[70] mt-2 w-32 p-1 rounded-3xl border border-white/15 bg-white/[0.08] shadow-[0_10px_34px_rgba(0,0,0,0.24),inset_0_1px_0_rgba(255,255,255,0.18)] backdrop-blur-xl backdrop-saturate-150">
                  {navItems.filter(item => item.path === '/favorites' || item.path === '/settings').map(item => (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={`block rounded-3xl px-3 py-2 text-sm transition-colors ${
                        location.pathname === item.path
                          ? 'bg-white/15 text-white'
                          : 'text-gray-300 hover:bg-white/10 hover:text-white'
                      }`}
                    >
                      {item.label}
                    </Link>
                  ))}
                </div>
                <div className="fixed inset-0 z-[60]" onClick={() => setMobileNavOpen(false)} />
              </>
            )}
            </div>
            <div className="relative shrink-0">
              <div className="flex items-center justify-end gap-1 rounded-3xl border border-white/15 bg-white/[0.08] px-2 py-1.5 shadow-[0_10px_34px_rgba(0,0,0,0.24),inset_0_1px_0_rgba(255,255,255,0.18)] backdrop-blur-xl backdrop-saturate-150 sm:gap-2 sm:px-3 sm:py-2">
              {libraries.length > 1 && (
                <button
                  onClick={() => setShowLibraryModal(true)}
                  className="glass-button h-8 max-w-9 gap-1.5 px-2 text-xs sm:max-w-none sm:px-3"
                  title={currentLibraryLabel || '切换媒体库'}
                >
                  <svg className="h-3 w-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                  <span className="hidden truncate sm:inline">{currentLibraryLabel || '库'}</span>
                </button>
              )}
              {currentLibraryLabel && libraries.length <= 1 && (
                <span className="glass-chip hidden max-w-32 truncate text-gray-400 sm:inline-flex">
                  {currentLibraryLabel}
                </span>
              )}
              <form onSubmit={e => e.preventDefault()} className="hidden sm:block">
                <div className="relative">
                <input
                  ref={searchInputRef}
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="搜索..."
                  className="glass-input w-44 py-1.5 pl-8 pr-3 text-sm md:w-52 md:focus:w-60"
                />
                <svg className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                </div>
              </form>
              <button
                type="button"
                onClick={() => setMobileSearchOpen(v => !v)}
                className="rounded-full p-1.5 text-gray-400 transition-colors hover:bg-white/10 hover:text-white sm:p-2 sm:hidden"
                aria-label="搜索"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </button>
              <button
                onClick={() => api.logout()}
                className="rounded-full p-1.5 text-gray-500 transition-colors hover:bg-red-500/10 hover:text-red-300 sm:p-2"
                title="登出"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
              </button>
              </div>
              {renderSearchPanel('hidden sm:block absolute right-0 top-full z-50 mt-2 max-h-96 w-96 overflow-y-auto p-1 rounded-3xl border border-white/15 bg-white/[0.08] shadow-[0_10px_34px_rgba(0,0,0,0.24),inset_0_1px_0_rgba(255,255,255,0.18)] backdrop-blur-xl backdrop-saturate-150')}
            </div>
          </div>
          {mobileSearchOpen && (
            <form onSubmit={e => e.preventDefault()} className="relative mx-auto mt-2 max-w-7xl px-4 sm:hidden">
              <div className="relative">
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索..."
                className="glass-input w-full py-2 pl-9 pr-3 text-sm"
              />
              <svg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              </div>
              {renderSearchPanel('absolute left-0 right-0 top-full z-50 mt-2 max-h-80 overflow-y-auto p-1 rounded-3xl border border-white/15 bg-white/[0.08] shadow-[0_10px_34px_rgba(0,0,0,0.24),inset_0_1px_0_rgba(255,255,255,0.18)] backdrop-blur-xl backdrop-saturate-150')}
            </form>
          )}
        </header>

        <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 py-5 sm:py-7">
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

        {scanToast.visible && <ScanToast {...scanToast} />}

        {toasts.length > 0 && (
          <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[70] flex flex-col gap-2">
            {toasts.map(t => (
              <div key={t.id} className="glass-popover px-4 py-2 text-sm text-white/90 animate-fade-in">
                {t.message}
              </div>
            ))}
          </div>
        )}
      </div>
    </ErrorBoundary>
  )
}
