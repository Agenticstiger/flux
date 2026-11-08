# RFC-10: Playback reads a FLUID data profile

*Calibration · Playback · the FLUID seam*

| | |
|---|---|
| Status | Proposed (2026-11-08) |
| Changes | `Playback.spec.sourceStream` is replaced by `Playback.spec.source`, a FLUID consumeRef. A fifth calibration target, `response`, joins the four existing ones. |
| Depends on | FLUID's `data_profile` expose kind, proposed in [RFC-data-profile-port.md](https://github.com/Agenticstiger/forge-cli/blob/main/RFC-data-profile-port.md). |
| Lands in | the next minor (0.6.0) adds and deprecates; a later minor removes `sourceStream`. |

## Gap

A Playback names the data a twin is fitted against with one field:

```yaml
spec:
  sourceStream: kafka://billing.events.v1
```

The validator can check that this is a URI and nothing else. It cannot tell what the stream contains, which version of it the twin was fitted against, who may read it, or whether it exists at all.

It also assumes the twin reads raw telemetry, which means records. Most data owners cannot hand records to a simulation team, let alone across an organization boundary, so in practice the field points at data the twin's builders were never allowed to see.

The output side of the seam has been a reference to a FLUID contract since 0.3.0: `Simulation.emits[]` names a product and an expose, and the validator checks both. The input side never got the same treatment. This RFC closes that gap, and it does it in a way that keeps records on the owner's side.

## Proposal

### `spec.source`: a FLUID consumeRef

`source` uses the field names and meaning of FLUID's `$defs.consumeRef`. FLUX defines its own closed copy, as the seam's dialect-boundary rule requires, with no `$ref` into the FLUID schema.

```yaml
spec:
  worldRef: q3-retention-world
  source:
    productId: telco.billing.customer_summary
    exposeId: customer_summary_profile
    versionConstraint: "^1.0"
    requiredPolicies: [aggregate-only]
    provenance:
      contractDigest: "sha256:<64 hex>"
```

| Field | Required | Meaning |
|---|---|---|
| `productId` | yes | The FLUID product, by its id. Resolved to a `.fluid.yml` in the bundle. |
| `exposeId` | yes | The expose of that product to read. Must be `kind: data_profile`. |
| `versionConstraint` | yes | A semver range the expose's `version` must satisfy. |
| `requiredPolicies` | no | Policy identifiers the consumer requires, as in FLUID. |
| `provenance.contractDigest` | no | The RFC-06 shape: canonical-JSON SHA-256 of the referenced contract. |

`versionConstraint` is optional in FLUID and required here. A profile's bins change meaning across a major version (new edges are new buckets), and a twin that silently starts fitting against different bins is the failure this whole seam exists to prevent. Every valid `source` is still a valid FLUID consumeRef; the implementation PR pins that with a regression case.

The validator checks, offline as it does for `emits[]`:

1. `productId` resolves to a `.fluid.yml` in the bundle. A dangling reference fails.
2. That document validates against the vendored FLUID schema for its own `fluidVersion`, and that version must have the `data_profile` kind.
3. `exposeId` names an expose of the product with `kind: data_profile`.
4. The expose's `version` satisfies `versionConstraint`, with the range rules RFC-03 and RFC-06 already use.
5. `provenance.contractDigest`, when set, matches the in-bundle contract. Contract drift after calibration fails the bundle, as it does on the output side.
6. Every calibration target, persona mapping and drift setting can be answered from what the profile declares (below).

### Why a profile, and not any expose

`source` accepts only `data_profile` exposes. A FLUID data profile publishes aggregates of one of its product's exposes (bucket counts on declared edges, sums and sums of squares, distinct counts, transition and dwell counts for event data) with small cells suppressed, and never a row. That is what a twin needs to fit its dials, and it is all a data owner has to share.

The FLUID contract holds only the profile's declaration. The numbers live in profile states behind the port, so shipping the contract inside a FLUX bundle shares no statistics, and the contract digest does not move when the profile refreshes. That is what makes rule 5 workable: a twin calibrated last week still verifies against the same contract this week.

A team that does have record access inside the boundary declares a profile on its own stream and points the Playback at that. The twin never needs the records.

### Calibration reads profile families

