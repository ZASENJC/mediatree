import { useState, useCallback, useEffect } from 'react'
import { Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom'
import { getActiveLibrary, setActiveLibrary, api, clearCache, MediaRoot } from './api'
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

  const currentLibraryLabel = (() => {
    if (!activeLib) return ''
    const parts = activeLib.split('/').filter(Boolean)
    return parts[parts.length - 1] || activeLib
  })()

  const loadLibraries = useCallback(async () => {
    try {
      const data = await api.mediaRoots()
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
    api.setupStatus().then(d => {
      if (d.needs_setup) setShowSetup(true)
      setCheckingSetup(false)
    }).catch(() => setCheckingSetup(false))
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

  if (checkingSetup) {
    return <div className="min-h-screen bg-dark-900" />
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
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-50 bg-dark-800/95 backdrop-blur border-b border-dark-600">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between gap-3">
          <Link to="/" className="text-lg font-semibold tracking-tight text-white hover:text-blue-400 transition-colors shrink-0">
            MediaTree
          </Link>
          <nav className="flex items-center gap-1 shrink-0">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                  location.pathname === item.path
                    ? 'bg-dark-600 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-dark-700'
                }`}
              >
                <span>{item.label}</span>
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-2 flex-1 justify-end">
            {libraries.length > 1 && (
              <button
                onClick={() => setShowLibraryModal(true)}
                className="text-xs text-gray-400 hover:text-white px-2 py-1 rounded bg-dark-700 hover:bg-dark-600 transition-colors flex items-center gap-1"
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                <span>{currentLibraryLabel || '库'}</span>
              </button>
            )}
            {currentLibraryLabel && libraries.length <= 1 && (
              <span className="text-xs text-gray-600 px-2 py-1 rounded bg-dark-700/50">
                {currentLibraryLabel}
              </span>
            )}
            <form onSubmit={handleSearch} className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => { if (searchResults.length > 0 || searchQuery) setSearchOpen(true) }}
                placeholder="搜索..."
                className="w-32 md:w-48 pl-7 pr-2 py-1.5 bg-dark-700 border border-dark-600 rounded-md text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:w-56 transition-all"
              />
              <svg className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              {searchOpen && (searchResults.length > 0 || searchLoading || (searchQuery && !searchLoading)) && (
                <div className="absolute top-full mt-1 right-0 w-80 max-h-96 overflow-y-auto bg-dark-800 border border-dark-600 rounded-lg shadow-2xl z-50">
                  {searchResults.length > 0 && (
                    <>
                      <div className="p-2 text-xs text-gray-500 border-b border-dark-600">
                        找到 {searchTotal} 个结果
                      </div>
                      {searchResults.slice(0, 15).map((movie: any) => (
                        <div
                          key={movie.id}
                          onClick={() => {
                            navigate(`/detail/${movie.id}`)
                            setSearchOpen(false)
                            setSearchQuery('')
                            setSearchResults([])
                          }}
                          className="flex items-center gap-3 p-2 hover:bg-dark-700 cursor-pointer transition-colors"
                        >
                          <img
                            src={api.coverUrl(movie.id)}
                            alt={movie.code}
                            className="w-10 h-14 object-cover rounded shrink-0 bg-dark-700"
                            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                          />
                          <div className="min-w-0">
                            <p className="text-sm text-white truncate">{movie.title || movie.code}</p>
                            <p className="text-xs text-gray-500">{movie.code}</p>
                            {movie.actress && (
                              <p className="text-xs text-gray-600 truncate">{movie.actress}</p>
                            )}
                          </div>
                        </div>
                      ))}
                      {searchTotal > 15 && (
                        <button
                          onClick={() => {
                            navigate(`/browse?code=${encodeURIComponent(searchQuery)}`)
                            setSearchOpen(false)
                            setSearchQuery('')
                            setSearchResults([])
                          }}
                          className="w-full p-2 text-xs text-blue-400 hover:text-blue-300 text-center border-t border-dark-600 hover:bg-dark-700"
                        >
                          查看全部 {searchTotal} 个结果 →
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
              )}
            </form>
            <button
              onClick={() => api.logout()}
              className="text-xs text-gray-500 hover:text-red-400 px-2 py-1 rounded hover:bg-dark-700 transition-colors"
              title="登出"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto px-4 py-6 w-full">
        {!searchOpen && (
          <Routes key={activeLib}>
            <Route path="/" element={<Home />} />
            <Route path="/browse" element={<Browse />} />
            <Route path="/folder" element={<FolderPage />} />
            <Route path="/detail/:id" element={<Detail />} />
            <Route path="/favorites" element={<Favorites />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        )}
        {searchOpen && (
          <div className="fixed inset-0 z-40" onClick={() => setSearchOpen(false)} />
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
    </div>
  )
}

function LibraryModal({ libraries, activeLib, onSelect, onClose }: {
  libraries: MediaRoot[]
  activeLib: string
  onSelect: (lib: MediaRoot) => void
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-dark-900">
      <div className="bg-dark-800 border border-dark-600 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl">
        <h2 className="text-lg font-bold mb-1">切换媒体库</h2>
        <p className="text-xs text-gray-500 mb-4">选择要浏览的媒体库</p>
        <div className="space-y-1.5">
          {libraries.map((lib) => (
            <button
              key={lib.path}
              onClick={() => onSelect(lib)}
              className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors border ${
                lib.path === activeLib
                  ? 'bg-blue-600/10 border-blue-500/30 text-blue-400'
                  : 'bg-dark-700 border-dark-600 hover:bg-dark-600 text-gray-300'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium flex items-center gap-1.5">
                  {lib.locked && (
                    <svg className="w-3 h-3 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
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
          className="mt-4 w-full py-2 text-sm text-gray-500 hover:text-white transition-colors"
        >
          取消
        </button>
      </div>
    </div>
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-dark-900">
      <div className="bg-dark-800 border border-dark-600 rounded-xl p-6 w-full max-w-xs mx-4 shadow-2xl">
        <div className="text-center mb-4">
          <svg className="w-8 h-8 text-yellow-500 mx-auto mb-2" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
          </svg>
          <h2 className="text-lg font-bold">{target.label}</h2>
          <p className="text-xs text-gray-500 mt-1">此媒体库已加密，请输入密码</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="password"
            value={pwd}
            onChange={e => setPwd(e.target.value)}
            placeholder="输入密码"
            autoFocus
            className="w-full px-3 py-2 bg-dark-700 border border-dark-600 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500 placeholder-gray-600"
          />
          {error && <p className="text-red-400 text-xs">{error}</p>}
          <button
            type="submit"
            disabled={checking}
            className="w-full py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            {checking ? '验证中...' : '确认'}
          </button>
          <button type="button" onClick={onCancel} className="w-full py-2 text-sm text-gray-400 hover:text-white transition-colors">
            取消
          </button>
        </form>
      </div>
    </div>
  )
}
