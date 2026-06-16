const ACTIVE_THEME_KEY = 'mediatree_active_theme'
const CUSTOM_THEMES_KEY = 'mediatree_custom_themes'
const CUSTOM_THEME_STYLE_ID = 'mediatree-custom-theme-style'
const THEME_EXPORT_VERSION = 2
const MAX_THEME_FILE_BYTES = 128 * 1024
const MAX_CUSTOM_CSS_LENGTH = 60 * 1024
const THEME_ROOT_SELECTOR = ':root[data-mediatree-theme]'

export type ThemeColorScheme = 'dark' | 'light' | 'auto'
export type ThemeCapability = 'tokens' | 'custom-css' | 'stable-selectors' | 'layout' | 'density' | 'motion'

export interface ThemePackage {
  schemaVersion?: number
  name: string
  label: string
  description?: string
  author?: string
  version?: string
  capabilities?: ThemeCapability[]
  colorScheme?: ThemeColorScheme
  tokens: Record<string, string>
  customCss?: string
  builtin?: boolean
}

export interface ThemeImportResult {
  themes: ThemePackage[]
  activeTheme?: string
}

export const DEFAULT_THEME_NAME = 'mediatree-dark'

const DEFAULT_DARK_TOKENS: Record<string, string> = {
  '--mt-font-family': '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Segoe UI", Roboto, sans-serif',
  '--mt-density-scale': '1',
  '--mt-layout-content-max': 'none',
  '--mt-layout-gap': '1.25rem',
  '--mt-layout-page-padding-x': 'clamp(1rem, 1.8vw, 1.5rem)',
  '--mt-layout-page-padding-y': '1.25rem',
  '--mt-layout-page-padding-x-wide': 'clamp(1rem, 1.8vw, 1.5rem)',
  '--mt-layout-page-padding-y-wide': '1.75rem',
  '--mt-media-grid-min': '9.75rem',
  '--mt-media-grid-max': '11rem',
  '--mt-media-card-width': '11rem',
  '--mt-media-card-height': '16.5rem',
  '--mt-media-grid-gap': '1rem',
  '--mt-media-grid-column-gap': '1rem',
  '--mt-media-grid-row-gap': '1.25rem',
  '--mt-motion-fast': '160ms',
  '--mt-motion-normal': '260ms',
  '--mt-theme-style': 'liquid-glass',
  '--mt-color-bg-start': '#03040a',
  '--mt-color-bg-mid': '#070911',
  '--mt-color-bg-end': '#0c0f17',
  '--mt-color-bg-glow': 'rgba(10, 132, 255, 0.24)',
  '--mt-color-page-overlay': 'linear-gradient(180deg, rgba(255,255,255,0.045), transparent 24%, rgba(0,0,0,0.42))',
  '--mt-color-noise-opacity': '0.04',
  '--mt-color-text': '#f5f5f7',
  '--mt-color-text-muted': '#9ca3af',
  '--mt-color-text-faint': '#6b7280',
  '--mt-color-surface': 'rgba(255,255,255,0.07)',
  '--mt-color-surface-elevated': 'rgba(255,255,255,0.11)',
  '--mt-color-surface-muted': 'rgba(255,255,255,0.06)',
  '--mt-color-surface-container': 'rgba(255,255,255,0.08)',
  '--mt-color-surface-container-high': 'rgba(255,255,255,0.12)',
  '--mt-color-surface-strong': 'rgba(0,0,0,0.35)',
  '--mt-color-control': 'rgba(255,255,255,0.08)',
  '--mt-color-control-hover': 'rgba(255,255,255,0.14)',
  '--mt-color-border': 'rgba(255,255,255,0.10)',
  '--mt-color-border-strong': 'rgba(255,255,255,0.18)',
  '--mt-color-accent': '#0A84FF',
  '--mt-color-accent-strong': '#00a4dc',
  '--mt-color-accent-soft': 'rgba(10,132,255,0.18)',
  '--mt-color-success': '#32D74B',
  '--mt-color-warning': '#FFD60A',
  '--mt-color-danger': '#FF375F',
  '--mt-radius-panel': '1.5rem',
  '--mt-radius-card': '1rem',
  '--mt-radius-control': '999px',
  '--mt-shadow-glass': '0 24px 80px rgba(0, 0, 0, 0.38), inset 0 1px 0 rgba(255, 255, 255, 0.12)',
  '--mt-shadow-card': '0 18px 50px rgba(0, 0, 0, 0.34)',
  '--mt-shadow-glow': '0 18px 48px rgba(10, 132, 255, 0.22)',
  '--mt-shadow-elevation-1': '0 1px 3px rgba(0, 0, 0, 0.18)',
  '--mt-shadow-elevation-2': '0 8px 24px rgba(0, 0, 0, 0.22)',
  '--mt-shadow-elevation-3': '0 18px 50px rgba(0, 0, 0, 0.28)',
  '--mt-backdrop-panel': 'blur(22px) saturate(170%)',
  '--mt-backdrop-card': 'blur(6px) saturate(130%)',
}

