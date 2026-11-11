#!/usr/bin/env bash
# Mirror the FLUX Simulation Engine's documentation into docs/engine/.
#
# The engine repository, Agenticstiger/flux-engine, is the only place those pages
# are written (its error and command pages are generated from the code). This
# copy exists so they are part of this site, served under /flux/engine/. Same
# pattern as scripts/sync-package-data.py: a generated mirror that CI re-creates
# and compares, so a copy that drifts from its source fails the build.
#
# The copy is pinned. scripts/engine-docs.ref names an engine tag (vX.Y.Z) or a
# full commit; a branch name is refused, because a moving pin is no pin. To take
# newer pages, change the pin, run this script, and commit docs/engine/ with it.
#
# Left out on purpose, because it is not user documentation: adr/, spec/,
# RELEASING.md, and accuracy/latest.json (the report's data; only Markdown is
# copied).
#
# Usage:  scripts/sync-engine-docs.sh [REF]
#   REF          a tag or full commit that overrides the pin, to try newer pages
#   ENGINE_REPO  where to fetch from (default: the public GitHub repository); a
#                path to a local clone works for a commit that is not published
set -euo pipefail

repo="${ENGINE_REPO:-https://github.com/Agenticstiger/flux-engine.git}"
# A local path is made absolute first: the script moves to the repository root below,
# and the fetch runs inside a scratch repository.
if [ -d "$repo" ]; then repo="$(cd "$repo" && pwd)"; fi

cd "$(dirname "$0")/.."

if [ "$#" -gt 1 ]; then
  echo "usage: scripts/sync-engine-docs.sh [REF]" >&2
  exit 2
fi
ref="${1:-}"
if [ -z "$ref" ]; then
  ref="$(grep -v -E '^[[:space:]]*(#|$)' scripts/engine-docs.ref | head -n 1 | tr -d '[:space:]' || true)"
fi
if ! [[ "$ref" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ || "$ref" =~ ^[0-9a-f]{40}$ ]]; then
  echo "REFUSED: the pin must be a vX.Y.Z tag or a full 40-character commit, not '$ref'" >&2
  exit 2
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
git init -q "$work/engine"
git -C "$work/engine" fetch -q --depth 1 "$repo" "$ref"
git -C "$work/engine" checkout -q --detach FETCH_HEAD
commit="$(git -C "$work/engine" rev-parse HEAD)"

src="$work/engine/docs"
if [ ! -d "$src" ]; then
  echo "REFUSED: $ref of the engine has no docs/ directory" >&2
  exit 1
fi

rm -rf docs/engine
mkdir -p docs/engine
pages=0
while IFS= read -r -d '' file; do
  file="${file#./}"
  mkdir -p "docs/engine/$(dirname "$file")"
  cp "$src/$file" "docs/engine/$file"
  chmod 644 "docs/engine/$file"
  pages=$((pages + 1))
done < <(cd "$src" && find . -type f -name '*.md' \
  ! -path './adr/*' ! -path './spec/*' ! -path './RELEASING.md' -print0 | LC_ALL=C sort -z)

# Anything else the engine keeps under docs/ is not copied. Say so, so a new kind
# of file (an image, say) is noticed instead of silently missing from the site.
others="$(cd "$src" && find . -type f ! -name '*.md' ! -path './accuracy/latest.json' \
  ! -path './adr/*' ! -path './spec/*' | LC_ALL=C sort)"
if [ -n "$others" ]; then
  echo "[sync-engine-docs] not copied, not Markdown:" >&2
  echo "$others" | sed 's/^/  /' >&2
fi

# The sidebar for /engine/ is a list in docs/.vuepress/config.ts. A page the engine
# added is on the site but not in the sidebar until someone lists it. The error code
# pages are reached from their index on purpose, so they are not expected there.
unlisted=""
while IFS= read -r -d '' file; do
  file="${file#./}"
  case "$file" in
    reference/errors/FLX-*.md) continue ;;
    */README.md) wanted="/engine/${file%README.md}" ;;
    *) wanted="/engine/$file" ;;
  esac
  if ! grep -q -F "'$wanted'" docs/.vuepress/config.ts \
    && ! grep -q -F "'/engine/${file}'" docs/.vuepress/config.ts; then
    unlisted="$unlisted  $file"$'\n'
  fi
done < <(cd docs/engine && find . -type f -name '*.md' -print0 | LC_ALL=C sort -z)
if [ -n "$unlisted" ]; then
  echo "[sync-engine-docs] WARNING: not in the /engine/ sidebar of docs/.vuepress/config.ts:" >&2
  printf '%s' "$unlisted" >&2
fi

echo "[sync-engine-docs] docs/engine <- flux-engine $ref ($commit): $pages pages"
