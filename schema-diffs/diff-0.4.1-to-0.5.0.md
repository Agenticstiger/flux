# FLUX Schema Diff: 0.4.1 → 0.5.0

**Additive, non-breaking.** Every valid 0.3.0–0.4.1 document validates
unchanged under 0.5.0 (regression-asserted). Ships the final two RFCs of the
[vNext roadmap](../docs/roadmap/README.md) — **all nine are now shipped**.

Both additions are *contracts about running and proving*, not new document
fields, so the core schema changes only its version window. The new normative
surface lives in two sibling schemas plus two reference tools.

## RFC-04 — The enforcement decision contract

New published schema `schema/flux-enforcement-0.5.0.json`: the request and
decision shapes every conformant policy gate implements.

```
decide(agentPolicy, {model, useCase, purpose?, tokens})
  -> {allow, reasonCode, reason, policyDigest, request}
```

Normative check order — first failure wins: `MODEL_NOT_ALLOWED`,
`USE_CASE_DENIED`, `USE_CASE_NOT_ALLOWED`, `PURPOSE_REQUIRED`,
`TOKEN_BUDGET_EXCEEDED`. Malformed input yields `INVALID_REQUEST`. A policy
declaring no models permits nothing (fail closed). Skill bindings narrow the
effective token budget and can never widen it.

`policyDigest` (canonical-JSON sha256 of the policy) makes every decision
auditable: the log proves *which* policy allowed a call.

- Reference gate: `scripts/enforce.py`
- Conformance vectors: `tests/enforcement-vectors.json` (34 cases pinning
  `allow`, `reasonCode` and `policyDigest`). CI runs them on every commit, and
  a meta-test asserts six deliberately-broken gates **fail** the suite.

Normative details that make the contract portable rather than merely
implementable:

- Integers follow JSON semantics (`200000.0` is `200000`, `true` is never `1`),
  bounded to 2^53-1 so they survive a JSON boundary.
- `model`/`useCase` are NFC-normalised and stripped before comparison;
  matching is case-sensitive.
- An off-spec policy is `INVALID_POLICY` — a missing `tokenBudget` is never
  "no budget".
- `policyDigest` is sha256 over the **RFC 8785 (JCS)** canonicalisation of the
  *document's* policy; skill narrowing is reported separately as
  `effectiveBudget`/`skillRef`, so a decision joins back to its document.

## RFC-09 — Signed evidence bundles

New published schema `schema/flux-manifest-0.5.0.json` and the reference
tool `scripts/bundle.py`:

```bash
python3 scripts/bundle.py pack   <bundle-dir> -o dist/
python3 scripts/bundle.py verify dist/<name>.flux.tgz
```

- **Deterministic archives** — sorted entries, zeroed mtimes in both the tar
  entries and the gzip header, fixed ownership: identical inputs produce
  byte-identical output.
- **Manifest** — per-file sha256 and a Merkle root built the **RFC 6962**
  way (leaves prefixed `0x00`, interior nodes `0x01`), with the path bound
  into each leaf so swapping two files' contents changes the root.
- **in-toto Statement** — `<bundle>.attestation.json`, so cosign and other
  supply-chain tooling can carry and sign FLUX evidence natively.
- **Attestation** — validator status and document count, Playback scorecards,
  and each seam crossing with its contract digest. `verify` recomputes it from
  scratch, so a manifest cannot claim what the bundle does not contain.
- **Profiles** — an offline bundler attests `core` or `enterprise` only;
  `runtime` requires a live engine and is deliberately unclaimable here.
- **Signing** — detached over the manifest bytes (ssh-keygen -Y, cosign,
  openssl). Because the manifest commits to the Merkle root, one signature
  covers the whole bundle. No key distribution is specified, by design.
- Packing **refuses** to run on a bundle that does not validate.

## Envelope / window

- `fluxVersion` enum widens to `["0.3.0", "0.4.0", "0.4.1", "0.5.0"]`.
- `$id` → `flux-schema-0.5.0.json`; `flux-schema-latest.json` aliases 0.5.0;
  UI hints regenerate as `flux-ui-hints-0.5.0.json`.
- Regression suite: 97 → **132 checks**.
- `verify` re-derives `schemaId` and `fluxVersions` as well as the attestation,
  budgets declared sizes before extracting, refuses symlinks/devices/duplicates
  and any member outside the bundle directory, and reports every malformed
  input as `[FAIL]` rather than a traceback.
- RFC-03 lockfile and RFC-06 contract digests also move to RFC 8785 (JCS);
  the example bundle's digests are regenerated accordingly.
