import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import {
  applyTheme,
  BUILTIN_THEMES,
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

test('sanitizeCustomCss scopes broad selectors to the theme root', () => {
  assert.equal(
    sanitizeCustomCss('body { color: red; }\n.glass-panel { border-radius: 10px; }'),
    ':root[data-mediatree-theme] body { color: red; }\n:root[data-mediatree-theme] .glass-panel { border-radius: 10px; }'
  )
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
  assert.equal(exported.version, 1)
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
