const assert = require('node:assert/strict')
require('../node_modules/sucrase/register')

const { normalizeLibraryScraperOptions, normalizeScraperOptions } = require('../src/scrapers.ts')

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

assert.deepEqual(
  normalizeScraperOptions([
    scraper({ name: 'auto', enabled: false }),
    scraper({ name: 'tmdb_tv', enabled: false }),
  ]).map(item => item.name),
  [],
  'disabled scrapers must not be shown in library dropdown',
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
  normalizeScraperOptions([
    scraper({ name: 'auto' }),
    scraper({ name: 'auto', label: 'Duplicate Auto' }),
    scraper({ name: 'custom_tv' }),
    scraper({ name: 'custom_tv', label: 'Duplicate Plugin' }),
  ]).map(item => item.name),
  ['auto', 'custom_tv'],
  'library dropdown options should keep the first enabled entry for each scraper name',
)

assert.deepEqual(
  normalizeScraperOptions([
    scraper({ name: 'disabled_plugin', label: 'Disabled Plugin', enabled: false, builtin: false }),
  ]).map(item => item.name),
  [],
  'library dropdown must rely on /api/scrapers availability instead of plugin-management rows',
)

assert.deepEqual(
  normalizeLibraryScraperOptions([
    scraper({ name: 'none', label: '不刮削', enabled: false, builtin: true }),
    scraper({ name: 'auto' }),
    scraper({ name: 'javdatabase' }),
  ]).map(item => item.name),
  ['none', 'auto', 'javdatabase'],
  'library settings must keep the built-in no-scrape option',
)

assert.ok(
  normalizeLibraryScraperOptions(undefined).some(item => item.name === 'none'),
  'library settings fallback options must include the no-scrape option while scrapers load',
)

assert.deepEqual(
  normalizeScraperOptions([
    scraper({ name: 'none', label: '不刮削' }),
    scraper({ name: 'auto' }),
  ]).map(item => item.name),
  ['auto'],
  'manual scrape options must keep hiding the no-op scraper',
)

console.log('scraper option tests passed')
