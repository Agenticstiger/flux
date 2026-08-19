<h1 align="center">FLUX</h1>

<p align="center"><strong>Flow Language for Universe eXperimentation</strong></p>
<p align="center">The open, declarative standard for governed synthetic customer universes — the discovery-side sibling of <a href="https://github.com/open-data-protocol/fluid">FLUID</a>.</p>

<p align="center">
  <a href="https://agenticstiger.github.io/flux/">📖 Documentation</a> ·
  <a href="https://agenticstiger.github.io/flux/guide/quickstart.html">🚀 Quickstart</a> ·
  <a href="https://agenticstiger.github.io/flux/schema/kinds.html">🧭 The Nineteen Kinds</a> ·
  <a href="https://agenticstiger.github.io/flux/concepts/seam.html">🔗 The FLUID Seam</a> ·
  <a href="https://agenticstiger.github.io/flux/roadmap/">🗺️ Roadmap</a> ·
  <a href="https://agenticstiger.github.io/flux/releases/0.5.0.html">✨ What's New</a>
</p>

---

FLUX describes **synthetic customer universes**: a governed digital twin in
which candidate rules and data products are discovered, stress-tested and
proven *before* a single production system is touched. A FLUX universe is
assembled from small declarative documents — nineteen kinds across six
families — and a `Simulation` emits its results under a
[FLUID](https://github.com/open-data-protocol/fluid) data-product contract:
**what is proven in the twin is byte-for-byte the contract that ships.**

```
FLUX discovers.  FLUID delivers.  The seam is where the risk goes to die.
```

## Status

**v0.5.0 — working draft.** All nine [vNext RFCs](docs/roadmap/rfcs.md) are
shipped additively on the 0.3.0 core — the spec now carries a runtime
enforcement contract with conformance vectors and portable, signable evidence
bundles alongside the declarative core. Pre-1.0: minor versions may break; every release
ships with a [schema diff](schema-diffs/) and a regression suite. The design
is documented in the position paper *"FLUX and FLUID"* (distributed separately
under CC BY 4.0); where the paper and this schema disagreed,
[docs/reconciliation.md](docs/reconciliation.md) is the honest ledger.

## The nineteen kinds

| Family | Kinds | Question it answers |
|---|---|---|
| Population | World, Persona, Segment | *Who* is in the universe |
| Commerce | Catalog, Offer, Channel, ConsentProfile | *What* can be sold, *how* it can be reached |
| Behaviour | Journey, JourneyTaxonomy, Signal, Detector | *What happens* and *what to watch for* |
| Activation | Campaign, Treatment, Experiment | *What we do* about it |
| Calibration | Playback | *How the twin stays honest* |
| Composition | Simulation, Module, Blueprint, VerticalPack | *How it assembles* and *travels* |

Every document shares one envelope, aligned with FLUID's:

```yaml
fluxVersion: "0.5.0"
kind: World
id: q3-retention-world
name: Q3 Retention World
metadata:
  owner:
    team: growth-lab
spec:
  seed: 42
  population:
    size: 25000
    lifecycleMix: { new: 0.15, active: 0.55, atrisk: 0.20, churned: 0.10 }
```

Any kind may additionally declare `agentPolicy` (model allow-list, token
budget, use-case limits) and `skills` — the uniform agentic extension point.
A skill never changes the shape a kind must satisfy, only the content it emits
within those bounds.

## The FLUID seam

A `Simulation` emits streams by **referencing** the FLUID contract they are
proven under — never by restating it:

```yaml
spec:
  worldRef: q3-retention-world
  emits:
    - productRef: telco.gold.payment_recovery_moment   # a .fluid.yml in the bundle
      exposeId: payment_recovery_moment                # an expose of that product
      fluidVersion: "0.7.5"                            # validated against the vendored FLUID schema
```

The offline validator resolves the reference, validates the `.fluid.yml`
against the vendored FLUID schema for the pinned version, and asserts the
expose exists. Promotion to production is not a re-implementation: the same
contract file is wrapped around the real estate.

## Validate a bundle

```bash
pip install jsonschema pyyaml rfc8785
python3 scripts/validate.py examples/telco-payment-recovery   # schema + cross-document
python3 scripts/enforce.py                                    # RFC-04 conformance vectors
python3 scripts/bundle.py pack examples/telco-payment-recovery -o dist/   # RFC-09 evidence bundle
```

Two layers, both offline (no cloud, no running engine):

1. **Schema** — every `*.flux.yml` against [`schema/flux-schema-0.5.0.json`](schema/flux-schema-0.5.0.json)
   (JSON Schema 2020-12, closed specs, typed everything).
2. **Cross-document** — every reference resolves to the right kind (no
   dangling links), mixes and weights sum to 1, transitions stay inside their
   taxonomies, skills stay inside their `agentPolicy`, and the FLUID seam conforms.

Use the schema in your editor:

```yaml
# yaml-language-server: $schema=https://agenticstiger.github.io/flux/schema/flux-schema-0.5.0.json
```

## Example

[`examples/telco-payment-recovery/`](examples/telco-payment-recovery/) is the
paper's worked example, complete: all nineteen kinds plus the FLUID contract
at the seam, green under CI.

## Repository layout

```
schema/          flux-schema-<version>.json (+ -latest alias) — normative
schema-diffs/    one diff document per version pair
examples/        validated bundles (CI-enforced)
vendor/fluid/    vendored FLUID schemas the seam validates against
scripts/         validate.py (references) · enforce.py (RFC-04 gate) · bundle.py (RFC-09)
tests/           regression suite + published enforcement conformance vectors
docs/            reconciliation ledger
```

## Relationship to FLUID

[FLUID](https://github.com/open-data-protocol/fluid) is the data-product
contract standard (MIT, [open-data-protocol](https://github.com/open-data-protocol)).
FLUX is the experimentation language that emits FLUID contracts. They are
separate standards with separate schemas, designed to interlock at exactly one
seam. This repo vendors FLUID schemas for offline seam validation; it does not
fork or redefine them.

## License

[Apache License 2.0](LICENSE). The originating position paper is distributed
separately under CC BY 4.0 by The FLUX Project.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), [GOVERNANCE.md](GOVERNANCE.md) and
[VERSIONING.md](VERSIONING.md). Spec changes travel as one PR touching schema
+ diff + examples + tests together.
