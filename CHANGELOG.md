# Changelog

## 0.3.0 — 2026-07-27

First open-source release (Apache 2.0). Breaking rework of the pre-release
0.2.0 draft; full details in
[schema-diffs/diff-0.2.0-to-0.3.0.md](schema-diffs/diff-0.2.0-to-0.3.0.md).

Highlights:

- **FLUID seam rebuilt**: `Simulation.emits[]` now references a `.fluid.yml`
  contract (`productRef` + `exposeId` + pinned `fluidVersion`) validated
  against vendored FLUID schemas, replacing an embedded stub whose required
  `promise` field never existed in FLUID.
- **Hard validation**: JSON Schema 2020-12, closed objects everywhere,
  `required: ["kind"]` dispatch, typed refs, floors and patterns throughout.
- **Envelope aligned with FLUID**: top-level `id`/`name`, required
  `metadata.owner`, camelCase.
- **Paper promises delivered in schema**: root-level `agentPolicy` + `skills`
  on every kind, `sovereignty`, Simulation composition refs, fidelity modes,
  golden-regression anchor, CloudEvents attributes on Signal, `Module.binds`
  ports, Playback calibration + drift.
- **Offline reference validator** (`scripts/validate.py`) and a 61-check
  regression suite pinning every closed gap.

## 0.2.0 — pre-release draft

Internal draft described by the July 2026 position paper. Never released.
Preserved at `schema/flux-schema-0.2.0.json` for the diff record.