export const BUILTIN_THEMES: ThemePackage[] = [
  {
    name: DEFAULT_THEME_NAME,
    label: 'MediaTree 暗色',
    description: '默认玻璃质感暗色主题。',
    schemaVersion: 2,
    capabilities: ['tokens', 'custom-css', 'stable-selectors', 'layout', 'density', 'motion'],
    colorScheme: 'dark',
    builtin: true,
    tokens: DEFAULT_DARK_TOKENS,
  },
  {
    name: 'soft-daylight',
    label: '晨光浅色',
    description: '适合白天使用的浅色主题。',
    schemaVersion: 2,
    capabilities: ['tokens', 'custom-css', 'stable-selectors', 'layout', 'density', 'motion'],
    colorScheme: 'light',
    builtin: true,
    tokens: {
      ...DEFAULT_DARK_TOKENS,
      '--mt-color-bg-start': '#f7fbff',
      '--mt-color-bg-mid': '#edf5f3',
      '--mt-color-bg-end': '#f8fafc',
      '--mt-color-bg-glow': 'rgba(20, 184, 166, 0.16)',
      '--mt-color-page-overlay': 'linear-gradient(180deg, rgba(255,255,255,0.58), transparent 32%, rgba(15,23,42,0.08))',
      '--mt-color-noise-opacity': '0.025',
      '--mt-color-text': '#0f172a',
      '--mt-color-text-muted': '#475569',
      '--mt-color-text-faint': '#64748b',
      '--mt-color-surface': 'rgba(255,255,255,0.66)',
      '--mt-color-surface-elevated': 'rgba(255,255,255,0.82)',
      '--mt-color-surface-muted': 'rgba(15,23,42,0.055)',
      '--mt-color-surface-container': 'rgba(255,255,255,0.7)',
      '--mt-color-surface-container-high': 'rgba(255,255,255,0.88)',
      '--mt-color-surface-strong': 'rgba(255,255,255,0.76)',
      '--mt-color-control': 'rgba(15,23,42,0.06)',
      '--mt-color-control-hover': 'rgba(15,23,42,0.1)',
      '--mt-color-border': 'rgba(15,23,42,0.11)',
      '--mt-color-border-strong': 'rgba(15,23,42,0.18)',
      '--mt-color-accent': '#0f766e',
      '--mt-color-accent-strong': '#0d9488',
      '--mt-color-accent-soft': 'rgba(15,118,110,0.14)',
      '--mt-shadow-glass': '0 20px 64px rgba(15, 23, 42, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.72)',
      '--mt-shadow-card': '0 16px 42px rgba(15, 23, 42, 0.12)',
      '--mt-shadow-glow': '0 16px 42px rgba(13, 148, 136, 0.16)',
      '--mt-shadow-elevation-1': '0 1px 3px rgba(15, 23, 42, 0.08)',
      '--mt-shadow-elevation-2': '0 8px 22px rgba(15, 23, 42, 0.1)',
      '--mt-shadow-elevation-3': '0 18px 42px rgba(15, 23, 42, 0.12)',
    },
    customCss: `
.media-grid-card img { filter: saturate(1.04) contrast(1.02); }
.drop-shadow { text-shadow: 0 1px 2px rgba(255,255,255,0.35); }
    `.trim(),
  },
  {
    name: 'cinema-ember',
    label: '深影院',
    description: '降低蓝色占比的观影暗色主题。',
    schemaVersion: 2,
    capabilities: ['tokens', 'custom-css', 'stable-selectors', 'layout', 'density', 'motion'],
    colorScheme: 'dark',
    builtin: true,
    tokens: {
      ...DEFAULT_DARK_TOKENS,
      '--mt-color-bg-start': '#080607',
      '--mt-color-bg-mid': '#121013',
      '--mt-color-bg-end': '#151a1d',
      '--mt-color-bg-glow': 'rgba(244, 114, 91, 0.16)',
      '--mt-color-text': '#f7f0ea',
      '--mt-color-text-muted': '#b9aaa2',
      '--mt-color-text-faint': '#85736b',
      '--mt-color-surface': 'rgba(255,246,238,0.075)',
      '--mt-color-surface-elevated': 'rgba(255,246,238,0.12)',
      '--mt-color-surface-muted': 'rgba(255,246,238,0.06)',
      '--mt-color-surface-container': 'rgba(255,246,238,0.08)',
      '--mt-color-surface-container-high': 'rgba(255,246,238,0.13)',
      '--mt-color-control': 'rgba(255,246,238,0.085)',
      '--mt-color-control-hover': 'rgba(255,246,238,0.145)',
      '--mt-color-border': 'rgba(255,238,224,0.11)',
      '--mt-color-border-strong': 'rgba(255,238,224,0.2)',
      '--mt-color-accent': '#f4725b',
      '--mt-color-accent-strong': '#2dd4bf',
      '--mt-color-accent-soft': 'rgba(244,114,91,0.16)',
      '--mt-shadow-glow': '0 18px 48px rgba(244, 114, 91, 0.18)',
    },
  },
]

