# The Nine RFCs

Each RFC closes a specific gap between the 0.3.x core and what the most
advanced implementations already do. Status: ✅ shipped · ◐ partial · 📋 proposed.

## RFC-01 — Trait distributions as first-class sampling ✅ shipped in 0.4.0

*Population · Persona*

**Gap:** `traits` are flat 0..1 scalars — a whole population gets one number.
A real twin samples a *distribution* per identity.

**Shipped:** a typed `trait` union — `scalar` (unchanged, 0.3.x-compatible),
`categorical` (weighted levels, validator-checked sum→1), `numeric` (bounded
normal μ/σ/min/max). Deterministic under seed.

```yaml
traits:
  digitalFluency: 0.7            # scalar — unchanged
  priceSensitivity:              # categorical distribution
    dist: categorical
    levels: { low: 0.2, medium: 0.5, high: 0.3 }
  monthlySpend:                  # bounded normal
    dist: normal
    mean: 42.0
    stddev: 11.0
    min: 0
```

## RFC-02 — A versioned extension port ✅ shipped in 0.4.0

*Envelope · all kinds*

**Gap:** the closed schema rejected any dialect-specific field (semantic
refs, audit, retention), forcing private forks.

**Shipped:** a reserved `extensions` envelope object keyed by namespace
(`<reverse-dns>/<major>`, e.g. `com.acme.flux/1`, or `x-*`), values
shallow-typed objects owned by the namespace. The core stays closed
everywhere else. See the [0.4.0 diff](/flux/schema/changelog).

```yaml
extensions:
  com.acme.flux/1:
    semanticRef: semantic/customer-360
    audit: { required: true, retentionDays: 365 }
```

## RFC-03 — Module supply chain: versioned refs + lockfile ✅ shipped in 0.4.0

*Composition · Module*

**Gap:** refs resolve as flat in-bundle ids — fine for one example, useless
for reuse across teams and verticals.

**Shipped:** optional `ref@range` semver syntax plus a `flux.lock` resolving
every versioned ref to an exact version and content digest, both
validator-enforced against the in-bundle document. (A `flux vendor` CLI for
cross-bundle fetching remains future work.)

```yaml
moduleRefs:
  - churn-detector@^2.1          # semver range
  - retention-treatment@3.0.4    # exact pin
# flux.lock records: churn-detector@2.1.3 sha256:9f2c…
```

## RFC-04 — A Runtime profile + reference enforcer 📋

*Governance · runtime · target 0.5.0*

**Gap:** `agentPolicy` is declared and validator-checked, but nothing
enforces it at call time — a conforming document can still make an
off-policy call.

**Proposal:** a normative **enforcement decision contract** — input (model,
useCase, purpose, tokens) → allow/deny + reason + audit record — plus a
reference gate and a conformance test-vector suite. Policy you can prove was
enforced, not just written.

## RFC-05 — Playback → a credibility scorecard ✅ shipped in 0.4.1

*Calibration · Playback*

**Gap:** `Playback` reports drift (PSI/KL/KS) but stops short of a verdict on
the honest question: *should I trust this twin's uplift?*

**Shipped:** a `scorecard` block — backtest window, calibration grade A–F,
prediction-interval coverage, and a required `credibility` 0..1. The seam
gates on it: `emits[].minCredibility` fails the bundle when the twin's own
score is below the bar (validator-enforced).

```yaml
scorecard:
  backtestWindow: P90D
  grade: B                   # A–F, from coverage + drift
  intervalCoverage: 0.92     # predicted vs observed
  credibility: 0.78          # seam may require ≥ threshold
```

## RFC-06 — Seam version negotiation + provenance ✅ shipped in 0.4.1

*Composition · Simulation*

**Gap:** the seam pins `fluidVersion` to a frozen enum of vendored versions.
A static enum ages badly and strands contracts on older FLUID releases.

**Shipped:** `fluidVersion` accepts a semver **range** (`^0.7.3`, `~0.7.4`)
resolved against the vendored compatibility set — the referenced document
must satisfy it, and at least one vendored schema must too. Each emit may
carry `provenance`: `contractDigest` is validator-enforced against the
in-bundle contract (proven bytes are shipped bytes); `outputDigest` is the
engine-attested run digest, verified at the Runtime profile (RFC-04):

```yaml
emits:
  - productRef: telco.gold.payment_recovery_moment
    exposeId: payment_recovery_moment
    fluidVersion: "^0.7.3"           # range, not frozen point
    minCredibility: 0.7              # RFC-05 gate on the twin's scorecard
    provenance:
      contractDigest: "sha256:762f…" # validator-enforced: contract drift fails
      outputDigest: "sha256:be91…"   # engine-attested at emit time
```

## RFC-07 — A semantic-model port ✅ shipped in 0.4.0

*Behaviour · Experiment*

**Gap:** `ossieRef` is an opaque string on Experiment metrics — unresolved,
unchecked. "Revenue" can mean three things in one bundle.

**Shipped:** `semanticRef` (`<model>/<measure>`) on Experiment metrics,
resolved by the validator against the measures a Module declares when
binding the `ossie-model` port — "revenue" means one governed thing per
bundle. `ossieRef` remains as a deprecated 0.3.0 alias.

## RFC-08 — Schema-driven authoring contract ◐ partial in 0.4.0

*Tooling · DX*

**Gap:** hand-edited YAML with validate-time feedback only will never reach
the product managers who actually design offers.

**Shipped (0.4.0):** the
[UI-hints artifact](https://agenticstiger.github.io/flux/schema/flux-ui-hints-0.4.0.json)
— per-kind titles, families, summaries, examples, and per-field widget hints
generated from the schema, enough for any tool to render a form.
**Remaining:** an LSP specification so Studio-class editors are portable
across dialects.

## RFC-09 — Signed bundles & evidence packs 📋

*Governance · release · target 0.5.0*

**Gap:** validation is a local pass/fail; nothing travels as proof.

**Proposal:** `flux bundle --sign` → deterministic archive + Merkle manifest
+ attestation (schema version, conformance profile, scorecard grade, seam
provenance). A regulator or partner verifies without the author's tooling.
