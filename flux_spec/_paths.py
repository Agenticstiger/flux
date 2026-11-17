"""Resource path resolution for flux_spec.

Two ways to run this package, one set of bytes:

* **Source checkout** — `flux_spec/` sits at the repo root next to `schema/`,
  `vendor/fluid/` and `tests/`. Those are canonical: a contributor edits them
  directly, and CI validates them in place.
* **Installed distribution** (`pip install flux-spec` or `pip install .`) —
  there is no `schema/` next to the installed package, only the committed
  copies under `flux_spec/data/` (kept in sync with the canonical files by
  `scripts/sync-package-data.py`, gated in CI by a `git diff --exit-code`).
  Those are read back via `importlib.resources` rather than a hardcoded
  site-packages path.

FLUID previews sit beside the releases, in `vendor/fluid-preview/`, and are
mirrored the same way.

Detection is a single filesystem check: does `schema/` exist next to this
package's parent directory?
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
REPO = _PACKAGE_DIR.parent
_SOURCE_CHECKOUT = (REPO / "schema").is_dir()


def _packaged(*parts: str) -> Path:
    return Path(importlib.resources.files("flux_spec").joinpath("data", *parts))


def _resource(*parts: str) -> Path:
    """A canonical directory of the checkout, or its packaged copy when installed."""
    return REPO.joinpath(*parts) if _SOURCE_CHECKOUT else _packaged(*parts)


def schema_dir() -> Path:
    return _resource("schema")


def vendor_fluid_dir() -> Path:
    return _resource("vendor", "fluid")


def vendor_fluid_preview_dir() -> Path:
    """FLUID previews, each pinned to a commit and a sha256 (vendor/fluid-preview/pins.json)."""
    return _resource("vendor", "fluid-preview")


def enforcement_vectors_path() -> Path:
    return (
        (REPO / "tests" / "enforcement-vectors.json")
        if _SOURCE_CHECKOUT
        else _packaged("vectors", "enforcement-vectors.json")
    )