const BUILTIN_THEME_NAMES = new Set(BUILTIN_THEMES.map(theme => theme.name))
const builtInTokenNames = new Set(BUILTIN_THEMES.flatMap(theme => Object.keys(theme.tokens)))
let appliedTokenNames = new Set<string>()

export function getThemeStorage(): Storage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}

function getDocument(): Document | null {
  return typeof document === 'undefined' ? null : document
}

function safeParseJson(input: string): unknown {
  try {
    return JSON.parse(input)
  } catch {
    throw new Error('主题文件不是有效 JSON')
  }
}

function normalizeText(value: unknown, fallback: string, maxLength: number) {
  const text = typeof value === 'string' ? value.trim() : ''
  if (!text) return fallback
  return text.slice(0, maxLength)
}

function normalizeThemeName(value: unknown, fallback?: string) {
  const raw = typeof value === 'string' ? value.trim().toLowerCase() : ''
  const name = raw || fallback || ''
  if (!/^[a-z0-9][a-z0-9_-]{1,48}$/.test(name)) {
    throw new Error('主题 name 只能使用 2-49 位小写字母、数字、短横线或下划线，并且必须以字母或数字开头')
  }
  return name
}

function normalizeColorScheme(value: unknown): ThemeColorScheme {
  return value === 'light' || value === 'auto' || value === 'dark' ? value : 'dark'
}

function normalizeSchemaVersion(value: unknown) {
  const version = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : 0
  return Number.isInteger(version) && version > 0 && version <= THEME_EXPORT_VERSION ? version : undefined
}

const ALLOWED_THEME_CAPABILITIES: ThemeCapability[] = ['tokens', 'custom-css', 'stable-selectors', 'layout', 'density', 'motion']
const ALLOWED_THEME_CAPABILITY_SET = new Set<string>(ALLOWED_THEME_CAPABILITIES)

