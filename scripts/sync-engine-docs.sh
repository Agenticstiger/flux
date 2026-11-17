#!/usr/bin/env bash
# Mirror the FLUX Simulation Engine's documentation into docs/engine/.
#
# The engine repository, Agenticstiger/flux-engine, is the only place those pages
# are written (its error and command pages are generated from the code). This
# copy exists so they are part of this site, served under /flux/engine/. Same
# pattern as scripts/sync-package-data.py: a generated mirror that CI re-creates
# and compares, so a copy that drifts from its source fails the build.
#
# The copy is pinned to an engine release. scripts/engine-docs.ref names a release
# tag (vX.Y.Z), so the site documents an engine people can install; a branch name
# or a bare commit is refused there. To take newer pages, change the pin to the
# new release tag, run this script, and commit docs/engine/ with it.
#
# Copied: every Markdown page, and the JSON files in spec/ (the engine's schemas
# and their examples). scripts/sync-public-assets.mjs serves those JSON files on
# the site, and each schema also at the address its $id names.
# Left out on purpose, because it is not user documentation: adr/, RELEASING.md,
# and accuracy/latest.json (the report's data).
#
# Usage:  scripts/sync-engine-docs.sh [REF]
#         scripts/sync-engine-docs.sh --check-pin
#   REF          a tag or full commit that overrides the pin, to try pages that are
#                not released yet. CI re-creates the copy from the pin, so a copy
#                made from REF is for a look, not for a commit.
#   --check-pin  check that the pin names a release tag of the engine repository,
#                and copy nothing
#   ENGINE_REPO  where to fetch from (default: the public GitHub repository); a
#                path to a local clone works for a commit that is not published
set -euo pipefail

repo="${ENGINE_REPO:-https://github.com/Agenticstiger/flux-engine.git}"
# A local path is made absolute first: the script moves to the repository root below,
# and the fetch runs inside a scratch repository.
if [ -d "$repo" ]; then repo="$(cd "$repo" && pwd)"; fi

cd "$(dirname "$0")/.."

release_tag='^v[0-9]+\.[0-9]+\.[0-9]+$'

read_pin() {
  grep -v -E '^[[:space:]]*(#|$)' scripts/engine-docs.ref | head -n 1 | tr -d '[:space:]' || true
}

require_release_pin() {
  if ! [[ "$1" =~ $release_tag ]]; then
    echo "REFUSED: scripts/engine-docs.ref must name an engine release tag (vX.Y.Z), not '$1'" >&2
    echo "  a commit or a branch documents an engine nobody can install; pass it as REF to try it" >&2
    exit 2
  fi
}

if [ "$#" -gt 1 ]; then
  echo "usage: scripts/sync-engine-docs.sh [REF | --check-pin]" >&2
  exit 2
fi

if [ "${1:-}" = "--check-pin" ]; then
  pin="$(read_pin)"
  require_release_pin "$pin"
  if ! git ls-remote --exit-code --tags "$repo" "refs/tags/$pin" > /dev/null; then
    echo "REFUSED: the engine repository has no tag $pin" >&2
    exit 1
  fi
  echo "[sync-engine-docs] the pin names the engine release tag $pin"
  exit 0
fi

ref="${1:-}"
if [ -z "$ref" ]; then
  ref="$(read_pin)"
  require_release_pin "$ref"
fi
if ! [[ "$ref" =~ $release_tag || "$ref" =~ ^[0-9a-f]{40}$ ]]; then
  echo "REFUSED: REF must be a vX.Y.Z tag or a full 40-character commit, not '$ref'" >&2
  exit 2
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
git init -q "$work/engine"
git -C "$work/engine" fetch -q --depth 1 "$repo" "$ref"
git -C "$work/engine" checkout -q --detach FETCH_HEAD
commit="$(git -C "$work/engine" rev-parse HEAD)"

src="$work/engine/docs"
if [ -L "$src" ]; then
  echo "REFUSED: docs/ in $ref of the engine is a symbolic link" >&2
  exit 1
fi
if [ ! -d "$src" ]; then
  echo "REFUSED: $ref of the engine has no docs/ directory" >&2
  exit 1
fi

rm -rf docs/engine
mkdir -p docs/engine
pages=0
files=0
while IFS= read -r -d '' file; do
  file="${file#./}"
  mkdir -p "docs/engine/$(dirname "$file")"
  cp "$src/$file" "docs/engine/$file"
  chmod 644 "docs/engine/$file"
  case "$file" in
    *.md) pages=$((pages + 1)) ;;
    *) files=$((files + 1)) ;;
  esac
done < <(cd "$src" && find . -type f \( -name '*.md' -o -path './spec/*.json' \) \
  ! -path './adr/*' ! -path './RELEASING.md' -print0 | LC_ALL=C sort -z)

# Anything else the engine keeps under docs/ is not copied. Say so, so a new kind
# of file (an image, say) is noticed instead of silently missing from the site.
others="$(cd "$src" && find . -type f ! -name '*.md' ! -path './spec/*.json' \
  ! -path './accuracy/latest.json' ! -path './adr/*' | LC_ALL=C sort)"
if [ -n "$others" ]; then
  echo "[sync-engine-docs] not copied, not Markdown:" >&2
  echo "$others" | sed 's/^/  /' >&2
fi

# A copied page that links into a part left out (adr/, RELEASING.md) would carry a
# dead link onto the site. Say so, so the pin change decides what to do about it.
dead="$(cd docs/engine && grep -r -n -o -E '\]\((\.{1,2}/)*(adr/|RELEASING\.md)[^)]*\)' \
  --include='*.md' . || true)"
if [ -n "$dead" ]; then
  echo "[sync-engine-docs] WARNING: links into adr/ or RELEASING.md, which are not copied:" >&2
  echo "$dead" | sed 's/^/  /' >&2
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

echo "[sync-engine-docs] docs/engine <- flux-engine $ref ($commit): $pages pages, $files spec files"
