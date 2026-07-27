# The Nineteen Kinds

> Generated from
> [`flux-schema-0.3.0.json`](https://agenticstiger.github.io/flux/schema/flux-schema-0.3.0.json)
> by `scripts/generate-kinds-doc.py` — do not edit by hand.

Every kind shares the [common envelope](/flux/schema/anatomy#the-envelope);
the tables below describe each kind's `spec`. Fields ending in `Ref`
(and `refList` fields) must resolve to a document of the right kind in the
same bundle — enforced by the [offline validator](/flux/schema/anatomy#the-offline-validator).

## Population

### World

*required: `seed`, `population`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `seed` | `integer` | **yes** |  | Deterministic PRNG seed |
| `vertical` | `string` | no | minLength 1 |  |
| `sovereignty` | `sovereignty` | no |  |  |
| `sovereignty.allowedZones` | array of `string` | **yes** | minItems 1; unique |  |
| `sovereignty.enforcement` | enum | no | `block`, `audit`; default `block` | block: execution mathematically fails outside allowed zones; audit: violations are recorded as lineage |
| `population` | `object` | **yes** |  |  |
| `population.size` | `integer` | **yes** | min 1 |  |
| `population.lifecycleMix` | `object` | **yes** | minProperties 1 | Fractions per lifecycle state |
| `population.markets` | array of `string` | no | minItems 1; unique | Named markets/operating companies the population is distributed across (formerly 'natcos' in 0.2.0 examples) |
| `temperature` | `object` | no | minProperties 1 | Per-dial stochastic temperature (0 = frozen, 1 = maximally variable), e.g |

### Persona

*at least 1 field*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `demographics` | `scalarMap` | no |  |  |
| `traits` | `object` | no | minProperties 1 | Named 0..1 proficiency scores (e.g |
| `worldview` | `object` | no | minProperties 1 |  |
| `worldview.riskTolerance` | enum | no | `low`, `medium`, `high` |  |
| `worldview.trustInInstitutions` | `unitInterval` | no | min 0; max 1 |  |
| `worldview.trendFollowing` | `unitInterval` | no | min 0; max 1 |  |
| `agenticPrompt` | array of `string` | no | minItems 1 | Prompt fragments for model-backed persona behavior |

### Segment

*required: `query`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `query` | `string` | **yes** | minLength 1 | Expression selecting Personas from the population |
| `queryLanguage` | const `flux-expr/1` | no | const `flux-expr/1` | The expression grammar the query is written in |

## Commerce

### Catalog

*required: `items`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `items` | array of `object` | **yes** | minItems 1 |  |
| `items[].sku` | `string` | **yes** | minLength 1 |  |
| `items[].name` | `string` | **yes** | minLength 1 |  |
| `items[].attributes` | `scalarMap` | no |  |  |

### Offer

*required: `catalogRef`, `pricing`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `catalogRef` | `ref` | **yes** |  | A reference to the id of another document in the same bundle (same grammar as identifier) |
| `pricing` | `object` | **yes** |  |  |
| `pricing.amount` | `number` | **yes** | min 0 |  |
| `pricing.currency` | `currencyCode` | **yes** |  | ISO 4217 alphabetic currency code |

### Channel

*required: `type`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `type` | anyOf | **yes** |  | Well-known channel type, or an x- prefixed extension type |
| `rateLimitPerSecond` | `integer` | no | min 1 |  |

### ConsentProfile

*at least 1 field*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `allowedJurisdictions` | array of `string` | no | minItems 1; unique |  |
| `requiresExplicitOptIn` | `boolean` | no |  |  |
| `allowedUseCases` | array of `string` | no | minItems 1; unique | Vocabulary aligned with FLUID agentPolicy.allowedUseCases; a contract emitted at the seam must be at least as strict as the gating ConsentProfile (validator-enforced) |
| `deniedUseCases` | array of `string` | no | minItems 1; unique |  |

## Behaviour

### Journey

*required: `trigger`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `trigger` | `object` | **yes** |  |  |
| `trigger.signalRef` | `ref` | **yes** |  | A reference to the id of another document in the same bundle (same grammar as identifier) |
| `trigger.condition` | `string` | no | minLength 1 | Optional flux-expr/1 predicate over the signal payload |
| `intervention` | `object` | no |  |  |
| `intervention.treatmentRef` | `ref` | **yes** |  | A reference to the id of another document in the same bundle (same grammar as identifier) |
| `intervention.action` | `string` | no | minLength 1 |  |
| `taxonomyRef` | `ref` | no |  | JourneyTaxonomy whose states this journey's reactions may transition to |
| `personaReactions` | `object` | no | minProperties 1 |  |

### JourneyTaxonomy

*required: `states`, `transitions`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `states` | array of `string` | **yes** | minItems 1; unique |  |
| `transitions` | array of `edge` | **yes** | minItems 1 | from/to must be members of states (validator-enforced) |
| `transitions[].from` | `string` | **yes** | minLength 1 |  |
| `transitions[].to` | `string` | **yes** | minLength 1 |  |

### Signal

*required: `source`, `type`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `envelope` | const `cloudevents/1.0` | no | const `cloudevents/1.0` | Every emitted record is a CloudEvents 1.0 envelope; this is the event-envelope port |
| `source` | `string` | **yes** | minLength 1 | CloudEvents 'source' context attribute |
| `type` | `string` | **yes** |  | CloudEvents 'type' context attribute |
| `dataschema` | `string` | no |  | URI of the payload schema (CloudEvents 'dataschema') |

### Detector

*required: `timeWindowMs`, `pattern`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `timeWindowMs` | `integer` | **yes** | min 1 |  |
| `pattern` | array of `object` | **yes** | minItems 1 | Ordered sequence of signal conditions that must occur within the window |
| `pattern[].signalRef` | `ref` | **yes** |  | A reference to the id of another document in the same bundle (same grammar as identifier) |
| `pattern[].predicate` | `string` | no | minLength 1 | flux-expr/1 predicate over the signal payload |

## Activation

### Campaign

*required: `treatmentRef`, `segmentRef`, `channelRef`, `consentRef`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `treatmentRef` | `ref` | **yes** |  | A reference to the id of another document in the same bundle (same grammar as identifier) |
| `segmentRef` | `ref` | **yes** |  | A reference to the id of another document in the same bundle (same grammar as identifier) |
| `channelRef` | `ref` | **yes** |  | A reference to the id of another document in the same bundle (same grammar as identifier) |
| `consentRef` | `ref` | **yes** |  | A reference to the id of another document in the same bundle (same grammar as identifier) |

### Treatment

*required: `actionType`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `actionType` | `string` | **yes** |  |  |
| `payloadTemplate` | `object` | no |  |  |

### Experiment

*required: `variants`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `variants` | array of `object` | **yes** | minItems 1 | Variant names must be unique and weights must sum to 1 (validator-enforced) |
| `variants[].name` | `string` | **yes** | minLength 1 |  |
| `variants[].weight` | `unitInterval` | **yes** | min 0; max 1 |  |
| `variants[].treatmentRef` | `ref` | **yes** |  | A reference to the id of another document in the same bundle (same grammar as identifier) |
| `variants[].isControl` | `boolean` | no | default `False` |  |
| `assignment` | `object` | no |  |  |
| `assignment.method` | const `largest_remainder` | **yes** | const `largest_remainder` | Integer cohort allocation with zero rounding loss |
| `assignment.seed` | `integer` | no |  |  |
| `metrics` | array of `object` | no | minItems 1 |  |
| `metrics[].name` | `string` | **yes** | minLength 1 |  |
| `metrics[].ossieRef` | `string` | no | minLength 1 | Reference into the governed Ossie semantic model (the ossie-model port) |

## Calibration

### Playback

*required: `worldRef`, `sourceStream`, `personaMapping`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `worldRef` | `ref` | **yes** |  | The World this playback calibrates |
| `sourceStream` | `string` | **yes** |  | URI of historical telemetry the twin is fitted against |
| `personaMapping` | array of `object` | **yes** | minItems 1 |  |
| `personaMapping[].behaviorPattern` | `string` | **yes** | minLength 1 | flux-expr/1 predicate over observed events |
| `personaMapping[].mapToPersona` | `ref` | **yes** |  | A reference to the id of another document in the same bundle (same grammar as identifier) |
| `calibration` | `object` | no |  | Which World dials are fitted from the source stream |
| `calibration.targets` | array of `string` | **yes** | minItems 1; unique |  |
| `calibration.window` | `string` | no | minLength 1 | Observation window, e.g |
| `calibration.method` | `string` | no | minLength 1 |  |
| `drift` | `object` | no |  | Twin-predicted vs estate-observed divergence is reported as drift against this threshold |
| `drift.metric` | enum | **yes** | `psi`, `kl`, `ks` |  |
| `drift.threshold` | `number` | **yes** | > 0 |  |
| `drift.onBreach` | enum | no | `warn`, `fail`; default `warn` |  |

## Composition

### Simulation

*required: `worldRef`, `emits`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `worldRef` | `ref` | **yes** |  | A reference to the id of another document in the same bundle (same grammar as identifier) |
| `fidelity` | enum | no | `deterministic`, `stochastic`, `agentic`; default `deterministic` | Escalating fidelities: deterministic (pure function of seed), stochastic (seed sweep -> distribution), agentic (model-backed actors under agentPolicy) |
| `seed` | `integer` | no |  | Overrides the World seed for this run |
| `sweep` | `object` | no |  | Stochastic mode: sweep seeds baseSeed..baseSeed+runs-1; each run remains independently replayable |
| `sweep.runs` | `integer` | **yes** | min 2 |  |
| `sweep.baseSeed` | `integer` | no |  |  |
| `golden` | `object` | no |  | Golden-regression anchor: the verify gate fails on a single byte of drift from this digest |
| `golden.baselineDigest` | `string` | **yes** |  |  |
| `sovereignty` | `sovereignty` | no |  |  |
| `sovereignty.allowedZones` | array of `string` | **yes** | minItems 1; unique |  |
| `sovereignty.enforcement` | enum | no | `block`, `audit`; default `block` | block: execution mathematically fails outside allowed zones; audit: violations are recorded as lineage |
| `timeBounds` | `object` | no |  | start must precede end (validator-enforced) |
| `timeBounds.start` | `rfc3339` | **yes** |  | RFC 3339 timestamp (lowercase t/z permitted, per the RFC) |
| `timeBounds.end` | `rfc3339` | **yes** |  | RFC 3339 timestamp (lowercase t/z permitted, per the RFC) |
| `personaRefs` | `refList` | no | minItems 1; unique |  |
| `segmentRefs` | `refList` | no | minItems 1; unique |  |
| `signalRefs` | `refList` | no | minItems 1; unique |  |
| `campaignRefs` | `refList` | no | minItems 1; unique |  |
| `experimentRefs` | `refList` | no | minItems 1; unique |  |
| `moduleRefs` | `refList` | no | minItems 1; unique |  |
| `emits` | array of `object` | **yes** | minItems 1; unique | The FLUID contract handoff seam |
| `emits[].productRef` | `ref` | **yes** |  | The id of the FLUID DataProduct document (.fluid.yml) proven by this simulation |
| `emits[].exposeId` | `string` | **yes** | minLength 1 | Which expose of the referenced DataProduct this stream fulfils |
| `emits[].fluidVersion` | enum | **yes** | `0.7.3`, `0.7.4`, `0.7.5` | FLUID schema version the referenced contract is validated against |

### Module

*required: `resources`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `resources` | array of `ref` | **yes** | minItems 1; unique |  |
| `binds` | array of `object` | no | minItems 1 | The seams this module binds to; a capability can be swapped without touching the documents that use it |
| `binds[].port` | enum | **yes** | `event-envelope`, `fluid-contract`, `ossie-model`, `binding-port` |  |
| `binds[].config` | `object` | no |  |  |

### Blueprint

*required: `topology`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `topology` | `object` | **yes** |  |  |
| `topology.nodes` | array of `ref` | **yes** | minItems 1; unique |  |
| `topology.edges` | array of `edge` | no | minItems 1 | from/to must be members of nodes (validator-enforced) |
| `topology.edges[].from` | `string` | **yes** | minLength 1 |  |
| `topology.edges[].to` | `string` | **yes** | minLength 1 |  |

### VerticalPack

*required: `industry`, `modules`*

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `industry` | `string` | **yes** | minLength 1 |  |
| `modules` | array of `ref` | **yes** | minItems 1; unique |  |

