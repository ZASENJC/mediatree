import { useState, useEffect } from 'react'
import { api } from '../../api'

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
      <div className="flex min-h-screen items-center justify-center bg-aurora">
        <div className="animate-pulse text-lg text-gray-400">检查媒体库...</div>
      </div>
    )
  }

  if (libs.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-aurora px-4 py-10">
        <div className="glass-modal w-full max-w-lg p-8 text-center">
          <div className="mx-auto mb-5 h-14 w-14 rounded-3xl border border-white/10 bg-white/[0.08] shadow-glass backdrop-blur-2xl" />
          <h1 className="mb-3 text-3xl font-bold tracking-tight text-white">未检测到媒体库</h1>
          <p className="mb-2 text-gray-400">容器内的 <span className="font-mono text-gray-300">/media</span> 目录下没有可配置的媒体库文件夹。</p>
          <p className="text-sm text-gray-500">请在 Docker 里挂载媒体目录，或在 <span className="font-mono text-gray-400">MEDIA_ROOT</span> 指向的目录下创建至少一个子文件夹后重启。</p>
        </div>
      </div>
    )
  }

  if (step === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-aurora px-4 py-10">
        <div className="glass-modal w-full max-w-lg p-8 text-center">
          <div className="mx-auto mb-5 h-14 w-14 rounded-3xl border border-white/10 bg-white/[0.08] shadow-glass backdrop-blur-2xl" />
          <p className="mb-2 text-xs uppercase tracking-[0.24em] text-apple-blue/80">MediaTree</p>
          <h1 className="mb-3 text-3xl font-bold tracking-tight text-white">欢迎使用 MediaTree</h1>
          <p className="mb-2 text-gray-400">检测到 {libs.length} 个媒体库</p>
          <p className="mb-8 text-sm text-gray-500">接下来为每个媒体库配置刮削数据源和密码</p>
          <button onClick={() => setStep(1)} className="glass-button-primary px-8 py-3 text-base">
            开始配置
          </button>
        </div>
      </div>
    )
  }

  const lib = libs[slide]
  const isLast = slide === libs.length - 1

  return (
    <div className="flex min-h-screen items-center justify-center bg-aurora px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex gap-1.5">
          {libs.map((_, i) => (
            <div key={i} className={`h-1 flex-1 rounded-full transition-all ${i <= slide ? 'bg-apple-blue shadow-glow' : 'bg-white/10'}`} />
          ))}
        </div>

        <div className="mb-5 text-center">
          <p className="mb-1 text-xs uppercase tracking-[0.24em] text-apple-blue/80">Setup</p>
          <h1 className="text-2xl font-bold tracking-tight text-white">配置媒体库</h1>
          <p className="mt-1 text-sm text-gray-500">{lib.label} ({slide + 1}/{libs.length})</p>
        </div>

        <div className="glass-modal space-y-5 p-4 sm:p-6">
          <div>
            <label className="mb-2 block text-sm font-medium text-white">刮削数据源</label>
            <div className="grid grid-cols-2 gap-2">
              {SCRAPER_OPTIONS.map(({ key, label, desc }) => (
                <button
                  key={key}
                  onClick={() => updateLib(slide, { scraper: key })}
                  className={`rounded-2xl border p-3 text-left transition-all ${
                    lib.scraper === key
                      ? 'border-apple-blue/50 bg-apple-blue/15 text-white shadow-glow'
                      : 'border-white/10 bg-white/[0.06] text-gray-400 hover:border-white/20 hover:bg-white/[0.1] hover:text-white'
                  }`}
                >
                  <div className="text-sm font-medium">{label}</div>
                  <div className="mt-0.5 text-xs text-gray-500">{desc}</div>
                </button>
              ))}
            </div>
          </div>

          {(['tmdb_movie', 'tmdb_tv', 'auto'].includes(lib.scraper)) && (
            <div>
              <label className="mb-1.5 block text-sm font-medium text-white">TMDB API 读访问令牌</label>
              <input
                type="password"
                value={tmdbAccessToken}
                onChange={e => setTmdbAccessToken(e.target.value)}
                placeholder="以 eyJ 开头的 Read Access Token"
                className="glass-input w-full px-3 py-2 text-sm"
              />
              <p className="mt-1 text-xs text-gray-500">填写 TMDB 设置页的 API Read Access Token，不是旧版 API Key。</p>
            </div>
          )}

          {lib.scraper === 'auto' && (
            <p className="rounded-2xl border border-apple-yellow/20 bg-apple-yellow/10 p-3 text-xs leading-relaxed text-gray-400">
              自动：会尝试判断刮削源，但可能效果不好；推荐按媒体库类型手动选择 TMDB 电影、TMDB 剧集/番剧、Bangumi 或 Javdatabase。
            </p>
          )}

          {lib.scraper === 'bangumi' && (
            <div>
              <label className="mb-1.5 block text-sm font-medium text-white">搜索类型</label>
              <div className="flex gap-2">
                {[
                  { key: '2', label: '仅动画' },
                  { key: '6', label: '仅真人' },
                  { key: '2,6', label: '全部' },
                ].map(({ key, label }) => (
                  <button
                    key={key}
                    onClick={() => updateLib(slide, { bangumi_type: key })}
                    className={`rounded-full border px-4 py-1.5 text-sm transition-all ${
                      lib.bangumi_type === key
                        ? 'border-apple-blue/50 bg-apple-blue/80 text-white shadow-glow'
                        : 'border-white/10 bg-white/[0.08] text-gray-400 hover:bg-white/[0.14] hover:text-white'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <label className="mb-1.5 block text-sm font-medium text-white">媒体库密码（可选）</label>
            <input
              type="password"
              value={lib.password}
              onChange={e => updateLib(slide, { password: e.target.value })}
              placeholder="留空则不设密码"
              className="glass-input w-full px-3 py-2 text-sm"
            />
          </div>
        </div>

        {error && <p className="mt-3 rounded-2xl border border-red-400/20 bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}

        <div className="mt-6 flex gap-3">
          {slide > 0 && (
            <button onClick={() => setSlide(s => s - 1)} className="glass-button px-4 py-2 text-sm">
              上一步
            </button>
          )}
          {!isLast ? (
            <button onClick={() => setSlide(s => s + 1)} className="glass-button-primary flex-1 px-4 py-2 text-sm">
              下一步
            </button>
          ) : (
            <button onClick={handleSave} disabled={saving} className="glass-button-primary flex-1 px-4 py-2 text-sm">
              {saving ? '保存中...' : '完成配置'}
            </button>
          )}
        </div>

        <p className="mt-3 text-center text-xs text-gray-600">保存后会自动启动第一次全库扫描和刮削。</p>
      </div>
    </div>
  )
}
