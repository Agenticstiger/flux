# Versions

One schema file per released version, immutable once published, each with a
versioned `$id`. The `fluxVersion` enum inside a file is its **compatibility
window** — the document versions it accepts.

| Version | Status | Window | Schema |
|---|---|---|---|
| **0.4.1** | current | `0.3.0`, `0.4.0`, `0.4.1` | [flux-schema-0.4.1.json](https://agenticstiger.github.io/flux/schema/flux-schema-0.4.1.json) + [UI hints](https://agenticstiger.github.io/flux/schema/flux-ui-hints-0.4.1.json) |
| 0.4.0 | superseded (additively) | `0.3.0`, `0.4.0` | [flux-schema-0.4.0.json](https://agenticstiger.github.io/flux/schema/flux-schema-0.4.0.json) |
| 0.3.0 | superseded (additively) | `0.3.0` | [flux-schema-0.3.0.json](https://agenticstiger.github.io/flux/schema/flux-schema-0.3.0.json) |
| 0.2.0 | pre-release draft, never shipped | `0.2.0` | [flux-schema-0.2.0.json](https://agenticstiger.github.io/flux/schema/flux-schema-0.2.0.json) |

`flux-schema-latest.json` is a byte-identical alias of the newest release
(CI-enforced):
[flux-schema-latest.json](https://agenticstiger.github.io/flux/schema/flux-schema-latest.json)

## The FLUID window

`Simulation.emits[].fluidVersion` enumerates exactly the FLUID schema versions
vendored by this release: **0.7.3, 0.7.4, 0.7.5**. Widening the window is
additive; narrowing it is breaking.

## Policy

Pre-1.0, minor versions may break — every release ships a
[changelog entry](/flux/schema/changelog) and regression tests pinning changed
behavior. Post-1.0: SemVer, additive-only minors. Full policy:
[VERSIONING.md](https://github.com/Agenticstiger/flux/blob/main/VERSIONING.md).
