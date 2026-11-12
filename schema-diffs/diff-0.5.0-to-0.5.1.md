# FLUX Schema Diff: 0.5.0 → 0.5.1

**Additive, non-breaking.** Every valid 0.3.0–0.5.0 document validates
unchanged under 0.5.1 (regression-asserted). One change: the FLUID seam window
widens to FLUID 0.7.6.

## The FLUID seam

- `vendor/fluid/fluid-schema-0.7.6.json` is vendored verbatim from FLUID
  ("FLUID 0.7.6 — Declarative Packaging Modes", additive over 0.7.5), and the
  `fluid-vendor-sync` workflow compares it with the published file. A
  `.fluid.yml` that declares `fluidVersion: "0.7.6"` is validated against it.
- `Simulation.emits[].fluidVersion` accepts the exact pin `"0.7.6"`:

```json
"enum": ["0.7.3", "0.7.4", "0.7.5", "0.7.6"]
```

  A range such as `^0.7.3` already reached 0.7.6 once it was vendored, under
  the same RFC-06 rules: the referenced document's own `fluidVersion` must
  satisfy the range, and at least one vendored schema must satisfy it.

## Envelope / window

- `fluxVersion` enum widens to `["0.3.0", "0.4.0", "0.4.1", "0.5.0", "0.5.1"]`.
- `$id` → `flux-schema-0.5.1.json`; `flux-schema-latest.json` aliases 0.5.1;
  UI hints regenerate as `flux-ui-hints-0.5.1.json`.
- `flux-enforcement-0.5.0.json` and `flux-manifest-0.5.0.json` are unchanged:
  0.5.1 changes no enforcement or bundle contract.

## Compatibility

`flux-schema-0.5.0.json` is immutable and still refuses an exact `"0.7.6"`
pin (regression-asserted), so a document that uses it pins
`fluxVersion: "0.5.1"`. Nothing that validated before is refused now.
