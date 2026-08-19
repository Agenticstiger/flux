# Schema Reference

The FLUX schema is **one JSON Schema file per released version** — normative,
immutable once published, served at a stable URL:

```
https://agenticstiger.github.io/flux/schema/flux-schema-0.4.0.json
https://agenticstiger.github.io/flux/schema/flux-schema-latest.json
```

- **[Anatomy](/flux/schema/anatomy)** — the envelope, the kind-branch
  structure, the shared `$defs` grammar, and what the offline validator adds.
- **[The Nineteen Kinds](/flux/schema/kinds)** — generated per-kind field
  reference, straight from the schema.
- **[Versions](/flux/schema/versions)** — every released version, its window,
  and its URL.
- **[Changelog](/flux/schema/changelog)** — human-written diffs, one per
  version pair.

## Editor integration

```yaml
# yaml-language-server: $schema=https://agenticstiger.github.io/flux/schema/flux-schema-0.4.0.json
```

## Validation is two layers

JSON Schema alone cannot express cross-document truths. The reference
validator (`scripts/validate.py`) adds: reference resolution (kind-typed, no
dangling links), sum checks (lifecycle mix, experiment weights), set
membership (taxonomy transitions, blueprint edges), agentPolicy bounds, and
full [FLUID seam conformance](/flux/concepts/seam) — all offline.
