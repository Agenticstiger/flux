# Conformance Profiles

One schema, three honest bars (roadmap principle P3). A lightweight
validator, a governed enterprise deployment, and a live engine should each be
able to claim "FLUX" truthfully — at different levels.

## Level 1 — Core ✅ *definable today*

The 0.3.x bar. Any tool can hit it.

- Schema + cross-document validation (the offline reference validator)
- FLUID seam resolves and validates against vendored schemas
- Deterministic under seed
- No extensions required

## Level 2 — Enterprise ◐ *three of five requirements shipped in 0.4.0*

Core, plus governance, semantics, and supply chain:

- Extensions declared and typed (RFC-02 — *shipped in 0.4.0*)
- Lockfile + pinned module refs (RFC-03 — *shipped in 0.4.0*)
- Playback scorecard present (RFC-05)
- Semantic-model port resolved (RFC-07 — *shipped in 0.4.0*)
- Signed, attested bundle (RFC-09)

## Level 3 — Runtime 📋 *lands with 0.5.0*

Enterprise, plus it actually runs and enforces:

- Enforcement contract passes the conformance test vectors (RFC-04)
- A live calibration loop feeds the scorecard
- Seam provenance emitted per run (RFC-06)

## Why profiles change the calculus

Under a single bar, an advanced implementation is judged against a line it
overshoots in some places and misses in others — it reads as
"non-conformant" even while doing *more* than the spec. Under profiles, the
same implementation certifies at the standard's **top tier**, and everything
it does becomes a demonstration of the standard rather than a deviation from
it. That is how a standard converts its most sophisticated potential adopter
into its reference implementation.
