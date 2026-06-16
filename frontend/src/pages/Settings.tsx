import { useEffect, useState, useRef, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { marked } from 'marked'
import { api, Config, MediaRoot, LibrarySetting, UpdateCheckResult, UpdateStatus, ScraperInfo, ScraperPlugin, clearCache, getServerUrl, setServerUrl as saveServerUrl, isNativeApp, resolveApiUrl } from '../api'
import { FALLBACK_SCRAPER_OPTIONS, normalizeScraperOptions } from '../scrapers'
import { getUiPrefs, setUiPrefs, dismissUpdate } from '../store'
import {
  BUILTIN_THEMES,
  getActiveThemeName,
  getAvailableThemes,
  getCustomThemes,
  importCustomThemes,
  parseThemeImportContent,
  removeCustomTheme,
  setActiveTheme,
  type ThemePackage,
} from '../theme'

function normalizeScraper(scraper?: string) {
  return scraper === 'tmdb' ? 'tmdb_movie' : (scraper || 'auto')
}

interface ScanState {
  status: string
  done: number
  total: number
}

export default function Settings() {
  const nativeApp = isNativeApp()
  const [config, setConfig] = useState<Config | null>(null)
  const [librariesLoading, setLibrariesLoading] = useState(true)

  const [javdbEnabled, setJavdbEnabled] = useState(true)
  const [tmdbKey, setTmdbKey] = useState('')
  const [tmdbToken, setTmdbToken] = useState('')
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')
  const [serverUrlInput, setServerUrlInput] = useState(() => getServerUrl())
  const [serverMsg, setServerMsg] = useState('')
  const [hideHomeTitleText, setHideHomeTitleText] = useState(() => getUiPrefs().hideHomeTitleText || false)
  const [showSourceName, setShowSourceName] = useState(() => getUiPrefs().showSourceName || false)
  const [customThemes, setCustomThemes] = useState<ThemePackage[]>(() => getCustomThemes())
  const [activeThemeName, setActiveThemeName] = useState(() => getActiveThemeName())
  const [themeMsg, setThemeMsg] = useState('')

  const [libraries, setLibraries] = useState<(MediaRoot & { settings?: LibrarySetting })[]>([])
  const [libScraper, setLibScraper] = useState<Record<string, string>>({})
  const [libPasswords, setLibPasswords] = useState<Record<string, string>>({})
  const [libSaving, setLibSaving] = useState<string | null>(null)
  const [libMsg, setLibMsg] = useState('')
  const [scrapers, setScrapers] = useState<ScraperInfo[]>(FALLBACK_SCRAPER_OPTIONS)
  const [plugins, setPlugins] = useState<ScraperPlugin[]>([])
  const [pluginMsg, setPluginMsg] = useState('')
  const [pluginBusy, setPluginBusy] = useState<string | null>(null)

  const [scanStates, setScanStates] = useState<Record<string, ScanState>>({})
  const [scanLogs, setScanLogs] = useState<Record<string, string[]>>({})
  const [logVisible, setLogVisible] = useState<Record<string, boolean>>({})
  const scanTimers = useRef<Record<string, ReturnType<typeof setInterval>>>({})
  const libraryScraperOptions = useMemo(
    () => normalizeScraperOptions(scrapers),
    [scrapers],
  )

  // auth
  const [oldUser, setOldUser] = useState('')
  const [oldPass, setOldPass] = useState('')
  const [newUser, setNewUser] = useState('')
  const [newPass, setNewPass] = useState('')
  const [authMsg, setAuthMsg] = useState('')
  const [authSaving, setAuthSaving] = useState(false)

  // update
  const [updateChecking, setUpdateChecking] = useState(true)
  const [updateResult, setUpdateResult] = useState<UpdateCheckResult | null>(null)
  const [updatePerforming, setUpdatePerforming] = useState<string | null>(null)
  const [updateMsg, setUpdateMsg] = useState('')
  const [updateProgress, setUpdateProgress] = useState<UpdateStatus | null>(null)
  const updateStatusTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  // changelog modal
  const [changelogModal, setChangelogModal] = useState<any>(null)
  const [changelogLoading, setChangelogLoading] = useState(false)
  const [changelogBody, setChangelogBody] = useState('')
  const [changelogError, setChangelogError] = useState('')

  const openChangelog = async (v: any) => {
    setChangelogModal(v)
    setChangelogLoading(true)
    setChangelogBody('')
    setChangelogError('')
    try {
      const result = await api.getChangelog(v.display_version || v.version)
      setChangelogBody(result.body || '暂无更新日志')
    } catch {
      setChangelogError('无法获取更新日志')
    }
    setChangelogLoading(false)
  }

  const formatSize = (size?: number) => {
    if (!size || size <= 0) return '大小未知'
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
    return `${(size / 1024 / 1024).toFixed(1)} MB`
  }

  const sourceLabel = (source?: string) => {
    if (source === 'app-package') return '应用包'
    if (source === 'docker-image') return 'Docker 镜像'
    return '镜像内置'
  }

  const statusLabel = (status?: string) => {
    switch (status) {
      case 'downloading': return '下载中'
      case 'verifying': return '校验中'
      case 'installing': return '安装中'
      case 'restarting': return '重启中'
      case 'error': return '失败'
      case 'success': return '完成'
      default: return '空闲'
    }
  }

  const normalizeVersion = (version?: string) => (version || '').replace(/^v/i, '')
  const compareVersions = (a?: string, b?: string) => {
    const left = normalizeVersion(a).split(/[.-]/).map(part => Number.parseInt(part, 10))
    const right = normalizeVersion(b).split(/[.-]/).map(part => Number.parseInt(part, 10))
    const length = Math.max(left.length, right.length)
    for (let i = 0; i < length; i++) {
      const leftPart = Number.isFinite(left[i]) ? left[i] : 0
      const rightPart = Number.isFinite(right[i]) ? right[i] : 0
      if (leftPart !== rightPart) return leftPart > rightPart ? 1 : -1
    }
    return 0
  }
  const isDockerSetupError = (message?: string) => {
    const text = message || ''
    return text.includes('Docker CLI') || text.includes('Docker socket') || text.includes('/var/run/docker.sock')
  }
  const getDockerUpdateShortError = (message?: string) => {
    if (!isDockerSetupError(message)) return message || '完整镜像更新失败'
    return '当前容器无法直接更新镜像，请在宿主机执行 docker compose pull && docker compose up -d。'
  }
  const getDockerUpdateGuide = (message?: string) => {
    const text = (message || '').trim()
    if (!text) return ''
    if (text.includes('Docker CLI')) {
      return '当前镜像缺少 Docker CLI，不能在设置页替换容器。请在宿主机执行 docker compose pull && docker compose up -d。'
    }
    if (text.includes('Docker socket') || text.includes('/var/run/docker.sock')) {
      return '当前容器没有挂载 Docker socket，不能在设置页替换容器。请在宿主机执行 docker compose pull && docker compose up -d。'
    }
    return ''
  }

  const stopUpdatePolling = () => {
    if (updateStatusTimer.current) {
      clearInterval(updateStatusTimer.current)
      updateStatusTimer.current = null
    }
  }

  const startUpdatePolling = (targetVersion: string) => {
    stopUpdatePolling()
    let attempts = 0
    const poll = async () => {
      attempts++
      try {
        const status = await api.updateStatus()
        setUpdateProgress(status)
        if (status.status === 'error') {
          setUpdateMsg(isDockerSetupError(status.message) ? '' : `更新失败: ${status.message || '未知错误'}`)
          stopUpdatePolling()
          return
        }
        if (status.status === 'success') {
          if (!targetVersion || normalizeVersion(status.version) === normalizeVersion(targetVersion)) {
            clearCache()
            window.location.reload()
          }
          return
        }
        if (status.status === 'restarting') {
          try {
            const version = await api.getVersion()
            if (normalizeVersion(version.version) === normalizeVersion(targetVersion)) {
              clearCache()
              window.location.reload()
            }
          } catch {}
        }
      } catch {
        if (attempts >= 40) {
          setUpdateMsg('服务重启中，请稍后手动刷新页面查看最新版本')
          stopUpdatePolling()
        }
      }
    }
    poll()
    updateStatusTimer.current = setInterval(poll, 1500)
  }

  const applyUpdateCheckResult = (result: UpdateCheckResult, freshMessage = false) => {
    setUpdateResult(result)
    if (result.has_update) {
      setUpdateMsg(`发现新版本 ${result.versions[0]?.display_version || ''}`)
    } else if (freshMessage) {
      setUpdateMsg('已是最新版本')
    }
  }

  const checkUpdates = async (freshMessage = false) => {
    setUpdateChecking(true)
    if (freshMessage) setUpdateMsg('正在检查更新...')
    try {
      const [result, status] = await Promise.all([
        api.checkForUpdates(),
        api.updateStatus().catch(() => null),
      ])
      applyUpdateCheckResult(result, freshMessage)
      if (status) setUpdateProgress(status)
    } catch {
      if (freshMessage) {
        setUpdateMsg('检查更新失败')
        setUpdateResult(null)
      }
    } finally {
      setUpdateChecking(false)
    }
  }

  const loadScrapers = async () => {
    try {
      const data = await api.scrapers()
      setScrapers(data.items || [])
    } catch {
      setScrapers(FALLBACK_SCRAPER_OPTIONS)
    }
  }

  const loadPlugins = async () => {
    try {
      const data = await api.scraperPlugins()
      setPlugins(data.items || [])
    } catch {
      setPlugins([])
    }
  }

  const reloadScraperState = async () => {
    await Promise.all([loadScrapers(), loadPlugins()])
  }


  useEffect(() => {
    api.getConfig().then(d => {
      setConfig(d)
      setJavdbEnabled(d.javdb_enabled)
      setTmdbKey(d.tmdb_api_key || '')
      setTmdbToken(d.tmdb_access_token || '')
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
    }).catch(() => {}).finally(() => setLibrariesLoading(false))

    reloadScraperState()

    // 自动检查更新
    checkUpdates(true)

    return () => {
      // Clear all scan polling timers on unmount
      for (const timer of Object.values(scanTimers.current)) {
        clearInterval(timer)
      }
      scanTimers.current = {}
      stopUpdatePolling()
    }
  }, [])

  const visibleUpdateVersions = useMemo(
    () => (updateResult?.versions || []).slice(0, 3),
    [updateResult]
  )

  const dockerUpdateGuide = useMemo(() => {
    if (updateProgress?.status === 'error' && updateProgress.update_type === 'docker-image') return ''
    const statusMessage = updateProgress?.status === 'error' ? updateProgress.message : ''
    return getDockerUpdateGuide(statusMessage || updateMsg)
  }, [updateMsg, updateProgress])

  const saveGlobal = async () => {
    setSaving(true)
    setMsg('')
    try {
      setUiPrefs({ ...getUiPrefs(), hideHomeTitleText })
      await api.updateConfig({
        javdb_enabled: javdbEnabled,
        tmdb_api_key: tmdbKey,
        tmdb_access_token: tmdbToken,
      })
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

  const uploadPlugin = async (file?: File) => {
    if (!file) return
    setPluginBusy('install')
    setPluginMsg('')
    try {
      await api.installScraperPlugin(file)
      await reloadScraperState()
      setPluginMsg('插件已安装，默认未启用')
    } catch (err) {
      setPluginMsg(`插件安装失败：${err instanceof Error ? err.message : '请查看后端日志'}`)
    } finally {
      setPluginBusy(null)
    }
  }

  const themeOptions = useMemo(
    () => getAvailableThemes(customThemes),
    [customThemes],
  )

  const refreshCustomThemes = () => {
    setCustomThemes(getCustomThemes())
  }

  const chooseTheme = (name: string) => {
    const applied = setActiveTheme(name)
    setActiveThemeName(applied.name)
    setThemeMsg(`已切换到 ${applied.label}`)
  }

  const importThemeFile = async (file?: File) => {
    if (!file) return
    setThemeMsg('')
    try {
      const result = parseThemeImportContent(await file.text(), file.name)
      const importedThemes = importCustomThemes(result.themes)
      refreshCustomThemes()
      const nextName = result.activeTheme && result.themes.some(theme => theme.name === result.activeTheme)
        ? result.activeTheme
        : result.themes[result.themes.length - 1]?.name
      if (nextName) {
        const applied = setActiveTheme(nextName)
        setActiveThemeName(applied.name)
      }
      setThemeMsg(`已导入 ${importedThemes.length} 个外观主题`)
    } catch (err) {
      setThemeMsg(`主题导入失败：${err instanceof Error ? err.message : '文件格式错误'}`)
    }
  }

  const deleteTheme = (theme: ThemePackage) => {
    if (theme.builtin) return
    if (!confirm(`确定删除主题 "${theme.label}"？`)) return
    removeCustomTheme(theme.name)
    refreshCustomThemes()
    if (activeThemeName === theme.name) {
      const applied = setActiveTheme(BUILTIN_THEMES[0].name)
      setActiveThemeName(applied.name)
    }
    setThemeMsg('主题已删除')
  }

  const togglePlugin = async (plugin: ScraperPlugin) => {
    setPluginBusy(plugin.name)
    setPluginMsg('')
    try {
      if (plugin.enabled) await api.disableScraperPlugin(plugin.name)
      else await api.enableScraperPlugin(plugin.name)
      await reloadScraperState()
      setPluginMsg(plugin.enabled ? '插件已停用' : '插件已启用')
    } catch (err) {
      setPluginMsg(`操作失败：${err instanceof Error ? err.message : '请查看后端日志'}`)
    } finally {
      setPluginBusy(null)
    }
  }

  const removePlugin = async (plugin: ScraperPlugin) => {
    if (!confirm(`确定删除刮削器插件 "${plugin.label || plugin.name}"？`)) return
    setPluginBusy(plugin.name)
    setPluginMsg('')
    try {
      await api.deleteScraperPlugin(plugin.name)
      await reloadScraperState()
      setPluginMsg('插件已删除')
    } catch (err) {
      setPluginMsg(`删除失败：${err instanceof Error ? err.message : '请确认没有媒体库正在使用该插件'}`)
    } finally {
      setPluginBusy(null)
    }
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

  const handleSaveServerUrl = () => {
    const normalized = saveServerUrl(serverUrlInput)
    setServerUrlInput(normalized)
    if (!normalized) {
      setServerMsg('请输入服务器地址')
      return
    }
    setServerMsg('服务器地址已保存，正在重新连接...')
    window.setTimeout(() => window.location.reload(), 500)
  }

  const cardClass = "glass-panel p-5"
  const sectionTitle = "mb-4 text-lg font-semibold text-white"
  const labelClass = "mb-1.5 block text-xs text-gray-500"
  const inputClass = "glass-input w-full px-3 py-1.5 text-xs"
  const btnClass = "inline-flex items-center justify-center rounded-full px-3 py-1.5 text-xs transition-all disabled:pointer-events-none disabled:opacity-50"
  const btnPrimary = `${btnClass} border border-apple-blue/40 bg-apple-blue/80 text-white shadow-glow hover:bg-apple-blue`
  const btnDark = `${btnClass} border border-white/10 bg-white/[0.08] text-gray-300 hover:bg-white/[0.14] hover:text-white`

  return (
    <div className="w-full min-w-0 space-y-5">
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
          {nativeApp && (
            <div className={cardClass}>
              <h2 className={sectionTitle}>服务器</h2>
              <label className={labelClass}>MediaTree 后端地址</label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <input
                  type="text"
                  value={serverUrlInput}
                  onChange={e => setServerUrlInput(e.target.value)}
                  placeholder="http://192.168.1.10:27580"
                  autoCapitalize="none"
                  autoCorrect="off"
                  className={inputClass}
                />
                <button type="button" onClick={handleSaveServerUrl} className={`${btnPrimary} shrink-0`}>
                  保存并重连
                </button>
              </div>
              {serverMsg && (
                <p className={`mt-2 text-xs ${serverMsg.includes('请输入') ? 'text-red-400' : 'text-green-400'}`}>{serverMsg}</p>
              )}
            </div>
          )}

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
                onClick={() => { const v = !hideHomeTitleText; setHideHomeTitleText(v); setUiPrefs({ ...getUiPrefs(), hideHomeTitleText: v }) }}
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
            <label className="mt-3 flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/[0.06] p-3 backdrop-blur-xl cursor-pointer">
              <div>
                <p className="text-sm font-medium text-white">使用源文件名称</p>
                <p className="mt-0.5 text-xs text-gray-500">开启后首页媒体库卡片显示源文件夹名称；关闭则显示刮削到的标题。</p>
              </div>
              <button
                role="switch"
                aria-checked={showSourceName}
                onClick={() => { const v = !showSourceName; setShowSourceName(v); setUiPrefs({ ...getUiPrefs(), showSourceName: v }) }}
                className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors duration-200 focus:outline-none ${
                  showSourceName ? 'bg-apple-blue' : 'bg-white/15'
                }`}
              >
                <span
                  className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-md transition-transform duration-200 ${
                    showSourceName ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </label>

            <div className="mt-4 border-t border-white/10 pt-4">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-semibold text-white">外观主题</h3>
                  <p className="mt-0.5 text-xs text-gray-500">导入主题文件即可更换整体外观。主题只保存在此浏览器。</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <label className={`${btnPrimary} cursor-pointer`}>
                    导入主题
                    <input
                      type="file"
                      accept=".json,application/json"
                      className="hidden"
                      onChange={e => {
                        importThemeFile(e.target.files?.[0])
                        e.currentTarget.value = ''
                      }}
                    />
                  </label>
                </div>
              </div>
              {themeMsg && (
                <p className={`mb-3 text-xs ${themeMsg.includes('失败') ? 'text-red-400' : 'text-apple-mint'}`}>
                  {themeMsg}
                </p>
              )}
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {themeOptions.map(theme => {
                  const active = theme.name === activeThemeName
                  const colorSchemeLabel = theme.colorScheme === 'light'
                    ? '浅色外观'
                    : theme.colorScheme === 'auto'
                      ? '跟随系统'
                      : '深色外观'
                  return (
                    <div
                      key={theme.name}
                      className={`rounded-2xl border p-3 backdrop-blur-xl transition-colors ${
                        active
                          ? 'border-apple-blue/40 bg-apple-blue/15'
                          : 'border-white/10 bg-white/[0.06]'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="mb-2 flex items-center gap-1.5">
                            <span
                              className="h-4 w-4 shrink-0 rounded-full border border-white/20"
                              style={{ background: theme.tokens['--mt-color-accent'] || '#0A84FF' }}
                            />
                            <p className="truncate text-sm font-medium text-white">{theme.label}</p>
                          </div>
                          <p className="text-[11px] text-gray-500">
                            {theme.builtin ? '内置主题' : '我的主题'} · {colorSchemeLabel}
                          </p>
                          {theme.description && (
                            <p className="mt-1 line-clamp-2 text-xs text-gray-500">{theme.description}</p>
                          )}
                        </div>
                        <div className="flex shrink-0 flex-col gap-1.5">
                          <button
                            type="button"
                            onClick={() => chooseTheme(theme.name)}
                            disabled={active}
                            className={`${active ? btnPrimary : btnDark} px-2 py-1 text-[11px] disabled:opacity-70`}
                          >
                            {active ? '使用中' : '切换'}
                          </button>
                          {!theme.builtin && (
                            <button
                              type="button"
                              onClick={() => deleteTheme(theme)}
                              className={`${btnDark} px-2 py-1 text-[11px]`}
                            >
                              删除
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
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

          {/* 媒体库配置 */}
          <div className={cardClass}>
            <h2 className={sectionTitle}>媒体库</h2>
            <div className="space-y-2">
            {librariesLoading && (
              <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-3 text-xs text-gray-500">
                媒体库加载中...
              </div>
            )}
            {[...libraries].sort((a, b) => a.label.localeCompare(b.label, 'zh-CN')).map((lib) => {
            const st = scanStates[lib.path]
            const progress = st && st.total > 0 ? Math.round((st.done / st.total) * 100) : 0
            const isScanning = st && st.status === 'scanning'
            const isClearing = st && st.status === 'clearing'
            const selectedScraper = libScraper[lib.path] || 'auto'
            const selectedScraperAvailable = libraryScraperOptions.some(item => item.name === selectedScraper)
            return (
              <div key={lib.path} className="space-y-2 rounded-2xl border border-white/10 bg-white/[0.06] p-3 backdrop-blur-xl">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-white truncate">{lib.label}</p>
                    <p className="text-xs text-gray-500">{lib.movie_count} 部</p>
                  </div>
                  <select
                    value={selectedScraperAvailable ? selectedScraper : ''}
                    onChange={e => setLibScraper(prev => ({ ...prev, [lib.path]: e.target.value }))}
                    disabled={libraryScraperOptions.length === 0}
                    className="glass-input px-2 py-1.5 text-xs text-gray-300"
                  >
                    {libraryScraperOptions.length === 0 ? (
                      <option value="">无可用刮削器</option>
                    ) : (
                      <>
                        {!selectedScraperAvailable && (
                          <option value="" disabled>当前刮削器不可用</option>
                        )}
                        {libraryScraperOptions.map(item => (
                          <option key={item.name} value={item.name}>
                            {item.label || item.name}
                          </option>
                        ))}
                      </>
                    )}
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

        {/* 右列 */}
        <div className="space-y-5">
          {/* 刮削器设置 */}
          <div className={cardClass}>
            <h2 className={sectionTitle}>刮削器</h2>
            <div className="space-y-3">
              <div>
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
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-gray-400">插件管理</h3>
                  <label className={`${btnDark} cursor-pointer`}>
                    {pluginBusy === 'install' ? '安装中...' : '上传插件'}
                    <input
                      type="file"
                      accept=".zip"
                      disabled={pluginBusy === 'install'}
                      className="hidden"
                      onChange={e => {
                        const file = e.target.files?.[0]
                        uploadPlugin(file)
                        e.currentTarget.value = ''
                      }}
                    />
                  </label>
                </div>
                <p className="mb-3 text-xs text-gray-500">
                  插件包必须是包含 plugin.json 的 zip。上传的插件是受信任本地代码，安装后需手动启用。
                </p>
                {pluginMsg && (
                  <p className={`mb-3 text-xs ${pluginMsg.includes('失败') ? 'text-red-400' : 'text-apple-mint'}`}>
                    {pluginMsg}
                  </p>
                )}
                <div className="space-y-2">
                  {plugins.length === 0 && (
                    <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-3 text-xs text-gray-500">
                      暂无已安装插件
                    </div>
                  )}
                  {plugins.map(plugin => (
                    <div key={plugin.name} className="flex flex-wrap items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.06] p-3 backdrop-blur-xl">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-white">{plugin.label || plugin.name}</p>
                        <p className="mt-0.5 text-xs text-gray-500">
                          {plugin.name} · v{plugin.version} · {plugin.supported_media_types.join(', ') || 'unknown'}
                        </p>
                        {plugin.description && <p className="mt-1 text-xs text-gray-500">{plugin.description}</p>}
                        {plugin.error && <p className="mt-1 text-xs text-red-400">{plugin.error}</p>}
                      </div>
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] ${plugin.enabled ? 'border-apple-mint/30 bg-apple-mint/10 text-apple-mint' : 'border-white/10 bg-white/[0.06] text-gray-400'}`}>
                        {plugin.enabled ? '已启用' : '未启用'}
                      </span>
                      <button
                        type="button"
                        onClick={() => togglePlugin(plugin)}
                        disabled={pluginBusy === plugin.name}
                        className={btnDark}
                      >
                        {pluginBusy === plugin.name ? '处理中...' : plugin.enabled ? '停用' : '启用'}
                      </button>
                      <button
                        type="button"
                        onClick={() => removePlugin(plugin)}
                        disabled={pluginBusy === plugin.name}
                        className={btnDark}
                      >
                        删除
                      </button>
                    </div>
                  ))}
                </div>
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
                      const res = await fetch(resolveApiUrl('/api/restore/upload'), {
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

          {/* 更新 */}
          <div className={cardClass}>
            <div className="flex items-center justify-between mb-4">
              <h2 className={sectionTitle + " mb-0"}>更新</h2>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => checkUpdates(true)}
                  disabled={updateChecking}
                  className={btnDark}
                >
                  {updateChecking ? '检查中...' : '检查更新'}
                </button>
              </div>
            </div>

            <div className="mb-3 grid grid-cols-1 gap-2 text-xs text-gray-500 sm:grid-cols-2">
              <p>
                当前版本：
                <span className="text-white font-medium">
                  {updateResult?.current_version || '...'}
                </span>
              </p>
              <p>
                运行来源：
                <span className="text-white font-medium">
                  {sourceLabel(updateResult?.current_source)}
                </span>
              </p>
              <p>
                镜像内置版本：
                <span className="text-white font-medium">
                  {updateResult?.base_version || '...'}
                </span>
              </p>
            </div>

            {updateResult?.latest_sync_warning && (
              <div className="mb-3 rounded-2xl border border-apple-yellow/30 bg-apple-yellow/10 px-3 py-2 text-xs text-apple-yellow">
                <p className="font-medium text-apple-yellow">DockerHub latest 尚未同步</p>
                <p className="mt-1 text-yellow-100/90">
                  {updateResult.latest_sync_warning.message}
                </p>
                <p className="mt-2 rounded-xl border border-apple-yellow/20 bg-black/20 px-2 py-1 font-mono text-[11px] leading-relaxed text-yellow-100">
                  {updateResult.latest_sync_warning.action}
                </p>
              </div>
            )}

            {updateMsg && (
              <p className={`mb-3 text-xs ${updateMsg.includes('失败') ? 'text-red-400' : updateMsg.includes('最新') ? 'text-apple-mint' : 'text-apple-yellow'}`}>
                {updateMsg}
              </p>
            )}

            {dockerUpdateGuide && (
              <div className="mb-3 rounded-2xl border border-red-400/20 bg-red-500/10 px-3 py-2 text-xs text-red-200">
                {dockerUpdateGuide}
              </div>
            )}

            {visibleUpdateVersions.length > 0 && (
              <div className="space-y-2">
                {visibleUpdateVersions.map((v: any, i: number) => {
                  const result = updateResult
                  if (!result) return null
                  const versionKey = normalizeVersion(v.version)
                  const dockerTargetVersion = v.required_image_version || v.version
                  const dockerTargetKey = normalizeVersion(dockerTargetVersion)
                  const currentVersion = result.effective_version || result.current_version
                  const versionPosition = compareVersions(versionKey, currentVersion)
                  const isCurrent = versionPosition === 0
                  const isOlderVersion = versionPosition < 0
                  const activeUpdate = updateProgress
                    && !isCurrent
                    && (
                      normalizeVersion(updateProgress.version) === versionKey
                      || (v.requires_image_update && normalizeVersion(updateProgress.version) === dockerTargetKey)
                    )
                    && updateProgress.status !== 'idle'
                    && updateProgress.status !== 'success'
                    ? updateProgress
                    : null
                  const isDockerUpdate = Boolean(activeUpdate && (activeUpdate.update_type === 'docker-image' || v.requires_image_update))
                  const isAppUpdate = Boolean(activeUpdate && !isDockerUpdate)
                  const progressPercent = activeUpdate?.total
                    ? Math.min(100, Math.round((activeUpdate.downloaded / activeUpdate.total) * 100))
                    : 0
                  const rollbackVersion = normalizeVersion(updateProgress?.rollback_version)
                  const canRollbackToThis = Boolean(updateProgress?.can_rollback && rollbackVersion && rollbackVersion === versionKey && !isCurrent)
                  const isBusy = updatePerforming === v.version || Boolean(activeUpdate && activeUpdate.status !== 'error')
                  const dockerErrorGuide = activeUpdate?.status === 'error' ? getDockerUpdateGuide(activeUpdate.message) : ''
                  return (
                    <div key={v.version}
                         className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.06] p-3 backdrop-blur-xl">
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-white truncate">
                            {v.display_version || v.version}
                            {isCurrent && (
                              <span className="ml-2 inline-flex items-center rounded-full border border-white/20 bg-white/10 px-2 py-0.5 text-[10px] text-gray-400">
                                当前
                              </span>
                            )}
                            {!isCurrent && i === 0 && result.has_update && (
                              <span className="ml-2 inline-flex items-center rounded-full border border-green-400/30 bg-green-500/15 px-2 py-0.5 text-[10px] text-green-400">
                                最新
                              </span>
                            )}
                          </p>
                          {v.published_at && (
                            <p className="mt-0.5 text-xs text-gray-500 truncate">
                              {new Date(v.published_at).toLocaleDateString('zh-CN')}
                            </p>
                          )}
                          <p className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-gray-500">
                            <span className={`inline-flex rounded-full border px-2 py-0.5 ${
                              v.requires_image_update
                                ? 'border-apple-yellow/30 bg-apple-yellow/10 text-apple-yellow'
                                : 'border-apple-mint/30 bg-apple-mint/10 text-apple-mint'
                            }`}>
                              {v.requires_image_update ? '需要完整镜像更新' : '应用包更新'}
                            </span>
                            {!v.requires_image_update && (
                              <span>{formatSize(v.size)}</span>
                            )}
                            {v.reason && (
                              <span className="truncate">{v.reason}</span>
                            )}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            onClick={() => openChangelog(v)}
                            className="text-xs text-apple-blue hover:text-white transition-colors"
                          >
                            更新日志
                          </button>
                          {canRollbackToThis ? (
                            <button
                              onClick={async () => {
                                if (!confirm(`确定要回滚到 ${v.display_version || v.version} 吗？服务将自动重启。`)) return
                                setUpdatePerforming(v.version)
                                setUpdateMsg('')
                                setUpdateProgress({
                                  status: 'restarting',
                                  version: v.version,
                                  downloaded: 0,
                                  total: 0,
                                  message: '正在回滚到此版本...',
                                  update_type: 'app-package',
                                })
                                try {
                                  const res = await api.rollbackUpdate()
                                  if (res.ok === false) throw new Error((res as any).error || '回滚失败')
                                  setUpdateMsg(res.message || '已触发回滚')
                                  startUpdatePolling(res.version || v.version)
                                } catch (e: any) {
                                  setUpdateMsg(`回滚失败: ${e.message || '未知错误'}`)
                                }
                                setUpdatePerforming(null)
                              }}
                              disabled={isBusy}
                              className={`${btnDark} text-xs px-2 py-1 disabled:opacity-50`}
                            >
                              {updatePerforming === v.version ? '回滚中...' : '回滚此版本'}
                            </button>
                          ) : !isCurrent && !v.requires_image_update ? (
                            <button
                              onClick={async () => {
                                if (!confirm(`确定要${isOlderVersion ? '回滚到' : '切换到'} ${v.display_version || v.version} 吗？容器将自动重启。`)) return
                                setUpdatePerforming(v.version)
                                setUpdateMsg('')
                                setUpdateProgress({
                                  status: 'downloading',
                                  version: v.version,
                                  downloaded: 0,
                                  total: 0,
                                  message: isOlderVersion ? '正在发起版本回滚...' : '正在发起应用包更新...',
                                  update_type: 'app-package',
                                })
                                startUpdatePolling(v.version)
                                try {
                                  const res = await api.performUpdate(v.version, 'app-package')
                                  if (res.ok === false) throw new Error(res.error || (isOlderVersion ? '回滚失败' : '更新失败'))
                                  setUpdateMsg(res.message || (isOlderVersion ? '回滚已触发' : '更新已触发'))
                                  dismissUpdate(v.version)
                                } catch (e: any) {
                                  setUpdateMsg(`${isOlderVersion ? '回滚' : '更新'}失败: ${e.message || '未知错误'}`)
                                }
                                setUpdatePerforming(null)
                              }}
                              disabled={isBusy}
                              className={`${btnPrimary} text-xs px-2 py-1 disabled:opacity-50`}
                            >
                              {updatePerforming === v.version
                                ? (isOlderVersion ? '回滚中...' : '更新中...')
                                : (isOlderVersion ? '回滚此版本' : '下载并更新')}
                            </button>
                          ) : !isCurrent && v.requires_image_update ? (
                            <button
                              onClick={async () => {
                                if (!confirm(`确定要执行完整镜像更新到 ${dockerTargetVersion} 吗？该操作需要已挂载 Docker socket。`)) return
                                setUpdatePerforming(v.version)
                                setUpdateMsg('')
                                setUpdateProgress({
                                  status: 'installing',
                                  version: dockerTargetVersion,
                                  downloaded: 0,
                                  total: 0,
                                  message: '正在发起完整镜像更新...',
                                  update_type: 'docker-image',
                                  logs: [],
                                })
                                startUpdatePolling(dockerTargetVersion)
                                try {
                                  const res = await api.performUpdate(dockerTargetVersion, 'docker-image')
                                  if (res.ok === false) throw new Error(res.error || '完整镜像更新失败')
                                  setUpdateMsg(res.message || '完整镜像更新已触发')
                                  dismissUpdate(dockerTargetVersion)
                                } catch (e: any) {
                                  const message = e.message || '未知错误'
                                  if (message.includes('Failed to fetch')) {
                                    setUpdateMsg('完整镜像更新已触发，服务可能正在重启')
                                  } else if (isDockerSetupError(message)) {
                                    setUpdateMsg('')
                                  } else {
                                    setUpdateMsg(`完整镜像更新失败: ${message}`)
                                  }
                                }
                                setUpdatePerforming(null)
                              }}
                              disabled={isBusy}
                              title={v.reason || '该版本需要完整镜像更新'}
                              className={`${btnDark} text-xs px-2 py-1 disabled:opacity-50`}
                            >
                              {updatePerforming === v.version ? '更新中...' : '完整镜像更新'}
                            </button>
                          ) : null}
                        </div>
                      </div>

                      {isAppUpdate && activeUpdate && (
                        <div className="rounded-2xl border border-white/10 bg-black/20 p-3 text-xs text-gray-300">
                          <div className="mb-2 flex items-center justify-between gap-3">
                            <span>{statusLabel(activeUpdate.status)}</span>
                            <span className="text-gray-500">
                              {activeUpdate.total > 0 ? `${progressPercent}%` : ''}
                            </span>
                          </div>
                          <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                            <div
                              className={`h-full rounded-full transition-all ${
                                activeUpdate.status === 'error' ? 'bg-red-400' : activeUpdate.total > 0 ? 'bg-apple-blue' : 'animate-pulse bg-apple-blue'
                              }`}
                              style={{ width: activeUpdate.total > 0 ? `${progressPercent}%` : '100%' }}
                            />
                          </div>
                          {activeUpdate.message && (
                            <p className={activeUpdate.status === 'error' ? 'mt-2 text-red-400' : 'mt-2 text-gray-500'}>
                              {activeUpdate.message}
                            </p>
                          )}
                        </div>
                      )}

                      {isDockerUpdate && activeUpdate && (
                        <div className="max-h-48 space-y-0.5 overflow-y-auto rounded-2xl border border-white/10 bg-black/35 p-3 font-mono text-[11px] text-gray-400">
                          <div className={activeUpdate.status === 'error' ? 'mb-1 text-red-400' : 'mb-1 text-gray-300'}>
                            {statusLabel(activeUpdate.status)}
                            {(dockerErrorGuide || activeUpdate.message) ? ` · ${dockerErrorGuide || getDockerUpdateShortError(activeUpdate.message)}` : ''}
                          </div>
                          {activeUpdate.status === 'error' ? null : (activeUpdate.logs || []).length > 0 ? (
                            activeUpdate.logs!.map((line, logIndex) => (
                              <div key={logIndex} className="break-all">{line}</div>
                            ))
                          ) : (
                            <div>等待 Docker 输出...</div>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {/* CHANGELOG Modal */}
            {changelogModal && createPortal(
              <div className="fixed inset-0 z-[70] bg-black/40 backdrop-blur-2xl flex items-center justify-center p-4"
                   onClick={() => setChangelogModal(null)}>
                <div className="glass-modal max-w-2xl w-full max-h-[80vh] flex flex-col rounded-3xl"
                     onClick={e => e.stopPropagation()}>
                  <div className="flex items-center justify-between p-5 border-b border-white/10 shrink-0">
                    <h3 className="text-lg font-semibold text-white">更新日志 — {changelogModal.display_version || changelogModal.version}</h3>
                    <button
                      onClick={() => setChangelogModal(null)}
                      className="inline-flex items-center justify-center w-8 h-8 rounded-full border border-white/10 text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                  </div>
                  <div className="flex-1 overflow-y-auto p-5">
                    {changelogLoading ? (
                      <div className="flex items-center justify-center py-12">
                        <div className="animate-pulse text-gray-400 text-sm">加载中...</div>
                      </div>
                    ) : changelogError ? (
                      <p className="text-sm text-red-400">{changelogError}</p>
                    ) : (
                      <div className="changelog-md text-sm text-gray-300 leading-relaxed"
                        dangerouslySetInnerHTML={{ __html: marked.parse(changelogBody) as string }} />
                    )}
                  </div>
                </div>
              </div>,
              document.body
            )}
          </div>

        </div>
      </div>
    </div>
  )
}
