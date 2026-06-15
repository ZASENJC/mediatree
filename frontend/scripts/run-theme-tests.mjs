import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { build } from 'esbuild'

const outdir = await mkdtemp(join(tmpdir(), 'mediatree-theme-tests-'))
const outfile = join(outdir, 'theme.test.mjs')

try {
  await build({
    absWorkingDir: process.cwd(),
    bundle: true,
    entryPoints: ['src/theme.test.ts'],
    format: 'esm',
    outfile,
    platform: 'node',
    sourcemap: 'inline',
  })

  await import(pathToFileURL(outfile).href)
  console.log('theme tests passed')
} finally {
  await rm(outdir, { recursive: true, force: true })
}
