# Versioning Policy

## One version, one file

The specification (language) version and the schema file version advance in
lockstep: release `X.Y.Z` publishes `schema/flux-schema-X.Y.Z.json` with a
matching versioned `$id`, and `schema/flux-schema-latest.json` is a
byte-identical alias of the newest release (CI-enforced). Published schema
files are immutable: a released file is never edited, only superseded.

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
vendored under `vendor/fluid/`. Adding a FLUID version to the window is
additive; dropping one is breaking. The vendored files are upstream FLUID
releases, verbatim — never patched locally.
