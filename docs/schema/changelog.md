# Changelog

One human-written diff per released version pair. The regression suite pins every behavioral change.

## 0.4.1 → 0.5.0

**Additive, non-breaking.** Every valid 0.3.0–0.4.1 document validates
unchanged under 0.5.0 (regression-asserted). Ships the final two RFCs of the
[vNext roadmap](/flux/roadmap/) — **all nine are now shipped**.

Both additions are *contracts about running and proving*, not new document
fields, so the core schema changes only its version window. The new normative
surface lives in two sibling schemas plus two reference tools.

## RFC-04 — The enforcement decision contract

New published schema `schema/flux-enforcement-0.5.0.json`: the request and
decision shapes every conformant policy gate implements.

```
decide(agentPolicy, {model, useCase, purpose?, tokens})
  -> {allow, reasonCode, reason, policyDigest, request}
```

Normative check order — first failure wins: `MODEL_NOT_ALLOWED`,
`USE_CASE_DENIED`, `USE_CASE_NOT_ALLOWED`, `PURPOSE_REQUIRED`,
`TOKEN_BUDGET_EXCEEDED`. Malformed input yields `INVALID_REQUEST`. A policy
declaring no models permits nothing (fail closed). Skill bindings narrow the
effective token budget and can never widen it.

`policyDigest` (canonical-JSON sha256 of the policy) makes every decision
auditable: the log proves *which* policy allowed a call.

- Reference gate: `scripts/enforce.py`
- Conformance vectors: `tests/enforcement-vectors.json` (34 cases pinning
  `allow`, `reasonCode` and `policyDigest`). CI runs them on every commit, and
  a meta-test asserts six deliberately-broken gates **fail** the suite.

Normative details that make the contract portable rather than merely
implementable:

- Integers follow JSON semantics (`200000.0` is `200000`, `true` is never `1`),
  bounded to 2^53-1 so they survive a JSON boundary.
- `model`/`useCase` are NFC-normalised and stripped before comparison;
  matching is case-sensitive.
- An off-spec policy is `INVALID_POLICY` — a missing `tokenBudget` is never
  "no budget".
- `policyDigest` is sha256 over the **RFC 8785 (JCS)** canonicalisation of the
  *document's* policy; skill narrowing is reported separately as
  `effectiveBudget`/`skillRef`, so a decision joins back to its document.

## RFC-09 — Signed evidence bundles

New published schema `schema/flux-manifest-0.5.0.json` and the reference
tool `scripts/bundle.py`:

```bash
python3 scripts/bundle.py pack   <bundle-dir> -o dist/
python3 scripts/bundle.py verify dist/<name>.flux.tgz
```

- **Deterministic archives** — sorted entries, zeroed mtimes in both the tar
  entries and the gzip header, fixed ownership: identical inputs produce
  byte-identical output.
- **Manifest** — per-file sha256 and a Merkle root built the **RFC 6962**
  way (leaves prefixed `0x00`, interior nodes `0x01`), with the path bound
  into each leaf so swapping two files' contents changes the root.
- **in-toto Statement** — `<bundle>.attestation.json`, so cosign and other
  supply-chain tooling can carry and sign FLUX evidence natively.
- **Attestation** — validator status and document count, Playback scorecards,
  and each seam crossing with its contract digest. `verify` recomputes it from
  scratch, so a manifest cannot claim what the bundle does not contain.
- **Profiles** — an offline bundler attests `core` or `enterprise` only;
  `runtime` requires a live engine and is deliberately unclaimable here.
- **Signing** — detached over the manifest bytes (ssh-keygen -Y, cosign,
  openssl). Because the manifest commits to the Merkle root, one signature
  covers the whole bundle. No key distribution is specified, by design.
- Packing **refuses** to run on a bundle that does not validate.

## Envelope / window

- `fluxVersion` enum widens to `["0.3.0", "0.4.0", "0.4.1", "0.5.0"]`.
- `$id` → `flux-schema-0.5.0.json`; `flux-schema-latest.json` aliases 0.5.0;
  UI hints regenerate as `flux-ui-hints-0.5.0.json`.
- Regression suite: 97 → **132 checks**.
- `verify` re-derives `schemaId` and `fluxVersions` as well as the attestation,
  budgets declared sizes before extracting, refuses symlinks/devices/duplicates
  and any member outside the bundle directory, and reports every malformed
  input as `[FAIL]` rather than a traceback.
- RFC-03 lockfile and RFC-06 contract digests also move to RFC 8785 (JCS);
  the example bundle's digests are regenerated accordingly.

