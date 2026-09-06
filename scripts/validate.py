#!/usr/bin/env python3
"""Compatibility shim onto flux_spec.validate — see flux_spec/validate.py.

This module's identity IS flux_spec.validate (via the sys.modules swap
below), not a copy of its names: tests/test_regression.py does
`sys.path.insert(0, "scripts"); from validate import Bundle`, and this keeps
that import — and any future one — pointed at the real module object.
"""
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flux_spec import validate as _impl

sys.modules[__name__] = _impl

if __name__ == "__main__":
    raise SystemExit(_impl.main(sys.argv[1:]))