Each target says which profile families it reads. A new optional map, `calibration.columns`, names the profile column that plays each role:

| Target | Roles in `calibration.columns` | The profile must declare |
|---|---|---|
| `population.size` | none | an `entity`, with `distinct` on it |
| `population.lifecycleMix` | `lifecycle` | `histogram` on that category column |
| `eventRates` | none, or `eventCount` | `transitions` (an event profile), or `moments` on the `eventCount` column (one row per entity) |
| `channelReach` | `channel` | an `entity` with `distinct` on it, and `groupBy` containing the channel column |
| `response` (new) | `variant`, `segment`, `outcome` | `groupBy` containing the variant and segment columns, and `moments` on the outcome column |

`entity` here is the profile's own `entity`: the column that identifies a customer, which the profile counts and never publishes.

A target whose role is missing from `calibration.columns`, a role that names a column the profile does not declare, or a missing family fails validation. The message names the target, the role and the family the profile has to add.

Category labels are data, so the validator cannot compare them. A conforming engine maps state labels onto the World's own keys (the `lifecycleMix` states, the Experiment's variant names), reports a label it cannot map, and treats a World key with no label as missing, never as zero.

### The `response` target

`response` fits the twin's response to treatments against observed experiment outcomes, per variant and per segment. It needs one more field, `calibration.experimentRef`, naming the Experiment whose variants the observed `variant` labels correspond to.

```yaml
calibration:
  targets: [population.lifecycleMix, response]
  window: P90D
  method: mle
  experimentRef: exp-reminder-timing
  columns:
    lifecycle: lifecycle_state
    variant: variant
    segment: segment
    outcome: paid_within_7d
```

The profile side is a grouped profile: `groupBy: [variant, segment]` with `moments` on the outcome. Each cell then carries `n`, the sum and the sum of squares, which are the sufficient statistics experiment analysis works from (gbstats takes exactly these, plus a sum of products for ratio metrics). A binary outcome is a 0/1 column whose sum is the number of conversions.

The validator requires `experimentRef` with the `response` target, requires it to resolve to an Experiment in the bundle, and requires the three roles. A cell or sum the profile suppressed (too few customers, or one customer dominating a sum) is missing data to the calibration, never zero. A segment with too few customers to publish simply does not constrain the fit, and the scorecard should say so rather than grade a fit on a cell that was never seen.

Which dials `response` moves is the calibration method's business, recorded by the calibration loop like the dials behind the four existing targets.

### Persona mapping on a profile

`personaMapping[].behaviorPattern` is a flux-expr/1 predicate "over observed events". A twin that only sees aggregates cannot evaluate a predicate record by record, so with a profile source the predicate has to be answerable from the profile:

- a comparison between one range column and a constant is answerable when the constant is one of the column's declared edges (`late_payment_count >= 2` needs an edge at 2);
- an equality between a category column and a label is answerable from its histogram;
- a conjunction over two or more columns is answerable when the profile groups by all but one of them.

Anything else is refused with a message naming the pattern and what the profile would need. flux-expr/1 has no published grammar yet, so this rule constrains only the subset above, and the implementation PR pins that subset with regression cases.

### Drift on declared edges

`drift` keeps its fields. PSI and KL are computed on the profile's histograms, so their bins are the declared edges: pinned, and the same on both sides of the comparison. KS becomes the binned statistic over the edges, which is a lower bound on the true KS distance; the drift doc should say so.

## The migrated example

The producer declares the profile in its own FLUID contract (abbreviated):

```yaml
exposes:
  - exposeId: customer_summary_profile
    kind: data_profile
    version: 1.0.0
    profile:
      source: customer_summary            # one row per customer and week
      entity: customer_id
      window: { column: as_of, length: P7D, mode: tumbling }
      columns:
        - { name: lifecycle_state, domain: category }
        - { name: late_payment_count, domain: range, edges: ["0", "1", "2", "3", "5", "10", "50"], resolution: "1" }
        - { name: billing_event_count, domain: range, edges: ["0", "5", "20", "100", "1000"], resolution: "1" }
      families: [histogram, moments, distinct]
      disclosure: { minCellSize: 10 }
```

The Playback reads it:

