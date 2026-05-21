import { useEffect, useState, useRef } from 'react'
import { api, Config, MediaRoot, LibrarySetting, Plugin, clearCache } from '../api'
import { getUiPrefs, setUiPrefs } from '../store'

const SCRAPER_META: Record<string, { label: string; desc: string; hasKey: boolean }> = {
  tmdb_movie: { label: 'TMDB 电影', desc: '适合电影库；tmdbid 调用 /movie 精确刮削', hasKey: true },
  tmdb_tv: { label: 'TMDB 剧集/番剧', desc: '适合剧集、番剧、电视剧库；tmdbid 调用 /tv 精确刮削', hasKey: true },
  bangumi: { label: 'Bangumi', desc: '适合番剧、动画、二次元条目', hasKey: false },
  javdatabase: { label: 'Javdatabase', desc: '适合 JAV 番号识别和刮削', hasKey: false },
  auto: { label: '自动', desc: '自动判断刮削源，但可能效果不好', hasKey: true },
  none: { label: '不刮削', desc: '只扫描本地文件，不联网刮削元数据', hasKey: false },
}

function normalizeScraper(scraper?: string) {
  return scraper === 'tmdb' ? 'tmdb_movie' : (scraper || 'auto')
}

interface ScanState {
  status: string
  done: number
  total: number
}

