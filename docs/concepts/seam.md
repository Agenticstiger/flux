# The FLUID Seam

The single most important design decision in FLUX: **a Simulation emits
streams by referencing the FLUID contract they are proven under — never by
restating it.**

```yaml
kind: Simulation
spec:
  worldRef: q3-retention-world
  emits:
    - productRef: telco.gold.payment_recovery_moment   # id of a .fluid.yml in the bundle
      exposeId: payment_recovery_moment                # an expose of that product
      fluidVersion: "^0.7.3"                           # exact pin or semver range (RFC-06)
      minCredibility: 0.7                              # gate on the twin's scorecard (RFC-05)
      provenance:
        contractDigest: "sha256:762f…"                 # proven bytes == shipped bytes
```

## Why reference, not embed

An embedded copy of a contract is a fork waiting to happen: the moment the
twin's copy and the shipped copy can differ, "what was proven" and "what
ships" are two documents. Referencing makes the claim *"the thing that ships
is the thing that was proven"* literally true — same file, same bytes, same
digest.

It also solves three mechanical problems:

- **Version skew** — `fluidVersion` is an exact vendored version or a semver
  range resolved against the vendored set (`0.7.3`–`0.7.5`); either way a
  contract can't silently target a FLUID version the toolchain has never seen,
  and ranges don't freeze the seam to a point release.
- **Dialect boundary** — FLUX and FLUID schemas evolve independently; each
  document is validated against *its own* schema, not through a cross-schema
  `$ref`.
- **Granularity** — FLUID's unit is a DataProduct containing `exposes[]`. The
  seam names product *and* expose, so multi-expose products work naturally and
  the validator asserts the expose actually exists.

## What the validator enforces at the seam

For every `emits[]` entry, [`scripts/validate.py`](https://github.com/Agenticstiger/flux/blob/main/scripts/validate.py):

1. resolves `productRef` to a `.fluid.yml` document in the bundle — dangling
   refs fail;
2. validates that document against the vendored FLUID schema for the pinned
   `fluidVersion` — an invalid contract fails the bundle (and every
   `.fluid.yml` is validated even if nothing references it);
3. asserts the document's own `fluidVersion` satisfies the pin or range;
4. asserts `exposeId` is a member of the product's `exposes[]`;
5. verifies `provenance.contractDigest` against the in-bundle contract —
   contract drift after proving fails the bundle;
6. enforces `minCredibility` against the Playback scorecard calibrating the
   Simulation's world — an untrustworthy twin cannot ship;
7. **consent strictness** — the emitted expose's `policy.agentPolicy` must be
   at least as strict as every `ConsentProfile` gating the Simulation's
   campaigns: it may not allow a use case a profile denies, nor exceed a
   profile's allow-list.

All offline. A bundle that is green locally is green in CI, and a contract
cannot "pass in the twin, fail at ship" — the fail surfaces at the gate.

## Shared vocabulary, one grammar

The two specs share an identifier grammar (FLUX's `$defs/identifier` is
byte-identical to FLUID's), a casing convention (camelCase), an envelope
(`id`/`name` top-level, `metadata.owner` required), and a policy vocabulary
(`allowedUseCases`/`deniedUseCases` on both sides of the seam) — so
seam-crossing comparison is field-to-field, and tooling that handles one spec
parses the other's envelope for free.
