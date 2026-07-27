// =====================================================================
// sync-public-assets.mjs
// =====================================================================
// Mirrors the canonical schema/ directory into docs/.vuepress/public/
// so the published site serves it under the site base — e.g.
// https://agenticstiger.github.io/flux/schema/flux-schema-0.3.0.json —
// keeping every schema `$id` URL resolvable byte-for-byte.
//
// The canonical copies stay at the repo root. These public/ mirrors are
// git-ignored and rebuilt on every `npm run docs:dev` / `docs:build`.
// =====================================================================

import { cpSync, rmSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const publicDir = resolve(root, 'docs/.vuepress/public')

for (const dir of ['schema', 'schema-diffs']) {
  const src = resolve(root, dir)
  const dest = resolve(publicDir, dir)
  if (!existsSync(src)) {
    console.warn(`[sync-assets] source missing: ${src} — skipping`)
    continue
  }
  rmSync(dest, { recursive: true, force: true })
  mkdirSync(dirname(dest), { recursive: true })
  cpSync(src, dest, { recursive: true })
  console.log(`[sync-assets] ${dir}/ -> docs/.vuepress/public/${dir}/`)
}
