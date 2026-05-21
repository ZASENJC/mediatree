import { useState, useEffect } from 'react'
import { api, setToken, getToken } from '../api'

export default function Login({ onLogin }: { onLogin?: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [needAuth, setNeedAuth] = useState(true)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    api.authStatus().then(data => {
      setNeedAuth(data.need_auth)
      if (!data.need_auth) {
        onLogin?.()
        window.location.href = '/'
        return
      }
      const tok = getToken()
      if (tok) {
        window.location.href = '/'
        return
      }
      setChecking(false)
    }).catch(() => setChecking(false))
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username || !password) return
    setLoading(true)
    setError('')
    try {
      const data = await api.login(username, password)
      if (data.ok && data.token) {
        setToken(data.token)
        onLogin?.()
        window.location.href = '/'
      }
    } catch {
      setError('账号或密码错误')
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

  if (!needAuth) return null

  return (
    <div className="flex min-h-screen items-center justify-center bg-aurora px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 h-14 w-14 rounded-3xl border border-white/10 bg-white/[0.08] shadow-glass backdrop-blur-2xl" />
          <h1 className="text-4xl font-bold tracking-tight text-white">MediaTree</h1>
          <p className="mt-2 text-sm text-gray-500">登录以访问媒体库</p>
        </div>

        <form onSubmit={handleSubmit} className="glass-modal space-y-4 p-6">
          <div>
            <label className="mb-1.5 block text-sm text-gray-400">账号</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="输入账号"
              autoFocus
              className="glass-input w-full px-3 py-2.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm text-gray-400">密码</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="输入密码"
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
            {loading ? '登录中...' : '登录'}
          </button>
        </form>
      </div>
    </div>
  )
}
