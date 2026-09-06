#!/usr/bin/env python3
"""Sync canonical spec artifacts into flux_spec/data/ for the flux-spec package.

The canonical, hand-edited copies of the schema, the vendored FLUID schemas
and the enforcement conformance vectors stay where contributors already
expect them: schema/, vendor/fluid/, tests/enforcement-vectors.json. This
script mirrors them into flux_spec/data/, where they ship inside the
flux-spec wheel/sdist and are read back at runtime via importlib.resources
(see flux_spec/_paths.py) whenever flux_spec is installed rather than run
from a source checkout.

Same pattern as scripts/sync-public-assets.mjs (schema/ -> docs/.vuepress/
public/schema/): a generated mirror, diffed in CI with `git diff
--exit-code` so a schema/vendor/vector change that forgets to re-run this
script fails the build instead of shipping a stale package. Stdlib only.

Run: python3 scripts/sync-package-data.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = REPO / "flux_spec" / "data"

# (source directory, dest directory under flux_spec/data/, glob pattern)
DIR_MIRRORS = [
    (REPO / "schema", DATA_DIR / "schema", "*.json"),
    (REPO / "vendor" / "fluid", DATA_DIR / "vendor" / "fluid", "*.json"),
]

# (source file, dest directory under flux_spec/data/)
FILE_MIRRORS = [
    (REPO / "tests" / "enforcement-vectors.json", DATA_DIR / "vectors"),
]


def _resync_dir(dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)


def main() -> int:
    for src, dest, pattern in DIR_MIRRORS:
        _resync_dir(dest)
        count = 0
        for path in sorted(src.glob(pattern)):
            shutil.copy2(path, dest / path.name)
            count += 1
        print(f"[sync-package-data] {src.relative_to(REPO)}/{pattern} -> {dest.relative_to(REPO)}/ ({count} files)")

    for src, dest in FILE_MIRRORS:
        _resync_dir(dest)
        shutil.copy2(src, dest / src.name)
        print(f"[sync-package-data] {src.relative_to(REPO)} -> {dest.relative_to(REPO)}/ (1 file)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