## 0.4.0 → 0.4.1

**Additive, non-breaking.** Every valid 0.3.0 and 0.4.0 document validates
unchanged under 0.4.1 (regression-asserted). Ships RFC-05 and RFC-06 of the
[vNext roadmap](/flux/roadmap/).

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

## 0.3.0 → 0.4.0

**Additive, non-breaking.** Every valid 0.3.0 document validates unchanged
under 0.4.0 (regression-asserted). Ships the first five RFCs of the
[vNext roadmap](/flux/roadmap/): RFC-01, RFC-02, RFC-03, RFC-07,
RFC-08.

## RFC-01 — Trait distributions

`Persona.spec.traits` values become a typed union (`$defs/trait`): a plain
0..1 scalar (0.3.0-compatible), a `categorical` distribution (weighted
levels; validator enforces sum→1), or a bounded `normal` (μ/σ/min/max;
validator enforces min < max). Sampling is deterministic under the World seed.

```yaml
traits:
  digitalFluency: 0.7
  priceSensitivity: { dist: categorical, levels: { low: 0.2, medium: 0.5, high: 0.3 } }
  monthlySpend: { dist: normal, mean: 42.0, stddev: 11.0, min: 0 }
```

## RFC-02 — The versioned extension port

New optional envelope field on every kind:

```yaml
extensions:
  com.acme.flux/1:                 # namespace: <reverse-dns>/<major>
    semanticRef: semantic/customer-360
    audit: { required: true, retentionDays: 365 }
  x-acme:                          # or an x- vendor key
    anything: goes-here
```

Keys must match `<reverse-dns>/<major>` or `x-*`; values must be objects,
their **contents owned by the namespace** (shallow-typed only). The core
stays closed everywhere else — this is the one sanctioned escape hatch, so
dialects extend without forking. Rejected (regression-pinned):
non-namespaced keys, non-object values, empty `extensions`.

## RFC-03 — Module supply chain

- New optional envelope field `version` (`x.y.z`) — the lockfile anchor.
- `Simulation.spec.moduleRefs` and `VerticalPack.spec.modules` items become
  `$defs/versionedRef`: `name` (unchanged), `name@2.1.3`, `name@^2.1`,
  `name@~2.1.0`.
- Any versioned ref requires a **`flux.lock`** in the bundle:

```yaml
lockVersion: 1
modules:
  module-payment-recovery:
    version: 2.1.3
    digest: sha256:<canonical-json sha256 of the module document>
```

The validator enforces: lock entry exists, pinned version satisfies the
range, the document's `version` matches the pin, and the content digest
matches the in-bundle document — content drift breaks the build.

## RFC-07 — The semantic-model port

`Experiment.spec.metrics[].semanticRef` (`<model>/<measure>`,
`$defs/semanticRef`) resolves against the measures a Module declares when
binding the `ossie-model` port (`binds[].config.measures`). The validator
rejects unknown measures and `semanticRef` use with no bound model.
`ossieRef` remains as a deprecated 0.3.0 alias.

## RFC-08 — UI hints artifact

New published artifact `schema/flux-ui-hints-0.4.0.json`, generated by
`scripts/generate-ui-hints.py` (CI-enforced in sync): per-kind titles,
families, summaries, example pointers, and per-field widget hints (slider
for 0..1, select for enums, reference pickers, trait-distribution editors).
Not normative — validation authority stays with the JSON Schema.

## Envelope / window

- `fluxVersion` enum widens to `["0.3.0", "0.4.0"]`; a 0.4.0 document still
  fails the immutable 0.3.0 schema file.
- `$id` → `flux-schema-0.4.0.json`; `flux-schema-latest.json` aliases 0.4.0.
- Regression suite: 61 → **85 checks**.

## 0.2.0 → 0.3.0

**Breaking release.** 0.3.0 is the first open-sourced version; 0.2.0 was a
pre-release draft that never shipped publicly. Every change below traces to a
finding of the pre-open-sourcing review (documents that wrongly passed, the
broken FLUID seam, or paper claims with no schema surface). The regression
suite (`tests/test_regression.py`) pins each one.

## Dialect & envelope