export default function Settings() {
  const [config, setConfig] = useState<Config | null>(null)
  const [loading, setLoading] = useState(true)

  const [javdbEnabled, setJavdbEnabled] = useState(true)
  const [javdbCache, setJavdbCache] = useState(24)
  const [tmdbCache, setTmdbCache] = useState(168)
  const [bangumiCache, setBangumiCache] = useState(168)
  const [tmdbKey, setTmdbKey] = useState('')
  const [tmdbToken, setTmdbToken] = useState('')
  const [reqInterval, setReqInterval] = useState(3)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')
  const [hideHomeTitleText, setHideHomeTitleText] = useState(() => getUiPrefs().hideHomeTitleText || false)

  const [libraries, setLibraries] = useState<(MediaRoot & { settings?: LibrarySetting })[]>([])
  const [libScraper, setLibScraper] = useState<Record<string, string>>({})
  const [libPasswords, setLibPasswords] = useState<Record<string, string>>({})
  const [libSaving, setLibSaving] = useState<string | null>(null)
  const [libMsg, setLibMsg] = useState('')

  const [scanStates, setScanStates] = useState<Record<string, ScanState>>({})
  const [scanLogs, setScanLogs] = useState<Record<string, string[]>>({})
  const [logVisible, setLogVisible] = useState<Record<string, boolean>>({})
  const scanTimers = useRef<Record<string, ReturnType<typeof setInterval>>>({})

  // auth
  const [oldUser, setOldUser] = useState('')
  const [oldPass, setOldPass] = useState('')
  const [newUser, setNewUser] = useState('')
  const [newPass, setNewPass] = useState('')
  const [authMsg, setAuthMsg] = useState('')
  const [authSaving, setAuthSaving] = useState(false)

  // plugins
  const [plugins, setPlugins] = useState<Plugin[]>([])
  const [pluginMsg, setPluginMsg] = useState('')

  useEffect(() => {
    api.getConfig().then(d => {
      setConfig(d)
      setJavdbEnabled(d.javdb_enabled)
      setJavdbCache(d.javdb_cache_hours)
      setTmdbCache(d.tmdb_cache_hours)
      setBangumiCache(d.bangumi_cache_hours)
      setTmdbKey(d.tmdb_api_key || '')
      setTmdbToken(d.tmdb_access_token || '')
      setReqInterval(d.javdb_request_interval)
    }).catch(() => {})

    Promise.all([api.mediaRoots(), api.librarySettings()]).then(([rootsData, settings]) => {
      const items = rootsData.items || []
      const settingMap: Record<string, LibrarySetting> = {}
      settings.forEach(s => { settingMap[s.media_root] = s })
      setLibraries(items.map(i => ({ ...i, settings: settingMap[i.path] })))
      const sp: Record<string, string> = {}
      items.forEach(i => {
        sp[i.path] = normalizeScraper(settingMap[i.path]?.scraper)
      })
      setLibScraper(sp)
    }).catch(() => {}).finally(() => setLoading(false))

    api.getPlugins().then(d => setPlugins(d.plugins)).catch(() => {})
  }, [])

  const saveGlobal = async () => {
    setSaving(true)
    setMsg('')
    try {
      setUiPrefs({ hideHomeTitleText })
      await api.updateConfig({
        javdb_enabled: javdbEnabled,
        javdb_cache_hours: javdbCache,
        tmdb_cache_hours: tmdbCache,
        bangumi_cache_hours: bangumiCache,
        javdb_request_interval: reqInterval,
        tmdb_api_key: tmdbKey,
        tmdb_access_token: tmdbToken,
      } as any)
      setMsg('已保存')
    } catch {
      setMsg('保存失败')
    }
    setSaving(false)
  }

  const saveLibrary = async (media_root: string) => {
    setLibSaving(media_root)
    setLibMsg('')
    try {
      await api.saveLibrarySetting({ media_root, scraper: libScraper[media_root] || 'auto' })
      if (libPasswords[media_root]) {
        await api.setLibraryPassword(media_root, libPasswords[media_root])
      }
      setLibMsg('已保存')
    } catch {
      setLibMsg('保存失败')
    }
    setLibSaving(null)
  }

  const doScan = async (media_root: string) => {
    clearCache()
    setScanStates(prev => ({ ...prev, [media_root]: { status: 'clearing', done: 0, total: 0 } }))
    setScanLogs(prev => ({ ...prev, [media_root]: [] }))
    setLogVisible(prev => ({ ...prev, [media_root]: true }))

    try { await api.clearLibrary(media_root) } catch {}

    setScanStates(prev => ({ ...prev, [media_root]: { status: 'scanning', done: 0, total: 0 } }))

    try { api.scan(media_root).catch(() => {}) } catch {}

    let pollCount = 0
    const timer = setInterval(async () => {
      pollCount++
      try {
        const st = await api.scanStatus(media_root)
        setScanStates(prev => ({
          ...prev,
          [media_root]: { status: st.status, done: st.done, total: st.total },
        }))
        if (st.status === 'done' || st.status === 'disabled' || pollCount > 120) {
          clearInterval(timer)
          delete scanTimers.current[media_root]
          clearCache()
        }
      } catch {}
      try {
        const log = await api.scanLog(media_root, 80)
        setScanLogs(prev => ({ ...prev, [media_root]: log.lines }))
      } catch {}
    }, 2000)
    scanTimers.current[media_root] = timer
  }

  const handleChangeAuth = async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthSaving(true)
    setAuthMsg('')
    try {
      await api.changePassword(oldUser, oldPass, newUser, newPass)
      setAuthMsg('密码已更新')
      setOldUser('')
      setOldPass('')
      setNewUser('')
      setNewPass('')
    } catch {
      setAuthMsg('更新失败（旧凭证错误）')
    }
    setAuthSaving(false)
  }

  const handleUploadPlugin = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setPluginMsg('')
    try {
      await api.uploadPlugin(file)
      setPluginMsg('插件安装成功')
      const d = await api.getPlugins()
      setPlugins(d.plugins)
    } catch {
      setPluginMsg('插件安装失败')
    }
    e.target.value = ''
  }

  const handleDeletePlugin = async (name: string) => {
    if (!confirm(`确定要删除插件 "${name}"？`)) return
    try {
      await api.deletePlugin(name)
      setPlugins(prev => prev.filter(p => p.name !== name))
    } catch {}
  }

  if (loading) return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="animate-pulse text-gray-400 text-lg">加载中...</div>
    </div>
  )

  const cardClass = "glass-panel p-5"
  const sectionTitle = "mb-4 text-lg font-semibold text-white"
  const labelClass = "mb-1.5 block text-xs text-gray-500"
  const inputClass = "glass-input w-full px-3 py-1.5 text-xs"
  const btnClass = "inline-flex items-center justify-center rounded-full px-3 py-1.5 text-xs transition-all disabled:pointer-events-none disabled:opacity-50"
  const btnPrimary = `${btnClass} border border-apple-blue/40 bg-apple-blue/80 text-white shadow-glow hover:bg-apple-blue`
  const btnDark = `${btnClass} border border-white/10 bg-white/[0.08] text-gray-300 hover:bg-white/[0.14] hover:text-white`

  return (
    <div className="space-y-5 max-w-7xl mx-auto">
      <div className="glass-panel flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-apple-blue/80">MediaTree</p>
          <h1 className="text-2xl font-bold tracking-tight text-white">设置</h1>
        </div>
        <button onClick={saveGlobal} disabled={saving} className={`${btnPrimary} disabled:opacity-50`}>
          {saving ? '保存中...' : '保存全局设置'}
        </button>
      </div>

      {msg && (
        <div className={`rounded-2xl border p-3 text-xs ${msg.includes('失败') ? 'border-red-400/20 bg-red-500/10 text-red-300' : msg.includes('成功') ? 'border-apple-mint/20 bg-apple-mint/10 text-apple-mint' : 'border-apple-mint/20 bg-apple-mint/10 text-apple-mint'}`}>{msg}</div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* 左列 */}
        <div className="space-y-5">
          {/* 界面偏好 */}
          <div className={cardClass}>
            <h2 className={sectionTitle}>界面偏好</h2>
            <label className="flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/[0.06] p-3 backdrop-blur-xl cursor-pointer">
              <div>
                <p className="text-sm font-medium text-white">无字模式</p>
                <p className="mt-0.5 text-xs text-gray-500">开启后首页仅展示影片封面图，隐藏卡片上的标题文字和目录数量。</p>
              </div>
              <button
                role="switch"
                aria-checked={hideHomeTitleText}
                onClick={() => { const v = !hideHomeTitleText; setHideHomeTitleText(v); setUiPrefs({ hideHomeTitleText: v }) }}
                className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors duration-200 focus:outline-none ${
                  hideHomeTitleText ? 'bg-apple-blue' : 'bg-white/15'
                }`}
              >
                <span
                  className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-md transition-transform duration-200 ${
                    hideHomeTitleText ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </label>
          </div>

          {/* 账号安全 */}
          <div className={cardClass}>
            <h2 className={sectionTitle}>账号安全</h2>
            <form onSubmit={handleChangeAuth} className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className={labelClass}>当前用户名</label>
                  <input type="text" value={oldUser} onChange={e => setOldUser(e.target.value)} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>当前密码</label>
                  <input type="password" value={oldPass} onChange={e => setOldPass(e.target.value)} className={inputClass} />
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className={labelClass}>新用户名</label>
                  <input type="text" value={newUser} onChange={e => setNewUser(e.target.value)} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>新密码</label>
                  <input type="password" value={newPass} onChange={e => setNewPass(e.target.value)} className={inputClass} />
                </div>
              </div>
              {authMsg && (
                <p className={`text-xs ${authMsg.includes('失败') ? 'text-red-400' : 'text-green-400'}`}>{authMsg}</p>
              )}
              <button type="submit" disabled={authSaving} className={`${btnPrimary} disabled:opacity-50`}>
                {authSaving ? '更新中...' : '修改用户名/密码'}
              </button>
            </form>
          </div>

          {/* 插件管理 */}
          <div className={cardClass}>
            <h2 className={sectionTitle}>插件管理</h2>
            <p className="text-xs text-gray-500 mb-3">上传自定义刮削器插件（.py 文件）</p>
            <div className="flex items-center gap-3 mb-4">
              <label className={`${btnPrimary} cursor-pointer`}>
                上传插件
                <input type="file" accept=".py" onChange={handleUploadPlugin} className="hidden" />
              </label>
              {pluginMsg && (
                <span className={`text-xs ${pluginMsg.includes('失败') ? 'text-red-400' : 'text-green-400'}`}>{pluginMsg}</span>
              )}
            </div>
            {plugins.filter(p => !p.builtin).length > 0 && (
              <div className="space-y-1">
                {plugins.filter(p => !p.builtin).map(p => (
                  <div key={p.name} className="flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/[0.06] p-3">
                    <div>
                      <p className="text-sm text-white">{p.label}</p>
                      <p className="text-xs text-gray-500">{p.description}</p>
                    </div>
                    <button onClick={() => handleDeletePlugin(p.name)}
                      className="rounded-full border border-red-400/20 bg-red-500/10 px-2.5 py-1 text-xs text-red-300 transition-colors hover:bg-red-500/20">
                      删除
                    </button>
                  </div>
                ))}
              </div>
            )}
            {plugins.filter(p => !p.builtin).length === 0 && (
              <p className="text-xs text-gray-600">暂无自定义插件</p>
            )}
          </div>
        </div>

        {/* 右列 */}
        <div className="space-y-5">
          {/* 刮削器设置 */}
          <div className={cardClass}>
            <h2 className={sectionTitle}>刮削器</h2>
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {[
                  { k: javdbCache, set: setJavdbCache, label: 'Javdatabase 缓存' },
                  { k: tmdbCache, set: setTmdbCache, label: 'TMDB 缓存' },
                  { k: bangumiCache, set: setBangumiCache, label: 'Bangumi 缓存' },
                ].map(({ k, set, label }) => (
                  <div key={label}>
                    <label className={labelClass}>{label}</label>
                    <div className="flex items-center gap-1">
                      <input type="number" min={1} max={720} value={k}
                        onChange={e => set(Number(e.target.value))}
                        className="glass-input w-20 px-2 py-1.5 text-xs sm:w-16" />
                      <span className="text-xs text-gray-600">小时</span>
                    </div>
                  </div>
                ))}
              </div>
              <div>
                <label className={labelClass}>请求间隔（秒）</label>
                <input type="number" min={1} max={30} value={reqInterval}
                  onChange={e => setReqInterval(Number(e.target.value))}
                  className="glass-input w-20 px-2 py-1.5 text-xs" />
              </div>
              <div className="border-t border-white/10 pt-3">
                <label className={labelClass}>TMDB API Key</label>
                <input type="text" value={tmdbKey} onChange={e => setTmdbKey(e.target.value)}
                  placeholder="去 themoviedb.org 免费申请" className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>TMDB 读访问令牌（推荐，优先使用）</label>
                <input type="password" value={tmdbToken} onChange={e => setTmdbToken(e.target.value)}
                  placeholder="Bearer Token" className={inputClass} />
              </div>

              <div className="mt-3 border-t border-white/10 pt-3">
                <h3 className="mb-3 text-sm font-semibold text-gray-400">内置刮削器</h3>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  {Object.entries(SCRAPER_META).filter(([k]) => k !== 'none').map(([key, val]) => (
                    <div key={key} className="rounded-2xl border border-white/10 bg-white/[0.06] p-3 backdrop-blur-xl">
                      <p className="text-sm font-medium text-white">{val.label}</p>
                      <p className="mt-0.5 text-xs text-gray-500">{val.desc}</p>
                      <span className="mt-2 inline-flex rounded-full border border-apple-mint/30 bg-apple-mint/10 px-2 py-0.5 text-[10px] text-apple-mint">已内置</span>
                    </div>
                  ))}
                </div>
                <p className="mt-3 text-xs text-gray-500 leading-relaxed">
                  自动会尝试判断刮削源，但可能效果不好；更推荐按媒体库类型选择 TMDB 电影、TMDB 剧集/番剧、Bangumi 或 Javdatabase。
                </p>
              </div>
            </div>
          </div>

          {/* 数据备份与恢复 */}
          <div className={cardClass}>
            <h2 className={sectionTitle}>数据备份与恢复</h2>
            <div className="flex flex-wrap items-center gap-3">
              <a href={api.backupUrl('core')} className={btnPrimary}>
                下载数据库备份
              </a>
              <a href={api.backupUrl('full')} className={btnPrimary}>
                下载完整备份 (含封面图)
              </a>
            </div>
            <p className="mt-3 text-xs text-gray-500">
              备份文件可通过下方上传恢复。完整备份包含数据库 + 所有封面图片缓存。
            </p>
            <div className="mt-3">
              <label className={labelClass}>上传备份恢复</label>
              <div className="flex items-center gap-2">
                <input type="file" accept=".db,.tar.gz,.gz"
                  onChange={async (e) => {
                    const file = e.target.files?.[0]
                    if (!file) return
                    if (!confirm(`确定要恢复备份 "${file.name}"？当前数据将被覆盖。`)) return
                    setMsg('')
                    try {
                      setSaving(true)
                      const formData = new FormData()
                      formData.append('file', file)
                      const token = localStorage.getItem('mediatree_token') || ''
                      const res = await fetch('/api/restore/upload', {
                        method: 'POST',
                        headers: token ? { Authorization: `Bearer ${token}` } : {},
                        body: formData,
                      })
                      if (res.ok) {
                        setMsg('恢复成功，即将刷新页面...')
                        clearCache()
                        setTimeout(() => window.location.reload(), 800)
                      } else setMsg('恢复失败')
                    } catch { setMsg('恢复失败') }
                    setSaving(false)
                  }}
                  className={inputClass} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 媒体库配置 */}
      <div className={cardClass}>
        <h2 className={sectionTitle}>媒体库</h2>
        <div className="space-y-2">
          {libraries.map((lib) => {
            const st = scanStates[lib.path]
            const progress = st && st.total > 0 ? Math.round((st.done / st.total) * 100) : 0
            const isScanning = st && st.status === 'scanning'
            const isClearing = st && st.status === 'clearing'
            return (
              <div key={lib.path} className="space-y-2 rounded-2xl border border-white/10 bg-white/[0.06] p-3 backdrop-blur-xl">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-white truncate">{lib.label}</p>
                    <p className="text-xs text-gray-500">{lib.movie_count} 部</p>
                  </div>
                  <select
                    value={libScraper[lib.path] || 'auto'}
                    onChange={e => setLibScraper(prev => ({ ...prev, [lib.path]: e.target.value }))}
                    className="glass-input px-2 py-1.5 text-xs text-gray-300"
                  >
                    {Object.entries(SCRAPER_META).map(([k, v]) => (
                      <option key={k} value={k}>{v.label}</option>
                    ))}
                  </select>
                  <input type="password" placeholder="密码"
                    value={libPasswords[lib.path] || ''}
                    onChange={e => setLibPasswords(prev => ({ ...prev, [lib.path]: e.target.value }))}
                    className="glass-input w-24 px-2 py-1.5 text-xs sm:w-16"
                  />
                  <button onClick={() => saveLibrary(lib.path)}
                    disabled={libSaving === lib.path}
                    className={btnPrimary + ' disabled:opacity-50'}>
                    {libSaving === lib.path ? '...' : '保存'}
                  </button>
                  <button onClick={() => doScan(lib.path)}
                    disabled={isScanning || isClearing}
                    className={`${btnDark} disabled:opacity-50`}>
                    {isClearing ? '清除中...' : isScanning ? '刮削中...' : '重新扫描'}
                  </button>
                </div>
                {(isScanning || isClearing || (st && st.status === 'done')) && (
                  <div>
                    {isClearing && (
                      <div className="flex items-center gap-2 text-xs text-gray-400">
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/10">
                          <div className="h-full animate-pulse bg-apple-yellow" style={{ width: '100%' }} />
                        </div>
                        清除已有数据...
                      </div>
                    )}
                    {isScanning && (
                      <div className="flex items-center gap-2 text-xs text-gray-400">
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/10">
                          <div className="h-full bg-apple-blue transition-all duration-500" style={{ width: `${progress}%` }} />
                        </div>
                        <span className="shrink-0">{st.done}/{st.total}</span>
                      </div>
                    )}
                    {st && st.status === 'done' && (
                      <div className="text-xs text-green-400">刮削完成</div>
                    )}
                  </div>
                )}
                {logVisible[lib.path] && scanLogs[lib.path] && scanLogs[lib.path]!.length > 0 && (
                  <div className="mt-2 max-h-48 space-y-0.5 overflow-y-auto rounded-2xl border border-white/10 bg-black/35 p-3 font-mono text-[11px] text-gray-400">
                    {scanLogs[lib.path]!.map((l, i) => (
                      <div key={i} className="break-all">{l}</div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
        {libMsg && (
          <div className={`mt-3 rounded-2xl border p-3 text-xs ${libMsg.includes('失败') ? 'border-red-400/20 bg-red-500/10 text-red-300' : 'border-apple-mint/20 bg-apple-mint/10 text-apple-mint'}`}>{libMsg}</div>
        )}
      </div>
    </div>
  )
}
