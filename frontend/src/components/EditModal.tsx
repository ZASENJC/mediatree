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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 backdrop-blur-xl">
      <div className="glass-modal w-full max-w-md p-5 sm:p-6">
        <div className="mb-5">
          <p className="text-xs uppercase tracking-[0.22em] text-apple-blue/70">Edit</p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-white">编辑影片信息</h2>
        </div>
        <form onSubmit={handleSave} className="space-y-3">
          <div>
            <label className="mb-1.5 block text-xs text-gray-500">标题</label>
            <input
              type="text" value={title} onChange={e => setTitle(e.target.value)}
              className="glass-input w-full px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs text-gray-500">番号/标识</label>
            <input
              type="text" value={code} onChange={e => setCode(e.target.value)}
              className="glass-input w-full px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs text-gray-500">演员</label>
            <input
              type="text" value={actress} onChange={e => setActress(e.target.value)}
              className="glass-input w-full px-3 py-2 text-sm"
            />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-xs text-gray-500">发行日</label>
              <input
                type="text" value={releaseDate} onChange={e => setReleaseDate(e.target.value)}
                placeholder="YYYY-MM-DD"
                className="glass-input w-full px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs text-gray-500">时长(分钟)</label>
              <input
                type="number" value={duration || ''} onChange={e => setDuration(Number(e.target.value))}
                className="glass-input w-full px-3 py-2 text-sm"
              />
            </div>
          </div>
          {error && <p className="rounded-2xl border border-red-400/20 bg-red-500/10 px-3 py-2 text-xs text-red-300">{error}</p>}
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="glass-button flex-1 py-2">
              取消
            </button>
            <button type="submit" disabled={saving}
              className="glass-button-primary flex-1 py-2">
              {saving ? '保存中...' : '保存'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
