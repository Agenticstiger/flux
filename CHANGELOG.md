# Changelog

## 0.5.2 - 2026-11-17

Specification 0.5.2, additive
([schema-diffs/diff-0.5.1-to-0.5.2.md](schema-diffs/diff-0.5.1-to-0.5.2.md)):

- **seam**: the FLUID 0.7.7 preview, which carries expose relationships
  (composite keys included) and validity windows, is vendored verbatim in
  `vendor/fluid-preview/fluid-schema-0.7.7.json`, pinned in
  `vendor/fluid-preview/pins.json` to forge-cli commit `32fce8e3` and the
  sha256 of its bytes. `Simulation.emits[].fluidVersion` accepts the exact pin
  `"0.7.7"`; a range never selects a preview, and the validator refuses one
  that would, with the fix in the message.
- **schema**: `schema/flux-schema-0.5.2.json`, with the `fluxVersion` window
  `["0.3.0", "0.4.0", "0.4.1", "0.5.0", "0.5.1", "0.5.2"]`;
  `flux-schema-latest.json` aliases it and `flux_spec.SCHEMA_VERSION` is
  `0.5.2`. The package version is `0.5.2`.
- **tooling**: `scripts/sync-fluid-preview.py` re-creates every preview from
  its pin and checks the sha256 (`--repin VERSION COMMIT` moves a pin), and a
  CI job fails when the committed copy differs from what the pin names. The
  wheel ships the previews under `flux_spec/data/vendor/fluid-preview/`.
- **docs**: VERSIONING.md says how a FLUID preview is vendored, selected,
  re-pinned and replaced by its release.
- **tests**: the regression suite checks the pin (bytes, commit, path, one pin
  per file), the exact 0.7.7 pin, a 0.7.7 contract with a composite-key
  relationship, a broken one, the range refusal, a 0.7.6 contract that uses
  relationships, a moved key changing the contract digest, and that the
  immutable 0.5.1 file still refuses the pin.

