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
      <div className="min-h-screen flex items-center justify-center bg-dark-900">
        <div className="animate-pulse text-gray-400 text-lg">检查中...</div>
      </div>
    )
  }

  if (!needAuth) return null

  return (
    <div className="min-h-screen flex items-center justify-center bg-dark-900 px-4">
      <div className="w-full max-w-sm mx-4">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white">MediaTree</h1>
          <p className="text-gray-500 mt-2 text-sm">登录以访问媒体库</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-dark-800 rounded-lg p-6 border border-dark-700 space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">账号</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="输入账号"
              autoFocus
              className="w-full px-3 py-2.5 bg-dark-700 border border-dark-600 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500 placeholder-gray-600"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">密码</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="输入密码"
              className="w-full px-3 py-2.5 bg-dark-700 border border-dark-600 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500 placeholder-gray-600"
            />
          </div>
          {error && (
            <p className="text-red-400 text-sm">{error}</p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            {loading ? '登录中...' : '登录'}
          </button>
        </form>
      </div>
    </div>
  )
}
