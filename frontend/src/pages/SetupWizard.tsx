import { useState, useEffect } from 'react'
import { api, MediaRoot } from '../api'

interface LibConfig {
  media_root: string
  label: string
  scraper: string
  tmdb_key: string
  bangumi_type: string
  password: string
}

export default function SetupWizard({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState(0)
  const [roots, setRoots] = useState<string[]>([])
  const [slide, setSlide] = useState(0)
  const [libs, setLibs] = useState<LibConfig[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.setupStatus().then(d => {
      if (!d.needs_setup) { onComplete(); return }
      setRoots(d.roots)
      setLibs(d.roots.map(r => ({
        media_root: r,
        label: r.split('/').filter(Boolean).pop() || r,
        scraper: 'javdatabase',
        tmdb_key: '',
        bangumi_type: '2',
        password: '',
      })))
    })
  }, [])

  const updateLib = (idx: number, patch: Partial<LibConfig>) => {
    setLibs(prev => prev.map((l, i) => i === idx ? { ...l, ...patch } : l))
  }

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      await api.setupSave(libs.map(l => ({
        media_root: l.media_root,
        scraper: l.scraper,
        tmdb_key: l.tmdb_key,
        bangumi_type: l.bangumi_type,
        password: l.password,
      })))
      onComplete()
    } catch {
      setError('保存失败')
    }
    setSaving(false)
  }

  if (libs.length === 0) return null

  if (step === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-dark-900 px-4">
        <div className="w-full max-w-lg text-center">
          <h1 className="text-3xl font-bold mb-3">欢迎使用 MediaTree</h1>
          <p className="text-gray-400 mb-2">检测到 {libs.length} 个媒体库</p>
          <p className="text-sm text-gray-500 mb-8">接下来为每个媒体库配置刮削数据源和密码</p>
          <button onClick={() => setStep(1)} className="px-8 py-3 bg-blue-600 hover:bg-blue-500 rounded-lg text-lg transition-colors">
            开始配置
          </button>
        </div>
      </div>
    )
  }

  const lib = libs[slide]
  const isLast = slide === libs.length - 1

  return (
    <div className="min-h-screen flex items-center justify-center bg-dark-900 px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 flex gap-1">
          {libs.map((_, i) => (
            <div key={i} className={`flex-1 h-1 rounded ${i <= slide ? 'bg-blue-500' : 'bg-dark-600'}`} />
          ))}
        </div>

        <h1 className="text-xl font-bold mb-1">配置媒体库</h1>
        <p className="text-sm text-gray-400 mb-6">{lib.label} ({slide + 1}/{libs.length})</p>

        <div className="space-y-5 bg-dark-800 rounded-xl p-6 border border-dark-600">
          <div>
            <label className="block text-sm font-medium mb-2">刮削数据源</label>
            <div className="grid grid-cols-2 gap-2">
              {[
                { key: 'javdatabase', label: 'Javdatabase', desc: 'JAV番号匹配' },
                { key: 'tmdb', label: 'TMDB', desc: '电影/电视剧' },
                { key: 'bangumi', label: 'Bangumi', desc: '动画/番剧' },
                { key: 'none', label: '关闭', desc: '不刮削' },
              ].map(({ key, label, desc }) => (
                <button
                  key={key}
                  onClick={() => updateLib(slide, { scraper: key })}
                  className={`p-3 rounded-lg border text-left transition-colors ${
                    lib.scraper === key
                      ? 'bg-blue-600/10 border-blue-500/40 text-blue-400'
                      : 'bg-dark-700 border-dark-600 text-gray-400 hover:bg-dark-600'
                  }`}
                >
                  <div className="text-sm font-medium">{label}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{desc}</div>
                </button>
              ))}
            </div>
          </div>

          {lib.scraper === 'tmdb' && (
            <div>
              <label className="block text-sm font-medium mb-1.5">TMDB API Key</label>
              <input
                type="text"
                value={lib.tmdb_key}
                onChange={e => updateLib(slide, { tmdb_key: e.target.value })}
                placeholder="去 themoviedb.org 免费申请"
                className="w-full px-3 py-2 bg-dark-700 border border-dark-600 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500 placeholder-gray-600"
              />
              <p className="text-xs text-gray-500 mt-1">在 themoviedb.org/settings/api 免费注册获取</p>
            </div>
          )}

          {lib.scraper === 'bangumi' && (
            <div>
              <label className="block text-sm font-medium mb-1.5">搜索类型</label>
              <div className="flex gap-2">
                {[
                  { key: '2', label: '仅动画' },
                  { key: '6', label: '仅真人' },
                  { key: '2,6', label: '全部' },
                ].map(({ key, label }) => (
                  <button
                    key={key}
                    onClick={() => updateLib(slide, { bangumi_type: key })}
                    className={`px-4 py-1.5 rounded text-sm transition-colors ${
                      lib.bangumi_type === key
                        ? 'bg-blue-600 text-white'
                        : 'bg-dark-700 text-gray-400 hover:bg-dark-600'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1.5">媒体库密码（可选）</label>
            <input
              type="password"
              value={lib.password}
              onChange={e => updateLib(slide, { password: e.target.value })}
              placeholder="留空则不设密码"
              className="w-full px-3 py-2 bg-dark-700 border border-dark-600 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500 placeholder-gray-600"
            />
          </div>
        </div>

        {error && <p className="text-red-400 text-sm mt-3">{error}</p>}

        <div className="flex gap-3 mt-6">
          {slide > 0 && (
            <button onClick={() => setSlide(s => s - 1)} className="px-4 py-2 bg-dark-700 hover:bg-dark-600 rounded-lg text-sm transition-colors">
              上一步
            </button>
          )}
          {!isLast ? (
            <button onClick={() => setSlide(s => s + 1)} className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm transition-colors">
              下一步
            </button>
          ) : (
            <button onClick={handleSave} disabled={saving} className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm transition-colors disabled:opacity-50">
              {saving ? '保存中...' : '完成配置'}
            </button>
          )}
        </div>

        <button onClick={onComplete} className="w-full mt-3 py-2 text-sm text-gray-500 hover:text-white transition-colors">
          跳过（稍后设置）
        </button>
      </div>
    </div>
  )
}
