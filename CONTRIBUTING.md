# Contributing

Thanks for helping build FLUX. The short version: spec changes are code
changes here — everything normative is validated by CI.

## Setup

```bash
pip install jsonschema pyyaml
python3 scripts/validate.py        # all example bundles must be green
python3 tests/test_regression.py   # regression suite must be green
```

## Making a change

- **Editorial** (typos, docs, descriptions that don't change validation):
  straight to PR.
- **Normative** (schema, seam, validator semantics): open an issue first,
  then one PR containing all of:
  1. the schema edit (`schema/flux-schema-<next>.json` — released files are immutable),
  2. the `schema-diffs/` entry,
  3. updated examples if the change touches them,
  4. regression tests — a validation behavior change without a test is not mergeable.
- **Examples**: new bundles go under `examples/<name>/` and must pass
  `scripts/validate.py` including the FLUID seam if they declare one.

## Style

- Schemas: JSON Schema 2020-12, camelCase fields, closed objects
  (`additionalProperties: false`), shared shapes in `$defs`, every field with a
  `description` that says what *enforces* any constraint the schema can't
  (e.g. "validator-enforced").
- Checks JSON Schema cannot express belong in `scripts/validate.py`, with a
  matching case in `tests/test_regression.py`.

## Licensing

By contributing you agree your contributions are licensed under the
[Apache License 2.0](LICENSE). Sign-off (`git commit -s`, DCO) is appreciated
but not yet required.
