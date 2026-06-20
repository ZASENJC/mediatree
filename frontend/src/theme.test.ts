import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import {
  applyTheme,
  BUILTIN_THEMES,
  createExampleTheme,
  createThemeExport,
  setActiveTheme,
  importCustomThemes,
  parseThemeFileContent,
  sanitizeCustomCss,
  type ThemePackage,
} from './theme'
import { formatMovieCardEpisodePrefix, formatMovieCardEpisodeTitle, getMovieCardCover } from './components/movieCardCover'
import { calculateTheaterPlayerSize } from './player/useAmbientColor'

function createMemoryStorage() {
  const values = new Map<string, string>()
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value) },
    removeItem: (key: string) => { values.delete(key) },
    clear: () => values.clear(),
  } as Storage
}

function createDocumentStub() {
  const styles = new Map<string, string>()
  const attributes = new Map<string, string>()
  const styleElement = { id: '', textContent: '' }
  const children: any[] = []

  return {
    documentElement: {
      style: {
        setProperty: (name: string, value: string) => { styles.set(name, value) },
        removeProperty: (name: string) => { styles.delete(name) },
        getPropertyValue: (name: string) => styles.get(name) ?? '',
      },
      setAttribute: (name: string, value: string) => { attributes.set(name, value) },
      getAttribute: (name: string) => attributes.get(name) ?? null,
    },
    head: {
      appendChild: (node: any) => {
        children.push(node)
        return node
      },
    },
    createElement: () => styleElement,
    getElementById: (id: string) => children.find(node => node.id === id) ?? null,
    styleElement,
  } as any
}

function assertCssRuleColor(css: string, selector: string, tokenName: string) {
  const selectorIndex = css.indexOf(selector)
  assert.notEqual(selectorIndex, -1, `missing selector: ${selector}`)

  const closingBraceIndex = css.indexOf('}', selectorIndex)
  assert.notEqual(closingBraceIndex, -1, `missing rule end for selector: ${selector}`)

  const declarationIndex = css.indexOf(`color: var(${tokenName})`, selectorIndex)
  assert.ok(
    declarationIndex !== -1 && declarationIndex < closingBraceIndex,
    `${selector} should set color: var(${tokenName})`
  )
}

function cssRuleBody(css: string, selector: string, occurrence = 0) {
  let selectorIndex = -1
  let searchFrom = 0
  for (let index = 0; index <= occurrence; index += 1) {
    selectorIndex = css.indexOf(selector, searchFrom)
    if (selectorIndex === -1) break
    searchFrom = selectorIndex + selector.length
  }
  assert.notEqual(selectorIndex, -1, `missing selector: ${selector}`)

  const openBraceIndex = css.indexOf('{', selectorIndex)
  assert.notEqual(openBraceIndex, -1, `missing rule start for selector: ${selector}`)

  const closingBraceIndex = css.indexOf('}', openBraceIndex)
  assert.notEqual(closingBraceIndex, -1, `missing rule end for selector: ${selector}`)

  return css.slice(openBraceIndex + 1, closingBraceIndex)
}

function cssRuleBodyBetween(css: string, selector: string, endPattern: string) {
  const selectorIndex = css.indexOf(selector)
  assert.notEqual(selectorIndex, -1, `missing selector: ${selector}`)

  const openBraceIndex = css.indexOf('{', selectorIndex)
  assert.notEqual(openBraceIndex, -1, `missing rule start for selector: ${selector}`)

  const closingBraceIndex = css.indexOf(endPattern, openBraceIndex)
  assert.notEqual(closingBraceIndex, -1, `missing rule end pattern for selector: ${selector}`)

  return css.slice(openBraceIndex + 1, closingBraceIndex)
}

test('parseThemeFileContent validates and normalizes a theme package', () => {
  const parsed = parseThemeFileContent(JSON.stringify({
    name: 'night-theater',
    label: 'Night Theater',
    colorScheme: 'dark',
    tokens: {
      '--mt-color-accent': '#8bb7ff',
      '--mt-radius-panel': '18px',
      '--mt-page-background': 'linear-gradient(135deg, #01040a, #14213d)',
      '--ignored-token': '#fff',
    },
    customCss: ':root[data-mediatree-theme] .movie-title { color: var(--mt-color-accent); }',
  }), 'night-theater.json')

  assert.equal(parsed.name, 'night-theater')
  assert.equal(parsed.label, 'Night Theater')
  assert.equal(parsed.colorScheme, 'dark')
  assert.deepEqual(parsed.tokens, {
    '--mt-color-accent': '#8bb7ff',
    '--mt-page-background': 'linear-gradient(135deg, #01040a, #14213d)',
    '--mt-radius-panel': '18px',
  })
  assert.equal(parsed.customCss, ':root[data-mediatree-theme] .movie-title { color: var(--mt-color-accent); }')
})

test('parseThemeFileContent preserves advanced skin metadata and design tokens', () => {
  const parsed = parseThemeFileContent(JSON.stringify({
    schemaVersion: 2,
    name: 'md3-soft',
    label: 'MD3 Soft',
    version: '1.0.0',
    capabilities: ['tokens', 'custom-css', 'stable-selectors', 'layout', 'density', 'motion', 'unknown'],
    colorScheme: 'light',
    tokens: {
      '--mt-font-family': 'Roboto, "Noto Sans SC", sans-serif',
      '--mt-density-scale': '0.92',
      '--mt-layout-content-max': '118rem',
      '--mt-layout-gap': '1rem',
      '--mt-layout-page-padding-x-wide': '2rem',
      '--mt-layout-page-padding-y-wide': '2rem',
      '--mt-motion-fast': '120ms',
      '--mt-motion-normal': '240ms',
      '--mt-color-surface-container': '#f3edf7',
      '--mt-color-surface-container-high': '#ece6f0',
      '--mt-shadow-elevation-2': '0 2px 10px rgba(0,0,0,0.12)',
      '--mt-theme-style': 'md3',
    },
    customCss: '.mt-panel { border-radius: 28px; }\n.mt-button-primary { box-shadow: none; }',
  }), 'md3-soft.json')

  assert.equal(parsed.schemaVersion, 2)
  assert.equal(parsed.version, '1.0.0')
  assert.deepEqual(parsed.capabilities, ['tokens', 'custom-css', 'stable-selectors', 'layout', 'density', 'motion'])
  assert.equal(parsed.tokens['--mt-font-family'], 'Roboto, "Noto Sans SC", sans-serif')
  assert.equal(parsed.tokens['--mt-density-scale'], '0.92')
  assert.equal(parsed.tokens['--mt-layout-content-max'], '118rem')
  assert.equal(parsed.tokens['--mt-layout-page-padding-x-wide'], '2rem')
  assert.equal(parsed.tokens['--mt-motion-fast'], '120ms')
  assert.equal(parsed.tokens['--mt-color-surface-container'], '#f3edf7')
  assert.equal(parsed.tokens['--mt-shadow-elevation-2'], '0 2px 10px rgba(0,0,0,0.12)')
  assert.equal(parsed.tokens['--mt-theme-style'], 'md3')
  assert.equal(
    parsed.customCss,
    ':root[data-mediatree-theme] .mt-panel { border-radius: 28px; }\n:root[data-mediatree-theme] .mt-button-primary { box-shadow: none; }'
  )
})

test('parseThemeFileContent rejects unsafe custom CSS', () => {
  assert.throws(
    () => parseThemeFileContent(JSON.stringify({
      name: 'unsafe',
      label: 'Unsafe',
      customCss: '.x { background: url(https://example.com/pixel); }',
    }), 'unsafe.json'),
    /不允许使用 @import、javascript:、外链 url 或 data:/
  )
})

test('built-in themes do not include removed light schemes', () => {
  assert.equal(
    BUILTIN_THEMES.some(item => item.name === 'material-you-light' || item.label === 'Material You 浅色'),
    false
  )
  assert.equal(
    BUILTIN_THEMES.some(item => item.name === 'soft-daylight' || item.label === '晨光浅色'),
    false
  )
  assert.ok(BUILTIN_THEMES.every(theme => theme.schemaVersion === 2))
  assert.ok(BUILTIN_THEMES.every(theme => theme.capabilities?.includes('stable-selectors')))
})

test('setActiveTheme falls back safely from the removed soft-daylight theme', () => {
  const storage = createMemoryStorage()
  const doc = createDocumentStub()

  const applied = setActiveTheme('soft-daylight', storage, doc)

  assert.equal(applied.name, BUILTIN_THEMES[0].name)
  assert.equal(storage.getItem('mediatree_active_theme'), BUILTIN_THEMES[0].name)
  assert.equal(doc.documentElement.getAttribute('data-mediatree-theme'), BUILTIN_THEMES[0].name)
})

test('createExampleTheme emits advanced skin metadata and stable selector CSS', () => {
  const example = JSON.parse(createExampleTheme())

  assert.equal(example.schemaVersion, 2)
  assert.equal(example.version, '1.0.0')
  assert.ok(example.capabilities.includes('stable-selectors'))
  assert.ok(example.capabilities.includes('layout'))
  assert.equal(example.tokens['--mt-font-family'], 'Inter, "Noto Sans SC", "Microsoft YaHei", sans-serif')
  assert.equal(example.tokens['--mt-density-scale'], '0.96')
  assert.equal(example.tokens['--mt-layout-content-max'], 'none')
  assert.equal(example.tokens['--mt-layout-page-padding-x'], 'clamp(2rem, 3.6vw, 3rem)')
  assert.equal(example.tokens['--mt-layout-page-padding-x-wide'], 'clamp(2rem, 3.6vw, 3rem)')
  assert.equal(example.tokens['--mt-media-grid-min'], '9.75rem')
  assert.equal(example.tokens['--mt-media-grid-max'], '11rem')
  assert.equal(example.tokens['--mt-media-card-width'], '11rem')
  assert.equal(example.tokens['--mt-media-card-height'], '16.5rem')
  assert.equal(example.tokens['--mt-media-grid-gap'], '1rem')
  assert.equal(example.tokens['--mt-media-grid-column-gap'], '1rem')
  assert.equal(example.tokens['--mt-media-grid-row-gap'], '1.25rem')
  assert.equal(example.tokens['--mt-theme-style'], 'advanced-skin')
  assert.match(example.customCss, /\.mt-panel/)
  assert.match(example.customCss, /\.mt-media-card/)
})

test('sanitizeCustomCss scopes broad selectors to the theme root', () => {
  assert.equal(
    sanitizeCustomCss('body { color: red; }\n.glass-panel { border-radius: 10px; }'),
    ':root[data-mediatree-theme] body { color: red; }\n:root[data-mediatree-theme] .glass-panel { border-radius: 10px; }'
  )
})

test('global CSS exposes stable theme hook selectors', () => {
  const css = readFileSync('src/index.css', 'utf8')
  for (const selector of [
    '.mt-app-shell',
    '.mt-topbar',
    '.mt-content',
    '.mt-panel',
    '.mt-card',
    '.mt-button',
    '.mt-button-primary',
    '.mt-input',
    '.mt-chip',
    '.liquid-glass',
    '.mt-popover',
    '.mt-dialog',
    '.mt-media-card',
  ]) {
    assert.ok(css.includes(selector), `missing stable selector: ${selector}`)
  }
})

