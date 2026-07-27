# Contributing & Governance

FLUX is an Apache-2.0 open specification stewarded under the Agenticstiger
organization, with a declared intent to move to a vendor-neutral home as
external contribution grows — see
[GOVERNANCE.md](https://github.com/Agenticstiger/flux/blob/main/GOVERNANCE.md).

## The short version

- **Spec changes are code changes.** One PR carries the schema edit, the
  schema-diff entry, example updates, and regression tests. CI enforces all of
  it — a normative change without tests is not mergeable.
- **Released schema files are immutable.** Changes go into the next
  `flux-schema-<version>.json`; `-latest` is a CI-checked alias.
- **Versioning**: pre-1.0 minors may break (always with a diff + tests);
  post-1.0 SemVer with additive-only minors. Policy:
  [VERSIONING.md](https://github.com/Agenticstiger/flux/blob/main/VERSIONING.md).
- **The seam is jointly owned**: changes to `Simulation.emits` or the vendored
  FLUID versions are checked against the current FLUID release.

## Start here

```bash
git clone https://github.com/Agenticstiger/flux.git
cd flux
pip install jsonschema pyyaml
python3 scripts/validate.py && python3 tests/test_regression.py
```

Then read
[CONTRIBUTING.md](https://github.com/Agenticstiger/flux/blob/main/CONTRIBUTING.md)
and open an issue for anything normative. Conduct:
[Contributor Covenant 2.1](https://github.com/Agenticstiger/flux/blob/main/CODE_OF_CONDUCT.md).
