const assert = require('node:assert/strict')
require('../node_modules/sucrase/register')

const { buildLibraryScraperOptions, normalizeScraperOptions } = require('../src/scrapers.ts')

const scraper = overrides => ({
  name: 'base',
  label: 'Base',
  description: '',
  supported_media_types: [],
  requires_api_key: false,
  enabled: true,
  builtin: false,
  ...overrides,
})

const plugin = overrides => ({
  name: 'plugin',
  version: '1.0.0',
  label: 'Plugin',
  description: '',
  supported_media_types: [],
  enabled: true,
  builtin: false,
  ...overrides,
})

assert.deepEqual(
  buildLibraryScraperOptions(
    [scraper({ name: 'auto', enabled: false }), scraper({ name: 'tmdb_tv', enabled: false })],
    [plugin({ name: 'custom_tv', enabled: false })],
  ).map(item => item.name),
  [],
  'disabled scrapers and disabled plugins must not be shown in library dropdown',
)

assert.deepEqual(
  normalizeScraperOptions([]),
  [],
  'an empty scraper response means no available scrapers and must not fall back to bundled defaults',
)

assert.ok(
  normalizeScraperOptions(undefined).some(item => item.name === 'auto'),
  'fallback defaults are only for loading or failed scraper responses',
)

assert.deepEqual(
  buildLibraryScraperOptions(
    [scraper({ name: 'auto' }), scraper({ name: 'auto', label: 'Duplicate Auto' })],
    [plugin({ name: 'custom_tv' }), plugin({ name: 'custom_tv', label: 'Duplicate Plugin' })],
  ).map(item => item.name),
  ['auto', 'custom_tv'],
  'library dropdown options should keep the first enabled entry for each scraper name',
)

assert.deepEqual(
  buildLibraryScraperOptions(
    [scraper({ name: 'custom_tv', label: 'Loaded From /api/scrapers' })],
    [plugin({ name: 'custom_tv', label: 'Plugin Management Copy', enabled: true })],
  ).map(item => item.label),
  ['Loaded From /api/scrapers'],
  'plugin-management rows must not duplicate enabled scrapers already returned by /api/scrapers',
)

console.log('scraper option tests passed')
