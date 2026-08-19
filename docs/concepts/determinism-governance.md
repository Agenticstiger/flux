# Deterministic & Governed

FLUX is built on three non-negotiable properties. *Declarative* is covered in
[The Six Families](/flux/concepts/families); this page is about the other two.

## Deterministic

Given a `seed`, every output is reproducible byte-for-byte: the same dials
compile to the same world, the same world materialises to the same population,
the same seed replays the same stochastic run.

Schema surfaces:

- `World.spec.seed` (required) — the root of all randomness; `Simulation.spec.seed`
  overrides it per run.
- `Simulation.spec.fidelity` — the three escalating fidelities:
  - **`deterministic`** — every agent is a pure function of the seed. The mode
    certification and legal-grade lineage rely on: identical submission,
    identical verdict.
  - **`stochastic`** — `sweep: { runs, baseSeed }` turns the same population
    into a Monte-Carlo ensemble: full distributions, tail risk, confidence
    intervals — while every individual run stays replayable from its own seed.
  - **`agentic`** — selected synthetic actors are backed by language models
    under `agentPolicy`, producing the messy, adaptive behaviour no author
    scripts — still seeded, still contract-conformant.
- `Simulation.spec.golden.baselineDigest` — the golden-regression anchor: the
  verify gate fails the build on a single byte of drift.
- `Experiment.spec.assignment` — `method: largest_remainder` allocates integer
  cohorts with zero rounding loss, so an experiment's arms sum exactly.

## Governed

Governance is first-class schema surface, not a bolt-on:

### ConsentProfile

A `ConsentProfile` cannot be empty — it must assert at least one constraint —
and a `Campaign` cannot exist without a `consentRef`. Its vocabulary
(`allowedUseCases` / `deniedUseCases`) is FLUID's, so the
[seam check](/flux/concepts/seam#what-the-validator-enforces-at-the-seam) can
compare profile against contract field-to-field.

### sovereignty

`World` and `Simulation` may declare:

```yaml
sovereignty:
  allowedZones: [eu-west, eu-central]
  enforcement: block   # block: fail to execute outside zones; audit: record as lineage
```

### agentPolicy + skills — the agentic extension point

Every kind — all nineteen — may declare `skills`: small, sandboxed
capabilities (optionally backed by a language model) that generate bounded
variation. Declaring `skills` **requires** `agentPolicy` (schema-enforced):

```yaml
agentPolicy:
  allowedModels: [local-sovereign-8b]
  tokenBudget: 200000
  allowedUseCases: [persona_variation]
  purposeLimitation: true
skills:
  - name: journey-improviser
    skillRef: flux.skills.journey_improviser
    purpose: persona_variation
    model: local-sovereign-8b     # must be in allowedModels (validator-enforced)
    tokenBudget: 50000            # must not exceed the policy budget
```

A skill never changes the *shape* a kind must satisfy — its schema and
contract are fixed — only the *content* it emits within those bounds. The
payoff is combinatorial: N skills across k kinds multiply the reachable
behaviour space roughly as N^k, yet every point in it remains a seeded,
contract-conformant, gate-checked artefact.

## What stays toolchain-level

Byte-for-byte replay, golden regression execution, and lineage capture are
properties of a reference engine, not expressible in JSON Schema. The schema's
job — done as of 0.3.0, extended in 0.4.0 — is to give the verify gate the anchors it needs:
seeds, fidelity modes, sweeps, digests, and assignment methods are all
declared surface.
