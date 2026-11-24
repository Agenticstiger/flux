---
description: "How the FLUX schema is published, one immutable JSON Schema per version at a stable URL, and the two layers of validation the offline validator applies."
---

# Schema Reference

The FLUX schema is **one JSON Schema file per released version** — normative,
immutable once published, served at a stable URL:

```
https://agenticstiger.github.io/flux/schema/flux-schema-<version>.json
https://agenticstiger.github.io/flux/schema/flux-schema-latest.json
```

`flux-schema-latest.json` is a byte-identical copy of the current release's
file; [Versions](/flux/schema/versions) lists every release.

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
# yaml-language-server: $schema=https://agenticstiger.github.io/flux/schema/flux-schema-latest.json
```

## Validation is two layers

JSON Schema alone cannot express cross-document truths. The reference
validator (`scripts/validate.py`) adds: reference resolution (kind-typed, no
dangling links), sum checks (lifecycle mix, experiment weights), set
membership (taxonomy transitions, blueprint edges), agentPolicy bounds, and
full [FLUID seam conformance](/flux/concepts/seam) — all offline.
