# The vNext Roadmap

FLUX 0.3.x is a rigorous core. The most advanced private implementations of
this idea are already **ahead of it** in places — richer population models,
versioned module reuse, runtime policy enforcement, graded calibration. The
roadmap's bet:

> **Make the open standard a strict superset.** An advanced implementation
> should migrate because it loses nothing it values and gains everything the
> standard offers — migration as an upgrade, never a compromise. Where an
> implementation breaks the spec today, it is usually *ahead of spec*: the
> right move is to pull those ideas upstream, not sand them off.

The full proposal is nine RFCs — see **[The Nine RFCs](/flux/roadmap/rfcs)** —
landing across staged releases, governed by five principles.

## Design principles

| # | Principle | Meaning |
|---|---|---|
| P1 | **Additive, not breaking** | Every 0.3.0 document stays valid in every 0.3.x/0.4.x release. New power is opt-in. |
| P2 | **Closed core, open edges** | `additionalProperties: false` stays; the [extension port](/flux/roadmap/rfcs#rfc-02-a-versioned-extension-port) is the one sanctioned escape hatch. |
| P3 | **Profiles, not one size** | [Core / Enterprise / Runtime conformance](/flux/roadmap/profiles) — a validator, a governed org, and a live engine each get an honest bar. |
| P4 | **Executable, not just checkable** | The spec grows a runtime enforcement contract, not only a schema. A standard you can run beats one you can only lint. |
| P5 | **Provenance everywhere** | Documents and seam crossings carry verifiable provenance, so "what was proven" is auditable end-to-end. |

## Staged releases

| Release | Scope | Status |
|---|---|---|
| **0.4.0** | RFC-01 trait distributions · RFC-02 extension port · RFC-03 module supply chain (`flux.lock`) · RFC-07 semantic-model port · RFC-08 UI hints — all additive, zero breakage | ✅ **shipped** |
| **0.4.1** | RFC-05 credibility scorecard · RFC-06 seam version ranges + provenance — additive | ✅ **shipped** |
| 0.5.0 | RFC-04 runtime enforcement contract · RFC-09 signed bundles — Level-3 Runtime becomes certifiable | 📋 proposed |

Each release is independently adoptable, and each RFC lands the repo's way:
**one PR touching schema + schema-diffs + examples + tests together.**

## The migration ledger

The decision rule for any advanced implementation: migrate when this table
has zero losses. Under the full roadmap:

| What an advanced implementation relies on | Under 0.3.0 | Under the roadmap |
|---|---|---|
| Trait distributions per identity | lost — flattened to scalars | **kept** — RFC-01 typed distributions *(shipped)* |
| Dialect vocabulary, audit/retention fields | illegal — forces a fork | **kept** — RFC-02 extension port *(shipped)* |
| Versioned modules & cross-bundle reuse | lost — flat in-bundle ids | **upgraded** — RFC-03 semver refs + lockfile *(shipped)* |
| Runtime policy enforcement | dropped — validator only | **upgraded** — RFC-04 enforcement contract |
| Closed-loop calibration verdicts | partial — drift only | **upgraded** — RFC-05 scorecard *(shipped)* |
| Contracts on older FLUID versions | stranded — frozen enum | **upgraded** — RFC-06 negotiated ranges *(shipped)* |
| Semantic metric binding | opaque string | **kept** — RFC-07 semantic-model port *(shipped)* |
| Form-based authoring tools | non-standard | **kept** — RFC-08 UI hints *(shipped)* |
| Evidence packs | local pass/fail only | **upgraded** — RFC-09 signed bundles |

Zero losses, four keeps, five upgrades — at which point a private dialect is
just maintenance debt, and the standard's top tier is the cheaper place to
live.
