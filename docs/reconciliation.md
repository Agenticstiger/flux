# Paper ↔ Schema Reconciliation (v0.3.0)

The position paper *"FLUX and FLUID: A Declarative Substrate for Core-to-Customer
Reinvention"* (Working Paper, July 2026, CC BY 4.0) describes FLUX v0.2.0. The
schema published here is **v0.3.0**, which closes the gaps a pre-release review
found between the paper's claims and what the 0.2.0 schema actually validated.
This page is the honest ledger: what the paper promises, what 0.3.0 delivers,
and what remains roadmap.

## Corrections to the paper

| Paper says | Reality in this repo |
|---|---|
| "Eighteen kinds, five families" (§3.1, glossary) | **Nineteen kinds, six families.** The paper's tables omit `Playback`, which the schema has always defined. We count it as its own *Calibration* family (§5.6 of the paper describes its role). |
| "its eighteen JSON schemas" (Availability) | One mono-schema per version with per-kind branches (`schema/flux-schema-<version>.json`), matching FLUID's publishing convention. Per-kind views may be generated later; the mono-schema is normative. |
| `Simulation.emits[].contract` embeds a FLUID document requiring a `promise` field (Listing 2 shape) | **`promise` never existed in FLUID.** 0.3.0 replaces the embedded stub with a reference seam: `{productRef, exposeId, fluidVersion}`. The referenced `.fluid.yml` is validated against the vendored FLUID schema for the pinned version — the seam *is* FLUID validation, and "the thing that ships is the thing that was proven" is byte-for-byte true. |
| Listing 1's extra population fields | Now first-class and typed: `population.markets` (renamed from the draft's vertical-specific field name; the kind is vertical-neutral) and `spec.temperature` (map of 0–1 dials). In 0.2.0 they passed only because unknown keys passed silently. |

## The three properties: delivered vs. roadmap

### Declarative — delivered
Nineteen kinds, closed specs (`additionalProperties: false` throughout), FLUID-aligned
envelope (`id`/`name` at top level, `metadata.owner` required), camelCase field names
matching FLUID's conventions.

### Deterministic — delivered in schema, enforced by toolchain
- `World.seed` (required) and `Simulation.seed` override.
- `Simulation.fidelity: deterministic | stochastic | agentic` — the three
  fidelities of paper §9.3.
- `Simulation.sweep` (stochastic seed sweeps), `Simulation.golden.baselineDigest`
  (the golden-regression anchor), `Experiment.assignment.method: largest_remainder`.
- The byte-for-byte replay guarantee itself is a property of the reference
  engine, not expressible in JSON Schema; the schema now provides the anchors
  the verify gate needs.

### Governed — delivered in schema, cross-checks in the validator
- `agentPolicy` (root-level, all kinds): model allow-list, token budget,
  use-case limits — vocabulary aligned with FLUID `exposes[].policy.agentPolicy`.
- `skills` (root-level, all kinds): the uniform agentic extension point of
  paper §3.5. Declaring `skills` requires `agentPolicy` (schema-enforced).
- `sovereignty` on `World` and `Simulation` (`allowedZones`, `enforcement: block|audit`).
- `ConsentProfile` can no longer be empty, and its vocabulary
  (`allowedUseCases`/`deniedUseCases`) matches FLUID's, so seam-crossing policy
  comparison is field-to-field. The "contract must be at least as strict as the
  gating ConsentProfile" rule is enforced by the reference validator at the
  seam: an emitted expose's `policy.agentPolicy` may not allow a use case a
  gating profile denies, nor exceed its allow-list (`scripts/validate.py`,
  regression-tested).

## The four seams (paper §3.4)

| Seam | Port | 0.3.0 surface |
|---|---|---|
| Contract | `fluid-contract` | `Simulation.emits[]` reference seam + vendored FLUID schemas + validator conformance check. **Fully delivered.** |
| Event | `event-envelope` | `Signal.envelope: cloudevents/1.0`, `source`, `type` (reverse-DNS), `dataschema` (URI) — the CloudEvents context attributes. Record-level envelope conformance is a runtime property. |
| Semantics | `ossie-model` | `Experiment.metrics[].ossieRef`. The Ossie model itself is out of scope for FLUX documents. |
| Binding | `binding-port` | `Module.binds[].port` enum over the four ports. |

## "Every arrow is a validated reference"

Now true, in two layers: the schema constrains every `*Ref` to the shared
identifier grammar (`^[a-z0-9][a-z0-9._-]*$`), and `scripts/validate.py`
resolves every reference offline against the bundle — kind-typed, no dangling
links — plus the checks JSON Schema cannot express (weight sums, lifecycle-mix
sums, state/node membership, seam conformance, agentPolicy bounds). CI runs
both on every commit, with no cloud and no running engine.

## Remaining roadmap (not yet in any schema)

- Journey ↔ JourneyTaxonomy deeper coupling (per-transition probabilities).
- `Playback` fit *methods* beyond declaration (the fitting itself is engine work).
- Ecosystem-scale kinds from paper §8–9 (federated registries, certification
  gates) — Horizon 2 scope, deliberately out of a v0.x single-firm spec.
