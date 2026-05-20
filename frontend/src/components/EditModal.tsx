import { useState } from 'react'
import { api, Movie } from '../api'

interface Props {
  movie: Movie
  onClose: () => void
  onSaved: () => void
  onSave?: (fields: Record<string, any>) => Promise<void>
}

export default function EditModal({ movie, onClose, onSaved, onSave }: Props) {
  const [title, setTitle] = useState(movie.title || '')
  const [code, setCode] = useState(movie.code || '')
  const [actress, setActress] = useState(movie.actress || '')
  const [releaseDate, setReleaseDate] = useState(movie.release_date || '')
  const [duration, setDuration] = useState(movie.duration || 0)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      if (onSave) {
        await onSave({
          title: title || undefined,
          release_date: releaseDate || undefined,
          duration: duration || undefined,
        })
      } else {
        await api.editMovie(movie.id, {
          title: title || undefined,
          code: code || undefined,
          actress: actress || undefined,
          release_date: releaseDate || undefined,
          duration: duration || undefined,
        })
      }
      onSaved()
      onClose()
    } catch {
      setError('保存失败')
    }
    setSaving(false)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-dark-800 border border-dark-600 rounded-lg p-4 sm:p-6 w-full max-w-md mx-4 shadow-2xl">
        <h2 className="text-lg font-bold mb-4">编辑影片信息</h2>
        <form onSubmit={handleSave} className="space-y-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">标题</label>
            <input
              type="text" value={title} onChange={e => setTitle(e.target.value)}
              className="w-full px-3 py-1.5 bg-dark-700 border border-dark-600 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">番号/标识</label>
            <input
              type="text" value={code} onChange={e => setCode(e.target.value)}
              className="w-full px-3 py-1.5 bg-dark-700 border border-dark-600 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">演员</label>
            <input
              type="text" value={actress} onChange={e => setActress(e.target.value)}
              className="w-full px-3 py-1.5 bg-dark-700 border border-dark-600 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">发行日</label>
              <input
                type="text" value={releaseDate} onChange={e => setReleaseDate(e.target.value)}
                placeholder="YYYY-MM-DD"
                className="w-full px-3 py-1.5 bg-dark-700 border border-dark-600 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">时长(分钟)</label>
              <input
                type="number" value={duration || ''} onChange={e => setDuration(Number(e.target.value))}
                className="w-full px-3 py-1.5 bg-dark-700 border border-dark-600 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
          {error && <p className="text-red-400 text-xs">{error}</p>}
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 py-2 bg-dark-700 hover:bg-dark-600 rounded-lg text-sm transition-colors text-gray-400">
              取消
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm transition-colors disabled:opacity-50">
              {saving ? '保存中...' : '保存'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