| | 0.2.0 | 0.3.0 |
|---|---|---|
| Dialect | draft-07, no `$id`, no reuse | **2020-12**, versioned `$id`, shared `$defs` (matches FLUID 0.7.5) |
| Identity | `metadata.id`, `metadata.name` | **Top-level `id`, `name`** (+ optional `description`, `tags`, `labels`) — FLUID envelope alignment |
| `metadata` | free-form | `owner.team` **required** (mirrors FLUID); `createdAt`, `annotations` |
| Unknown keys | silently accepted everywhere | **`additionalProperties: false`** at every level |
| Casing | snake_case | **camelCase** (matches FLUID and the seam fields) |
| `fluxVersion` | `const "0.2.0"` | `enum ["0.3.0"]` (compatibility-window convention, per FLUID) |
| Kind dispatch | `if` without `required` → 27-error spray when `kind` absent | `required: ["kind"]` in every `if`; kind-absent yields exactly one error |

## The FLUID seam (breaking, the point of the release)

0.2.0 embedded a contract stub requiring `["fluidVersion", "kind", "promise"]`.
**`promise` has never existed in any FLUID schema** — every genuine FLUID
document failed the seam and garbage passed it. 0.3.0 replaces embedding with
referencing:

```yaml
emits:
  - productRef: telco.gold.payment_recovery_moment   # id of a .fluid.yml in the bundle
    exposeId: payment_recovery_moment                # must be an expose of that product
    fluidVersion: "0.7.5"                            # enum of vendored FLUID schemas
```

The validator resolves `productRef`, validates the document against
`vendor/fluid/fluid-schema-<fluidVersion>.json`, and asserts `exposeId`
membership. The proven contract and the shipped contract are the same file.

## New surfaces (paper promises now delivered)

- Root-level **`agentPolicy`** and **`skills`** on every kind; `skills` ⇒ `agentPolicy` required.
- **`sovereignty`** (`allowedZones`, `enforcement: block|audit`) on World and Simulation.
- **Simulation composition**: `personaRefs`, `segmentRefs`, `signalRefs`, `campaignRefs`, `experimentRefs`, `moduleRefs`; plus `fidelity` (deterministic/stochastic/agentic), `seed`, `sweep`, `golden.baselineDigest`.
- **Signal** carries CloudEvents context attributes (`envelope`, `source`, `type`, `dataschema`); 0.2.0 `payload_schema` → `dataschema`.
- **Module.binds** over the four ports; **Experiment** gains `assignment` (largest_remainder) and `metrics[].ossieRef`.
- **Playback** gains `worldRef` (required), `calibration`, `drift` (psi/kl/ks + threshold).
- **World** gains `population.markets` (renamed from the draft's vertical-specific field) and typed `temperature`.

## Renames

- `Persona.spec.skills` → **`traits`** (ends the collision with agentic skills); `agentic_prompt` → `agenticPrompt`.
- `ConsentProfile`: `permitted_purposes`/`blocked_purposes` → **`allowedUseCases`/`deniedUseCases`** (FLUID agentPolicy vocabulary); `allowed_jurisdictions` → `allowedJurisdictions`; `requires_explicit_opt_in` → `requiresExplicitOptIn`.
- `Simulation.spec.world` → `worldRef`; `time_bounds` → `timeBounds`; all `*_ref` → `*Ref`; `lifecycle_mix` → `lifecycleMix`.

## Tightening (previously silent false-passes)

- Refs: shared `$defs/ref` pattern `^[a-z0-9][a-z0-9._-]*$` — empty and
  whitespace refs rejected; `Detector.pattern` items are now `{signalRef, predicate}` objects.
- Required floors: `minItems: 1` on `emits`, `items`, `resources`, `modules`,
  `variants`, `pattern`, `states`, `transitions`, `nodes`; `minProperties: 1` on
  `lifecycleMix`, ConsentProfile and Persona specs; `uniqueItems` on states/nodes/refs lists.
- Numbers: `timeWindowMs ≥ 1`, `rateLimitPerSecond ≥ 1`, `pricing.amount ≥ 0`,
  `currency` = ISO-4217 pattern, probabilities via `$defs/unitInterval`.
- `Experiment.variants[]`: `name`, `weight`, `treatmentRef` all required; `isControl` added.
- `Journey`: `trigger` required (with `signalRef`); `intervention.treatmentRef` required;
  reactions gain `outcome`/`nextState`.
- Timestamps: RFC 3339 **pattern** enforcement (draft-07 `format` was annotation-only).
- `Channel.type`: closed enum gains an `x-` extension escape hatch.
- Edges/transitions: `from`/`to` required.

## Moved to the offline validator (inexpressible in JSON Schema)

Reference resolution & kind-typing, `lifecycleMix`/variant-weight sums,
variant-name uniqueness, transitions ⊆ states, edges ⊆ nodes,
`nextState` ∈ taxonomy, `timeBounds.start < end`, skill model/budget within
`agentPolicy`, and full FLUID seam conformance. See `scripts/validate.py`.
