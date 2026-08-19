---
home: true
title: Home
heroText: FLUX
tagline: Declare the universe. Prove the rule. Ship the contract that was proven.
actions:
  - text: Get Started →
    link: /guide/
    type: primary
  - text: The FLUID Seam
    link: /concepts/seam
    type: secondary
  - text: The Nineteen Kinds
    link: /schema/kinds
    type: secondary
features:
  - title: Declarative
    details: A governed synthetic customer universe is nineteen small YAML documents, not a codebase. Adding a vertical or a rule is a configuration change, validated by one JSON Schema.
  - title: Deterministic
    details: Every run is a pure function of a seed — byte-for-byte replayable, golden-regression anchored, with stochastic sweeps and agentic fidelity layered on top, never instead.
  - title: Governed
    details: ConsentProfile, sovereignty, and agentPolicy are schema surfaces, not policy docs. Skills give every kind bounded, model-backed variation under an enforced budget.
  - title: The FLUID Seam
    details: A Simulation emits streams by referencing the FLUID contract they are proven under — never restating it. What ships to production is byte-for-byte what the twin proved.
  - title: Offline Validation
    details: Schema plus reference validator resolve every reference, check every sum and set, and validate the seam against vendored FLUID schemas — no cloud, no running engine.
  - title: Open & Apache-2.0
    details: Spec, schemas, validator, and examples in one repo, CI-enforced. Governance and versioning policies written down from day one.
footer: Apache-2.0 Licensed | © The FLUX Project — Flow Language for Universe eXperimentation
---

> **FLUX discovers. FLUID delivers. The seam is where the risk goes to die.**

FLUX describes **synthetic customer universes**: governed digital twins in which candidate rules and data products are discovered, stress-tested and proven *before* a single production system is touched — then shipped under the exact [FLUID](https://open-data-protocol.github.io/fluid/) contract the twin proved.

## The shape of a document

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
  vertical: telco
  population:
    size: 25000
    lifecycleMix: { new: 0.15, active: 0.55, atrisk: 0.20, churned: 0.10 }
    markets: [mkt-a, mkt-b, mkt-c]
  temperature: { engagement: 0.5, campaignResponse: 0.5 }
```

25,000 synthetic subscribers across three markets, one in five already at risk — declared, never coded.

## Where to go next

- **[Guide](/flux/guide/)** — what FLUX is and a hands-on quickstart.
- **[Concepts](/flux/concepts/)** — the two-spec substrate, the six families, the seam, and the three properties.
- **[Schema Reference](/flux/schema/)** — the envelope, all nineteen kinds, versions and changelog.
- **[Examples](/flux/examples/)** — the complete telco payment-recovery universe, all nineteen kinds green under CI.
- **[FLUID](https://open-data-protocol.github.io/fluid/)** — the delivery-side contract standard this spec emits into.
