import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import {
  applyTheme,
  BUILTIN_THEMES,
  createExampleTheme,
  createThemeExport,
  importCustomThemes,
  parseThemeFileContent,
  sanitizeCustomCss,
  type ThemePackage,
} from './theme'
import { formatMovieCardEpisodePrefix, formatMovieCardEpisodeTitle, getMovieCardCover } from './components/movieCardCover'

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

test('built-in themes do not include the removed Material You light scheme', () => {
  assert.equal(
    BUILTIN_THEMES.some(item => item.name === 'material-you-light' || item.label === 'Material You 浅色'),
    false
  )
  assert.ok(BUILTIN_THEMES.every(theme => theme.schemaVersion === 2))
  assert.ok(BUILTIN_THEMES.every(theme => theme.capabilities?.includes('stable-selectors')))
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
  assert.equal(example.tokens['--mt-layout-page-padding-x'], 'clamp(1rem, 1.8vw, 1.5rem)')
  assert.equal(example.tokens['--mt-layout-page-padding-x-wide'], 'clamp(1rem, 1.8vw, 1.5rem)')
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

  assert.match(topbar, /className=\{`mt-topbar sticky top-0 z-50/)
  assert.match(topbar, /\$\{topbarCompact \? 'is-compact' : 'is-expanded'\}/)
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
  assert.match(topbar, /className="topbar-round-button rounded-full text-white transition-colors hover:bg-red-500\/10 hover:text-white"/)
  assert.match(topbar, /aria-label="展开搜索"/)
  assert.match(topbar, /aria-label="收起搜索"/)
  assert.match(topbar, /className=\{`topbar-search-form \$\{desktopSearchOpen \? 'is-open' : ''\} hidden sm:flex`\}/)
  assert.match(topbar, /className="topbar-search-input glass-input/)
  assert.match(topbar, /\? 'bg-white\/18 text-white shadow-sm'\s*:\s*'text-white hover:bg-white\/10'/)
  assert.match(topbar, /className="rounded-full px-1\.5 py-1\.5 text-xs text-white transition-colors hover:bg-white\/10 sm:px-2"/)
  assert.match(topbar, /className="rounded-full p-1\.5 text-white transition-colors hover:bg-white\/10 sm:p-2 sm:hidden"/)
  assert.doesNotMatch(topbar, /className="rounded-full p-1\.5 text-white transition-colors hover:bg-red-500\/10 hover:text-white sm:p-2"/)
  assert.match(app, /const \[desktopSearchOpen, setDesktopSearchOpen\] = useState\(false\)/)
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
  const compactCollapsed = cssRuleBody(css, '.mt-topbar.is-compact .topbar-brand-text,')
  const logo = cssRuleBody(css, '.mt-topbar .topbar-logo-mark {')
  const compactLibraryTrigger = cssRuleBody(css, '.mt-topbar .topbar-compact-library-trigger {')
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
  assert.match(topbar, /--mt-topbar-motion-duration:\s*1488ms;/)
  assert.match(topbar, /--mt-topbar-content-duration:\s*1152ms;/)
  assert.match(topbar, /--mt-topbar-icon-fade-duration:\s*560ms;/)
  assert.match(topbar, /--mt-topbar-icon-exit-duration:\s*420ms;/)
  assert.match(topbar, /--mt-topbar-compact-icon-delay:\s*280ms;/)
  assert.match(topbar, /--mt-topbar-content-reveal-delay:\s*420ms;/)
  assert.match(topbar, /--mt-topbar-content-stagger:\s*100ms;/)
  assert.match(topbar, /--mt-topbar-text-fade-duration:\s*960ms;/)
  assert.match(topbarShell, /padding-inline:\s*var\(--mt-layout-page-padding-x\);/)
  assert.match(css, /@media \(min-width:\s*640px\)\s*\{[^}]*\.mt-topbar \.topbar-shell\s*\{[^}]*padding-inline:\s*var\(--mt-layout-page-padding-x-wide\);/s)
  assert.match(topbarGlass, /inline-size:\s*var\(--mt-topbar-expanded-width,\s*auto\);/)
  assert.match(topbarGlass, /min-inline-size:\s*var\(--mt-topbar-ball-size\);/)
  assert.match(topbarGlass, /max-inline-size:\s*var\(--mt-topbar-expanded-width,\s*34rem\);/)
  assert.match(topbarGlass, /overflow:\s*hidden;/)
  assert.match(topbarGlass, /transition:[^}]*max-inline-size\s+var\(--mt-topbar-motion-duration\)\s+var\(--mt-topbar-ease\)/s)
  assert.match(topbarGlass, /will-change:\s*max-inline-size,\s*inline-size,\s*border-radius,\s*padding,\s*transform;/)
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
  assert.match(compactGlass, /border-radius:\s*999px;/)
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
  assert.match(logo, /inset-inline-start:\s*calc\(\(var\(--mt-topbar-ball-size\)\s*-\s*1\.45rem\)\s*\/\s*2\);/)
  assert.doesNotMatch(logo, /transform:/)
  assert.match(compactLibraryTrigger, /opacity\s+var\(--mt-topbar-icon-exit-duration\)\s+ease,/)
  assert.match(compactLibraryTrigger, /justify-content:\s*center;/)
  assert.match(compactLibraryTrigger, /padding:\s*0;/)
  assert.doesNotMatch(compactLibraryTrigger, /transform:/)
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
  assert.match(compactTrigger, /opacity\s+var\(--mt-topbar-icon-fade-duration\)\s+ease\s+var\(--mt-topbar-compact-icon-delay\),/)
  assert.match(compactTrigger, /pointer-events:\s*auto;/)
  assert.doesNotMatch(compactTrigger, /transform:/)
})

test('liquid glass uses a compact dark frosted surface', () => {
  const css = readFileSync('src/index.css', 'utf8')
  const liquidGlass = cssRuleBody(css, '.liquid-glass {')
  const lightTextRemapIndex = css.indexOf(':root[data-mediatree-color-scheme="light"] .text-white')
  const topbarWhiteIndex = css.indexOf('.mt-topbar .liquid-glass,')

  assert.match(liquidGlass, /overflow:\s*hidden;/)
  assert.match(liquidGlass, /isolation:\s*isolate;/)
  assert.match(liquidGlass, /border-radius:\s*18px;/)
  assert.match(liquidGlass, /border:\s*1px solid rgba\(255,\s*255,\s*255,\s*0\.12\);/)
  assert.match(liquidGlass, /background:\s*rgba\(8,\s*10,\s*18,\s*0\.62\);/)
  assert.match(liquidGlass, /backdrop-filter:\s*blur\(4px\) saturate\(140%\);/)
  assert.match(liquidGlass, /box-shadow:\s*none;/)
  assert.doesNotMatch(liquidGlass, /var\(--mt-shadow-glass\)/)
  assert.doesNotMatch(liquidGlass, /brightness\(/)
  assert.match(css, /\.liquid-glass::after\s*\{[^}]*border:\s*1px solid rgba\(255,\s*255,\s*255,\s*0\.06\);[^}]*\}/s)
  assert.doesNotMatch(cssRuleBody(css, '.liquid-glass::after {'), /box-shadow:/)
  assert.match(css, /\.mt-topbar \.glass-button,[^}]*\.mt-topbar \.glass-input:focus\s*\{[^}]*box-shadow:\s*none;/s)
  assert.ok(lightTextRemapIndex !== -1 && topbarWhiteIndex > lightTextRemapIndex)
  assert.match(css, /\.mt-topbar \.liquid-glass,[^}]*\.mt-topbar \.glass-input\s*\{[^}]*color:\s*#fff;/s)
})

test('global layout fills available width responsively', () => {
  const css = readFileSync('src/index.css', 'utf8')
  const root = cssRuleBody(css, ':root')
  const content = cssRuleBody(css, '.mt-content')
  const mediaGrid = cssRuleBody(css, '.media-grid {')

  assert.equal(BUILTIN_THEMES[0].tokens['--mt-layout-content-max'], 'none')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-layout-page-padding-x'], 'clamp(1rem, 1.8vw, 1.5rem)')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-layout-page-padding-x-wide'], 'clamp(1rem, 1.8vw, 1.5rem)')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-media-grid-min'], '9.75rem')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-media-grid-max'], '11rem')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-media-card-width'], '11rem')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-media-card-height'], '16.5rem')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-media-grid-gap'], '1rem')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-media-grid-column-gap'], '1rem')
  assert.equal(BUILTIN_THEMES[0].tokens['--mt-media-grid-row-gap'], '1.25rem')
  assert.match(root, /--mt-layout-content-max:\s*none;/)
  assert.match(root, /--mt-layout-page-padding-x:\s*clamp\(1rem,\s*1\.8vw,\s*1\.5rem\);/)
  assert.match(root, /--mt-layout-page-padding-x-wide:\s*clamp\(1rem,\s*1\.8vw,\s*1\.5rem\);/)
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

test('home library uses poster grid cards with external title metadata', () => {
  const css = readFileSync('src/index.css', 'utf8')
  const source = readFileSync('src/pages/home/Home.tsx', 'utf8')
  const libraryGrid = source.match(/<div className="home-poster-grid[\s\S]*?\{tree\.map/)?.[0] ?? ''
  const card = source.match(/className="home-poster-card media-grid-card group cursor-pointer"[\s\S]*?<\/div>\s*\)\s*\}\)/)?.[0] ?? ''
  const posterCard = cssRuleBody(css, '.home-poster-grid > .home-poster-card {')
  const posterCover = cssRuleBody(css, '.home-poster-cover {')

  assert.ok(libraryGrid.includes('home-poster-grid'), 'home library grid should use poster-grid class')
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
  assert.match(posterCard, /height:\s*calc\(var\(--mt-media-card-height\) \+ 3\.375rem\);/)
  assert.match(posterCard, /display:\s*flex;/)
  assert.match(posterCard, /flex-direction:\s*column;/)
  assert.match(posterCover, /overflow:\s*hidden;/)
  assert.match(posterCover, /border-radius:\s*var\(--mt-radius-card\);/)
  assert.match(css, /(^|\n)\.home-poster-watched-action\s*\{\s*opacity:\s*0;/)
  assert.match(css, /\.home-poster-card:hover \.home-poster-watched-action,[^}]*\.home-poster-card:focus-within \.home-poster-watched-action\s*\{[^}]*opacity:\s*1;/s)
})

test('folder episode cards prefer episode stills and placeholder missing metadata', () => {
  const css = readFileSync('src/index.css', 'utf8')
  const folderSource = readFileSync('src/pages/folder/FolderPage.tsx', 'utf8')
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
  assert.match(folderGrid, /--mt-media-card-width:\s*16rem;/)
  assert.match(folderGrid, /--mt-media-card-height:\s*9rem;/)
  assert.match(folderSource, /folder-episode-grid/)
  assert.match(folderSource, /coverStrategy="episode-still-only"/)
})

test('continue watching cards use episode stills or cached movie snapshots', () => {
  const homeSource = readFileSync('src/pages/home/Home.tsx', 'utf8')
  const cardSource = readFileSync('src/components/MovieCard.tsx', 'utf8')
  const playerSource = readFileSync('src/components/VideoPlayer.tsx', 'utf8')
  const detailSource = readFileSync('src/pages/detail/Detail.tsx', 'utf8')

  assert.deepEqual(
    getMovieCardCover({ tmdb_type: 'tv', tmdb_episode: 3, episode_still: undefined }, 'continue-watching'),
    { kind: 'episode-still', isEpisode: true, hasEpisodeStill: false, usesLandscape: true }
  )
  assert.deepEqual(
    getMovieCardCover({ tmdb_type: 'movie', tmdb_episode: undefined, episode_number: undefined }, 'continue-watching'),
    { kind: 'continue-snapshot', isEpisode: false, hasEpisodeStill: false, usesLandscape: true }
  )
  assert.match(homeSource, /folder-episode-grid[\s\S]*coverStrategy="continue-watching"/)
  assert.match(cardSource, /api\.continueCoverUrl\(movie\.id\)/)
  assert.match(cardSource, /CONTINUE_SNAPSHOT_RETRY_DELAYS_MS/)
  assert.match(cardSource, /setContinueSnapshotRetryIndex\(index => Math\.min\(index \+ 1, CONTINUE_SNAPSHOT_RETRY_DELAYS_MS\.length\)\)/)
  assert.match(playerSource, /api\.saveProgress\(movieId, pos, total, true, captureContinueSnapshot\)/)
  assert.match(detailSource, /captureContinueSnapshot=\{captureContinueSnapshot\}/)
  assert.doesNotMatch(playerSource, /api\.resetContinueCover\(movieId\)/)
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
  assert.match(hook, /const MOVE_THRESHOLD_PX = 0\.5/)
  assert.match(hook, /const RESIZE_TRACK_MS = 220/)
  assert.match(hook, /window\.requestAnimationFrame\(trackResizeMotion\)/)
  assert.match(hook, /window\.performance\.now\(\) \+ RESIZE_TRACK_MS/)
  assert.match(hook, /runAnimationNow\(\)/)
  assert.match(hook, /window\.innerWidth === lastViewportWidth/)
  assert.doesNotMatch(handleWindowResizeBody, /lastRects\s*=\s*readRects\(grids\)/)
  assert.match(hook, /const ANIMATION_MS = 180/)
  assert.match(hook, /card\.animate/)
  assert.match(hook, /DOMMatrixReadOnly/)
  assert.match(hook, /getComputedStyle\(card\)\.transform/)
  assert.match(hook, /left:\s*after\.left\s*-\s*activeOffset\.left/)
  assert.match(hook, /top:\s*after\.top\s*-\s*activeOffset\.top/)
  assert.match(hook, /const fromX = dx \+ activeOffset\.left/)
  assert.match(hook, /const fromY = dy \+ activeOffset\.top/)
  assert.match(hook, /__mediaGridAnimationCount/)
  assert.doesNotMatch(hook, /animation\.cancel\(\)/)
  assert.doesNotMatch(hook, /__mediaGridAnimation\?\.cancel\(\)/)
  assert.match(hook, /translate\(\$\{fromX\}px,\s*\$\{fromY\}px\)/)
  assert.doesNotMatch(hook, /scale\(/)
})

test('settings theme copy is user-facing', () => {
  const source = readFileSync('src/pages/settings/Settings.tsx', 'utf8')

  assert.ok(source.includes('外观主题'))
  assert.ok(source.includes('导入主题文件即可更换整体外观'))
  assert.ok(source.includes('导入主题'))
  assert.doesNotMatch(source, /JSON 主题包|上传主题|下载示例主题|导出我的主题/)
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
