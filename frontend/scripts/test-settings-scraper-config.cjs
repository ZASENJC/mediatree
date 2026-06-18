const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const repoRoot = path.resolve(__dirname, '..')
const settingsSource = fs.readFileSync(path.join(repoRoot, 'src/pages/settings/Settings.tsx'), 'utf8')
const apiTypesSource = fs.readFileSync(path.join(repoRoot, 'src/api/types.ts'), 'utf8')

assert.ok(
  !settingsSource.includes('javdbEnabled') && !settingsSource.includes('setJavdbEnabled'),
  'Settings must not keep state for the deprecated global Javdatabase toggle',
)

assert.ok(
  !settingsSource.includes('javdb_enabled'),
  'Settings must not read or write deprecated javdb_enabled config',
)

assert.ok(
  !settingsSource.includes('启用 Javdatabase'),
  'Settings must not render the deprecated global Javdatabase toggle',
)

assert.ok(
  !apiTypesSource.includes('javdb_enabled'),
  'Config type must not expose deprecated javdb_enabled config',
)

assert.ok(
  !apiTypesSource.includes('tmdb_api_key'),
  'Config type must not expose TMDB API Key to the Settings form',
)

assert.ok(
  !settingsSource.includes('tmdbKey') && !settingsSource.includes('setTmdbKey'),
  'Settings must not keep UI state for the deprecated TMDB API Key field',
)

assert.ok(
  !settingsSource.includes('tmdb_api_key'),
  'Settings must not read or write tmdb_api_key from the scraper config form',
)

assert.ok(
  !settingsSource.includes('TMDB API Key'),
  'Settings must not render the deprecated TMDB API Key input',
)

assert.ok(
  settingsSource.includes('TMDB 读访问令牌'),
  'Settings must keep the TMDB read access token input',
)

assert.ok(
  settingsSource.includes('https://zasenjc.github.io/mediatree/guide/configuration#获取-tmdb-读取访问令牌'),
  'Settings must link to the TMDB read access token tutorial',
)

console.log('settings scraper config tests passed')
