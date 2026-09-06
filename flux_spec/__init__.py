"""flux_spec — the FLUX reference validator, RFC-04 enforcement gate, and
RFC-09 evidence bundler, as an installable package.

    from flux_spec.validate import Bundle
    from flux_spec.enforce import decide, run_vectors
    from flux_spec.bundle import pack, verify

`scripts/validate.py`, `scripts/enforce.py` and `scripts/bundle.py` at the
repo root remain the documented CLI entry points — they are thin shims onto
this package, so command-line behaviour is unchanged.
"""

__version__ = "0.5.0"

# The FLUX schema version this package's vendored/packaged data matches
# (schema/flux-schema-<SCHEMA_VERSION>.json, i.e. the current "latest").
SCHEMA_VERSION = "0.5.0"

__all__ = ["__version__", "SCHEMA_VERSION"]
