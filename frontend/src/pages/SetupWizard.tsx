import { useState, useEffect } from 'react'
import { api } from '../api'

interface LibConfig {
  media_root: string
  label: string
  scraper: string
  tmdb_key: string
  bangumi_type: string
  password: string
}

const SCRAPER_OPTIONS = [
  {
    key: 'tmdb_movie',
    label: 'TMDB 电影',
    desc: '电影库；tmdbid 调用 /movie 精确刮削',
  },
  {
    key: 'tmdb_tv',
    label: 'TMDB 剧集/番剧',
    desc: '剧集/番剧库；tmdbid 调用 /tv 精确刮削',
  },
  {
    key: 'bangumi',
    label: 'Bangumi',
    desc: '番剧、动画、二次元条目',
  },
  {
    key: 'javdatabase',
    label: 'Javdatabase',
    desc: 'JAV 番号识别和刮削',
  },
  {
    key: 'auto',
    label: '自动',
    desc: '自动判断，可能效果不好',
  },
  {
    key: 'none',
    label: '不刮削',
    desc: '只扫描本地文件',
  },
]

export default function SetupWizard({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState(0)
  const [slide, setSlide] = useState(0)
  const [libs, setLibs] = useState<LibConfig[]>([])
  const [tmdbAccessToken, setTmdbAccessToken] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    api.setupStatus().then(d => {
      if (!d.needs_setup) { onComplete(); return }
      setLibs(d.roots.map(r => ({
        media_root: r,
        label: r.split('/').filter(Boolean).pop() || r,
        scraper: 'auto',
        tmdb_key: '',
        bangumi_type: '2',
        password: '',
      })))
      setLoaded(true)
    }).catch(() => setLoaded(true))
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
      })), tmdbAccessToken)
      onComplete()
    } catch {
      setError('保存失败')
    }
    setSaving(false)
  }

  if (!loaded) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-dark-900">
        <div className="animate-pulse text-gray-400 text-lg">检查媒体库...</div>
      </div>
    )
  }

  if (libs.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-dark-900 px-4">
        <div className="w-full max-w-lg text-center">
          <h1 className="text-3xl font-bold mb-3">未检测到媒体库</h1>
          <p className="text-gray-400 mb-2">容器内的 <span className="font-mono text-gray-300">/media</span> 目录下没有可配置的媒体库文件夹。</p>
          <p className="text-sm text-gray-500">请在 Docker 里挂载媒体目录，或在 <span className="font-mono text-gray-400">MEDIA_ROOT</span> 指向的目录下创建至少一个子文件夹后重启。</p>
        </div>
      </div>
    )
  }

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
            <div key={i} className={`flex-1 h-1 rounded-lg ${i <= slide ? 'bg-blue-500' : 'bg-dark-600'}`} />
          ))}
        </div>

        <h1 className="text-xl font-bold mb-1">配置媒体库</h1>
        <p className="text-sm text-gray-400 mb-6">{lib.label} ({slide + 1}/{libs.length})</p>

        <div className="space-y-5 bg-dark-800 rounded-lg p-4 sm:p-6 border border-dark-600">
          <div>
            <label className="block text-sm font-medium mb-2">刮削数据源</label>
            <div className="grid grid-cols-2 gap-2">
              {SCRAPER_OPTIONS.map(({ key, label, desc }) => (
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

          {(['tmdb_movie', 'tmdb_tv', 'auto'].includes(lib.scraper)) && (
            <div>
              <label className="block text-sm font-medium mb-1.5">TMDB API 读访问令牌</label>
              <input
                type="password"
                value={tmdbAccessToken}
                onChange={e => setTmdbAccessToken(e.target.value)}
                placeholder="以 eyJ 开头的 Read Access Token"
                className="w-full px-3 py-2 bg-dark-700 border border-dark-600 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500 placeholder-gray-600"
              />
              <p className="text-xs text-gray-500 mt-1">填写 TMDB 设置页的 API Read Access Token，不是旧版 API Key。</p>
            </div>
          )}

          {lib.scraper === 'auto' && (
            <p className="text-xs text-gray-500 leading-relaxed">
              自动：会尝试判断刮削源，但可能效果不好；推荐按媒体库类型手动选择 TMDB 电影、TMDB 剧集/番剧、Bangumi 或 Javdatabase。
            </p>
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

        <p className="mt-3 text-center text-xs text-gray-600">保存后会自动启动第一次全库扫描和刮削。</p>
      </div>
    </div>
  )
}
