# FLUX Schema Diff: 0.2.0 → 0.3.0

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
