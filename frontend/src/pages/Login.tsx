import { useState, useEffect } from 'react'
import { api, setToken, getToken, getServerUrl, setServerUrl, isNativeApp } from '../api'

export default function Login({ onLogin }: { onLogin?: () => void }) {
  const nativeApp = isNativeApp()
  const [serverUrlInput, setServerUrlInput] = useState(() => getServerUrl())
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [needAuth, setNeedAuth] = useState(true)
  const [authConfigured, setAuthConfigured] = useState(true)
  const [checking, setChecking] = useState(true)
  const [loggedOut, setLoggedOut] = useState(
    () => new URLSearchParams(window.location.search).has('logout')
  )
  const setupMode = needAuth && !authConfigured

  useEffect(() => {
    if (nativeApp && !getServerUrl()) {
      setChecking(false)
      return
    }
    api.authStatus().then(data => {
      setNeedAuth(data.need_auth)
      setAuthConfigured(data.auth_configured)
      if (!data.need_auth) {
        if (!loggedOut) {
          onLogin?.()
          window.location.href = '/'
          return
        }
        setChecking(false)
        return
      }
      const tok = getToken()
      if (tok && data.auth_configured) {
        window.location.href = '/'
        return
      }
      setChecking(false)
    }).catch(() => setChecking(false))
  }, [nativeApp])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (nativeApp) {
      const normalized = setServerUrl(serverUrlInput)
      setServerUrlInput(normalized)
      if (!normalized) {
        setError('请输入服务器地址')
        return
      }
    }
    if (!nativeApp && (!username || !password)) return
    setLoading(true)
    setError('')
    try {
      const status = await api.authStatus()
      setNeedAuth(status.need_auth)
      setAuthConfigured(status.auth_configured)
      if (!status.need_auth) {
        onLogin?.()
        window.location.href = '/'
        return
      }
      if (!username || !password) {
        setError('请输入账号和密码')
        setLoading(false)
        return
      }
      if (!status.auth_configured && password.length < 8) {
        setError('密码至少需要 8 位')
        setLoading(false)
        return
      }
      const data = status.auth_configured
        ? await api.login(username, password)
        : await api.setupAuth(username, password)
      if (data.ok) {
        setToken(data.token || '')
        await api.ensureMediaToken(true).catch(() => {})
        onLogin?.()
        window.location.href = '/'
      }
    } catch (err) {
      setError(err instanceof TypeError ? '无法连接服务器' : (setupMode ? '初始化失败' : '账号或密码错误'))
    }
    setLoading(false)
  }

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-aurora">
        <div className="animate-pulse text-lg text-gray-400">检查中...</div>
      </div>
    )
  }

  if (!needAuth && !loggedOut) return null

  return (
    <div className="flex min-h-screen items-center justify-center bg-aurora px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <img
            src="/login-logo.png"
            alt="MediaTree"
            className="mx-auto mb-4 h-16 w-16 object-contain drop-shadow-[0_0_18px_rgba(190,255,170,0.45)]"
          />
          <h1 className="text-4xl font-bold tracking-tight text-white">MediaTree</h1>
          <p className="mt-2 text-sm text-gray-500">{setupMode ? '创建管理员账号后开始使用' : '登录以访问媒体库'}</p>
        </div>

        <form onSubmit={handleSubmit} className="glass-modal space-y-4 p-6">
          {nativeApp && (
            <div>
              <label className="mb-1.5 block text-sm text-gray-400">服务器地址</label>
              <input
                type="text"
                value={serverUrlInput}
                onChange={e => setServerUrlInput(e.target.value)}
                placeholder="http://192.168.1.10:27580"
                autoCapitalize="none"
                autoCorrect="off"
                className="glass-input w-full px-3 py-2.5 text-sm"
              />
              <p className="mt-1.5 text-xs text-gray-500">填写正在运行的 MediaTree 后端地址。</p>
            </div>
          )}
          <div>
            <label className="mb-1.5 block text-sm text-gray-400">{setupMode ? '管理员账号' : '账号'}</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder={setupMode ? '创建管理员账号' : '输入账号'}
              autoFocus
              className="glass-input w-full px-3 py-2.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm text-gray-400">{setupMode ? '管理员密码' : '密码'}</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder={setupMode ? '至少 8 位密码' : '输入密码'}
              className="glass-input w-full px-3 py-2.5 text-sm"
            />
          </div>
          {error && (
            <p className="text-sm text-red-400">{error}</p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="glass-button-primary w-full py-2.5 text-sm"
          >
            {loading ? '连接中...' : (setupMode ? '创建并进入' : (nativeApp ? '连接 / 登录' : '登录'))}
          </button>
        </form>
      </div>
    </div>
  )
}
