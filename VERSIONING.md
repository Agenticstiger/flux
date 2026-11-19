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

## Evidence packs across releases

An evidence pack names, in its manifest's `schemaId`, the `$id` of
the schema its documents were validated against. `pack` always validates
against the current schema. `verify` accepts a `schemaId` that is the `$id` of
a version inside the current window (the `fluxVersion` enum of
`flux-schema-latest.json`) and re-validates the documents against that
version's schema file, which ships with the package. So a pack made by an
earlier release in the window still verifies after an upgrade. Re-packing is
never the remedy: it changes the manifest bytes and breaks a detached
signature over them. A `schemaId` outside the window, from before a breaking
reset or from a newer release, is refused with the versions the toolchain
accepts. Verify that pack with a flux-spec release whose window includes it.
Two more cases refuse a pack from inside the window: its FLUID contract
declares a preview whose pin has moved since (FLUID previews, below), and one
of its documents is outside an input bound that the current release sets
(Input bounds, below).

This leans on the rule above: a release that tightens a constraint is breaking
and resets the window. So no schema inside the window accepts a document that
the current schema refuses for the same `fluxVersion`, and a pack that names
an older schema in the window gains nothing a current pack would be refused.

## Pre-1.0 vs post-1.0

- **Pre-1.0 (now):** minor versions MAY break. Every release — breaking or not
  — ships a `schema-diffs/diff-A-to-B.md` and regression tests pinning changed
  behavior.
- **Post-1.0:** SemVer. Patch = editorial/constraint-relaxing fixes; minor =
  additive only (every valid document stays valid, window widens); major =
  breaking, with a migration section in the diff. A FLUID preview's pin move
  and a change to an input bound are outside these rules (FLUID previews and
  Input bounds, below).

## What counts as breaking

Adding a required field, removing or renaming any field, tightening any
constraint (pattern, enum, minimum, `additionalProperties`), narrowing the
seam's `fluidVersion` enum, or changing validator semantics so a previously
green bundle fails. A FLUID preview's pin move (FLUID previews, below) and a
change to an input bound (Input bounds, below) are the two exceptions.

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
- A pin move does not reset the window, even when the new pin refuses what the
  old one accepted. `validate` and `verify` check a contract that declares a
  preview against the preview the running release carries, whatever
  `fluxVersion` the bundle's documents pin, so the move can refuse a bundle,
  or a pack, that an earlier release accepted. The schema diff names what the
  new pin refuses, and a pack it refuses verifies with the release that made
  it.
- When FLUID releases the version, the next specification release vendors the
  release in `vendor/fluid/` and removes the preview and its entry in
  `pins.json` (the file stays, with an empty list once no preview is left). An
  exact pin keeps working, ranges start to reach the version, and the schema
  diff names anything the release changed from the preview.

## Input bounds

A release may refuse input that an earlier release accepted when the input is
outside the JSON data model, or when it is past a limit that RFC 8259 (sections
6 and 9) lets an implementation set. Three kinds of change fall under this
rule:

- **Outside the JSON data model.** A number that is not finite (NaN, an
  infinity), a string that holds a lone surrogate, a mapping key that is not a
  string, and a value JSON has no spelling for.
- **Implementation limits.** The range and the precision of a number (a float
  past what a double holds, a number that needs more than a set number of
  digits written out), and the size, the depth and what a YAML document writes
  out once its aliases and merge keys are written out.
- **Enforcement input.** `decide` may answer input that is off-spec with
  `INVALID_POLICY`, where an earlier release raised, or read the input as
  another one: a policy RFC 8785 cannot write, and a skill that is not an
  object or whose `tokenBudget` is not an integer.

Such a change does not reset the window, even when it refuses a bundle, a pack
or a call that an earlier release accepted. The schema diff of the release
names each of them with what the earlier release accepted, and a pack that a
bound refuses verifies with the release that made it.
