# FLUX Schema Diff: 0.5.1 → 0.5.2

**Additive, non-breaking.** Every valid 0.3.0 to 0.5.1 document validates
unchanged under 0.5.2 (regression-asserted). One change: the FLUID seam window
gains FLUID 0.7.7, a preview, which only an exact pin selects.

## The FLUID seam

- FLUID 0.7.7 is not released yet. It carries the expose relationships
  (`exposes[].semantics.relationships[]`: `to`, `fromColumns`, `toColumns`,
  `cardinality`, `joinType`, with composite keys as one relationship) and the
  validity windows (`validityParams`) that the engine reads keys and history
  from. It is vendored as a preview, verbatim, in
  `vendor/fluid-preview/fluid-schema-0.7.7.json`, from
  `Agenticstiger/forge-cli` `fluid_build/schemas/fluid-schema-0.7.7.json` at
  commit `32fce8e3ae0a5bcb104af048a6fc67938c198f31`, sha256
  `4c72dea22a5f3c31dc1882723b07cc16de0bb52e0199db0f5daba8fdc480b4da`. The
  pin is `vendor/fluid-preview/pins.json`; CI re-creates the file from it
  (`scripts/sync-fluid-preview.py`) and fails on any byte difference. The
  0.7.7 file FLUID publishes today is an earlier preview without the
  relationships, so the release copies in `vendor/fluid/` and their weekly
  comparison with FLUID's published schemas are unchanged.
- A `.fluid.yml` that declares `fluidVersion: "0.7.7"` is validated against
  the preview, and its errors read `fails FLUID 0.7.7 (preview)`.
- `Simulation.emits[].fluidVersion` accepts the exact pin `"0.7.7"`:

```json
"enum": ["0.7.3", "0.7.4", "0.7.5", "0.7.6", "0.7.7"]
```

- A range never selects a preview. A range resolves against the vendored
  releases only, so `^0.7.3` still reaches 0.7.6 and no further, and an emit
  whose range would reach a 0.7.7 contract is refused with a message that
  says to pin `"0.7.7"` exactly (validator-enforced). This is node-semver's
  rule for prereleases.

## Envelope / window

- `fluxVersion` enum widens to
  `["0.3.0", "0.4.0", "0.4.1", "0.5.0", "0.5.1", "0.5.2"]`.
- `$id` → `flux-schema-0.5.2.json`; `flux-schema-latest.json` aliases 0.5.2;
  UI hints regenerate as `flux-ui-hints-0.5.2.json`.
- `flux-enforcement-0.5.0.json` and `flux-manifest-0.5.0.json` are unchanged:
  0.5.2 changes no enforcement or bundle contract.

## Compatibility

`flux-schema-0.5.1.json` is immutable and still refuses an exact `"0.7.7"`
pin (regression-asserted), so a document that uses it pins
`fluxVersion: "0.5.2"`. Nothing that validated before is refused now: before
0.5.2, no vendored schema existed for a 0.7.7 contract.

The preview can change. Its pin moves only in a flux-spec release with a note
in that release's schema diff (VERSIONING.md, FLUID previews). When FLUID
releases 0.7.7, the release replaces the preview in `vendor/fluid/`, an exact
pin keeps working, and ranges start to reach it.
