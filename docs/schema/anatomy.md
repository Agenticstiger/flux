# Anatomy

`flux-schema-<version>.json` is a JSON Schema **2020-12** document with a
versioned `$id`, closed objects throughout, and a shared `$defs` vocabulary —
the same dialect and conventions as FLUID 0.7.5.

## The envelope

Every document, regardless of kind:

```yaml
fluxVersion: "0.3.0"   # enum of the versions this schema file accepts
kind: World            # discriminator: one of nineteen
id: q3-retention-world # $defs/identifier — the target other documents reference
name: Q3 Retention World
description: …         # optional
tags: […]              # optional
labels: { k: v }       # optional string map
metadata:
  owner:
    team: growth-lab   # required — accountability is not optional
  createdAt: …         # optional RFC 3339
agentPolicy: …         # optional; required if skills are declared
skills: […]            # optional agentic extension point (any kind)
spec: …                # the kind-specific block
```

Top-level `additionalProperties: false` — unknown envelope keys are rejected,
as they are inside every kind's `spec`. A typo is an error, not a silent
no-op.

## Kind dispatch

The schema carries one `if/then` branch per kind, each guarded with
`required: ["kind"]`. Consequences you'll actually notice:

- a document with the wrong kind's fields fails loudly at the exact paths;
- a document *missing* `kind` produces exactly one error naming `kind` — not
  an error spray from every branch;
- a `spec` is validated by exactly one branch, and that branch owns it
  completely (`additionalProperties: false`).

## The shared grammar (`$defs`)

| Def | Meaning |
|---|---|
| `identifier` / `ref` | `^[A-Za-z0-9_][A-Za-z0-9_.-]*[A-Za-z0-9_]$` — **byte-identical to FLUID's** identifier, so any legal FLUID product id is a legal FLUX ref |
| `refList` | non-empty, unique list of refs |
| `unitInterval` | number in `[0, 1]` — probabilities, mixes, temperatures |
| `rfc3339` | timestamp with lexically-bounded fields, lowercase `t`/`z` permitted |
| `currencyCode` | ISO-4217 `^[A-Z]{3}$` |
| `sovereignty` | `allowedZones` + `enforcement: block \| audit` |
| `agentPolicy` | model allow-list, token budget, use-case limits — FLUID-aligned vocabulary |
| `skillBinding` | name, skillRef, purpose, optional model/budget |
| `edge` | `{from, to}`, both required — taxonomy transitions, blueprint edges |

## The offline validator

What JSON Schema cannot express, [`scripts/validate.py`](https://github.com/Agenticstiger/flux/blob/main/scripts/validate.py)
enforces — offline, no cloud, no engine:

| Check | Failure it prevents |
|---|---|
| Reference resolution, kind-typed | dangling or wrongly-typed `*Ref` |
| Id uniqueness (flux **and** fluid docs) | last-write-wins ambiguity at the seam |
| `lifecycleMix` / variant weights sum to 1 | populations and experiments that don't add up |
| Transitions ⊆ states, edges ⊆ nodes | unreachable taxonomy states, phantom topology |
| `timeBounds.start < end` | inverted simulation windows |
| skills within `agentPolicy` | model or budget escapes |
| Every `.fluid.yml` valid for its declared version | broken contracts riding along in a bundle |
| [Seam conformance + consent strictness](/flux/concepts/seam) | proving one thing, shipping another |

Malformed input (broken YAML, non-mapping documents, schema-invalid shapes)
produces clean, located error messages — never a stack trace. The
[regression suite](https://github.com/Agenticstiger/flux/blob/main/tests/test_regression.py)
pins all of it.