function normalizeCapabilities(value: unknown): ThemeCapability[] | undefined {
  if (!Array.isArray(value)) return undefined
  const capabilities = value
    .filter((item): item is ThemeCapability => typeof item === 'string' && ALLOWED_THEME_CAPABILITY_SET.has(item))
    .filter((item, index, items) => items.indexOf(item) === index)
  return capabilities.length > 0 ? capabilities : undefined
}

function isAllowedThemeToken(name: string) {
  return /^--(?:mt|player-ui)-[a-z0-9-]+$/i.test(name)
}

function assertSafeCssText(value: string) {
  const lower = value.toLowerCase()
  if (
    lower.includes('@import')
    || lower.includes('javascript:')
    || lower.includes('data:')
    || lower.includes('expression(')
    || lower.includes('-moz-binding')
    || lower.includes('</style')
    || lower.includes('<script')
  ) {
    throw new Error('主题 CSS 不允许使用 @import、javascript:、外链 url 或 data:')
  }

  const urlPattern = /url\s*\(\s*(['"]?)(.*?)\1\s*\)/gi
  let match: RegExpExecArray | null
  while ((match = urlPattern.exec(value))) {
    const url = (match[2] || '').trim().toLowerCase()
    if (/^(?:https?:)?\/\//.test(url) || url.startsWith('data:') || url.startsWith('javascript:')) {
      throw new Error('主题 CSS 不允许使用 @import、javascript:、外链 url 或 data:')
    }
  }
}

function normalizeTokens(tokens: unknown): Record<string, string> {
  if (!tokens || typeof tokens !== 'object' || Array.isArray(tokens)) return {}
  const normalized: Record<string, string> = {}
  for (const [name, rawValue] of Object.entries(tokens as Record<string, unknown>)) {
    if (!isAllowedThemeToken(name)) continue
    if (typeof rawValue !== 'string' && typeof rawValue !== 'number') continue
    const value = String(rawValue).trim()
    if (!value || value.length > 3000) continue
    assertSafeCssText(value)
    normalized[name] = value
  }
  return normalized
}

function splitSelectorList(selectorList: string) {
  const selectors: string[] = []
  let current = ''
  let depth = 0
  for (const char of selectorList) {
    if (char === '(' || char === '[') depth++
    if (char === ')' || char === ']') depth = Math.max(0, depth - 1)
    if (char === ',' && depth === 0) {
      selectors.push(current)
      current = ''
    } else {
      current += char
    }
  }
  selectors.push(current)
  return selectors
}

function scopeSelector(selector: string) {
  const trimmed = selector.trim()
  if (!trimmed || trimmed.includes('[data-mediatree-theme]')) return trimmed
  if (trimmed === ':root' || trimmed === 'html') return THEME_ROOT_SELECTOR
  if (trimmed.startsWith(':root ') || trimmed.startsWith('html ')) {
    return `${THEME_ROOT_SELECTOR}${trimmed.replace(/^(:root|html)/, '')}`
  }
  return `${THEME_ROOT_SELECTOR} ${trimmed}`
}

function findMatchingBrace(css: string, openIndex: number) {
  let depth = 0
  for (let i = openIndex; i < css.length; i++) {
    if (css[i] === '{') depth++
    if (css[i] === '}') {
      depth--
      if (depth === 0) return i
    }
  }
  return -1
}

function scopeCss(css: string): string {
  let output = ''
  let index = 0
  while (index < css.length) {
    const openIndex = css.indexOf('{', index)
    if (openIndex < 0) {
      output += css.slice(index)
      break
    }
    const prelude = css.slice(index, openIndex).trim()
    const closeIndex = findMatchingBrace(css, openIndex)
    if (closeIndex < 0) {
      output += css.slice(index)
      break
    }
    const body = css.slice(openIndex + 1, closeIndex)
    if (prelude.startsWith('@media') || prelude.startsWith('@supports') || prelude.startsWith('@container')) {
      output += `${prelude} {${scopeCss(body)}}`
    } else if (prelude.startsWith('@')) {
      output += `${prelude} {${body}}`
    } else {
      const scopedPrelude = splitSelectorList(prelude).map(scopeSelector).join(', ')
      output += `${scopedPrelude} {${body}}`
    }
    index = closeIndex + 1
    if (css[index] === '\n') {
      output += '\n'
      index++
    }
  }
  return output.trim()
}

export function sanitizeCustomCss(customCss?: string) {
  const css = (customCss || '').trim()
  if (!css) return ''
  if (css.length > MAX_CUSTOM_CSS_LENGTH) {
    throw new Error('主题 CSS 不能超过 60KB')
  }
  assertSafeCssText(css)
  return scopeCss(css)
}

function normalizeThemePackage(input: unknown, fallbackName?: string): ThemePackage {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new Error('主题文件必须是 JSON 对象')
  }
  const data = input as Record<string, unknown>
  const name = normalizeThemeName(data.name, fallbackName)
  const label = normalizeText(data.label, name, 80)
  const theme: ThemePackage = {
    schemaVersion: normalizeSchemaVersion(data.schemaVersion ?? (typeof data.version === 'number' ? data.version : undefined)),
    name,
    label,
    description: normalizeText(data.description, '', 220) || undefined,
    author: normalizeText(data.author, '', 80) || undefined,
    version: normalizeText(data.version, '', 32) || undefined,
    capabilities: normalizeCapabilities(data.capabilities),
    colorScheme: normalizeColorScheme(data.colorScheme),
    tokens: normalizeTokens(data.tokens),
    customCss: sanitizeCustomCss(typeof data.customCss === 'string' ? data.customCss : ''),
  }
  if (Object.keys(theme.tokens).length === 0 && !theme.customCss) {
    throw new Error('主题至少需要提供 tokens 或 customCss')
  }
  return theme
}

function fallbackNameFromFile(fileName?: string) {
  const base = (fileName || 'custom-theme').split('/').pop() || 'custom-theme'
  return base.replace(/\.[^.]+$/, '').toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '') || 'custom-theme'
}

export function parseThemeFileContent(content: string, fileName?: string): ThemePackage {
  if (content.length > MAX_THEME_FILE_BYTES) {
    throw new Error('主题文件不能超过 128KB')
  }
  return normalizeThemePackage(safeParseJson(content), fallbackNameFromFile(fileName))
}

export function parseThemeImportContent(content: string, fileName?: string): ThemeImportResult {
  if (content.length > MAX_THEME_FILE_BYTES) {
    throw new Error('主题文件不能超过 128KB')
  }
  const data = safeParseJson(content)
  if (data && typeof data === 'object' && !Array.isArray(data) && Array.isArray((data as any).themes)) {
    const themes = (data as any).themes.map((theme: unknown, index: number) =>
      normalizeThemePackage(theme, `${fallbackNameFromFile(fileName)}-${index + 1}`)
    )
    if (themes.length === 0) throw new Error('主题包没有包含可导入主题')
    return {
      themes,
      activeTheme: typeof (data as any).activeTheme === 'string' ? (data as any).activeTheme : undefined,
    }
  }
  return { themes: [normalizeThemePackage(data, fallbackNameFromFile(fileName))] }
}

export function getCustomThemes(storage = getThemeStorage()): ThemePackage[] {
  if (!storage) return []
  try {
    const raw = storage.getItem(CUSTOM_THEMES_KEY)
    const items = raw ? JSON.parse(raw) : []
    if (!Array.isArray(items)) return []
    return items.map((item, index) => normalizeThemePackage(item, `custom-theme-${index + 1}`))
  } catch {
    return []
  }
}

export function saveCustomThemes(themes: ThemePackage[], storage = getThemeStorage()) {
  if (!storage) return
  const normalized = themes
    .filter(theme => !theme.builtin)
    .map(theme => ({ ...normalizeThemePackage(theme), builtin: undefined }))
  storage.setItem(CUSTOM_THEMES_KEY, JSON.stringify(normalized))
}

export function saveCustomTheme(theme: ThemePackage, storage = getThemeStorage()) {
  if (BUILTIN_THEME_NAMES.has(theme.name)) {
    throw new Error('自定义主题不能使用内置主题 name')
  }
  const customThemes = getCustomThemes(storage).filter(item => item.name !== theme.name)
  const normalized = { ...normalizeThemePackage(theme), builtin: undefined }
  saveCustomThemes([...customThemes, normalized], storage)
  return normalized
}

export function importCustomThemes(themes: ThemePackage[], storage = getThemeStorage()) {
  const normalized = themes.map(theme => {
    if (BUILTIN_THEME_NAMES.has(theme.name)) {
      throw new Error('自定义主题不能使用内置主题 name')
    }
    return { ...normalizeThemePackage(theme), builtin: undefined }
  })
  const nextThemes = getCustomThemes(storage)
  normalized.forEach(theme => {
    const existingIndex = nextThemes.findIndex(item => item.name === theme.name)
    if (existingIndex >= 0) nextThemes[existingIndex] = theme
    else nextThemes.push(theme)
  })
  saveCustomThemes(nextThemes, storage)
  return normalized
}

export function removeCustomTheme(name: string, storage = getThemeStorage()) {
  const customThemes = getCustomThemes(storage).filter(theme => theme.name !== name)
  saveCustomThemes(customThemes, storage)
}

export function getAvailableThemes(customThemes = getCustomThemes()) {
  return [...BUILTIN_THEMES, ...customThemes]
}

export function getActiveThemeName(storage = getThemeStorage()) {
  try {
    return storage?.getItem(ACTIVE_THEME_KEY) || DEFAULT_THEME_NAME
  } catch {
    return DEFAULT_THEME_NAME
  }
}

export function getThemeByName(name: string, customThemes = getCustomThemes()) {
  return getAvailableThemes(customThemes).find(theme => theme.name === name) || BUILTIN_THEMES[0]
}

function ensureStyleElement(doc: Document) {
  let styleEl = doc.getElementById(CUSTOM_THEME_STYLE_ID) as HTMLStyleElement | null
  if (!styleEl) {
    styleEl = doc.createElement('style')
    styleEl.id = CUSTOM_THEME_STYLE_ID
    doc.head.appendChild(styleEl)
  }
  return styleEl
}

export function applyTheme(theme: ThemePackage, doc = getDocument()) {
  if (!doc) return theme
  const root = doc.documentElement
  const tokens = normalizeTokens(theme.tokens)
  const allTokenNames = new Set([...builtInTokenNames, ...appliedTokenNames, ...Object.keys(tokens)])
  allTokenNames.forEach(name => root.style.removeProperty(name))
  Object.entries(tokens).forEach(([name, value]) => root.style.setProperty(name, value))
  appliedTokenNames = new Set(Object.keys(tokens))

  root.setAttribute('data-mediatree-theme', theme.name)
  root.setAttribute('data-mediatree-theme-source', theme.builtin ? 'builtin' : 'custom')
  root.setAttribute('data-mediatree-color-scheme', theme.colorScheme || 'dark')
  if (theme.colorScheme && theme.colorScheme !== 'auto') {
    root.style.setProperty('color-scheme', theme.colorScheme)
  } else {
    root.style.removeProperty('color-scheme')
  }

  ensureStyleElement(doc).textContent = sanitizeCustomCss(theme.customCss)
  return theme
}

export function setActiveTheme(name: string, storage = getThemeStorage(), doc = getDocument()) {
  const theme = getThemeByName(name, getCustomThemes(storage))
  try {
    storage?.setItem(ACTIVE_THEME_KEY, theme.name)
  } catch {}
  return applyTheme(theme, doc)
}

export function initializeTheme(storage = getThemeStorage(), doc = getDocument()) {
  return setActiveTheme(getActiveThemeName(storage), storage, doc)
}

export function createThemeExport(activeTheme: ThemePackage, customThemes?: ThemePackage[], storage = getThemeStorage()) {
  const activeName = activeTheme.name || getActiveThemeName(storage)
  const themes = customThemes ?? getCustomThemes(storage)
  return JSON.stringify({
    version: THEME_EXPORT_VERSION,
    activeTheme: activeName,
    exportedAt: new Date().toISOString(),
    themes: themes.map(theme => ({ ...theme, builtin: undefined })),
  }, null, 2)
}

export function createExampleTheme() {
  return JSON.stringify({
    schemaVersion: 2,
    name: 'advanced-skin',
    label: '我的高级外观',
    description: '可作为大幅改造 MediaTree 外观的主题模板。',
    author: 'MediaTree user',
    version: '1.0.0',
    capabilities: ['tokens', 'custom-css', 'stable-selectors', 'layout', 'density', 'motion'],
    colorScheme: 'light',
    tokens: {
      '--mt-font-family': 'Inter, "Noto Sans SC", "Microsoft YaHei", sans-serif',
      '--mt-density-scale': '0.96',
      '--mt-layout-content-max': 'none',
      '--mt-layout-gap': '1rem',
      '--mt-layout-page-padding-x': 'clamp(1rem, 1.8vw, 1.5rem)',
      '--mt-layout-page-padding-y': '1.25rem',
      '--mt-layout-page-padding-x-wide': 'clamp(1rem, 1.8vw, 1.5rem)',
      '--mt-layout-page-padding-y-wide': '1.5rem',
      '--mt-media-grid-min': '9.75rem',
      '--mt-media-grid-max': '11rem',
      '--mt-media-card-width': '11rem',
      '--mt-media-card-height': '16.5rem',
      '--mt-media-grid-gap': '1rem',
      '--mt-media-grid-column-gap': '1rem',
      '--mt-media-grid-row-gap': '1.25rem',
      '--mt-motion-fast': '140ms',
      '--mt-motion-normal': '240ms',
      '--mt-theme-style': 'advanced-skin',
      '--mt-color-bg-start': '#f8fafc',
      '--mt-color-bg-mid': '#eef6f6',
      '--mt-color-bg-end': '#f7f1fb',
      '--mt-color-bg-glow': 'rgba(20, 184, 166, 0.14)',
      '--mt-color-page-overlay': 'linear-gradient(180deg, rgba(255,255,255,0.64), transparent 34%, rgba(15,23,42,0.04))',
      '--mt-color-noise-opacity': '0',
      '--mt-color-text': '#111827',
      '--mt-color-text-muted': '#4b5563',
      '--mt-color-text-faint': '#6b7280',
      '--mt-color-surface': 'rgba(255,255,255,0.82)',
      '--mt-color-surface-elevated': 'rgba(255,255,255,0.94)',
      '--mt-color-surface-muted': 'rgba(15,23,42,0.055)',
      '--mt-color-surface-container': '#eef6f6',
      '--mt-color-surface-container-high': '#e7f0f3',
      '--mt-color-border': 'rgba(15,23,42,0.12)',
      '--mt-color-border-strong': 'rgba(15,23,42,0.2)',
      '--mt-color-accent': '#0f766e',
      '--mt-color-accent-strong': '#7c3aed',
      '--mt-color-accent-soft': 'rgba(15,118,110,0.14)',
      '--mt-radius-panel': '24px',
      '--mt-radius-card': '18px',
      '--mt-radius-control': '999px',
      '--mt-shadow-glass': '0 16px 40px rgba(15, 23, 42, 0.12)',
      '--mt-shadow-card': '0 10px 28px rgba(15, 23, 42, 0.1)',
      '--mt-shadow-glow': '0 12px 32px rgba(15, 118, 110, 0.14)',
      '--mt-shadow-elevation-1': '0 1px 3px rgba(15, 23, 42, 0.08)',
      '--mt-shadow-elevation-2': '0 8px 22px rgba(15, 23, 42, 0.1)',
      '--mt-shadow-elevation-3': '0 18px 42px rgba(15, 23, 42, 0.12)',
      '--mt-backdrop-panel': 'none',
      '--mt-backdrop-card': 'none',
    },
    customCss: '.mt-panel { border-width: 1px; }\\n.mt-topbar .liquid-glass { background: var(--mt-color-surface-container-high); }\\n.mt-media-card:hover { filter: saturate(1.08); transform: translateY(-3px); }',
  }, null, 2)
}
