# Contributing

Thanks for helping build FLUX. The short version: spec changes are code
changes here — everything normative is validated by CI.

## Setup

```bash
pip install jsonschema pyyaml rfc8785
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

## The engine pages are copies

Everything under `docs/engine/` is copied from the engine's own repository,
[Agenticstiger/flux-engine](https://github.com/Agenticstiger/flux-engine), at the
release tag named in `scripts/engine-docs.ref`. Do not edit those pages here.
Change them in the engine repository. Once an engine release carries the change,
set its tag (`vX.Y.Z`) in `scripts/engine-docs.ref`, run
`scripts/sync-engine-docs.sh` and commit `docs/engine/` with it. The pin is a
release tag only: CI refuses a commit or a branch, because the site documents an
engine people can install. A page the engine adds also needs an entry in the
`/engine/` sidebar of `docs/.vuepress/config.ts`; the script warns when one is
missing, and when a copied page links to `RELEASING.md`, which is not copied.
The engine's `spec/` pages come with their JSON schemas, and the site serves
each schema at the address its `$id` names. The decision records in `adr/` are
copied too, because the spec pages cite them. CI re-creates the copy from
the pin and fails if it differs.

## Licensing

By contributing you agree your contributions are licensed under the
[Apache License 2.0](LICENSE). Sign-off (`git commit -s`, DCO) is appreciated
but not yet required.