test('topbar keeps split liquid glass groups', () => {
  const app = readFileSync('src/App.tsx', 'utf8')
  const topbar = app.match(/<header[\s\S]*?className=\{`mt-topbar[\s\S]*?<\/header>/)?.[0] ?? ''

  assert.match(topbar, /className=\{`mt-topbar sticky top-0 z-50 pt-6 sm:pt-9/)
  assert.doesNotMatch(topbar, /pt-2 sm:pt-3/)
  assert.match(topbar, /\$\{topbarCompact \? 'is-compact' : 'is-expanded'\}/)
  assert.match(topbar, /\$\{settingsDrawerOpen \? 'is-settings-drawer-open' : ''\}/)
  assert.match(topbar, /onPointerEnter=\{\(\) => setTopbarHovering\(true\)\}/)
  assert.match(topbar, /onPointerLeave=\{\(\) => setTopbarHovering\(false\)\}/)
  assert.match(topbar, /onFocusCapture=\{\(\) => setTopbarFocused\(true\)\}/)
  assert.match(topbar, /className="topbar-shell flex h-12 w-full min-w-0 items-center justify-between gap-2 transform-gpu sm:h-14 sm:gap-3"/)
  assert.match(topbar, /className="flex min-w-0 items-center gap-1\.5 liquid-glass topbar-glass topbar-left-glass/)
  assert.match(topbar, /className="flex items-center justify-end gap-1\.5 liquid-glass topbar-glass topbar-right-glass/)
  assert.match(topbar, /className="topbar-brand-link shrink-0 text-base font-semibold tracking-tight text-white transition-colors hover:text-white sm:text-lg"/)
  assert.match(topbar, /className="topbar-logo-mark" src="\/site-logo\.png"/)
  assert.match(topbar, /className="topbar-compact-library-trigger"/)
  assert.match(topbar, /ref=\{topbarLeftRef\}/)
  assert.match(topbar, /ref=\{topbarRightRef\}/)
  assert.match(topbar, /className="topbar-collapsible topbar-nav/)
  assert.match(topbar, /className="topbar-collapsible topbar-right-expanded/)
  assert.match(topbar, /className="topbar-collapsible topbar-right-expanded[\s\S]*<\/div>\s*<button[\s\S]*className="topbar-compact-library-trigger"/)
  assert.match(topbar, /ref=\{desktopSearchRootRef\} className="relative shrink-0"/)
  assert.match(topbar, /className="glass-button topbar-library-button/)
  assert.match(topbar, /className="topbar-library-label hidden truncate sm:inline-block"/)
  assert.match(topbar, /className="glass-chip topbar-library-chip/)
  assert.match(topbar, /className="topbar-icon-button hidden sm:inline-flex"/)
  assert.match(topbar, /onClick=\{openSettingsDrawer\}[\s\S]*className=\{`topbar-icon-button relative inline-flex/)
  assert.match(topbar, /aria-label="设置"/)
  assert.match(topbar, /\{hasUpdate && <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-red-500" \/>}/)
  assert.doesNotMatch(topbar, /\{hasUpdate && <span className="absolute -top-1 -right-1\.5 h-2 w-2 rounded-full bg-red-500" \/>}/)
  assert.match(topbar, /className="topbar-round-button rounded-full text-white transition-colors hover:bg-red-500\/10 hover:text-white"/)
  assert.match(topbar, /aria-label="展开搜索"/)
  assert.match(topbar, /aria-label="收起搜索"/)
  assert.match(topbar, /className=\{`topbar-search-form \$\{desktopSearchOpen \? 'is-open' : ''\} hidden sm:flex`\}/)
  assert.match(topbar, /topbar-search-form[\s\S]*<\/form>[\s\S]*className="rounded-full p-1\.5 text-white transition-colors hover:bg-white\/10 sm:p-2 sm:hidden"[\s\S]*<button[\s\S]*onClick=\{openSettingsDrawer\}/)
  assert.doesNotMatch(topbar, /item\.path === '\/settings'/)
  assert.match(topbar, /className="topbar-search-input glass-input/)
  assert.match(topbar, /\? 'bg-white\/18 text-white shadow-sm'\s*:\s*'text-white hover:bg-white\/10'/)
  assert.match(topbar, /className="rounded-full px-1\.5 py-1\.5 text-xs text-white transition-colors hover:bg-white\/10 sm:px-2"/)
  assert.match(topbar, /className="rounded-full p-1\.5 text-white transition-colors hover:bg-white\/10 sm:p-2 sm:hidden"/)
  assert.doesNotMatch(topbar, /className="rounded-full p-1\.5 text-white transition-colors hover:bg-red-500\/10 hover:text-white sm:p-2"/)
  assert.match(app, /const \[desktopSearchOpen, setDesktopSearchOpen\] = useState\(false\)/)
  assert.match(app, /const settingsDrawerOpen = location\.pathname === '\/settings'/)
  assert.match(app, /className=\{`mt-topbar sticky top-0 z-50 pt-6 sm:pt-9 \$\{topbarCompact \? 'is-compact' : 'is-expanded'\} \$\{settingsDrawerOpen \? 'is-settings-drawer-open' : ''\}`\}/)
  assert.match(app, /const mainRouteLocation = settingsDrawerOpen/)
  assert.match(app, /const contentPathname = settingsDrawerOpen/)
  assert.match(app, /const openSettingsDrawer = \(\) => \{[\s\S]*navigate\('\/settings', \{ state: \{ settingsBackgroundLocation: mainRouteLocation \} \}\)/)
  assert.match(app, /const closeSettingsDrawer = \(\) => \{[\s\S]*navigate\('\/', \{ replace: true \}\)/)
  assert.match(app, /<Routes key=\{activeLib\} location=\{mainRouteLocation\}>/)
  assert.match(app, /<Route path="\/settings" element=\{<Home \/>\} \/>/)
  assert.match(app, /<Settings open onClose=\{closeSettingsDrawer\} \/>/)
  assert.match(app, /const onWheel = \(event: WheelEvent\) => \{[\s\S]*event\.deltaY > 0[\s\S]*event\.deltaY < 0[\s\S]*\}/)
  assert.match(app, /window\.addEventListener\('wheel', onWheel, \{ passive: true \}\)/)
  assert.doesNotMatch(app, /window\.scrollY > 8/)
  assert.doesNotMatch(app, /window\.requestAnimationFrame\(updateTopbarPosition\)/)
  assert.match(app, /const TOPBAR_LIBRARY_LABEL_LIMIT = 5/)
  assert.match(app, /const TOPBAR_LIBRARY_LABEL_PREFIX = 2/)
  assert.match(app, /function formatTopbarLibraryLabel\(label: string\)/)
  assert.match(app, /Array\.from\(normalized\)/)
  assert.match(app, /chars\.slice\(0, TOPBAR_LIBRARY_LABEL_PREFIX\)\.join\(''\)\}\.\.\.`/)
  assert.match(app, /const currentLibraryDisplayLabel = formatTopbarLibraryLabel\(currentLibraryLabel\)/)
  assert.match(topbar, /\{currentLibraryDisplayLabel \|\| '库'\}/)
  assert.match(topbar, /\{currentLibraryDisplayLabel\}/)
  assert.match(app, /useLayoutEffect/)
  assert.match(app, /const measureTopbarGlass = useCallback/)
  assert.match(app, /const flushTopbarLayout = useCallback/)
  assert.match(app, /const setTopbarWheelDirectionWithMeasure = useCallback/)
  assert.match(app, /--mt-topbar-expanded-width/)
  assert.match(app, /const measureExpandedTopbarGlass = useCallback/)
  assert.match(app, /cloneNode\(true\) as HTMLElement/)
  assert.match(app, /className = 'mt-topbar is-expanded topbar-measure-host'/)
  assert.match(app, /clone\.style\.setProperty\('inline-size', 'max-content'\)/)
  assert.doesNotMatch(app, /clone\.querySelector\('\.topbar-search-form'\)\?\.classList\.add\('is-open'\)/)
  assert.match(app, /element\.style\.setProperty\('--mt-topbar-expanded-width', `\$\{width\}px`\)/)
  assert.match(app, /const desktopSearchRootRef = useRef<HTMLDivElement \| null>\(null\)/)
  assert.match(app, /document\.addEventListener\('pointerdown', handlePointerDown, true\)/)
  assert.match(app, /desktopSearchRootRef\.current\?\.contains\(target\)/)
  assert.match(app, /document\.removeEventListener\('pointerdown', handlePointerDown, true\)/)
  assert.match(app, /topbarHovering \|\| desktopSearchOpen \|\| mobileNavOpen \|\| mobileSearchOpen \|\| showLibraryModal/)
  assert.doesNotMatch(app, /topbarHovering \|\| topbarFocused \|\| searchOpen \|\| desktopSearchOpen/)
  assert.match(app, /setTopbarFocused\(false\)[\s\S]*setDesktopSearchOpen\(false\)[\s\S]*setSearchOpen\(false\)[\s\S]*setMobileSearchOpen\(false\)/)
  assert.match(app, /currentLibraryDisplayLabel,\s*libraries\.length,\s*location\.pathname,\s*hasUpdate,\s*desktopSearchOpen\]/)
  assert.match(app, /const topbarShouldCompact = topbarWheelDirection === 'down' && !topbarOpenByInteraction/)
  assert.match(app, /if \(topbarShouldCompact\) \{[\s\S]*measureTopbarGlass\(\)[\s\S]*flushTopbarLayout\(\)[\s\S]*window\.requestAnimationFrame\(\(\) => \{[\s\S]*window\.requestAnimationFrame\(\(\) => \{[\s\S]*setTopbarCompact\(true\)/)
  assert.doesNotMatch(topbar, /text-gray-[0-9]+/)
  assert.doesNotMatch(topbar, /hover:text-(?!white)/)
  assert.doesNotMatch(topbar, /style=\{\{ boxShadow:/)
  assert.doesNotMatch(app, /<header[^>]*liquid-glass/)
})

test('topbar compact mode animates into two icon spheres', () => {
  const css = readFileSync('src/index.css', 'utf8')
  const topbar = cssRuleBody(css, '.mt-topbar {')
  const topbarShell = cssRuleBody(css, '.mt-topbar .topbar-shell {')
  const topbarGlass = cssRuleBody(css, '.mt-topbar .topbar-glass {')
  const brandText = cssRuleBody(css, '.mt-topbar .topbar-brand-text {')
  const leftGlass = cssRuleBody(css, '.mt-topbar .topbar-left-glass {')
  const rightGlass = cssRuleBody(css, '.mt-topbar .topbar-right-glass {')
  const collapsible = cssRuleBody(css, '.mt-topbar .topbar-collapsible,')
  const compactGlass = cssRuleBody(css, '.mt-topbar.is-compact .topbar-glass {')
  const compactRightGlass = cssRuleBody(css, '.mt-topbar.is-compact .topbar-right-glass {')
  const compactCollapsed = cssRuleBody(css, '.mt-topbar.is-compact .topbar-brand-text,')
  const topbarGlassOverlay = cssRuleBody(css, '.mt-topbar .topbar-glass::after {')
  const logo = cssRuleBody(css, '.mt-topbar .topbar-logo-mark {')
  const compactLibraryTrigger = cssRuleBody(css, '.mt-topbar .topbar-compact-library-trigger {')
  const compactLibraryTriggerIcon = cssRuleBody(css, '.mt-topbar .topbar-compact-library-trigger svg {')
  const topbarIconButton = cssRuleBody(css, '.mt-topbar .topbar-icon-button {')
  const topbarMetrics = cssRuleBody(css, '.mt-topbar .topbar-icon-button,')
  const controlShadowRule = cssRuleBody(css, '.mt-topbar .topbar-library-button,', 1)
  const libraryButton = cssRuleBody(css, '.mt-topbar .topbar-library-button {')
  const libraryLabel = cssRuleBody(css, '.mt-topbar .topbar-library-label {')
  const roundButton = cssRuleBody(css, '.mt-topbar .topbar-round-button {', 1)
  const searchForm = cssRuleBody(css, '.mt-topbar .topbar-search-form {')
  const searchOpenForm = cssRuleBody(css, '.mt-topbar .topbar-search-form.is-open {')
  const searchInput = cssRuleBody(css, '.mt-topbar .topbar-search-input {')
  const compactLogo = cssRuleBody(css, '.mt-topbar.is-compact .topbar-logo-mark {')
  const compactTrigger = cssRuleBody(css, '.mt-topbar.is-compact .topbar-compact-library-trigger {')

  assert.match(topbar, /--mt-topbar-ball-size:\s*2\.625rem;/)
  assert.match(topbar, /--mt-topbar-logo-size:\s*2\.0625rem;/)
  assert.match(topbar, /--mt-topbar-compact-action-icon-size:\s*1rem;/)
  assert.match(topbar, /--mt-topbar-expanded-radius:\s*1\.125rem;/)
  assert.match(topbar, /--mt-topbar-compact-radius:\s*calc\(var\(--mt-topbar-ball-size\)\s*\/\s*2\);/)
  assert.match(topbar, /--mt-topbar-motion-duration:\s*1488ms;/)
  assert.match(topbar, /--mt-topbar-content-duration:\s*1152ms;/)
  assert.match(topbar, /--mt-topbar-icon-fade-duration:\s*560ms;/)
  assert.match(topbar, /--mt-topbar-icon-exit-duration:\s*420ms;/)
  assert.match(topbar, /--mt-topbar-compact-icon-delay:\s*280ms;/)
  assert.match(topbar, /--mt-topbar-content-reveal-delay:\s*420ms;/)
  assert.match(topbar, /--mt-topbar-content-stagger:\s*100ms;/)
  assert.match(topbar, /--mt-topbar-text-fade-duration:\s*960ms;/)
  assert.match(topbar, /opacity:\s*1;/)
  assert.match(topbar, /transform:\s*translateY\(0\);/)
  assert.match(topbar, /transition:[^}]*opacity\s+260ms\s+ease/s)
  assert.match(topbar, /transition:[^}]*transform\s+260ms\s+ease/s)
  assert.match(topbar, /will-change:\s*opacity,\s*transform;/)
  assert.match(topbarShell, /padding-inline:\s*var\(--mt-layout-page-padding-x\);/)
  assert.match(css, /@media \(min-width:\s*640px\)\s*\{[^}]*\.mt-topbar \.topbar-shell\s*\{[^}]*padding-inline:\s*var\(--mt-layout-page-padding-x-wide\);/s)
  assert.match(topbarGlass, /inline-size:\s*var\(--mt-topbar-expanded-width,\s*auto\);/)
  assert.match(topbarGlass, /min-inline-size:\s*var\(--mt-topbar-ball-size\);/)
  assert.match(topbarGlass, /max-inline-size:\s*var\(--mt-topbar-expanded-width,\s*34rem\);/)
  assert.match(topbarGlass, /overflow:\s*hidden;/)
  assert.match(topbarGlass, /border-radius:\s*var\(--mt-topbar-expanded-radius\);/)
  assert.match(topbarGlass, /transition:[^}]*max-inline-size\s+var\(--mt-topbar-motion-duration\)\s+var\(--mt-topbar-ease\)/s)
  assert.match(topbarGlass, /transition:[^}]*border-radius\s+var\(--mt-topbar-motion-duration\)\s+var\(--mt-topbar-ease\)/s)
  assert.match(topbarGlass, /will-change:\s*max-inline-size,\s*inline-size,\s*border-radius,\s*padding,\s*transform;/)
  assert.match(topbarGlassOverlay, /border-radius\s+var\(--mt-topbar-motion-duration\)\s+var\(--mt-topbar-ease\)/)
  assert.match(leftGlass, /position:\s*relative;/)
  assert.match(leftGlass, /transform-origin:\s*left center;/)
  assert.match(rightGlass, /transform-origin:\s*right center;/)
  assert.match(brandText, /opacity\s+var\(--mt-topbar-text-fade-duration\)\s+ease\s+var\(--mt-topbar-content-reveal-delay\)/)
  assert.match(collapsible, /min-inline-size:\s*0;/)
  assert.match(collapsible, /opacity\s+var\(--mt-topbar-text-fade-duration\)\s+ease\s+calc\(var\(--mt-topbar-content-reveal-delay\)\s*\+\s*var\(--mt-topbar-content-stagger\)\)/)
  assert.match(compactGlass, /(^|\n)\s*inline-size:\s*var\(--mt-topbar-ball-size\);/)
  assert.match(compactGlass, /min-inline-size:\s*var\(--mt-topbar-ball-size\);/)
  assert.match(compactGlass, /max-inline-size:\s*var\(--mt-topbar-ball-size\);/)
  assert.match(compactGlass, /block-size:\s*var\(--mt-topbar-ball-size\);/)
  assert.match(compactGlass, /border-radius:\s*var\(--mt-topbar-compact-radius\);/)
  assert.doesNotMatch(compactGlass, /border-radius:\s*999px;/)
  assert.match(compactRightGlass, /align-items:\s*center;/)
  assert.match(compactRightGlass, /justify-content:\s*center;/)
  assert.match(compactCollapsed, /inline-size:\s*0;/)
  assert.match(compactCollapsed, /min-inline-size:\s*0;/)
  assert.match(compactCollapsed, /max-inline-size:\s*0;/)
  assert.match(compactCollapsed, /flex-basis:\s*0;/)
  assert.match(compactCollapsed, /opacity:\s*0;/)
  assert.match(compactCollapsed, /pointer-events:\s*none;/)
  assert.match(compactCollapsed, /opacity\s+var\(--mt-topbar-text-fade-duration\)\s+ease[;,]/)
  assert.doesNotMatch(css, /\.mt-topbar\.is-compact \.topbar-brand-text,[^}]*\.mt-topbar\.is-compact \.topbar-collapsible\s*\{[^}]*transform:\s*translateX/s)
  assert.doesNotMatch(css, /\.mt-topbar\.is-compact \.topbar-right-expanded\s*\{[^}]*transform:\s*translateX/s)
  assert.match(logo, /opacity\s+var\(--mt-topbar-icon-exit-duration\)\s+ease;/)
  assert.match(logo, /position:\s*absolute;/)
  assert.match(logo, /inset-inline-start:\s*calc\(\(var\(--mt-topbar-ball-size\)\s*-\s*var\(--mt-topbar-logo-size\)\)\s*\/\s*2\);/)
  assert.match(logo, /inline-size:\s*var\(--mt-topbar-logo-size\);/)
  assert.match(logo, /block-size:\s*var\(--mt-topbar-logo-size\);/)
  assert.match(logo, /max-inline-size:\s*var\(--mt-topbar-logo-size\);/)
  assert.doesNotMatch(logo, /transform:/)
  assert.match(compactLibraryTrigger, /opacity\s+var\(--mt-topbar-icon-exit-duration\)\s+ease,/)
  assert.match(compactLibraryTrigger, /block-size:\s*100%;/)
  assert.match(compactLibraryTrigger, /justify-content:\s*center;/)
  assert.match(compactLibraryTrigger, /padding:\s*0;/)
  assert.doesNotMatch(compactLibraryTrigger, /transform:/)
  assert.match(compactLibraryTriggerIcon, /display:\s*block;/)
  assert.match(compactLibraryTriggerIcon, /inline-size:\s*var\(--mt-topbar-compact-action-icon-size\);/)
  assert.match(compactLibraryTriggerIcon, /block-size:\s*var\(--mt-topbar-compact-action-icon-size\);/)
  assert.match(topbarMetrics, /block-size:\s*2rem;/)
  assert.match(topbarMetrics, /align-items:\s*center;/)
  assert.match(topbarMetrics, /justify-content:\s*center;/)
  assert.match(topbarMetrics, /line-height:\s*1;/)
  assert.match(topbarIconButton, /background:\s*transparent;/)
  assert.match(topbarIconButton, /box-shadow:\s*none;/)
  assert.match(topbarIconButton, /transition:[^}]*box-shadow\s+var\(--mt-motion-fast\)\s+ease/s)
  assert.match(controlShadowRule, /box-shadow:\s*none;/)
  assert.match(libraryButton, /padding-block:\s*0;/)
  assert.match(libraryLabel, /max-inline-size:\s*4\.25rem;/)
  assert.match(roundButton, /inline-size:\s*2rem;/)
  assert.match(roundButton, /padding:\s*0;/)
  assert.match(css, /\.mt-topbar \.topbar-icon-button:hover,[^}]*\.mt-topbar \.topbar-icon-button:focus-visible\s*\{[^}]*box-shadow:\s*0 8px 22px rgba\(0,\s*0,\s*0,\s*0\.18\);/s)
  assert.match(css, /\.mt-topbar \.topbar-library-button:hover,[^}]*\.mt-topbar \.topbar-search-form.is-open:focus-within\s*\{[^}]*box-shadow:\s*0 8px 22px rgba\(0,\s*0,\s*0,\s*0\.18\);/s)
  assert.match(searchForm, /inline-size:\s*2rem;/)
  assert.match(searchForm, /block-size:\s*2rem;/)
  assert.match(searchForm, /line-height:\s*1;/)
  assert.match(searchForm, /background:\s*transparent;/)
  assert.match(searchForm, /box-shadow:\s*none;/)
  assert.match(searchOpenForm, /inline-size:\s*14rem;/)
  assert.match(searchOpenForm, /background:\s*var\(--mt-color-control\);/)
  assert.match(searchInput, /opacity:\s*0;/)
  assert.match(searchInput, /padding-inline:\s*0\.45rem 0\.25rem;/)
  assert.match(searchInput, /font-size:\s*0\.8125rem;/)
  assert.match(searchInput, /line-height:\s*1;/)
  assert.match(css, /\.mt-topbar \.topbar-search-input::placeholder\s*\{[^}]*font-size:\s*0\.8125rem;/s)
  assert.match(css, /\.mt-topbar \.topbar-search-form\.is-open \.topbar-search-input\s*\{[^}]*opacity:\s*1;/s)
  assert.match(compactLogo, /opacity:\s*1;/)
  assert.match(compactLogo, /opacity\s+var\(--mt-topbar-icon-fade-duration\)\s+ease\s+var\(--mt-topbar-compact-icon-delay\);/)
  assert.doesNotMatch(compactLogo, /transform:/)
  assert.match(compactTrigger, /inline-size:\s*var\(--mt-topbar-ball-size\);/)
  assert.match(compactTrigger, /max-inline-size:\s*var\(--mt-topbar-ball-size\);/)
  assert.match(compactTrigger, /block-size:\s*var\(--mt-topbar-ball-size\);/)
  assert.match(compactTrigger, /flex:\s*0 0 var\(--mt-topbar-ball-size\);/)
  assert.match(compactTrigger, /opacity\s+var\(--mt-topbar-icon-fade-duration\)\s+ease\s+var\(--mt-topbar-compact-icon-delay\),/)
  assert.match(compactTrigger, /pointer-events:\s*auto;/)
  assert.doesNotMatch(compactTrigger, /transform:/)

  const settingsOpenTopbar = cssRuleBody(css, '.mt-topbar.is-settings-drawer-open {')
  assert.match(settingsOpenTopbar, /opacity:\s*0;/)
  assert.match(settingsOpenTopbar, /pointer-events:\s*none;/)
  assert.match(settingsOpenTopbar, /transform:\s*translateY\(-0\.35rem\);/)
})

test('settings drawer aligns to the topbar and keeps selection weight only on active tabs', () => {
  const settings = readFileSync('src/pages/settings/Settings.tsx', 'utf8')
  const css = readFileSync('src/index.css', 'utf8')

  assert.match(settings, /const \[closing, setClosing\] = useState\(false\)/)
  assert.match(settings, /const \[settingsScrollbarVisible, setSettingsScrollbarVisible\] = useState\(false\)/)
  assert.match(settings, /const settingsScrollbarTimer = useRef<number \| null>\(null\)/)
  assert.match(settings, /const revealSettingsScrollbar = useCallback\(\(\) => \{[\s\S]*setSettingsScrollbarVisible\(true\)[\s\S]*window\.setTimeout\(\(\) => \{[\s\S]*setSettingsScrollbarVisible\(false\)[\s\S]*\}, 2000\)/)
  assert.match(settings, /const cardClass = "settings-section"/)
  assert.match(settings, /const sectionTitle = "settings-section-title"/)
  assert.match(settings, /const tabButtonClass = "settings-tab-button"/)
  assert.match(settings, /settings-drawer-panel liquid-glass/)
  assert.match(settings, /max-w-\[min\(100vw-1rem,36rem\)\]/)
  assert.match(settings, /className=\{\"settings-drawer-backdrop fixed inset-0 z-\[60\]\" \+ \(closing \? ' is-closing' : ''\)\}/)
  assert.doesNotMatch(settings, /settings-drawer-backdrop fixed inset-0 z-\[60\][^\"]*bg-black/)
  assert.doesNotMatch(settings, /settings-drawer-backdrop fixed inset-0 z-\[60\][^\"]*backdrop-blur/)
  assert.match(settings, /settings-drawer-shell flex h-full w-full justify-end px-3 py-6 sm:px-4 sm:py-9/)
  assert.match(settings, /settings-drawer-panel liquid-glass flex h-full/)
  assert.doesNotMatch(settings, /settings-drawer-panel liquid-glass[^"]*border border-white\/10/)
  assert.doesNotMatch(settings, /settings-drawer-panel liquid-glass[^"]*shadow-glass/)
  assert.match(settings, /settings-drawer-header flex shrink-0 items-start justify-between gap-4 border-b border-white\/10/)
  assert.match(settings, /settings-drawer-body flex min-h-0 flex-1 gap-2/)
  assert.match(settings, /settings-row-copy/)
  assert.match(settings, /settings-tab-content settings-scroll-content[^"]*flex-1[^"]*overflow-y-auto/)
  assert.match(settings, /onScroll=\{revealSettingsScrollbar\}/)
  assert.match(settings, /settingsScrollbarVisible \? ' is-scrolling' : ''/)
  assert.match(settings, /settings-tab-rail flex shrink-0 flex-col gap-0\.5/)
  assert.doesNotMatch(settings, /settings-tab-rail liquid-glass/)
  assert.doesNotMatch(settings, /rounded-\[1\.5rem\][^"]*settings-tab-rail/)
  assert.match(settings, /role="tablist"/)
  assert.match(settings, /aria-orientation="vertical"/)
  assert.match(settings, /role="tab"/)
  assert.match(settings, /aria-selected=\{active\}/)
  assert.match(settings, /className="settings-tab-label"/)
  assert.doesNotMatch(settings, /<span className="truncate">\{tab\.label\}<\/span>/)
  assert.match(settings, /className=\{tabButtonClass \+ " " \+ \(active \? 'is-active text-white' : 'text-gray-400 hover:text-white'\)\}/)
  assert.doesNotMatch(settings, /is-active border-apple-blue\/40 bg-apple-blue\/18 text-apple-blue shadow-glow/)
  assert.doesNotMatch(settings, /settings-tab-strip/)
  assert.doesNotMatch(settings, /const cardClass = "glass-panel p-5"/)

  const panelRule = cssRuleBody(css, '.settings-drawer-panel {')
  assert.match(panelRule, /--settings-drawer-inner-padding:\s*clamp\(2rem, 4vw, 3rem\);/)
  assert.match(panelRule, /--settings-drawer-body-start-padding:\s*clamp\(1\.15rem, 2\.4vw, 1\.65rem\);/)
  assert.match(panelRule, /inline-size:\s*min\(calc\(100vw - 1rem\), 36rem\)/)
  assert.doesNotMatch(panelRule, /block-size:\s*min\(calc\(100dvh - var\(--settings-drawer-safe-area\)/)
  assert.doesNotMatch(panelRule, /max-inline-size:\s*none;/)
  assert.match(panelRule, /animation:\s*settings-drawer-panel-in 0\.52s cubic-bezier\(0\.16, 1, 0\.3, 1\) both/)
  assert.doesNotMatch(panelRule, /background:/)
  assert.doesNotMatch(panelRule, /backdrop-filter:/)
  assert.doesNotMatch(panelRule, /-webkit-backdrop-filter:/)
  assert.doesNotMatch(panelRule, /box-shadow:/)
  assert.doesNotMatch(panelRule, /var\(--mt-color-surface\)/)
  assert.doesNotMatch(panelRule, /var\(--mt-backdrop-panel\)/)
  assert.doesNotMatch(panelRule, /background:\s*var\(--mt-color-surface\);/)
  assert.doesNotMatch(panelRule, /rgba\(10, 132, 255/)
  assert.doesNotMatch(panelRule, /brightness\(/)
  assert.doesNotMatch(panelRule, /blur\(/)
  assert.doesNotMatch(panelRule, /linear-gradient/)
  assert.doesNotMatch(panelRule, /radial-gradient/)
  assert.doesNotMatch(panelRule, /inset/)
  assert.doesNotMatch(css, /\.settings-drawer-panel::before\s*\{/)
  assert.doesNotMatch(css, /\.settings-drawer-panel::after\s*\{/)

  const panelGlassRule = cssRuleBody(css, ':root .settings-drawer-panel.liquid-glass {')
  assert.match(panelGlassRule, /border:\s*0;/)
  assert.doesNotMatch(panelGlassRule, /border-color:/)
  assert.match(panelGlassRule, /background:\s*rgba\(5, 7, 13, 0\.96\);/)
  assert.match(panelGlassRule, /backdrop-filter:\s*blur\(34px\) saturate\(170%\);/)
  assert.match(panelGlassRule, /-webkit-backdrop-filter:\s*blur\(34px\) saturate\(170%\);/)
  assert.match(panelGlassRule, /box-shadow:\s*none;/)
  assert.doesNotMatch(panelGlassRule, /linear-gradient|radial-gradient|rgba\(10,\s*132,\s*255|brightness\(|inset/)

  const shellRule = cssRuleBody(css, '.settings-drawer-shell {')
  assert.match(shellRule, /align-items:\s*stretch;/)
  assert.doesNotMatch(shellRule, /justify-content:\s*center;/)
  assert.doesNotMatch(shellRule, /padding:\s*var\(--settings-drawer-safe-area\);/)

  const headerRule = cssRuleBody(css, '.settings-drawer-header {')
  assert.match(headerRule, /padding:\s*var\(--settings-drawer-inner-padding\);/)

  const bodyRule = cssRuleBody(css, '.settings-drawer-body {')
  assert.match(bodyRule, /min-height:\s*0;/)
  assert.match(bodyRule, /padding:\s*var\(--settings-drawer-body-start-padding\) var\(--settings-drawer-inner-padding\) var\(--settings-drawer-inner-padding\);/)

  const scrollRule = cssRuleBody(css, '.settings-scroll-content {')
  assert.match(scrollRule, /overflow-x:\s*hidden;/)
  assert.match(scrollRule, /overflow-y:\s*auto;/)
  assert.match(scrollRule, /scrollbar-gutter:\s*stable;/)
  assert.match(scrollRule, /scrollbar-width:\s*thin;/)
  assert.match(scrollRule, /scrollbar-color:\s*transparent transparent;/)

  const scrollActiveRule = cssRuleBody(css, '.settings-scroll-content.is-scrolling {')
  assert.match(scrollActiveRule, /scrollbar-color:\s*rgba\(255, 255, 255, 0\.24\) transparent;/)
  assert.match(css, /\.settings-scroll-content::-webkit-scrollbar\s*\{[^}]*width:\s*6px;[^}]*height:\s*0;[^}]*\}/s)
  assert.match(css, /\.settings-scroll-content::-webkit-scrollbar-thumb\s*\{[^}]*background:\s*transparent;[^}]*\}/s)
  assert.match(css, /\.settings-scroll-content\.is-scrolling::-webkit-scrollbar-thumb\s*\{[^}]*background:\s*rgba\(255, 255, 255, 0\.24\);[^}]*\}/s)

  const panelOutRule = cssRuleBody(css, '.settings-drawer-panel.is-closing {')
  assert.match(panelOutRule, /settings-drawer-panel-out 0\.42s cubic-bezier\(0\.76, 0, 0\.24, 1\) both/)

  const sectionRule = cssRuleBody(css, '.settings-section {')
  assert.match(sectionRule, /padding:\s*1rem 0 0;/)
  assert.match(sectionRule, /border-top:\s*1px solid rgba\(255, 255, 255, 0\.1\)/)
  assert.match(sectionRule, /background:\s*transparent;/)
  assert.match(sectionRule, /box-shadow:\s*none;/)
  assert.doesNotMatch(sectionRule, /border-radius:/)

  const firstSectionRule = cssRuleBody(css, '.settings-section:first-child {')
  assert.match(firstSectionRule, /border-top:\s*0;/)
  assert.match(firstSectionRule, /padding-top:\s*0;/)

  assert.match(settings, /mt-4 border-t border-white\/10 pt-4/)
  assert.match(settings, /mt-3 border-t border-white\/10 pt-3/)
  assert.doesNotMatch(settings, /flex shrink-0 items-start justify-between gap-4 border-b border-white\/10 px-4 py-4 sm:px-5/)
  assert.doesNotMatch(settings, /settings-drawer-header[^\n]*px-4 py-4/)
  assert.doesNotMatch(settings, /settings-drawer-header[^\n]*p-5/)

  const rowCopyRule = cssRuleBody(css, '.settings-row-copy {')
  assert.match(rowCopyRule, /display:\s*grid;/)
  assert.match(rowCopyRule, /align-content:\s*center;/)
  assert.match(rowCopyRule, /gap:\s*0\.1875rem;/)

  const railRule = cssRuleBody(css, '.settings-tab-rail {')
  assert.match(railRule, /inline-size:\s*6\.6rem/)
  assert.match(railRule, /border:\s*0;/)
  assert.match(railRule, /background:\s*transparent;/)
  assert.match(railRule, /box-shadow:\s*none;/)
  assert.doesNotMatch(railRule, /border-left:/)
  assert.doesNotMatch(railRule, /backdrop-filter:/)
  assert.match(railRule, /animation:\s*settings-tab-rail-in 0\.44s cubic-bezier\(0\.22, 1, 0\.36, 1\) both/)

  const tabButtonRule = cssRuleBody(css, '.settings-tab-rail .settings-tab-button {')
  assert.match(tabButtonRule, /min-height:\s*2\.15rem;/)
  assert.match(tabButtonRule, /border:\s*0;/)
  assert.match(tabButtonRule, /background:\s*transparent;/)
  assert.match(tabButtonRule, /box-shadow:\s*none;/)
  assert.match(tabButtonRule, /padding:\s*0\.45rem 0\.78rem;/)
  assert.match(tabButtonRule, /font-size:\s*0\.76rem;/)
  assert.match(tabButtonRule, /font-weight:\s*600;/)
  assert.match(tabButtonRule, /line-height:\s*1\.2;/)

  const activeTabRule = cssRuleBody(css, '.settings-tab-rail .settings-tab-button.is-active {')
  assert.match(activeTabRule, /background:\s*rgba\(255, 255, 255, 0\.115\)/)
  assert.match(activeTabRule, /box-shadow:\s*0 10px 26px rgba\(0, 0, 0, 0\.24\),\s*inset 0 1px 0 rgba\(255, 255, 255, 0\.11\)/)

  const tabLabelRule = cssRuleBody(css, '.settings-tab-label {')
  assert.match(tabLabelRule, /overflow:\s*visible;/)
  assert.match(tabLabelRule, /text-overflow:\s*clip;/)
  assert.match(tabLabelRule, /white-space:\s*nowrap;/)

  assert.match(css, /@keyframes settings-drawer-panel-out/)
  assert.match(css, /@keyframes settings-drawer-backdrop-out/)
  assert.match(css, /@keyframes settings-tab-rail-in/)
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/)
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)\s*\{[\s\S]*\.mt-topbar,[\s\S]*\.mt-topbar\.is-settings-drawer-open,[\s\S]*transition:\s*none !important;[\s\S]*animation:\s*none !important;/)
})

test('settings drawer preserves the background scroll position', () => {
  const app = readFileSync('src/App.tsx', 'utf8')
  const css = readFileSync('src/index.css', 'utf8')

  assert.match(app, /type SettingsBackgroundScrollLock = \{[\s\S]*x: number[\s\S]*y: number[\s\S]*bottomOffset: number[\s\S]*\}/)
  assert.match(app, /function readSettingsBackgroundScrollLock\(\): SettingsBackgroundScrollLock/)
  assert.match(app, /bottomOffset:\s*Math\.max\(0, maxScrollY - window\.scrollY\)/)
  assert.match(app, /function getSettingsBackgroundRestoreY\(scrollLock: SettingsBackgroundScrollLock\): number/)
  assert.match(app, /scrollLock\.bottomOffset <= SETTINGS_BOTTOM_SCROLL_TOLERANCE/)
  assert.match(app, /return Math\.max\(0, maxScrollY - scrollLock\.bottomOffset\)/)
  assert.match(app, /const settingsBackgroundScrollRef = useRef<SettingsBackgroundScrollLock \| null>\(null\)/)
  assert.match(app, /settingsBackgroundScrollRef\.current = readSettingsBackgroundScrollLock\(\)/)
  assert.match(app, /const scrollLock = settingsBackgroundScrollRef\.current \|\| readSettingsBackgroundScrollLock\(\)/)
  assert.match(app, /body\.style\.overflowY = 'hidden'/)
  assert.match(app, /documentElement\.style\.overflowY = 'hidden'/)
  assert.match(app, /body\.style\.setProperty\('scrollbar-gutter', 'stable'\)/)
  assert.match(app, /documentElement\.style\.setProperty\('scrollbar-gutter', 'stable'\)/)
  assert.match(app, /window\.scrollTo\(scrollLock\.x, scrollLock\.y\)/)
  assert.doesNotMatch(app, /body\.style\.position = 'fixed'/)
  assert.doesNotMatch(app, /body\.style\.top = `-\$\{scrollLock\.y\}px`/)
  assert.match(app, /window\.history\.scrollRestoration = 'manual'/)
  assert.match(app, /const restoreScroll = \(\) => \{[\s\S]*window\.scrollTo\(scrollLock\.x, getSettingsBackgroundRestoreY\(scrollLock\)\)[\s\S]*\}/)
  assert.match(app, /window\.requestAnimationFrame\(\(\) => \{[\s\S]*restoreScroll\(\)[\s\S]*window\.requestAnimationFrame\(restoreScroll\)[\s\S]*\}\)/)
  assert.match(app, /window\.setTimeout\(restoreScroll, 80\)/)
  assert.match(css, /\.settings-drawer-backdrop\s*\{[^}]*overscroll-behavior:\s*contain;/s)
  assert.match(css, /\.settings-scroll-content\s*\{[^}]*overscroll-behavior:\s*contain;/s)
})

test('settings data tab constrains width without horizontal scrolling', () => {
  const settings = readFileSync('src/pages/settings/Settings.tsx', 'utf8')
  const css = readFileSync('src/index.css', 'utf8')

  assert.match(settings, /className="settings-backup-actions"/)
  assert.match(settings, /className="settings-file-field flex min-w-0 items-center gap-2"/)
  assert.match(settings, /className=\{inputClass \+ " settings-file-input"\}/)
  assert.match(settings, /className="settings-update-list"/)
  assert.match(settings, /className="settings-update-card space-y-3/)
  assert.match(settings, /className="settings-update-summary"/)
  assert.doesNotMatch(settings, /settings-update-summary flex flex-col/)
  assert.match(settings, /className="settings-update-title"/)
  assert.match(settings, /className="settings-update-version-row"/)
  assert.match(settings, /className="settings-update-version text-sm font-semibold text-white"/)
  assert.match(settings, /className="settings-update-date text-xs text-gray-500"/)
  assert.match(settings, /className="settings-update-meta/)
  assert.match(settings, /\{v\.reason && \(\s*<p className="settings-update-reason text-xs text-gray-400"/)
  assert.match(settings, /className="settings-update-actions flex flex-wrap items-center gap-2"/)
  assert.doesNotMatch(settings, /className="flex shrink-0 flex-wrap items-center gap-2"/)
  assert.match(settings, /className="settings-update-log max-h-48/)

  const tabStackRule = cssRuleBody(css, '.settings-tab-stack {')
  assert.match(tabStackRule, /min-width:\s*0;/)
  assert.match(tabStackRule, /max-width:\s*100%;/)
  assert.match(tabStackRule, /overflow:\s*hidden;/)

  const sectionRule = cssRuleBody(css, '.settings-section {')
  assert.match(sectionRule, /min-width:\s*0;/)
  assert.match(sectionRule, /max-width:\s*100%;/)
  assert.match(sectionRule, /overflow:\s*hidden;/)

  const backupActionsRule = cssRuleBody(css, '.settings-backup-actions {')
  assert.match(backupActionsRule, /display:\s*flex;/)
  assert.match(backupActionsRule, /flex-wrap:\s*wrap;/)
  assert.match(backupActionsRule, /max-width:\s*100%;/)

  const fileInputRule = cssRuleBody(css, '.settings-file-input {')
  assert.match(fileInputRule, /min-width:\s*0;/)
  assert.match(fileInputRule, /max-width:\s*100%;/)

  const updateListRule = cssRuleBody(css, '.settings-update-list {')
  assert.match(updateListRule, /display:\s*grid;/)
  assert.match(updateListRule, /min-width:\s*0;/)
  assert.match(updateListRule, /max-width:\s*100%;/)
  assert.match(updateListRule, /overflow:\s*hidden;/)

  const updateCardRule = cssRuleBody(css, '.settings-update-card {')
  assert.match(updateCardRule, /min-width:\s*0;/)
  assert.match(updateCardRule, /max-width:\s*100%;/)
  assert.match(updateCardRule, /overflow:\s*hidden;/)

  const updateSummaryRule = cssRuleBody(css, '.settings-update-summary {')
  assert.match(updateSummaryRule, /display:\s*grid;/)
  assert.match(updateSummaryRule, /min-width:\s*0;/)
  assert.match(updateSummaryRule, /gap:\s*0\.65rem;/)

  const updateTitleRule = cssRuleBody(css, '.settings-update-title {')
  assert.match(updateTitleRule, /display:\s*grid;/)
  assert.match(updateTitleRule, /gap:\s*0\.3rem;/)

  const updateVersionRowRule = cssRuleBody(css, '.settings-update-version-row {')
  assert.match(updateVersionRowRule, /display:\s*flex;/)
  assert.match(updateVersionRowRule, /flex-wrap:\s*wrap;/)
  assert.match(updateVersionRowRule, /align-items:\s*center;/)

  const updateVersionRule = cssRuleBody(css, '.settings-update-version {')
  assert.match(updateVersionRule, /line-height:\s*1\.25;/)
  assert.match(updateVersionRule, /overflow-wrap:\s*anywhere;/)

  const updateDateRule = cssRuleBody(css, '.settings-update-date {')
  assert.match(updateDateRule, /line-height:\s*1\.2;/)

  const updateMetaRule = cssRuleBody(css, '.settings-update-meta {')
  assert.match(updateMetaRule, /display:\s*flex;/)
  assert.match(updateMetaRule, /flex-wrap:\s*wrap;/)
  assert.match(updateMetaRule, /align-items:\s*center;/)
  assert.match(updateMetaRule, /line-height:\s*1\.35;/)

  const updateReasonRule = cssRuleBody(css, '.settings-update-reason {')
  assert.match(updateReasonRule, /display:\s*block;/)
  assert.match(updateReasonRule, /max-width:\s*100%;/)
  assert.match(updateReasonRule, /overflow-wrap:\s*anywhere;/)
  assert.match(updateReasonRule, /word-break:\s*break-word;/)
  assert.match(updateReasonRule, /line-height:\s*1\.62;/)

  const updateActionsRule = cssRuleBody(css, '.settings-update-actions {')
  assert.match(updateActionsRule, /min-width:\s*0;/)
  assert.match(updateActionsRule, /max-width:\s*100%;/)
  assert.match(updateActionsRule, /width:\s*100%;/)
  assert.match(updateActionsRule, /padding-top:\s*0\.25rem;/)

  const updateLogRule = cssRuleBody(css, '.settings-update-log {')
  assert.match(updateLogRule, /overflow-x:\s*hidden;/)
})

test('settings general tab uses compact theme cards and tidy library rows', () => {
  const settings = readFileSync('src/pages/settings/Settings.tsx', 'utf8')
  const css = readFileSync('src/index.css', 'utf8')

  assert.match(settings, /className="settings-theme-grid"/)
  assert.match(settings, /className=\{"settings-theme-card " \+ \(active \? 'is-active' : ''\)\}/)
  assert.match(settings, /className="settings-theme-card-header"/)
  assert.match(settings, /className="settings-theme-card-copy"/)
  assert.match(settings, /className="settings-theme-card-heading"/)
  assert.match(settings, /className="settings-theme-card-dot"/)
  assert.match(settings, /className="settings-theme-card-title"/)
  assert.match(settings, /className="settings-theme-card-meta"/)
  assert.match(settings, /className="settings-theme-card-desc"/)
  assert.match(settings, /className="settings-theme-card-actions"/)
  assert.doesNotMatch(settings, /grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3/)

  assert.match(settings, /className="settings-library-list"/)
  assert.match(settings, /className="settings-library-card"/)
  assert.match(settings, /className="settings-library-header"/)
  assert.match(settings, /className="settings-library-title-group"/)
  assert.match(settings, /className="settings-library-count"/)
  assert.match(settings, /className="settings-library-form"/)
  assert.match(settings, /className="settings-library-field settings-library-field-wide"/)
  assert.match(settings, /className="settings-library-field"/)
  assert.match(settings, /className="settings-library-footer"/)
  assert.match(settings, /className="settings-library-status"/)
  assert.match(settings, /className="settings-library-actions"/)
  assert.doesNotMatch(settings, /space-y-2 rounded-2xl border border-white\/10 bg-white\/\[0\.06\] p-3 backdrop-blur-xl/)
  assert.match(settings, /className="settings-option-group"/)
  assert.match(settings, /className="settings-option-row"/)
  assert.match(settings, /className="settings-option-control"/)
  assert.match(settings, /className="settings-tab-stack"/)
  assert.doesNotMatch(settings, /className="space-y-5"/)
  assert.doesNotMatch(settings, /flex items-center justify-between gap-4 rounded-2xl border border-white\/10 bg-white\/\[0\.06\] p-3 backdrop-blur-xl/)

  const tabStackRule = cssRuleBody(css, '.settings-tab-stack {')
  assert.match(tabStackRule, /display:\s*grid;/)
  assert.match(tabStackRule, /gap:\s*1rem;/)

  const sectionRule = cssRuleBody(css, '.settings-section {')
  assert.match(sectionRule, /padding:\s*1rem 0 0;/)

  const themeGridRule = cssRuleBody(css, '.settings-theme-grid {')
  assert.match(themeGridRule, /grid-template-columns:\s*minmax\(0, 1fr\);/)
  assert.doesNotMatch(themeGridRule, /repeat\(2/)

  const themeCardRule = cssRuleBody(css, '.settings-theme-card {')
  assert.match(themeCardRule, /display:\s*grid;/)
  assert.match(themeCardRule, /grid-template-columns:\s*minmax\(0, 1fr\) auto;/)
  assert.match(themeCardRule, /overflow:\s*hidden;/)

  const activeThemeCardRule = cssRuleBody(css, '.settings-theme-card.is-active {')
  assert.match(activeThemeCardRule, /background:\s*rgba\(255, 255, 255, 0\.06\);/)
  assert.doesNotMatch(activeThemeCardRule, /rgba\(10,\s*132,\s*255/)

  const themeCopyRule = cssRuleBody(css, '.settings-theme-card-copy {')
  assert.match(themeCopyRule, /display:\s*grid;/)

  const themeHeadingRule = cssRuleBody(css, '.settings-theme-card-heading {')
  assert.match(themeHeadingRule, /align-items:\s*baseline;/)

  const themeTitleRule = cssRuleBody(css, '.settings-theme-card-title {')
  assert.match(themeTitleRule, /white-space:\s*nowrap;/)
  assert.match(themeTitleRule, /text-overflow:\s*ellipsis;/)

  const themeDescRule = cssRuleBody(css, '.settings-theme-card-desc {')
  assert.match(themeDescRule, /display:\s*-webkit-box;/)
  assert.match(themeDescRule, /-webkit-line-clamp:\s*1;/)

  const themeActionsRule = cssRuleBody(css, '.settings-theme-card-actions {')
  assert.match(themeActionsRule, /flex:\s*0 0 auto;/)

  const optionGroupRule = cssRuleBody(css, '.settings-option-group {')
  assert.match(optionGroupRule, /overflow:\s*hidden;/)
  assert.match(optionGroupRule, /border:\s*0;/)
  assert.match(optionGroupRule, /border-radius:\s*1\.1rem;/)

  const optionRowRule = cssRuleBody(css, '.settings-option-row {')
  assert.match(optionRowRule, /display:\s*flex;/)
  assert.match(optionRowRule, /justify-content:\s*space-between;/)

  const optionDividerRule = cssRuleBody(css, '.settings-option-row \+ .settings-option-row {')
  assert.match(optionDividerRule, /border-top:\s*1px solid rgba\(255, 255, 255, 0\.1\);/)

  const libraryCardRule = cssRuleBody(css, '.settings-library-card {')
  assert.match(libraryCardRule, /display:\s*grid;/)
  assert.match(libraryCardRule, /gap:\s*0\.68rem;/)

  const libraryFormRule = cssRuleBody(css, '.settings-library-form {')
  assert.match(libraryFormRule, /grid-template-columns:\s*minmax\(0, 1\.15fr\) minmax\(7\.5rem, 0\.85fr\);/)

  const libraryFooterRule = cssRuleBody(css, '.settings-library-footer {')
  assert.match(libraryFooterRule, /display:\s*flex;/)

  const libraryStatusRule = cssRuleBody(css, '.settings-library-status {')
  assert.match(libraryStatusRule, /display:\s*flex;/)

  const libraryActionsRule = cssRuleBody(css, '.settings-library-actions {')
  assert.match(libraryActionsRule, /justify-content:\s*flex-end;/)
})

test('liquid glass uses a single-tone dark frosted surface without highlights', () => {
  const css = readFileSync('src/index.css', 'utf8')
  const liquidGlass = cssRuleBody(css, '.liquid-glass {')
  const lightTextRemapIndex = css.indexOf(':root[data-mediatree-color-scheme="light"] .text-white')
  const topbarWhiteIndex = css.indexOf('.mt-topbar .liquid-glass,')

  assert.match(liquidGlass, /overflow:\s*hidden;/)
  assert.match(liquidGlass, /isolation:\s*isolate;/)
  assert.match(liquidGlass, /border-radius:\s*18px;/)
  assert.match(liquidGlass, /border:\s*0;/)
  assert.match(liquidGlass, /background:\s*rgba\(8,\s*10,\s*18,\s*0\.78\);/)
  assert.match(liquidGlass, /backdrop-filter:\s*blur\(28px\) saturate\(170%\);/)
  assert.match(liquidGlass, /-webkit-backdrop-filter:\s*blur\(28px\) saturate\(170%\);/)
  assert.match(liquidGlass, /box-shadow:\s*none;/)
  assert.doesNotMatch(liquidGlass, /var\(--mt-shadow-glass\)/)
  assert.doesNotMatch(liquidGlass, /brightness\(/)
  assert.doesNotMatch(liquidGlass, /linear-gradient|radial-gradient|rgba\(10,\s*132,\s*255/)
  assert.doesNotMatch(css, /\.liquid-glass::before\s*\{/)
  assert.match(css, /\.liquid-glass::after\s*\{[^}]*border:\s*0;[^}]*\}/s)
  assert.doesNotMatch(cssRuleBody(css, '.liquid-glass::after {'), /box-shadow:/)
  assert.doesNotMatch(cssRuleBody(css, '.liquid-glass::after {'), /linear-gradient|radial-gradient|rgba\(10,\s*132,\s*255/)
  assert.match(css, /\.mt-topbar \.glass-button,[^}]*\.mt-topbar \.glass-input:focus\s*\{[^}]*box-shadow:\s*none;/s)
  assert.ok(lightTextRemapIndex !== -1 && topbarWhiteIndex > lightTextRemapIndex)
  assert.match(css, /\.mt-topbar \.liquid-glass,[^}]*\.mt-topbar \.glass-input\s*\{[^}]*color:\s*#fff;/s)
})

test('container surfaces do not render outline borders', () => {
  const css = readFileSync('src/index.css', 'utf8')

  const selectors = [
    '.glass-panel {',
    '.glass-card {',
    '.glass-popover {',
    '.glass-modal {',
    ':root .settings-drawer-panel.liquid-glass {',
    '.settings-theme-card {',
    '.settings-library-card {',
    '.home-continue-cover {',
    '.home-poster-cover {',
  ]

  for (const selector of selectors) {
    const rule = cssRuleBody(css, selector)
    assert.match(rule, /border:\s*0;/, `${selector} should remove the container outline`)
    assert.doesNotMatch(rule, /border:\s*1px/, `${selector} should not draw a 1px outline`)
  }
})

test('global layout fills available width responsively', () => {
  const css = readFileSync('src/index.css', 'utf8')
  const root = cssRuleBody(css, ':root')
  const content = cssRuleBody(css, '.mt-content')
  const mediaGrid = cssRuleBody(css, '.media-grid {')

  assert.equal(BUILTIN_THEMES[0].tokens['--mt-layout-content-max'], 'none')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-layout-page-padding-x'], 'clamp(2rem, 3.6vw, 3rem)')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-layout-page-padding-x-wide'], 'clamp(2rem, 3.6vw, 3rem)')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-media-grid-min'], '9.75rem')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-media-grid-max'], '11rem')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-media-card-width'], '11rem')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-media-card-height'], '16.5rem')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-media-grid-gap'], '1rem')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-media-grid-column-gap'], '1rem')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-media-grid-row-gap'], '1.25rem')
  assert.match(root, /--mt-layout-content-max:\s*none;/)
  assert.match(root, /--mt-layout-page-padding-x:\s*clamp\(2rem,\s*3\.6vw,\s*3rem\);/)
  assert.match(root, /--mt-layout-page-padding-y:\s*1\.25rem;/)
  assert.match(root, /--mt-layout-page-padding-x-wide:\s*clamp\(2rem,\s*3\.6vw,\s*3rem\);/)
  assert.match(root, /--mt-layout-page-padding-y-wide:\s*1\.75rem;/)
  assert.match(content, /width:\s*100%;/)
  assert.match(content, /min-width:\s*0;/)
  assert.match(content, /padding-inline:\s*var\(--mt-layout-page-padding-x\);/)
  assert.match(mediaGrid, /width:\s*100%;/)
  assert.match(mediaGrid, /min-width:\s*0;/)
  assert.match(mediaGrid, /display:\s*flex;/)
  assert.match(mediaGrid, /flex-wrap:\s*wrap;/)
  assert.match(root, /--mt-media-grid-max:\s*11rem;/)
  assert.match(root, /--mt-media-card-width:\s*11rem;/)
  assert.match(root, /--mt-media-card-height:\s*16\.5rem;/)
  assert.match(root, /--mt-media-grid-gap:\s*1rem;/)
  assert.match(root, /--mt-media-grid-column-gap:\s*1rem;/)
  assert.match(root, /--mt-media-grid-row-gap:\s*1\.25rem;/)
  assert.match(mediaGrid, /column-gap:\s*var\(--mt-media-grid-column-gap,\s*var\(--mt-media-grid-gap\)\)\s*!important;/)
  assert.match(mediaGrid, /row-gap:\s*var\(--mt-media-grid-row-gap,\s*var\(--mt-media-grid-gap\)\)\s*!important;/)
  assert.match(mediaGrid, /justify-content:\s*center;/)
  assert.doesNotMatch(mediaGrid, /grid-template-columns:/)
  assert.match(css, /@media \(max-width:\s*640px\),\s*\(orientation:\s*portrait\) and \(max-width:\s*820px\)\s*\{[^}]*\.media-grid\s*\{[^}]*--mt-media-mobile-grid-width:\s*calc\(100% - var\(--mt-media-grid-column-gap,\s*var\(--mt-media-grid-gap\)\) - var\(--mt-media-grid-column-gap,\s*var\(--mt-media-grid-gap\)\)\);[^}]*--mt-media-card-width:\s*min\(11rem,\s*calc\(var\(--mt-media-mobile-grid-width\) \/ 3\)\)\s*!important;[^}]*--mt-media-card-height:\s*min\(16\.5rem,\s*calc\(var\(--mt-media-mobile-grid-width\) \/ 2\)\)\s*!important;/s)
  assert.match(css, /\.media-grid-card\s*\{[^}]*contain-intrinsic-size:\s*var\(--mt-media-card-width\)\s+var\(--mt-media-card-height\);/s)
  assert.match(css, /\.media-grid\s*>\s*\.media-grid-card\s*\{[^}]*width:\s*var\(--mt-media-card-width\);[^}]*height:\s*var\(--mt-media-card-height\);[^}]*min-width:\s*var\(--mt-media-card-width\);[^}]*max-width:\s*var\(--mt-media-card-width\);[^}]*min-height:\s*var\(--mt-media-card-height\);[^}]*max-height:\s*var\(--mt-media-card-height\);/s)
  assert.match(css, /\.media-grid\s+\.media-grid-card\s*\{[^}]*transition:\s*box-shadow\s+var\(--mt-motion-normal\)\s+ease,\s*border-color\s+var\(--mt-motion-normal\)\s+ease;[^}]*transform:\s*none;[^}]*will-change:\s*auto;/s)
  assert.match(css, /\.media-grid\s+\.media-grid-card\.is-layout-animating\s*\{[^}]*will-change:\s*transform;/s)
  assert.match(css, /\.media-grid\s+\.media-grid-card:hover,\s*\.media-grid\s+\.media-grid-card:focus-visible\s*\{[^}]*transform:\s*none;/s)
  assert.match(css, /\.media-grid\s+\.media-grid-card\s+img\s*\{[^}]*transition:\s*none\s*!important;[^}]*transform:\s*none\s*!important;/s)
})

test('home page stacks continue watching above library grid with a conditional divider', () => {
  const css = readFileSync('src/index.css', 'utf8')
  const source = readFileSync('src/pages/home/Home.tsx', 'utf8')
  const sortDropdownSource = readFileSync('src/components/SortDropdown.tsx', 'utf8')
  const scrollButton = cssRuleBody(css, '.home-scroll-button {')
  const scrollIcon = cssRuleBody(css, '.home-scroll-icon {')
  const divider = cssRuleBody(css, '.home-section-separator {')
  const continueHeadingIndex = source.indexOf('home-section-title">继续观看')
  const continueStripIndex = source.indexOf('home-continue-strip')
  const separatorIndex = source.indexOf('home-section-separator')
  const sortIndex = source.indexOf('<SortDropdown options={sortOptions}')
  const libraryGridIndex = source.indexOf('home-poster-grid')

  assert.doesNotMatch(source, /text-xs uppercase tracking-\[0\.24em\][\s\S]*Library/)
  assert.doesNotMatch(source, /tab === 'recent' \? '继续观看' : '我的媒体库'/)
  assert.doesNotMatch(source, /tab === 'recent' \? `共 \$\{recentTotal\} 部` : `共 \$\{tree\.length\} 个目录`/)
  assert.doesNotMatch(source, /setTab\('library'\)/)
  assert.doesNotMatch(source, /setTab\('recent'\)/)
  assert.match(source, /if \(libraryLoading \|\| recentLoading\)/)
  assert.doesNotMatch(source, /if \(libraryLoading && recentLoading\)/)
  assert.doesNotMatch(source, /home-section-title">媒体库/)
  assert.ok(continueHeadingIndex !== -1, 'continue watching heading should be rendered')
  assert.ok(continueStripIndex > continueHeadingIndex, 'continue strip should follow its heading')
  assert.ok(separatorIndex > continueStripIndex, 'divider should appear after continue watching')
  assert.ok(sortIndex > separatorIndex, 'sort control should follow the divider')
  assert.ok(libraryGridIndex > sortIndex, 'poster grid should follow the sort control')
  assert.match(source, /recentMovies\.length > 0 && \(\s*<>[\s\S]*className="home-section-separator" aria-hidden="true"[\s\S]*<\/>\s*\)/)
  assert.match(source, /<div className="home-section-header home-continue-header">/)
  assert.match(source, /<div className="home-section-header home-library-header">\s*<SortDropdown options=\{sortOptions\}/)
  assert.match(source, /className="home-scroll-icon"/)
  assert.match(scrollButton, /align-items:\s*flex-end;/)
  assert.match(scrollButton, /height:\s*2rem;/)
  assert.match(scrollIcon, /height:\s*1\.125rem;/)
  assert.match(scrollIcon, /width:\s*1\.125rem;/)
  assert.match(divider, /height:\s*1px;/)
  assert.match(divider, /margin:\s*clamp\(2rem,\s*4\.2vw,\s*3\.25rem\) 0;/)
  assert.match(divider, /background:\s*linear-gradient\(90deg,\s*transparent,\s*rgba\(255,\s*255,\s*255,\s*0\.18\),\s*transparent\);/)
  assert.match(source, /<SortDropdown options=\{sortOptions\} current=\{sort\} onChange=\{handleSort\} variant="menu" size="heading" \/>/)
  assert.match(sortDropdownSource, /size\?: 'default' \| 'heading'/)
  assert.match(sortDropdownSource, /const isHeadingSize = size === 'heading'/)
  assert.match(sortDropdownSource, /h-\[1\.125rem\]\s+w-\[1\.75rem\]/)
  assert.match(sortDropdownSource, /h-\[0\.625rem\]\s+w-3/)
  assert.match(sortDropdownSource, /h-px/)
  assert.match(sortDropdownSource, /top-\[0\.28125rem\]/)
  assert.match(sortDropdownSource, /translate-y-px/)
})

test('browse and favorites keep the aligned page heading pattern while settings becomes a drawer', () => {
  const css = readFileSync('src/index.css', 'utf8')
  const browseSource = readFileSync('src/pages/browse/Browse.tsx', 'utf8')
  const favoritesSource = readFileSync('src/pages/favorites/Favorites.tsx', 'utf8')
  const appSource = readFileSync('src/App.tsx', 'utf8')
  const settingsSource = readFileSync('src/pages/settings/Settings.tsx', 'utf8')
  const alignedPage = cssRuleBody(css, '.home-aligned-page {')
  const browseHeader = cssRuleBody(css, '.browse-library-header {')

  assert.match(alignedPage, /--mt-home-section-title-gap:\s*0\.85rem;/)
  assert.match(alignedPage, /--mt-home-library-title-gap:\s*calc\(var\(--mt-home-section-title-gap\) \+ 3px\);/)
  assert.match(alignedPage, /padding-top:\s*calc\(2rem - \(0\.9375rem \* 1\.2\)\);/)
  assert.match(css, /\.home-page,\s*\.browse-page,\s*\.favorites-page\s*\{/)
  assert.match(browseSource, /className=\{`home-aligned-page browse-page space-y-5 \$\{browseOpening \? 'is-browse-opening' : ''\}`\}/)
  assert.match(browseSource, /className="home-section-header browse-library-header"/)
  assert.match(favoritesSource, /className="home-aligned-page favorites-page space-y-5"/)
  assert.match(browseHeader, /justify-content:\s*space-between;/)
  assert.match(browseHeader, /padding-inline:\s*0;/)
  assert.match(browseHeader, /margin-bottom:\s*var\(--mt-home-library-title-gap\);/)
  assert.match(appSource, /onClick=\{openSettingsDrawer\}[\s\S]*aria-label="设置"/)
  assert.match(appSource, /<Settings open onClose=\{closeSettingsDrawer\} \/>/)
  assert.match(settingsSource, /settings-drawer-panel/)
  assert.match(settingsSource, /settings-tab-rail/)
  assert.doesNotMatch(settingsSource, /home-aligned-page w-full min-w-0 space-y-5/)
  assert.doesNotMatch(settingsSource, /home-section-header home-library-header/)
})

test('home library uses poster grid cards with external title metadata', () => {
  const css = readFileSync('src/index.css', 'utf8')
  const source = readFileSync('src/pages/home/Home.tsx', 'utf8')
  const libraryGrid = source.match(/<div className="home-poster-grid[\s\S]*?\{tree\.map/)?.[0] ?? ''
  const card = source.match(/className="home-poster-card media-grid-card group cursor-pointer"[\s\S]*?<\/div>\s*\)\s*\}\)/)?.[0] ?? ''
  const sharedPosterPageRule = cssRuleBody(css, '.home-page,')
  const sectionHeader = cssRuleBody(css, '.home-section-header {')
  const posterGrid = cssRuleBody(css, '.home-poster-grid {')
  const libraryHeader = cssRuleBody(css, '.home-library-header {')
  const posterCover = cssRuleBody(css, '.home-poster-cover {')
  const mediaCardRuleIndex = css.indexOf('.media-grid > .media-grid-card {')
  const homePosterCardRuleIndex = css.indexOf('.home-poster-grid > .home-poster-card {')
  const posterCard = cssRuleBody(css, '.home-poster-grid > .home-poster-card {', 1)

  assert.match(source, /className=\{`home-page \$\{homeReturning \? 'is-home-returning' : ''\} \$\{homeOpening \? 'is-home-opening' : ''\}`\}/)
  assert.match(sharedPosterPageRule, /display:\s*flex;/)
  assert.match(sharedPosterPageRule, /flex-direction:\s*column;/)
  assert.match(source, /<section className="home-section home-library-section">/)
  assert.match(source, /<div className="home-section-header home-library-header">/)
  assert.ok(libraryGrid.includes('home-poster-grid'), 'home library grid should use poster-grid class')
  assert.doesNotMatch(libraryGrid, /grid-cols-|sm:grid-cols-|md:grid-cols-|lg:grid-cols-|xl:grid-cols-|2xl:grid-cols-/)
  assert.match(libraryGrid, /className="home-poster-grid media-grid"/)
  assert.doesNotMatch(libraryGrid, /data-media-grid-motion="off"/)
  assert.match(sharedPosterPageRule, /--mt-home-continue-width:\s*clamp\(var\(--mt-home-continue-min\),\s*var\(--mt-home-continue-fluid\),\s*var\(--mt-home-continue-max\)\);/)
  assert.match(sharedPosterPageRule, /--mt-home-poster-min:\s*6rem;/)
  assert.match(sharedPosterPageRule, /--mt-home-poster-max:\s*calc\(var\(--mt-home-continue-width\) \* 0\.6667\);/)
  assert.match(sharedPosterPageRule, /--mt-home-poster-three-column-width:\s*calc\(\(100% - \(var\(--mt-media-grid-column-gap,\s*var\(--mt-media-grid-gap\)\) \* 2\)\) \/ 3\);/)
  assert.match(sharedPosterPageRule, /--mt-home-poster-width:\s*clamp\(var\(--mt-home-poster-min\),\s*var\(--mt-home-poster-three-column-width\),\s*var\(--mt-home-poster-max\)\);/)
  assert.match(sharedPosterPageRule, /--mt-home-poster-grid-template:\s*repeat\(auto-fill,\s*minmax\(0,\s*var\(--mt-home-poster-width\)\)\);/)
  assert.match(sharedPosterPageRule, /--mt-home-section-title-gap:\s*0\.85rem;/)
  assert.match(sharedPosterPageRule, /--mt-home-library-title-gap:\s*calc\(var\(--mt-home-section-title-gap\) \+ 3px\);/)
  assert.match(sharedPosterPageRule, /--mt-media-grid-gap:\s*clamp\(1rem,\s*2\.6vw,\s*3rem\);/)
  assert.match(sectionHeader, /align-items:\s*flex-end;/)
  assert.match(sectionHeader, /margin-bottom:\s*var\(--mt-home-section-title-gap\);/)
  assert.match(libraryHeader, /padding-inline:\s*0;/)
  assert.match(libraryHeader, /transform:\s*translateY\(-0\.3125rem\);/)
  assert.match(libraryHeader, /margin-bottom:\s*var\(--mt-home-library-title-gap\);/)
  assert.match(posterGrid, /display:\s*grid;/)
  assert.match(posterGrid, /width:\s*100%;/)
  assert.match(posterGrid, /min-width:\s*0;/)
  assert.match(posterGrid, /grid-template-columns:\s*var\(--mt-home-poster-grid-template\);/)
  assert.match(posterGrid, /justify-content:\s*space-between;/)
  assert.match(posterGrid, /justify-items:\s*stretch;/)
  assert.doesNotMatch(sharedPosterPageRule, /auto-fit/)
  assert.ok(homePosterCardRuleIndex > mediaCardRuleIndex, 'home poster card sizing must override generic media grid card sizing')
  assert.match(css, /@media \(max-width:\s*640px\),\s*\(orientation:\s*portrait\) and \(max-width:\s*820px\)\s*\{[\s\S]*?\.home-page,\s*\.browse-page,\s*\.favorites-page\s*\{[\s\S]*?--mt-home-poster-min:\s*0;[\s\S]*?--mt-home-poster-max:\s*11\.5rem;[\s\S]*?--mt-home-poster-width:\s*min\(var\(--mt-home-poster-max\),\s*var\(--mt-home-poster-three-column-width\)\);[\s\S]*?--mt-media-grid-gap:\s*0\.75rem;/s)
  assert.match(card, /className="home-poster-cover relative aspect-\[2\/3\]/)
  assert.match(card, /home-poster-watch-status/)
  assert.match(card, /watchState\.watched \? <CheckIcon/)
  assert.match(card, /watchState\.unwatchedCount > 99 \? '99\+' : watchState\.unwatchedCount/)
  assert.match(card, /home-poster-watched-action absolute bottom-2 right-2/)
  assert.match(card, /aria-label=\{watchState\.watched \? '取消已看' : '标记已看'\}/)
  assert.match(card, /home-poster-meta min-w-0 text-center/)
  assert.match(card, /home-poster-title line-clamp-2/)
  assert.match(card, /home-poster-year mt-1/)
  assert.doesNotMatch(card, /home-poster-progress/)
  assert.doesNotMatch(card, /progress_percent/)
  assert.doesNotMatch(card, /bg-gradient-to-t from-black/)
  assert.doesNotMatch(card, /absolute bottom-0 left-0 right-0 min-w-0 p-3/)
  assert.match(source, /function getHomeFolderWatchState\(node: FolderNode, watchedOverride\?: boolean\)/)
  assert.match(source, /function getHomeFolderYear\(node: FolderNode\): string/)
  assert.match(posterCard, /width:\s*100%;/)
  assert.match(posterCard, /min-width:\s*0;/)
  assert.match(posterCard, /max-width:\s*none;/)
  assert.match(posterCard, /content-visibility:\s*visible;/)
  assert.match(posterCard, /height:\s*auto;/)
  assert.match(posterCard, /contain-intrinsic-size:\s*var\(--mt-home-poster-width\)\s+calc\(var\(--mt-home-poster-width\) \* 1\.5 \+ 3\.375rem\);/)
  assert.match(posterCard, /display:\s*flex;/)
  assert.match(posterCard, /flex-direction:\s*column;/)
  assert.match(posterCover, /overflow:\s*hidden;/)
  assert.match(posterCover, /border:\s*0;/)
  assert.match(posterCover, /border-radius:\s*var\(--mt-radius-card\);/)
  assert.match(css, /(^|\n)\.home-poster-watched-action\s*\{\s*opacity:\s*0;/)
  assert.match(css, /\.home-poster-card:hover \.home-poster-watched-action,[^}]*\.home-poster-card:focus-within \.home-poster-watched-action\s*\{[^}]*opacity:\s*1;/s)
})

test('home to folder navigation shares the clicked poster with the folder page entrance', () => {
  const css = readFileSync('src/index.css', 'utf8')
  const homeSource = readFileSync('src/pages/home/Home.tsx', 'utf8')
  const folderSource = readFileSync('src/pages/folder/FolderPage.tsx', 'utf8')
  const transitionLayer = cssRuleBody(css, '.home-folder-transition {')
  const transitionImage = cssRuleBody(css, '.home-folder-transition-image {')
  const homeReturn = cssRuleBody(css, '.home-page.is-home-returning {')
  const folderBackdropEntrance = cssRuleBody(css, '.folder-page.is-folder-entering .folder-backdrop-layer {')
  const folderContentEntrance = cssRuleBody(css, '.folder-page.is-folder-entering .folder-content-layer {', 1)
  const reducedMotionIndex = css.indexOf('@media (prefers-reduced-motion: reduce) {')

  assert.match(homeSource, /import \{ useNavigate, useSearchParams, useLocation \}/)
  assert.match(homeSource, /type FolderTransitionState =/)
  assert.match(homeSource, /import \{ useEffect, useState, useCallback, useRef, useLayoutEffect, type CSSProperties \}/)
  assert.match(homeSource, /const location = useLocation\(\)/)
  assert.match(homeSource, /const initialHomeReturnTransitionRef = useRef<FolderTransitionState \| null>\(/)
  assert.match(homeSource, /\(location\.state as \{ homeReturnTransition\?: FolderTransitionState \} \| null\)\?\.homeReturnTransition \|\| null/)
  assert.match(homeSource, /const initialHomeReturnTransition = initialHomeReturnTransitionRef\.current/)
  assert.match(homeSource, /const homeReturnStartedRef = useRef\(false\)/)
  assert.match(homeSource, /const sourceCover = e\.currentTarget\.querySelector\('\.home-poster-cover'\)/)
  assert.match(homeSource, /sourceCover\??\.getBoundingClientRect\(\)/)
  assert.match(homeSource, /const folderTransition: FolderTransitionState =/)
  assert.match(homeSource, /navigate\(`\/folder\?\$\{p\.toString\(\)\}`, \{ state: \{ folderTransition \} \}\)/)
  assert.match(homeSource, /const \[homeReturnTransition, setHomeReturnTransition\] = useState<FolderTransitionState \| null>\(null\)/)
  assert.match(homeSource, /const \[homeReturning, setHomeReturning\] = useState\(false\)/)
  assert.doesNotMatch(homeSource, /useState<FolderTransitionState \| null>\(initialHomeReturnTransition \|\| null\)/)
  assert.doesNotMatch(homeSource, /useState\(Boolean\(initialHomeReturnTransition\)\)/)
  assert.match(homeSource, /useLayoutEffect\(\(\) => \{[\s\S]*if \(libraryLoading \|\| recentLoading \|\| homeReturnStartedRef\.current\) return[\s\S]*homeReturnStartedRef\.current = true[\s\S]*setHomeReturnTransition\(initialHomeReturnTransition\)[\s\S]*setHomeReturning\(true\)/)
  assert.match(homeSource, /if \(libraryLoading \|\| recentLoading \|\| homeReturnStartedRef\.current\) return/)
  assert.match(homeSource, /homeReturnStartedRef\.current = true/)
  assert.match(homeSource, /navigate\(\{ pathname: location\.pathname,\s*search: location\.search,\s*hash: location\.hash \}, \{ replace: true,\s*state: null \}\)/)
  assert.match(homeSource, /window\.setTimeout\(\(\) => setHomeReturnTransition\(null\), HOME_RETURN_TRANSITION_MS\)/)
  assert.match(homeSource, /className=\{`home-page \$\{homeReturning \? 'is-home-returning' : ''\} \$\{homeOpening \? 'is-home-opening' : ''\}`\}/)
  assert.match(homeSource, /homeReturnTransition && createPortal\(/)
  assert.match(homeSource, /className="home-folder-transition-image"/)
  assert.doesNotMatch(homeSource, /is-reverse/)
  assert.doesNotMatch(homeSource, /folderTransitionTimerRef/)
  assert.doesNotMatch(homeSource, /setFolderTransition/)
  assert.doesNotMatch(homeSource, /HOME_FOLDER_TRANSITION_MS/)

  assert.match(folderSource, /import \{ useSearchParams, useNavigate, useLocation \}/)
  assert.match(folderSource, /type FolderTransitionState =/)
  assert.match(folderSource, /import \{ useEffect, useState, useMemo, useRef, useCallback, useLayoutEffect, type CSSProperties \}/)
  assert.match(folderSource, /const location = useLocation\(\)/)
  assert.match(folderSource, /const initialFolderTransitionRef = useRef<FolderTransitionState \| null>\(/)
  assert.match(folderSource, /\(location\.state as \{ folderTransition\?: FolderTransitionState \} \| null\)\?\.folderTransition \|\| null/)
  assert.match(folderSource, /const initialFolderTransition = initialFolderTransitionRef\.current/)
  assert.match(folderSource, /const \[folderTransition, setFolderTransition\] = useState<FolderTransitionState \| null>\(null\)/)
  assert.match(folderSource, /const \[folderEntryBackdropKey, setFolderEntryBackdropKey\] = useState<number \| null>\(null\)/)
  assert.match(folderSource, /const returnTransitionRef = useRef<FolderTransitionState \| null>\(initialFolderTransition \|\| null\)/)
  assert.match(folderSource, /const folderEntryStartedRef = useRef\(false\)/)
  assert.match(folderSource, /const \[folderEntering, setFolderEntering\] = useState\(false\)/)
  assert.doesNotMatch(folderSource, /useState<FolderTransitionState \| null>\(initialFolderTransition \|\| null\)/)
  assert.doesNotMatch(folderSource, /useState\(Boolean\(initialFolderTransition\)\)/)
  assert.match(folderSource, /useLayoutEffect\(\(\) => \{[\s\S]*if \(loading \|\| folderEntryStartedRef\.current\) return[\s\S]*folderEntryStartedRef\.current = true[\s\S]*setFolderTransition\(initialFolderTransition\)[\s\S]*setFolderEntering\(true\)/)
  assert.match(folderSource, /if \(loading \|\| folderEntryStartedRef\.current\) return/)
  assert.match(folderSource, /folderEntryStartedRef\.current = true/)
  assert.match(folderSource, /setFolderEntryBackdropKey\(activeBackdrop \? fadeKey : null\)/)
  assert.match(folderSource, /navigate\(\{ pathname: location\.pathname,\s*search: location\.search,\s*hash: location\.hash \}, \{ replace: true,\s*state: null \}\)/)
  assert.match(folderSource, /\}, \[initialFolderTransition,\s*loading\]\)/)
  assert.match(folderSource, /if \(!folderEntering \|\| !activeBackdrop\) return[\s\S]*setFolderEntryBackdropKey\(fadeKey\)/)
  assert.match(folderSource, /const goHome = \(\) => \{/)
  assert.match(folderSource, /navigate\('\/', \{ state: \{ homeReturnTransition: returnTransitionRef\.current \} \}\)/)
  assert.match(folderSource, /onClick=\{goHome\}/)
  assert.match(folderSource, /window\.setTimeout\(\(\) => setFolderTransition\(null\), FOLDER_ENTRY_TRANSITION_MS\)/)
  assert.match(folderSource, /className=\{`folder-page \$\{folderEntering \? 'is-folder-entering' : ''\} relative z-0 space-y-6`\}/)
  assert.match(folderSource, /className="folder-backdrop-layer pointer-events-none fixed inset-0 -z-10 overflow-hidden"/)
  assert.match(folderSource, /className="folder-content-layer"/)
  assert.match(folderSource, /const useFolderEntryBackdropImage = folderEntering \|\| \(folderEntryBackdropKey === fadeKey && Boolean\(activeBackdrop\)\)/)
  assert.match(folderSource, /useFolderEntryBackdropImage \? 'folder-entry-backdrop-image' : 'animate-backdrop-in'/)
  assert.match(folderSource, /folderTransition && createPortal\(/)
  assert.match(folderSource, /className="home-folder-transition"/)
  assert.match(folderSource, /className="home-folder-transition-image"/)

  assert.match(transitionLayer, /position:\s*fixed;/)
  assert.match(transitionLayer, /inset:\s*0;/)
  assert.match(transitionLayer, /z-index:\s*65;/)
  assert.match(transitionLayer, /pointer-events:\s*none;/)
  assert.match(transitionLayer, /background:\s*transparent;/)
  assert.doesNotMatch(transitionLayer, /animation:/)
  assert.match(transitionImage, /position:\s*fixed;/)
  assert.match(transitionImage, /left:\s*var\(--home-folder-transition-left\);/)
  assert.match(transitionImage, /top:\s*var\(--home-folder-transition-top\);/)
  assert.match(transitionImage, /width:\s*var\(--home-folder-transition-width\);/)
  assert.match(transitionImage, /height:\s*var\(--home-folder-transition-height\);/)
  assert.match(transitionImage, /animation:\s*home-folder-transition-zoom\s+520ms/)
  assert.match(homeReturn, /animation:\s*home-page-clear-in\s+520ms/)
  assert.match(homeReturn, /filter:\s*blur\(12px\) brightness\(0\.68\);/)
  assert.match(folderBackdropEntrance, /animation:\s*folder-backdrop-clear-in\s+520ms/)
  assert.match(folderBackdropEntrance, /filter:\s*blur\(18px\) brightness\(0\.54\);/)
  assert.match(folderBackdropEntrance, /transform:\s*none;/)
  assert.match(cssRuleBody(css, '.folder-entry-backdrop-image {'), /opacity:\s*0\.8;/)
  assert.match(folderContentEntrance, /animation:\s*folder-content-clear-in\s+520ms/)
  assert.match(folderContentEntrance, /filter:\s*blur\(10px\) brightness\(0\.72\);/)
  assert.match(css, /@keyframes home-folder-transition-zoom\s*\{[\s\S]*filter:\s*blur\(16px\) saturate\(122%\);[\s\S]*transform:\s*translate3d\(0,\s*0,\s*0\) scale\(1\.34\);/s)
  assert.doesNotMatch(css, /home-folder-transition-zoom-out/)
  assert.doesNotMatch(css, /\.home-folder-transition-image\.is-reverse/)
  assert.doesNotMatch(css, /home-folder-transition-backdrop/)
  assert.match(css, /@keyframes home-page-clear-in\s*\{[\s\S]*filter:\s*blur\(12px\) brightness\(0\.68\);[\s\S]*filter:\s*blur\(0\) brightness\(1\);/s)
  assert.match(css, /@keyframes folder-backdrop-clear-in\s*\{[\s\S]*filter:\s*blur\(18px\) brightness\(0\.54\);[\s\S]*filter:\s*blur\(0\) brightness\(1\);/s)
  assert.match(css, /@keyframes folder-content-clear-in\s*\{[\s\S]*filter:\s*blur\(10px\) brightness\(0\.72\);[\s\S]*filter:\s*blur\(0\) brightness\(1\);/s)
  assert.doesNotMatch(css.match(/@keyframes folder-backdrop-clear-in\s*\{[\s\S]*?\n\}/)?.[0] || '', /scale\(|translate|transform:/)
  assert.ok(reducedMotionIndex !== -1, 'reduced-motion media query should exist')
  const reducedTransitionIndex = css.indexOf('.home-folder-transition,', reducedMotionIndex)
  assert.ok(reducedTransitionIndex > reducedMotionIndex)
  const reducedTransitionRule = css.slice(
    reducedTransitionIndex,
    css.indexOf('}', reducedTransitionIndex) + 1
  )
  for (const selector of [
    '.home-folder-transition',
    '.home-folder-transition-image',
    '.home-page.is-home-returning',
    '.folder-entry-backdrop-image',
    '.folder-page.is-folder-entering .folder-backdrop-layer',
    '.folder-page.is-folder-entering .folder-content-layer',
  ]) {
    assert.ok(reducedTransitionRule.includes(selector), `missing reduced-motion selector: ${selector}`)
  }
  assert.match(reducedTransitionRule, /animation-duration:\s*1ms\s*!important;/)
})

test('folder episode cards prefer episode stills and placeholder missing metadata', () => {
  const css = readFileSync('src/index.css', 'utf8')
  const folderSource = readFileSync('src/pages/folder/FolderPage.tsx', 'utf8')
  const folderSection = cssRuleBody(css, '.folder-episode-section {')
  const folderGrid = cssRuleBody(css, '.folder-episode-grid {')

  assert.deepEqual(
    getMovieCardCover({ tmdb_type: 'tv', tmdb_episode: 3, episode_still: 'https://img.example/still.jpg' }, 'episode-still-only'),
    { kind: 'episode-still', isEpisode: true, hasEpisodeStill: true, usesLandscape: true }
  )
  assert.deepEqual(
    getMovieCardCover({ tmdb_type: 'tv', tmdb_episode: 4 }, 'episode-still-only'),
    { kind: 'placeholder', isEpisode: true, hasEpisodeStill: false, usesLandscape: true }
  )
  assert.deepEqual(
    getMovieCardCover({ tmdb_type: 'movie', tmdb_episode: undefined }, 'episode-still-only'),
    { kind: 'placeholder', isEpisode: false, hasEpisodeStill: false, usesLandscape: true }
  )
  assert.match(folderSection, /padding-top:\s*clamp\(1rem,\s*2\.4vw,\s*1\.5rem\);/)
  assert.match(folderSource, /className="folder-episode-section"/)
  assert.match(folderGrid, /--mt-media-card-width:\s*16rem;/)
  assert.match(folderGrid, /--mt-media-card-height:\s*9rem;/)
  assert.match(folderSource, /folder-episode-grid/)
  assert.match(folderSource, /coverStrategy="episode-still-only"/)
})

test('folder backdrop header keeps episode controls below the first viewport', () => {
  const folderSource = readFileSync('src/pages/folder/FolderPage.tsx', 'utf8')

  assert.match(folderSource, /min-h-\[calc\(100dvh-5\.5rem\)\]/)
  assert.match(folderSource, /sm:min-h-\[calc\(100dvh-6\.75rem\)\]/)
  assert.match(folderSource, /bottom-0 p-4 pb-16 sm:p-7 sm:pb-24/)
  assert.doesNotMatch(folderSource, /min-h-\[clamp\(18rem,42vh,30rem\)\]/)
  assert.doesNotMatch(folderSource, /sm:min-h-\[clamp\(20rem,46vh,34rem\)\]/)
  assert.doesNotMatch(folderSource, /pb-10 sm:p-7 sm:pb-16/)
})

test('folder season selector keeps inactive tab labels white', () => {
  const folderSource = readFileSync('src/pages/folder/FolderPage.tsx', 'utf8')

  assert.match(folderSource, /!seasonFilter && !specialsSelected \? 'bg-apple-blue\/80 text-white shadow-glow' : 'text-white\/80 hover:bg-white\/\[0\.08\] hover:text-white'/)
  assert.match(folderSource, /seasonFilter === tab\.path \? 'bg-apple-blue\/80 text-white shadow-glow' : 'text-white\/80 hover:bg-white\/\[0\.08\] hover:text-white'/)
  assert.match(folderSource, /specialsSelected \? 'bg-apple-pink\/80 text-white shadow-glow' : 'text-white\/80 hover:bg-apple-pink\/10 hover:text-white'/)
  assert.doesNotMatch(folderSource, /text-gray-400 hover:bg-white\/\[0\.08\] hover:text-white/)
  assert.doesNotMatch(folderSource, /text-gray-400 hover:bg-apple-pink\/10 hover:text-apple-pink/)
})

test('continue watching cards use episode stills or cached movie snapshots', () => {
  const homeSource = readFileSync('src/pages/home/Home.tsx', 'utf8')
  const css = readFileSync('src/index.css', 'utf8')
  const cardSource = readFileSync('src/components/MovieCard.tsx', 'utf8')
  const coverHelperSource = readFileSync('src/components/movieCardCover.ts', 'utf8')
  const playerSource = readFileSync('src/components/VideoPlayer.tsx', 'utf8')
  const detailSource = readFileSync('src/pages/detail/Detail.tsx', 'utf8')
  const strip = cssRuleBody(css, '.home-continue-strip {')
  const item = cssRuleBody(css, '.home-continue-item {')
  const cover = cssRuleBody(css, '.home-continue-cover {')
  const coverImage = cssRuleBody(css, '.home-continue-cover img {')
  const coverPlaceholder = cssRuleBody(css, '.home-continue-cover-placeholder {')
  const coverShade = cssRuleBody(css, '.home-continue-cover-shade {')
  const progressTrack = cssRuleBody(css, '.home-continue-progress-track {')
  const heading = cssRuleBody(css, '.home-section-title {')

  assert.doesNotMatch(homeSource, /import \{ getMovieCardCover \} from '\.\.\/\.\.\/components\/movieCardCover'/)
  assert.match(homeSource, /function getHomeContinueCoverKind\(movie: Movie\): 'episode-still' \| 'continue-snapshot'/)
  assert.match(homeSource, /const isEpisode = movie\.tmdb_type === 'tv' \|\| movie\.tmdb_episode != null \|\| movie\.episode_number != null/)
  assert.match(homeSource, /if \(isEpisode\) return 'episode-still'/)
  assert.match(homeSource, /if \(coverKind === 'episode-still'\) return api\.episodeStillUrl\(movie\.id\)/)
  assert.match(homeSource, /if \(coverKind === 'continue-snapshot'\) return api\.continueCoverUrl\(movie\.id\)/)
  assert.doesNotMatch(coverHelperSource, /continue-watching/)
  assert.match(homeSource, /home-continue-strip[\s\S]*recentMovies\.map/)
  assert.match(homeSource, /getHomeContinueCoverSrc\(movie\)/)
  assert.match(homeSource, /home-continue-progress-bar/)
  assert.match(strip, /display:\s*flex;/)
  assert.match(strip, /overflow-x:\s*auto;/)
  assert.match(strip, /flex-wrap:\s*nowrap;/)
  assert.match(cssRuleBody(css, '.home-page,'), /--mt-home-continue-width:\s*clamp\(var\(--mt-home-continue-min\),\s*var\(--mt-home-continue-fluid\),\s*var\(--mt-home-continue-max\)\);/)
  assert.doesNotMatch(item, /--mt-home-continue-width:/)
  assert.match(item, /flex:\s*0 0 min\(var\(--mt-home-continue-width\),\s*calc\(100vw - 2rem\)\);/)
  assert.match(cover, /aspect-ratio:\s*16 \/ 9;/)
  assert.match(coverPlaceholder, /z-index:\s*0;/)
  assert.match(coverImage, /position:\s*relative;/)
  assert.match(coverImage, /z-index:\s*1;/)
  assert.match(coverShade, /z-index:\s*2;/)
  assert.match(progressTrack, /z-index:\s*3;/)
  assert.match(heading, /font-size:\s*0\.9375rem;/)
  assert.match(heading, /color:\s*rgba\(255,\s*255,\s*255,\s*0\.62\);/)
  assert.doesNotMatch(cardSource, /api\.continueCoverUrl\(movie\.id\)/)
  assert.doesNotMatch(cardSource, /CONTINUE_SNAPSHOT_RETRY_DELAYS_MS/)
  assert.doesNotMatch(cardSource, /setContinueSnapshotRetryIndex/)
  assert.match(playerSource, /api\.saveProgress\(movieId, pos, total, true, captureContinueSnapshot\)/)
  assert.match(detailSource, /captureContinueSnapshot=\{captureContinueSnapshot\}/)
  assert.doesNotMatch(playerSource, /api\.resetContinueCover\(movieId\)/)
})

test('detail page opts into autoplay without changing VideoPlayer default reuse behavior', () => {
  const playerSource = readFileSync('src/components/VideoPlayer.tsx', 'utf8')
  const detailSource = readFileSync('src/pages/detail/Detail.tsx', 'utf8')

  assert.match(playerSource, /autoPlay\?: boolean/)
  assert.match(playerSource, /autoPlay = false/)
  assert.match(playerSource, /autoplay: autoPlay/)
  assert.match(detailSource, /<VideoPlayer[\s\S]*\sautoPlay[\s\S]*episodes=\{episodes\}/)
})

test('detail page fits the player to the viewport with matching side and bottom gutters', () => {
  const css = readFileSync('src/index.css', 'utf8')
  const playerSource = readFileSync('src/components/VideoPlayer.tsx', 'utf8')
  const detailSource = readFileSync('src/pages/detail/Detail.tsx', 'utf8')
  const detailPage = cssRuleBody(css, '.detail-page {')
  const detailStage = cssRuleBody(css, '.detail-player-stage {')
  const detailToolbar = cssRuleBody(css, '.detail-player-toolbar {')
  const detailBackButton = cssRuleBody(css, '.detail-back-button {')
  const detailInfoStack = cssRuleBody(css, '.detail-info-stack {')
  const fittedWrapper = cssRuleBody(css, '.fitted-player-wrapper {')
  const fittedArt = cssRuleBody(css, '.fitted-player-wrapper .mediatree-artplayer {')
  const actionRow = cssRuleBody(css, '.fitted-player-wrapper .player-action-row {')
  const stageIndex = detailSource.indexOf("className={theaterMode ? 'contents' : 'detail-player-stage'}")
  const infoStackIndex = detailSource.indexOf('className="detail-info-stack"')

  assert.match(detailSource, /className=\{theaterMode \? 'flex-1 flex flex-col min-h-0' : 'detail-page'\}/)
  assert.match(detailSource, /className=\{theaterMode \? 'contents' : 'detail-player-stage'\}/)
  assert.doesNotMatch(detailSource, /className="detail-first-screen"/)
  assert.notEqual(stageIndex, -1)
  assert.ok(infoStackIndex > stageIndex, 'detail info should be rendered after the player stage')
  assert.match(detailSource, /className="detail-player-toolbar"/)
  assert.match(detailSource, /className="detail-info-stack"/)
  assert.match(detailSource, /fitToContainer/)
  assert.match(playerSource, /fitToContainer\?: boolean/)
  assert.match(playerSource, /const FITTED_ACTION_ROW_HEIGHT = 52/)
  assert.match(playerSource, /fitToContainer && !theaterMode \? FITTED_ACTION_ROW_HEIGHT : 0/)
  assert.match(detailPage, /--detail-player-edge-gap:\s*var\(--mt-layout-page-padding-x\);/)
  assert.match(detailPage, /--detail-player-top-reserve:\s*calc\(7\.75rem \+ var\(--mt-layout-page-padding-y\)\);/)
  assert.match(detailPage, /gap:\s*0\.75rem;/)
  assert.match(detailToolbar, /display:\s*flex;/)
  assert.match(detailStage, /block-size:\s*max\(18rem,\s*calc\(100dvh - var\(--detail-player-top-reserve\) - var\(--detail-player-edge-gap\)\)\);/)
  assert.match(detailStage, /align-items:\s*stretch;/)
  assert.match(detailInfoStack, /margin-top:\s*var\(--detail-player-edge-gap\);/)
  assert.match(detailInfoStack, /padding-top:\s*clamp\(1rem,\s*2\.4vw,\s*1\.5rem\);/)
  assert.doesNotMatch(detailBackButton, /position:\s*absolute;/)
  assert.match(fittedWrapper, /justify-content:\s*flex-end;/)
  assert.match(fittedArt, /height:\s*100% !important;/)
  assert.doesNotMatch(actionRow, /position:\s*absolute;/)
  assert.match(actionRow, /min-height:\s*2rem;/)
})

test('theater player sizing reserves external action row height and clears impossible fits', () => {
  assert.deepEqual(
    calculateTheaterPlayerSize(1280, 800, 16 / 9, 52),
    { width: 1280, height: 720 }
  )
  assert.deepEqual(
    calculateTheaterPlayerSize(1000, 400, 16 / 9, 52),
    { width: 618, height: 348 }
  )
  assert.equal(calculateTheaterPlayerSize(1000, 40, 16 / 9, 52), null)
  assert.deepEqual(
    calculateTheaterPlayerSize(900, 500, Number.NaN),
    { width: 888, height: 500 }
  )
})

test('movie card episode labels prefer tmdb_episode and fall back to episode_number', () => {
  assert.equal(
    formatMovieCardEpisodePrefix({ tmdb_season: 2, tmdb_episode: 4, episode_number: undefined, episode_title: undefined, title: undefined, code: 'S02E04' }),
    'S02·E04'
  )
  assert.equal(
    formatMovieCardEpisodePrefix({ tmdb_season: undefined, tmdb_episode: undefined, episode_number: 7, episode_title: undefined, title: undefined, code: 'EP07' }),
    'E07'
  )
  assert.equal(
    formatMovieCardEpisodeTitle({ tmdb_season: 2, tmdb_episode: undefined, episode_number: 4, episode_title: 'Episode Four', title: 'Show', code: 'S02E04' }),
    'S02·E04 Episode Four'
  )
  assert.equal(
    formatMovieCardEpisodeTitle({ tmdb_season: undefined, tmdb_episode: undefined, episode_number: undefined, episode_title: undefined, title: 'Show', code: 'SHOW' }),
    'Show'
  )
})

test('media grid layout shifts animate with translate-only FLIP motion', () => {
  const app = readFileSync('src/App.tsx', 'utf8')
  const hook = readFileSync('src/hooks/useMediaGridMotion.ts', 'utf8')
  const handleWindowResizeBody = hook.match(/const handleWindowResize = \(\) => \{([\s\S]*?)\n    \}/)?.[1] ?? ''

  assert.match(app, /useMediaGridMotion\(\)/)
  assert.match(hook, /prefers-reduced-motion:\s*reduce/)
  assert.match(hook, /ResizeObserver/)
  assert.match(hook, /MutationObserver/)
  assert.match(hook, /window\.addEventListener\('resize',\s*handleWindowResize/)
  assert.match(hook, /media-grid:not\(\[data-media-grid-motion="off"\]\)/)
  assert.match(hook, /const MOVE_THRESHOLD_PX = 0\.5/)
  assert.match(hook, /const LAYOUT_MOTION_FPS = 60/)
  assert.match(hook, /const FRAME_MS = 1000 \/ LAYOUT_MOTION_FPS/)
  assert.match(hook, /const ANIMATION_FRAMES = 18/)
  assert.match(hook, /const ANIMATION_MS = Math\.round\(ANIMATION_FRAMES \* FRAME_MS\)/)
  assert.match(hook, /const RESIZE_TRACK_FRAMES = 24/)
  assert.match(hook, /const RESIZE_TRACK_MS = Math\.round\(RESIZE_TRACK_FRAMES \* FRAME_MS\)/)
  assert.match(hook, /const scheduleAnimationFrame = \(\) => \{/)
  assert.match(hook, /window\.requestAnimationFrame\(trackResizeMotion\)/)
  assert.match(hook, /window\.requestAnimationFrame\(runAnimationFrame\)/)
  assert.match(hook, /window\.performance\.now\(\) \+ RESIZE_TRACK_MS/)
  assert.match(hook, /runAnimationNow\(\)/)
  assert.match(hook, /window\.innerWidth === lastViewportWidth/)
  assert.doesNotMatch(handleWindowResizeBody, /lastRects\s*=\s*readRects\(grids\)/)
  assert.match(hook, /card\.animate/)
  assert.match(hook, /DOMMatrixReadOnly/)
  assert.match(hook, /getComputedStyle\(card\)\.transform/)
  assert.match(hook, /function getDocumentCardLayoutRect\(card: HTMLElement,\s*activeOffset\?: CardRect\): CardRect/)
  assert.match(hook, /const rect = getDocumentCardRect\(card\)/)
  assert.match(hook, /const offset = activeOffset \?\? readTransformOffset\(getComputedStyle\(card\)\.transform\)/)
  assert.match(hook, /left:\s*rect\.left\s*-\s*offset\.left/)
  assert.match(hook, /top:\s*rect\.top\s*-\s*offset\.top/)
  assert.match(hook, /rects\.set\(card,\s*getDocumentCardLayoutRect\(card\)\)/)
  assert.match(hook, /const afterLayout = getDocumentCardLayoutRect\(card,\s*activeOffset\)/)
  assert.match(hook, /const fromX = dx \+ activeOffset\.left/)
  assert.match(hook, /const fromY = dy \+ activeOffset\.top/)
  assert.match(hook, /__mediaGridAnimationCount/)
  assert.doesNotMatch(hook, /animation\.cancel\(\)/)
  assert.doesNotMatch(hook, /__mediaGridAnimation\?\.cancel\(\)/)
  assert.match(hook, /translate3d\(\$\{fromX\}px,\s*\$\{fromY\}px,\s*0\)/)
  assert.doesNotMatch(hook, /scale\(/)
})

test('media grid layout motion compares page coordinates so scrolling is not animated as layout movement', () => {
  const hook = readFileSync('src/hooks/useMediaGridMotion.ts', 'utf8')

  assert.match(hook, /function getDocumentCardRect\(card: HTMLElement\): CardRect/)
  assert.match(hook, /left:\s*rect\.left\s*\+\s*window\.scrollX/)
  assert.match(hook, /top:\s*rect\.top\s*\+\s*window\.scrollY/)
  assert.match(hook, /const rect = getDocumentCardRect\(card\)/)
  assert.match(hook, /const afterLayout = getDocumentCardLayoutRect\(card,\s*activeOffset\)/)
  assert.doesNotMatch(hook, /const after = card\.getBoundingClientRect\(\)/)
})

test('home page plays a top-to-bottom opening drop animation without fighting grid motion', () => {
  const css = readFileSync('src/index.css', 'utf8')
  const homeSource = readFileSync('src/pages/home/Home.tsx', 'utf8')
  const hook = readFileSync('src/hooks/useMediaGridMotion.ts', 'utf8')
  const openingHeader = cssRuleBody(css, '.home-page.is-home-opening .home-section-header,', 1)
  const openingContinue = cssRuleBody(css, '.home-page.is-home-opening .home-continue-item {')
  const openingCard = cssRuleBody(css, '.home-page.is-home-opening .home-poster-grid > .home-poster-card,', 1)
  const continueKeyframes = css.match(/@keyframes home-opening-continue-in\s*\{[\s\S]*?\n\}/)?.[0] || ''

  assert.match(homeSource, /const HOME_OPENING_ANIMATION_MS = 1680/)
  assert.match(homeSource, /const HOME_OPENING_MAX_ITEMS = 48/)
  assert.match(homeSource, /const homeOpeningStartedRef = useRef\(false\)/)
  assert.match(homeSource, /const \[homeOpening, setHomeOpening\] = useState\(false\)/)
  assert.match(homeSource, /prefers-reduced-motion:\s*reduce/)
  assert.match(homeSource, /setHomeOpening\(true\)/)
  assert.match(homeSource, /window\.setTimeout\(\(\) => setHomeOpening\(false\), HOME_OPENING_ANIMATION_MS\)/)
  assert.match(homeSource, /className=\{`home-page \$\{homeReturning \? 'is-home-returning' : ''\} \$\{homeOpening \? 'is-home-opening' : ''\}`\}/)
  assert.match(homeSource, /--home-opening-index/)
  assert.match(openingHeader, /animation:\s*home-opening-header-drop\s+420ms/)
  assert.match(openingContinue, /animation:\s*home-opening-continue-in\s+360ms/)
  assert.match(openingContinue, /animation-delay:\s*calc\(40ms \+ min\(var\(--home-opening-index,\s*0\),\s*48\) \* 16ms\);/)
  assert.match(css, /@keyframes home-opening-continue-in\s*\{[\s\S]*filter:\s*blur\(8px\) brightness\(0\.9\);[\s\S]*filter:\s*blur\(0\) brightness\(1\);/s)
  assert.doesNotMatch(continueKeyframes, /translate3d|translateY|rotateX/)
  assert.match(openingCard, /animation:\s*home-opening-card-drop\s+520ms/)
  assert.match(openingCard, /animation-delay:\s*calc\(40ms \+ min\(var\(--home-opening-index,\s*0\),\s*48\) \* 22ms\);/)
  assert.match(css, /@keyframes home-opening-card-drop\s*\{[\s\S]*translate3d\(0,\s*-2\.4rem,\s*0\)[\s\S]*translate3d\(0,\s*0,\s*0\)/s)
  assert.doesNotMatch(css.match(/@keyframes home-opening-card-drop\s*\{[\s\S]*?\n\}/)?.[0] || '', /translate3d\(0,\s*0\.[1-9]/)
  assert.doesNotMatch(css, /\.home-page\.is-home-opening \.home-poster-grid\s*\{[\s\S]*pointer-events:\s*none;/)
  assert.match(css, /@media \(prefers-reduced-motion:\s*reduce\)\s*\{[\s\S]*\.home-page\.is-home-opening \.home-continue-item,[\s\S]*\.home-page\.is-home-opening \.home-poster-grid > \.home-poster-card[\s\S]*animation-duration:\s*1ms\s*!important;/s)
  assert.match(hook, /function isGridEntranceAnimating\(grid: Element\)/)
  assert.match(hook, /grid\.closest\('\.is-home-opening,\s*\.is-browse-opening'\)/)
  assert.match(hook, /function getDocumentCardLayoutRect\(card: HTMLElement,\s*activeOffset\?: CardRect\): CardRect/)
  assert.match(hook, /if \(isGridEntranceAnimating\(grid\)\) \{[\s\S]*nextRects\.set\(card,\s*getDocumentCardLayoutRect\(card\)\)[\s\S]*return/s)
})

test('settings theme copy is user-facing', () => {
  const source = readFileSync('src/pages/settings/Settings.tsx', 'utf8')

  assert.ok(source.includes('外观主题'))
  assert.ok(source.includes('导入主题文件即可更换整体外观'))
  assert.ok(source.includes('导入主题'))
  assert.doesNotMatch(source, /JSON 主题包|上传主题|下载示例主题|导出我的主题/)
})

test('settings scraper tab manages built-in and uploaded scrapers in one plugin list', () => {
  const source = readFileSync('src/pages/settings/Settings.tsx', 'utf8')

  assert.doesNotMatch(source, /所有可用刮削器/)
  assert.doesNotMatch(source, /scrapers\.map\(\s*scraper\s*=>/)
  assert.match(source, /plugins\.map\(\s*plugin\s*=>/)
  assert.ok(source.includes("plugin.builtin ? '内置' : '插件'"))
  assert.doesNotMatch(source, />\s*\{plugin\.enabled \? '已启用' : '未启用'\}\s*</)
  assert.match(source, /\{pluginBusy === plugin\.name \? '处理中\.\.\.' : plugin\.enabled \? '停用' : '启用'\}/)
})

test('setup wizard includes the TMDB token configuration guide link', () => {
  const settings = readFileSync('src/pages/settings/Settings.tsx', 'utf8')
  const setup = readFileSync('src/pages/setup/SetupWizard.tsx', 'utf8')
  const tmdbGuideHref = 'https://zasenjc.github.io/mediatree/guide/configuration#获取-tmdb-读取访问令牌'

  assert.ok(settings.includes(`href="${tmdbGuideHref}"`))
  assert.ok(setup.includes(`href="${tmdbGuideHref}"`))
  assert.match(setup, /target="_blank"/)
  assert.match(setup, /rel="noreferrer"/)
})

test('applyTheme writes tokens, color scheme, dataset, and custom CSS', () => {
  const doc = createDocumentStub()
  const theme: ThemePackage = {
    name: 'mint',
    label: 'Mint',
    colorScheme: 'light',
    tokens: {
      '--mt-color-accent': '#2fbf71',
      '--mt-color-text': '#111827',
    },
    customCss: '.glass-panel { box-shadow: none; }',
  }

  applyTheme(theme, doc)

  assert.equal(doc.documentElement.getAttribute('data-mediatree-theme'), 'mint')
  assert.equal(doc.documentElement.getAttribute('data-mediatree-theme-source'), 'custom')
  assert.equal(doc.documentElement.getAttribute('data-mediatree-color-scheme'), 'light')
  assert.equal(doc.documentElement.style.getPropertyValue('--mt-color-accent'), '#2fbf71')
  assert.equal(doc.documentElement.style.getPropertyValue('--mt-color-text'), '#111827')
  assert.equal(
    doc.styleElement.textContent,
    ':root[data-mediatree-theme] .glass-panel { box-shadow: none; }'
  )
})

test('createThemeExport includes the active built-in and custom themes', () => {
  const storage = createMemoryStorage()
  const customTheme: ThemePackage = {
    name: 'custom-blue',
    label: 'Custom Blue',
    tokens: { '--mt-color-accent': '#4f8cff' },
  }
  const exported = JSON.parse(createThemeExport(BUILTIN_THEMES[0], [customTheme], storage))

  assert.equal(exported.activeTheme, BUILTIN_THEMES[0].name)
  assert.equal(exported.themes[0].name, customTheme.name)
  assert.equal(exported.version, 2)
})

test('importCustomThemes rejects built-in names without changing stored custom themes', () => {
  const storage = createMemoryStorage()
  const existing: ThemePackage = {
    name: 'existing-theme',
    label: 'Existing',
    tokens: { '--mt-color-accent': '#123456' },
  }
  importCustomThemes([existing], storage)

  assert.throws(
    () => importCustomThemes([{
      name: BUILTIN_THEMES[0].name,
      label: 'Duplicate Builtin',
      tokens: { '--mt-color-accent': '#ffffff' },
    }], storage),
    /不能使用内置主题 name/
  )

  const exported = JSON.parse(createThemeExport(BUILTIN_THEMES[0], undefined, storage))
  assert.deepEqual(exported.themes.map((theme: ThemePackage) => theme.name), ['existing-theme'])
})

test('light color schemes remap fixed Tailwind text utilities to theme text tokens', () => {
  const css = readFileSync('src/index.css', 'utf8')
  const scope = ':root[data-mediatree-color-scheme="light"]'
  const utilitiesIndex = css.indexOf('@tailwind utilities;')
  const compatibilityIndex = css.indexOf(`${scope} .text-white`)

  assert.ok(utilitiesIndex >= 0, 'missing Tailwind utilities import')
  assert.ok(
    compatibilityIndex > utilitiesIndex,
    'light text compatibility rules should be declared after Tailwind utilities'
  )

  for (const selector of [
    `${scope} .text-white`,
    `${scope} .text-white\\/90`,
  ]) {
    assertCssRuleColor(css, selector, '--mt-color-text')
  }

  for (const selector of [
    `${scope} .text-white\\/70`,
    `${scope} .text-gray-100`,
    `${scope} .text-gray-200`,
    `${scope} .text-gray-300`,
    `${scope} .text-gray-400`,
  ]) {
    assertCssRuleColor(css, selector, '--mt-color-text-muted')
  }

  for (const selector of [
    `${scope} .text-white\\/60`,
    `${scope} .text-white\\/10`,
    `${scope} .text-gray-500`,
    `${scope} .text-gray-600`,
  ]) {
    assertCssRuleColor(css, selector, '--mt-color-text-faint')
  }

  assertCssRuleColor(css, `${scope} .hover\\:text-white:hover`, '--mt-color-text')

  const primaryButtonRule = cssRuleBody(css, '.glass-button-primary')
  assert.match(primaryButtonRule, /color:\s*#fff\b/)
  assert.doesNotMatch(primaryButtonRule, /@apply[^;]*\btext-white\b/)
})
