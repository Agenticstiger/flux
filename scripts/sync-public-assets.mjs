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
// The engine's spec JSON files get the same treatment (end of this file).
// =====================================================================

import { cpSync, rmSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve, sep } from 'node:path'
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

// The engine's schemas and their examples (docs/engine/spec/*.json, copied from
// the engine by scripts/sync-engine-docs.sh) are served beside their spec pages,
// so the pages' links to them resolve. A schema whose $id is an address under
// /flux/engine/spec/ on this site is served there too, byte for byte, so the
// $id of a document's $schema can be fetched. The copies are rebuilt on every
// build, and git ignores them.
const SITE = 'https://agenticstiger.github.io/flux/'
const engineSpec = resolve(root, 'docs/engine/spec')
const engineDest = resolve(publicDir, 'engine')
rmSync(engineDest, { recursive: true, force: true })
const place = (bytes, dest) => {
  mkdirSync(dirname(dest), { recursive: true })
  writeFileSync(dest, bytes)
}
// An $id is served only when its path under the site is plain segments of
// letters, digits, '.', '_' and '-' ending in .json, and only where no other
// file is served already, so one schema cannot stand in for another.
const SPEC_ID_PATH = /^engine\/spec\/[A-Za-z0-9_-][A-Za-z0-9._-]*(\/[A-Za-z0-9_-][A-Za-z0-9._-]*)*\.json$/
if (existsSync(engineSpec)) {
  // Regular files only: a symbolic link is not followed onto the site.
  const files = readdirSync(engineSpec, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.json'))
    .map((entry) => entry.name)
    .sort()
  const bytesOf = new Map(files.map((name) => [name, readFileSync(resolve(engineSpec, name))]))
  const served = new Set(files.map((name) => `engine/spec/${name}`))
  for (const name of files) place(bytesOf.get(name), resolve(engineDest, 'spec', name))
  for (const name of files) {
    let id
    try {
      const doc = JSON.parse(bytesOf.get(name).toString('utf8'))
      id = doc !== null && typeof doc === 'object' ? doc.$id : undefined
    } catch {
      console.warn(`[sync-assets] docs/engine/spec/${name} is not JSON; served under its own name only`)
      continue
    }
    if (typeof id !== 'string' || !id.startsWith(`${SITE}engine/spec/`)) continue
    const rel = id.slice(SITE.length)
    const dest = resolve(publicDir, rel)
    if (!SPEC_ID_PATH.test(rel) || !dest.startsWith(resolve(engineDest, 'spec') + sep)) {
      console.warn(`[sync-assets] docs/engine/spec/${name}: $id ${id} is not a plain path under /flux/engine/spec/; not served there`)
      continue
    }
    if (rel === `engine/spec/${name}`) {
      console.log(`[sync-assets] docs/engine/spec/${name} -> ${id}`) // its own name already
      continue
    }
    if (served.has(rel)) {
      console.warn(`[sync-assets] docs/engine/spec/${name}: $id ${id} is served by another file already; not served there`)
      continue
    }
    try {
      place(bytesOf.get(name), dest)
    } catch (error) {
      // A path under another served file's name, for one, cannot be made.
      console.warn(`[sync-assets] docs/engine/spec/${name}: $id ${id} cannot be served (${error.code || error.message}); not served there`)
      continue
    }
    served.add(rel)
    console.log(`[sync-assets] docs/engine/spec/${name} -> ${id}`)
  }
}
