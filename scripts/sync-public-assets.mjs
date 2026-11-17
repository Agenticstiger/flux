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
if (existsSync(engineSpec)) {
  for (const name of readdirSync(engineSpec).filter((n) => n.endsWith('.json')).sort()) {
    const bytes = readFileSync(resolve(engineSpec, name))
    place(bytes, resolve(engineDest, 'spec', name))
    let id
    try {
      id = JSON.parse(bytes.toString('utf8')).$id
    } catch {
      console.warn(`[sync-assets] docs/engine/spec/${name} is not JSON; served under its own name only`)
      continue
    }
    if (typeof id !== 'string' || !id.startsWith(`${SITE}engine/spec/`)) continue
    // An $id that climbs out of /flux/engine/spec/ is not served at all.
    const dest = resolve(publicDir, id.slice(SITE.length))
    if (!dest.startsWith(resolve(engineDest, 'spec') + sep)) {
      console.warn(`[sync-assets] docs/engine/spec/${name}: $id ${id} leaves /flux/engine/spec/; not served there`)
      continue
    }
    place(bytes, dest)
    console.log(`[sync-assets] docs/engine/spec/${name} -> ${id}`)
  }
}
