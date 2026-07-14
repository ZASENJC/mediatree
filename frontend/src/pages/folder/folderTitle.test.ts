import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { buildFolderLogoQueue, findAvailableFolderLogo } from './folderTitle'

const folderTitleSource = readFileSync('src/pages/folder/folderTitle.tsx', 'utf8')

test('folder title logos prefer Chinese, then English, and ignore other languages', () => {
  const queue = buildFolderLogoQueue([
    { url: '/english-small.svg', width: 500, height: 180, language: 'en' },
    { url: '/generic.svg', width: 1200, height: 400, language: null },
    { url: '/chinese-small.svg', width: 600, height: 200, language: 'zh' },
    { url: '/japanese.svg', width: 1400, height: 500, language: 'ja' },
    { url: '/chinese-large.svg', width: 1000, height: 320, language: 'zh' },
    { url: '/english-large.svg', width: 900, height: 300, language: 'en' },
  ])

  assert.deepEqual(queue.map(logo => logo.url), [
    '/chinese-large.svg',
    '/chinese-small.svg',
    '/english-large.svg',
    '/english-small.svg',
  ])
})

test('folder title logos fall back to text when no Chinese or English logo exists', () => {
  const queue = buildFolderLogoQueue([
    { url: '/generic.svg', width: 1200, height: 400, language: null },
    { url: '/japanese.svg', width: 1400, height: 500, language: 'ja' },
  ])

  assert.deepEqual(queue, [])
})

test('folder title logos advance from failed Chinese artwork to English, then text', () => {
  const queue = buildFolderLogoQueue([
    { url: '/english.svg', width: 800, height: 240, language: 'en' },
    { url: '/chinese.svg', width: 900, height: 260, language: 'zh' },
  ])

  assert.equal(findAvailableFolderLogo(queue, new Set())?.url, '/chinese.svg')
  assert.equal(findAvailableFolderLogo(queue, new Set(['/chinese.svg']))?.url, '/english.svg')
  assert.equal(findAvailableFolderLogo(queue, new Set(['/chinese.svg', '/english.svg'])), undefined)
})

test('folder text title uses the enlarged backdrop scale', () => {
  assert.match(folderTitleSource, /max-w-4xl break-words text-4xl[^']*sm:text-6xl/)
})

test('folder text title uses the enlarged panel scale', () => {
  assert.match(folderTitleSource, /break-words text-3xl[^']*sm:text-4xl/)
})

test('folder logo title uses larger frames in both header layouts', () => {
  assert.match(folderTitleSource, /flex h-24 w-\[82vw\][^']*sm:h-36/)
  assert.match(folderTitleSource, /flex h-20 w-\[78vw\][^']*sm:h-28/)
})
