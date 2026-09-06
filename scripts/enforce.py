#!/usr/bin/env python3
"""Compatibility shim onto flux_spec.enforce — see flux_spec/enforce.py.

This module's identity IS flux_spec.enforce (via the sys.modules swap
below), not a copy of its names: tests/test_regression.py does
`sys.path.insert(0, "scripts"); import enforce` and calls e.g.
`enforce.decide(...)` / `enforce.policy_digest(...)` directly.
"""
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flux_spec import enforce as _impl

sys.modules[__name__] = _impl

if __name__ == "__main__":
    raise SystemExit(_impl.main())
