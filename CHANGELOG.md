# Changelog

## 0.4.1 — 2026-08-20

Additive; ships RFC-05 and RFC-06
([schema-diffs/diff-0.4.0-to-0.4.1.md](schema-diffs/diff-0.4.0-to-0.4.1.md)):

- **RFC-05 — credibility scorecard**: `Playback.spec.scorecard` (grade A–F,
  interval coverage, required `credibility`) plus the seam gate
  `emits[].minCredibility` — an untrustworthy twin cannot ship a contract.
- **RFC-06 — seam ranges + provenance**: `fluidVersion` accepts semver ranges
  resolved against the vendored set; `emits[].provenance.contractDigest`
  binds the proven contract bytes to the shipped ones (validator-enforced),
  `outputDigest` reserved for engine attestation.
- `fluxVersion` window `["0.3.0", "0.4.0", "0.4.1"]`; regression suite grows
  to 97 checks.

## 0.4.0 — 2026-08-19

Additive; ships the first five vNext RFCs
([schema-diffs/diff-0.3.0-to-0.4.0.md](schema-diffs/diff-0.3.0-to-0.4.0.md)):

- **RFC-01 — trait distributions**: Persona traits are scalars or typed
  categorical / bounded-normal distributions, validator sum- and bounds-checked.
- **RFC-02 — versioned extension port**: optional `extensions` envelope
  object keyed by `<reverse-dns>/<major>` namespaces (or `x-*`); dialects
  extend legally while the core stays closed.
- **RFC-03 — module supply chain**: `ref@semver-range` on moduleRefs/modules,
  envelope `version`, and a `flux.lock` binding every versioned ref to an
  exact version + content digest (validator-enforced).
- **RFC-07 — semantic-model port**: `semanticRef` on Experiment metrics,
  resolved against measures declared by a Module binding `ossie-model`.
- **RFC-08 — UI hints**: generated `schema/flux-ui-hints-0.4.0.json` for
  form-based authoring tools.
- `fluxVersion` window `["0.3.0", "0.4.0"]` — every 0.3.0 document stays
  valid; regression suite grows to 85 checks.

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
