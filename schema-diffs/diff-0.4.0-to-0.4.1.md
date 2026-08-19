# FLUX Schema Diff: 0.4.0 → 0.4.1

**Additive, non-breaking.** Every valid 0.3.0 and 0.4.0 document validates
unchanged under 0.4.1 (regression-asserted). Ships RFC-05 and RFC-06 of the
[vNext roadmap](../docs/roadmap/README.md).

## RFC-05 — The credibility scorecard

New optional `Playback.spec.scorecard`:

```yaml
scorecard:
  backtestWindow: P90D       # ISO-8601 duration
  grade: B                   # A–F, produced by the calibration engine
  intervalCoverage: 0.92     # observed outcomes inside predicted intervals
  credibility: 0.78          # required — the twin's overall trust score
```

And the seam gate: `Simulation.emits[].minCredibility` (0..1). The validator
fails the bundle when no Playback scorecard calibrates the Simulation's world
or when the twin's best credibility is below the bar. Twin claims become
graded, not asserted — and an untrustworthy twin cannot ship a contract.

## RFC-06 — Seam version ranges + provenance

- `emits[].fluidVersion` now also accepts a semver **range** (`^0.7.3`,
  `~0.7.4`), resolved against the vendored FLUID set. The referenced
  document's own `fluidVersion` must satisfy the pin or range, and at least
  one vendored schema must satisfy a range (validator-enforced). Exact pins
  behave exactly as in 0.4.0; the seam no longer freezes to a point release.
- New optional `emits[].provenance`:
  - `contractDigest` — canonical-JSON sha256 of the referenced FLUID
    document, **validator-enforced**: contract drift after proving fails the
    bundle (proven bytes are shipped bytes).
  - `outputDigest` — the engine-attested run digest; format-checked here,
    value-verified at the Runtime profile (RFC-04).

## Envelope / window

- `fluxVersion` enum widens to `["0.3.0", "0.4.0", "0.4.1"]`.
- `$id` → `flux-schema-0.4.1.json`; `flux-schema-latest.json` aliases 0.4.1;
  UI hints regenerate as `flux-ui-hints-0.4.1.json`.
- Regression suite: 85 → **97 checks**.
