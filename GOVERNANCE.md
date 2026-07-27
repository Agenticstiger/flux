# Governance

## Current model: steward-maintainer

FLUX is in working-draft stage (pre-1.0). The specification is stewarded by
its originating maintainers under the Agenticstiger organization. Decisions on
spec changes are made by the maintainers, in the open, through issues and pull
requests on this repository.

## Vendor neutrality intent

FLUX is designed as an open standard, not a product surface. The maintainers'
declared intent is that, as the specification gains external contributors and
implementations, this repository moves to a vendor-neutral home — the natural
candidate being [open-data-protocol](https://github.com/open-data-protocol),
where the FLUID specification already lives, so both halves of the substrate
share one neutral org. GitHub repository transfers leave permanent redirects,
so this move costs adopters nothing. The trigger for revisiting: the first
sustained external contributor, or the 1.0 cut, whichever comes first.

## How spec changes happen

1. **Issue first** for anything normative (schema, seam, validator semantics).
   Editorial fixes may go straight to PR.
2. **One PR carries the whole change**: schema edit + schema-diff entry +
   example updates + regression tests. CI enforces that examples validate and
   the regression suite stays green; a normative change without tests is not
   mergeable.
3. **Versioning** follows [VERSIONING.md](VERSIONING.md). Breaking changes
   require a version bump and a diff document.
4. The **FLUID seam** is jointly owned: changes to `Simulation.emits` or the
   vendored FLUID versions require checking against the current FLUID release
   and noting the compatibility window in the diff.

## Becoming a maintainer

Sustained, quality contributions (spec text, validator, examples, review) over
several months, followed by nomination and consensus of the existing
maintainers. The bar is judgment on compatibility questions, not volume.

## Code of conduct

[Contributor Covenant 2.1](CODE_OF_CONDUCT.md). Reports go to the maintainers.
