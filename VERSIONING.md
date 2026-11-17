# Versioning Policy

## One version, one file

The specification (language) version and the schema file version advance in
lockstep: release `X.Y.Z` publishes `schema/flux-schema-X.Y.Z.json` with a
matching versioned `$id`, and `schema/flux-schema-latest.json` is a
byte-identical alias of the newest release (CI-enforced). Published schema
files are immutable: a released file is never edited, only superseded.

## Package re-releases

The `flux-spec` package on PyPI follows the specification version, with one extra
form. A packaging-only fix (corrected metadata, or a README that is out of date on
the PyPI page) is republished as a PEP 440 post-release, `X.Y.Z.postN`, tagged
`vX.Y.Z.postN`. It carries the same specification: `flux_spec.SCHEMA_VERSION` stays
`X.Y.Z`, `schema/flux-schema-X.Y.Z.json` is still the schema, no document pins
`fluxVersion: "X.Y.Z.postN"`, and there is no schema diff. The release workflow
checks that the tag, `pyproject.toml` and `flux_spec.__version__` carry the full
version, and that `SCHEMA_VERSION` and the schema file match the version without
the `.postN`. Anything that changes a schema, the validator's behaviour or the
enforcement contract is a specification release and takes a new `X.Y.Z`.

## Document pinning and compatibility windows

Every FLUX document pins `fluxVersion`. Each schema file's `fluxVersion` enum
lists the versions it accepts — its *compatibility window* (the convention
FLUID 0.7.5 uses: `["0.7.3", "0.7.4", "0.7.5"]`). A release that is fully
backward-compatible widens the window; a breaking release resets it.

## Pre-1.0 vs post-1.0

- **Pre-1.0 (now):** minor versions MAY break. Every release — breaking or not
  — ships a `schema-diffs/diff-A-to-B.md` and regression tests pinning changed
  behavior.
- **Post-1.0:** SemVer. Patch = editorial/constraint-relaxing fixes; minor =
  additive only (every valid document stays valid, window widens); major =
  breaking, with a migration section in the diff.

## What counts as breaking

Adding a required field, removing or renaming any field, tightening any
constraint (pattern, enum, minimum, `additionalProperties`), narrowing the
seam's `fluidVersion` enum, or changing validator semantics so a previously
green bundle fails.

## The FLUID seam window

`Simulation.emits[].fluidVersion` enumerates exactly the FLUID schema versions
vendored under `vendor/fluid/` and `vendor/fluid-preview/`. Adding a FLUID
version to the window is additive; dropping one is breaking. The vendored files are upstream FLUID
releases, verbatim — never patched locally.

### FLUID previews

A FLUID version that FLUID has not released yet can be vendored as a preview,
in `vendor/fluid-preview/`, when the engine needs it before the release. A
preview is copied verbatim from the repository where FLUID's schema is written
(forge-cli), at one full commit, and `vendor/fluid-preview/pins.json` records
the repository, the path, that commit and the sha256 of the bytes. CI
re-creates every preview from its pin with `scripts/sync-fluid-preview.py` and
fails on any byte difference.

- Only an exact pin selects a preview. A semver range resolves against the
  vendored releases only, so `^0.7.3` never reaches a preview. This is the rule
  node-semver applies to prereleases, and the one FLUID's own tooling applies
  to a preview schema: it counts only where a contract declares it.
- A pin moves only through a flux-spec PR that re-pins it
  (`scripts/sync-fluid-preview.py --repin VERSION COMMIT`), and the move ships
  in a specification release with a schema-diff note. A preview can change
  between two such releases.
- When FLUID releases the version, the next specification release vendors the
  release in `vendor/fluid/` and removes the preview and its entry in
  `pins.json` (the file stays, with an empty list once no preview is left). An
  exact pin keeps working, ranges start to reach the version, and the schema
  diff names anything the release changed from the preview.
