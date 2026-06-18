import { useState } from 'react'
import { api, type MediaRoot } from '../api'

interface PasswordModalProps {
  target: MediaRoot
  onOk: (path: string) => void
  onCancel: () => void
}

export default function PasswordModal({ target, onOk, onCancel }: PasswordModalProps) {
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
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4 backdrop-blur-2xl">
      <div className="glass-modal w-full max-w-xs p-6">
        <div className="mb-4 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-apple-yellow/10">
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
    </div>
  )
}