```yaml
spec:
  worldRef: q3-retention-world
  source:
    productId: telco.billing.customer_summary
    exposeId: customer_summary_profile
    versionConstraint: "^1.0"
  personaMapping:
    - behaviorPattern: "late_payment_count >= 2"
      mapToPersona: persona-pragmatic-family
  calibration:
    targets: [population.lifecycleMix, eventRates]
    window: P90D
    method: mle
    columns:
      lifecycle: lifecycle_state
      eventCount: billing_event_count
  drift: { metric: psi, threshold: 0.2, onBreach: warn }
```

The persona pattern compares against a declared edge, lifecycle mix reads the `lifecycle_state` histogram, and event rates come from the per-customer event count. Nothing in either document holds a record or a statistic.

## Compatibility and migration

The change is staged so that no document breaks before it has had a release to move.

1. Expand, in 0.6.0. `source`, `calibration.columns`, `calibration.experimentRef` and the `response` target are added. `sourceStream` becomes optional and deprecated, and a Playback must carry exactly one of `source` and `sourceStream` (validator-enforced). Nothing is required that was not required before and no constraint tightens, so every 0.5.0 document stays valid and the 0.6.0 window covers 0.3.0 to 0.6.0. The validator warns on every `sourceStream`.
2. Migrate. The telco example moves to `source`, as above, with the producer's contract added to the bundle.
3. Verify. The regression suite pins both shapes through 0.6.x: an old Playback with `sourceStream` passes with a warning, a new one with `source` passes, one with both fails, one with neither fails.
4. Contract, in a later minor. `sourceStream` is removed. That is breaking under VERSIONING.md, so it ships with a migration section in its diff, and not before at least one minor release has carried the deprecation warning.

Rollback is cheap until step 4. If this RFC is withdrawn after 0.6.0, `source` stays optional and unused, and a Playback can switch back to `sourceStream` without any other change.

### The seam window

The FLUID seam is jointly owned (GOVERNANCE.md, item 4), so this is checked against the current FLUID release. `data_profile` does not exist in any FLUID version vendored today (0.7.3 to 0.7.5). It is proposed for FLUID's open 0.7.7 preview. The implementation therefore has an order: FLUID ships the kind, FLUX vendors that FLUID version verbatim, and only then can rule 2 pass for any bundle. Vendoring a new FLUID version also widens `Simulation.emits[].fluidVersion`, which is additive under VERSIONING.md.

## What the implementation PR carries

Per CONTRIBUTING.md, one PR after the issue for this RFC is agreed:

- `schema/flux-schema-0.6.0.json` with the new fields and the deprecation, and `flux-schema-latest.json` moved to it;
- `schema-diffs/diff-0.5.0-to-0.6.0.md`, including the seam window note;
- the vendored FLUID version that has `data_profile`, and the package data re-synced;
- the telco example migrated;
- validator checks in `scripts/validate.py` with a regression case for each rule above, including the four shape cases in step 3;
- the regenerated kinds doc and UI hints;
- `docs/concepts/seam.md` describing the input side of the seam.

## Alternatives considered

Keep `sourceStream` and add a reference beside it for good. Two ways to say one thing, and the one the validator cannot check would stay the easy one.

Accept any FLUID expose in `source`, a stream or a table as well as a profile. That brings back record access for the twin, which is the problem, and it gives the validator nothing to check calibration against, because only a profile declares its families.

Put the profile's values in the Playback document. Every refresh would change the document, its digest and the signed evidence pack (RFC-09), and the statistics would travel with every copy of the bundle.

A FLUX-native profile kind. It would restate on the FLUX side what FLUID already declares, which is exactly what the seam is designed to avoid: reference, never restate.

## Open questions

1. Vendor the FLUID preview that carries `data_profile`, or wait until FLUID promotes it to stable? The weekly vendor-sync job compares vendored copies with FLUID's published schemas, and a preview can still change.
2. FLUID gives `requiredPolicies` no checkable meaning. Should the validator check entries against the profile expose's declared policy (its `policy.agentPolicy` use cases, say), or keep a shape-only check until FLUID defines one?
3. Should the scorecard name the profile states it calibrated on and backtested against (by sequence and digest), so it is visible that the backtest used a later state than the fit?
