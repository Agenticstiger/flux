---
description: "Every released FLUX schema version with its compatibility window, schema URLs and accepted FLUID versions, plus the versioning policy."
---

# Versions

One schema file per released version, immutable once published, each with a
versioned `$id`. The `fluxVersion` enum inside a file is its **compatibility
window** — the document versions it accepts.

| Version | Status | Window | Schema |
|---|---|---|---|
| **0.5.4** | current | `0.3.0` to `0.5.4` | [flux-schema-0.5.4.json](https://agenticstiger.github.io/flux/schema/flux-schema-0.5.4.json) + [UI hints](https://agenticstiger.github.io/flux/schema/flux-ui-hints-0.5.4.json) · [enforcement](https://agenticstiger.github.io/flux/schema/flux-enforcement-0.5.0.json) · [manifest](https://agenticstiger.github.io/flux/schema/flux-manifest-0.5.0.json) (both unchanged from 0.5.0) |
| 0.5.3 | superseded (additively for FLUX; the validator's input bounds tightened) | `0.3.0` to `0.5.3` | [flux-schema-0.5.3.json](https://agenticstiger.github.io/flux/schema/flux-schema-0.5.3.json) + [UI hints](https://agenticstiger.github.io/flux/schema/flux-ui-hints-0.5.3.json) · [enforcement](https://agenticstiger.github.io/flux/schema/flux-enforcement-0.5.0.json) · [manifest](https://agenticstiger.github.io/flux/schema/flux-manifest-0.5.0.json) (both unchanged from 0.5.0) |
| 0.5.2 | superseded (additively for FLUX; the 0.7.7 preview moved) | `0.3.0` to `0.5.2` | [flux-schema-0.5.2.json](https://agenticstiger.github.io/flux/schema/flux-schema-0.5.2.json) + [UI hints](https://agenticstiger.github.io/flux/schema/flux-ui-hints-0.5.2.json) · [enforcement](https://agenticstiger.github.io/flux/schema/flux-enforcement-0.5.0.json) · [manifest](https://agenticstiger.github.io/flux/schema/flux-manifest-0.5.0.json) |
| 0.5.1 | superseded (additively) | `0.3.0` to `0.5.1` | [flux-schema-0.5.1.json](https://agenticstiger.github.io/flux/schema/flux-schema-0.5.1.json) + [UI hints](https://agenticstiger.github.io/flux/schema/flux-ui-hints-0.5.1.json) · [enforcement](https://agenticstiger.github.io/flux/schema/flux-enforcement-0.5.0.json) · [manifest](https://agenticstiger.github.io/flux/schema/flux-manifest-0.5.0.json) |
| 0.5.0 | superseded (additively) | `0.3.0` to `0.5.0` | [flux-schema-0.5.0.json](https://agenticstiger.github.io/flux/schema/flux-schema-0.5.0.json) + [UI hints](https://agenticstiger.github.io/flux/schema/flux-ui-hints-0.5.0.json) · [enforcement](https://agenticstiger.github.io/flux/schema/flux-enforcement-0.5.0.json) · [manifest](https://agenticstiger.github.io/flux/schema/flux-manifest-0.5.0.json) |
| 0.4.1 | superseded (additively) | `0.3.0`, `0.4.0`, `0.4.1` | [flux-schema-0.4.1.json](https://agenticstiger.github.io/flux/schema/flux-schema-0.4.1.json) |
| 0.4.0 | superseded (additively) | `0.3.0`, `0.4.0` | [flux-schema-0.4.0.json](https://agenticstiger.github.io/flux/schema/flux-schema-0.4.0.json) |
| 0.3.0 | superseded (additively) | `0.3.0` | [flux-schema-0.3.0.json](https://agenticstiger.github.io/flux/schema/flux-schema-0.3.0.json) |
| 0.2.0 | pre-release draft, never shipped | `0.2.0` | [flux-schema-0.2.0.json](https://agenticstiger.github.io/flux/schema/flux-schema-0.2.0.json) |

`flux-schema-latest.json` is a byte-identical alias of the newest release
(CI-enforced):
[flux-schema-latest.json](https://agenticstiger.github.io/flux/schema/flux-schema-latest.json)

## The FLUID window

`Simulation.emits[].fluidVersion` enumerates exactly the FLUID schema versions
vendored by this release: the releases **0.7.3, 0.7.4, 0.7.5, 0.7.6**, and the
**0.7.7 preview**. A preview is vendored from a pinned commit, and only the
exact pin `"0.7.7"` selects it: a range such as `^0.7.3` never does. Widening
the window is additive; narrowing it is breaking.

Since 0.5.3 the preview is pinned to forge-cli commit `e88301f7`, and 0.5.4
does not move it. A preview can change when its pin moves, and the 0.5.3 move
changed what it accepts: the
[changelog](/flux/schema/changelog) lists what a 0.7.7 contract may now carry
and what is refused.

## Policy

Pre-1.0, minor versions may break — every release ships a
[changelog entry](/flux/schema/changelog) and regression tests pinning changed
behavior. Post-1.0: SemVer, additive-only minors. Full policy:
[VERSIONING.md](https://github.com/Agenticstiger/flux/blob/main/VERSIONING.md).
