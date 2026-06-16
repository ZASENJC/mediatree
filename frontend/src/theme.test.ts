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

function cssRuleBody(css: string, selector: string) {
  const selectorIndex = css.indexOf(selector)
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
    '.mt-popover',
    '.mt-dialog',
    '.mt-media-card',
  ]) {
    assert.ok(css.includes(selector), `missing stable selector: ${selector}`)
  }
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
  assert.match(mediaGrid, /column-gap:\s*var\(--mt-media-grid-gap\)\s*!important;/)
  assert.match(mediaGrid, /row-gap:\s*var\(--mt-media-grid-gap\)\s*!important;/)
  assert.match(mediaGrid, /justify-content:\s*center;/)
  assert.doesNotMatch(mediaGrid, /grid-template-columns:/)
  assert.match(css, /\.media-grid-card\s*\{[^}]*contain-intrinsic-size:\s*var\(--mt-media-card-width\)\s+var\(--mt-media-card-height\);/s)
  assert.match(css, /\.media-grid\s*>\s*\.media-grid-card\s*\{[^}]*width:\s*var\(--mt-media-card-width\);[^}]*height:\s*var\(--mt-media-card-height\);[^}]*min-width:\s*var\(--mt-media-card-width\);[^}]*max-width:\s*var\(--mt-media-card-width\);[^}]*min-height:\s*var\(--mt-media-card-height\);[^}]*max-height:\s*var\(--mt-media-card-height\);/s)
  assert.match(css, /\.media-grid\s+\.media-grid-card\s*\{[^}]*transition:\s*none\s*!important;[^}]*transform:\s*none\s*!important;[^}]*will-change:\s*auto;/s)
  assert.match(css, /\.media-grid\s+\.media-grid-card:hover,\s*\.media-grid\s+\.media-grid-card:focus-visible\s*\{[^}]*transform:\s*none\s*!important;/s)
  assert.match(css, /\.media-grid\s+\.media-grid-card\s+img\s*\{[^}]*transition:\s*none\s*!important;[^}]*transform:\s*none\s*!important;/s)
})

test('settings theme copy is user-facing', () => {
  const source = readFileSync('src/pages/Settings.tsx', 'utf8')

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