- **examples**: the towers contract declares `tenancy_count`,
  `chronic_sla_breaches` and `months_to_lease_expiry` as `INTEGER` instead of
  `DECIMAL(10,0)` and `DECIMAL(6,0)`, and `simulation.flux.yml` re-pins its
  `provenance.contractDigest`. The decimal types were a workaround for an
  engine that refused a drawn count in an `INTEGER` column;
  [flux-engine#19](https://github.com/Agenticstiger/flux-engine/pull/19)
  removes that limit.

- **bundle**: `verify` re-validates a pack against the schema its manifest's
  `schemaId` names, when that schema is inside the compatibility window, so a
  pack made by flux-spec 0.5.0 or 0.5.1 verifies under this release without a
  re-pack (a re-pack would break a detached signature over the manifest).
  Until now `verify` refused every `schemaId` but the current one, so each
  release broke the packs made by the one before, every `fluxsim ship`
  archive included. An id outside the window is refused with the versions the
  toolchain accepts, and the `[ok]` report names the schema it re-validated
  against. VERSIONING.md states the rule. The regression suite packs the
  example the way 0.5.0 and 0.5.1 did and verifies it, checks that the named
  schema is the one applied, and refuses the 0.2.0 draft, a newer release and
  a reset window; each archive attack now checks the reason it was refused.
  The wheel smoke test checks that the installed package ships every schema
  in the window.
- **bundle**: `pack` refuses a bundle that holds a symlink, before it reads
  anything, the way `verify` refuses a link inside an archive and flux-engine
  refuses one before it packs. `pack` used to read through a linked file, so
  the target's bytes (an ssh key, a `.env`) went into the archive, and it left
  a linked directory out without a word. It also opens `flux-manifest.json`
  with `O_NOFOLLOW` where the platform has it, so a link that appears after
  that check fails the pack instead of overwriting the file it points to, and
  a manifest it cannot write is a `[FAIL]` line, not a traceback. A manifest
  it creates is owner-only (0600); the archive entry keeps its fixed mode.
- **tests**: `verify`'s refusals of an archive member with `..`, an absolute
  path, a symlink, a hard link, a FIFO or a file beside the bundle directory,
  and of an archive above the member cap, are each pinned by their message.
  Until now none of them was exercised.

## 0.5.1 - 2026-11-12

Specification 0.5.1, additive
([schema-diffs/diff-0.5.0-to-0.5.1.md](schema-diffs/diff-0.5.0-to-0.5.1.md)):

- **seam**: FLUID 0.7.6 is vendored (`vendor/fluid/fluid-schema-0.7.6.json`,
  verbatim from FLUID), and `Simulation.emits[].fluidVersion` accepts the
  exact pin `"0.7.6"`.
- **schema**: `schema/flux-schema-0.5.1.json`, with the `fluxVersion` window
  `["0.3.0", "0.4.0", "0.4.1", "0.5.0", "0.5.1"]`; `flux-schema-latest.json`
  aliases it, and `flux_spec.SCHEMA_VERSION` and the package version are
  `0.5.1`.
- **examples**: `examples/towers-tenant-renewal/`, tenant renewal risk at a
  tower company, emitting for a FLUID 0.7.6 contract.
- **tests**: the regression suite checks the exact 0.7.6 pin, the towers
  bundle, a broken 0.7.6 contract, and that the immutable 0.5.0 file still
  refuses the pin.

## 0.5.0.post1 - 2026-11-11

Packaging only. The specification and the schema are unchanged:
`flux_spec.SCHEMA_VERSION` stays `0.5.0` and `schema/flux-schema-0.5.0.json` is
still the current schema. A `.postN` release republishes the same specification
with corrected package metadata (see [VERSIONING.md](VERSIONING.md)).

- **packaging**: the package page on PyPI now says `pip install flux-spec` and the
  `python3 -m flux_spec.validate|enforce|bundle` modules, where 0.5.0 still said
  "not yet on PyPI". `flux_spec` is the importable package behind
  `scripts/validate.py`, `scripts/enforce.py` and `scripts/bundle.py` (thin shims,
  no behaviour change); 0.5.0 was its first upload, on 2026-11-11.
- **release**: the release workflow accepts a `vX.Y.Z.postN` tag. It checks the full
  version against `pyproject.toml` and `flux_spec.__version__`, and the version
  without `.postN` against `SCHEMA_VERSION` and the schema file. A plain `vX.Y.Z`
  tag is checked as before, and `tests/test_release_guard.py` runs the guard
  against both.
- **docs**: an Engine section (`/engine/`) with the documentation of the FLUX
  Simulation Engine, copied from its repository
  (`Agenticstiger/flux-engine`). The README, the guide and the roadmap pages now
  point at the published packages and the current version.

## 0.5.0 — 2026-08-20

Additive; ships RFC-04 and RFC-09 — **all nine vNext RFCs are now shipped**
([schema-diffs/diff-0.4.1-to-0.5.0.md](schema-diffs/diff-0.4.1-to-0.5.0.md)):

- **RFC-04 — enforcement decision contract**: `schema/flux-enforcement-0.5.0.json`,
  the reference gate `scripts/enforce.py`, and 34 published conformance
  vectors pinning allow/reasonCode/policyDigest. Normative check order,
  fail-closed defaults (off-spec policies are rejected, not reinterpreted),
  JSON-semantic integers, NFC-normalised identifiers, skills that narrow but
  never widen, and RFC 8785 (JCS) canonical digests. A meta-test asserts six
  deliberately-broken gates fail the suite.
- **RFC-09 — signed evidence bundles**: `schema/flux-manifest-0.5.0.json` and
  `scripts/bundle.py`. Deterministic archives, per-file digests, a Merkle
  root, and an attestation `verify` recomputes from scratch. Detached
  signing over the manifest; offline bundlers never claim the runtime profile.
- `fluxVersion` window `["0.3.0", "0.4.0", "0.4.1", "0.5.0"]`; regression
  suite grows to 132 checks; CI runs the vectors and a bundle round-trip.
- Prior art adopted rather than reinvented: RFC 6962 Merkle domain separation,
  RFC 8785 canonical JSON, reproducible-builds.org archive recipe, in-toto
  Statements, and Cedar's authorization model. New dependency: `rfc8785`.

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
