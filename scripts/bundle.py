#!/usr/bin/env python3
"""Compatibility shim onto flux_spec.bundle — see flux_spec/bundle.py.

This module's identity IS flux_spec.bundle (via the sys.modules swap
below), not a copy of its names: tests/test_regression.py does
`sys.path.insert(0, "scripts"); import bundle as bundle_tool` and pokes
module globals directly (e.g. `bundle_tool.MAX_BUNDLE_BYTES = ...` to test
the archive-bomb cap) — a plain `from flux_spec.bundle import *` would copy
that name into a separate module namespace and the mutation would never
reach the function that reads it.
"""
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flux_spec import bundle as _impl

sys.modules[__name__] = _impl

if __name__ == "__main__":
    raise SystemExit(_impl.main())
