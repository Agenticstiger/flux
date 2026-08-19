# Runtime & Evidence

Through 0.4.1, FLUX was something you could *check*. From 0.5.0 it is also
something you can **run** and **prove** — the two RFCs that turn a schema into
a substrate.

## Enforcement: policy with teeth (RFC-04)

`agentPolicy` declares what an AI call may do. Declaration alone is a lint:
nothing stops a conforming document from making an off-policy call at
runtime. 0.5.0 adds the missing half — a **normative decision contract** every
conformant gate implements:

```
decide(agentPolicy, request) -> decision
```

The request is `{model, useCase, purpose?, tokens}`; the decision is
`{allow, reasonCode, reason, policyDigest, request}`. Checks run in a fixed
order and **the first failure wins**:

| Order | Reason code | Fires when |
|---|---|---|
| 0 | `INVALID_POLICY` | the policy itself is off-spec — **fail closed** |
| 1 | `INVALID_REQUEST` | the request is malformed |
| 2 | `MODEL_NOT_ALLOWED` | model is outside `allowedModels` |
| 3 | `USE_CASE_DENIED` | use case appears in `deniedUseCases` |
| 4 | `USE_CASE_NOT_ALLOWED` | `allowedUseCases` is declared and the use case is absent |
| 5 | `PURPOSE_REQUIRED` | `purposeLimitation` is on (**default true**) and no purpose was given |
| 6 | `TOKEN_BUDGET_EXCEEDED` | tokens exceed the effective budget |

Three properties turn "implementable" into "portable", and each exists because
a plausible gate gets it wrong:

- **Integers are JSON values, not host types.** JSON Schema `"type": "integer"`
  accepts `200000.0`, so a gate testing `isinstance(x, int)` silently stops
  enforcing budgets on a *schema-valid* policy. Integers above 2^53-1 are
  rejected outright — they cannot cross a JSON boundary without precision loss.
- **Identifiers are normalised.** `useCase` is caller-supplied, so raw equality
  makes a deny-list advisory: `Advertising`, `advertising␠` and a Cyrillic
  homoglyph all slip past. Identifiers are NFC-normalised and stripped before
  comparison; matching is case-sensitive.
- **Off-spec policies are rejected, not reinterpreted.** A missing or
  non-integer `tokenBudget` is `INVALID_POLICY`, never "no budget".

The order is normative because it makes decisions *comparable*: two
independent gates, given the same policy and request, return not just the same
verdict but the same reason. A policy that declares no models permits nothing —
gates **fail closed**.

The evaluation model is deliberately familiar: **default deny** and **forbid
overrides permit** are exactly the semantics of
[Cedar](https://docs.cedarpolicy.com/auth/authorization.html) and
[Open Policy Agent](https://www.openpolicyagent.org/). FLUX diverges in one
place — Cedar's `diagnostics.reason` lists the policy ids that matched, which
suits a general policy language; FLUX has a fixed five-check contract, so a
closed `reasonCode` enum is what makes conformance mechanically testable.

**Skills narrow, never widen.** When a call is made through a skill binding,
the skill's `tokenBudget` becomes the effective budget. It can only be lower:
the document validator already rejects a skill budget above its policy's.

**Every decision is auditable.** `policyDigest` is the SHA-256 of the policy
canonicalised per [RFC 8785 (JCS)](https://datatracker.ietf.org/doc/rfc8785/),
so a Python gate and a JavaScript gate agree byte-for-byte — plain
`JSON.stringify`/`json.dumps` do not, differing on number spelling and
non-ASCII escaping. It digests the **document's** policy, never a synthesised
one: when a skill narrows the budget, the decision records `skillRef` and
`effectiveBudget` alongside, so an auditor can join a decision back to the
document that authorised it *and* see what actually applied.

### Conformance is a test suite, not a claim

The vectors are published:
[`tests/enforcement-vectors.json`](https://github.com/Agenticstiger/flux/blob/main/tests/enforcement-vectors.json)
— 34 cases pinning `allow`, `reasonCode` **and** `policyDigest` across allow
paths, every deny code, budget boundaries, skill narrowing (including a skill
that tries to *widen*), malformed requests, off-spec policies, normalisation
evasions, canonicalisation, and the check-order tie-breaks. Run the reference
gate, or your own:

```bash
python3 scripts/enforce.py                    # the reference implementation
python3 scripts/enforce.py --vectors mine.json
```

A vendor demonstrates RFC-04 conformance by reproducing every vector. That is
what makes "did it pass the gate?" a reproducible fact rather than an opinion.

**The suite is itself tested.** A conformance suite that everything passes
proves nothing, so the regression tests build six gates each carrying one real
defect — a fail-open `purposeLimitation` default, a skill that replaces rather
than narrows the budget, `isinstance(x, int)` budget handling, case-folded
matching, lenient handling of off-spec policies, and a fabricated
`policyDigest` — and assert that **every one fails**. When a vector is added,
that meta-test is what keeps it load-bearing.

## Evidence bundles: proof that travels (RFC-09)

A local `[ok]` convinces the person who ran it. A regulator, a partner, or a
consortium needs something portable:

```bash
python3 scripts/bundle.py pack   examples/telco-payment-recovery -o dist/
python3 scripts/bundle.py verify dist/telco-payment-recovery.flux.tgz
```

`pack` validates the bundle, writes `flux-manifest.json`, and emits a
**deterministic** archive following the
[reproducible-builds.org recipe](https://reproducible-builds.org/docs/archives/):
entries sorted by name (by Unicode code point, so no locale trap), mtime
zeroed in both the tar entries *and* the gzip header, ownership normalised to
`0/0` with empty names, fixed mode, and GNU rather than PAX format — PAX
extended headers can carry `atime`/`ctime`. The same inputs always produce
byte-identical output, so two parties can compare bundles by digest alone.

The manifest carries:

- **per-file sha256** for every file in the bundle;
- a **Merkle root** over the sorted entries, built the
  [RFC 6962](https://datatracker.ietf.org/doc/html/rfc6962#section-2.1)
  (Certificate Transparency) way — leaves prefixed `0x00`, interior nodes
  `0x01`, so an interior hash can never be replayed as a leaf. One deliberate
  divergence: a leaf commits to `path‖0x00‖digest` rather than to file bytes
  alone, because a manifest must bind *which* file has which digest —
  otherwise swapping two files' contents would leave the root unchanged;
- an **attestation** of what the toolchain could actually prove: validator
  status and document count, the Playback scorecards found, and each seam
  crossing with its contract digest.

`verify` re-derives everything the manifest asserts rather than trusting any
of it: every file digest, the Merkle root, the `schemaId`, the `fluxVersions`,
and the attestation itself — a manifest claiming a scorecard the bundle
doesn't contain fails, as does one claiming a `fluxVersion` its documents
don't pin. It needs no engine, no network, and no trust in whoever packed it.

Hostile archives are rejected *before* anything is written to disk: declared
sizes are budgeted first (gzip compresses zeros about 1000:1, so a 500 KB
archive can otherwise claim gigabytes), only regular files are extracted —
never symlinks or devices — and every member must live under one shared
top-level directory, because a member outside it would be extracted but never
digested. Malformed input yields `[FAIL]` with a reason; never a traceback.

### Honest profiles

An offline bundler attests `core` (validator green) or `enterprise`
(validator green *and* a Playback scorecard present). It never attests
`runtime`: [Level 3](/flux/roadmap/profiles) requires a live engine, and
claiming it from a packer would be a lie the format shouldn't let you tell.

### Interop: in-toto attestations

`pack` also writes `<bundle>.attestation.json` — the same claims shaped as an
[in-toto Statement v1](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md),
the format SLSA provenance and cosign already speak:

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [{ "name": "telco-payment-recovery.flux.tgz",
                "digest": { "sha256": "0f964a…" } }],
  "predicateType": "https://agenticstiger.github.io/flux/attestation/v1",
  "predicate": { "profile": "enterprise", "merkleRoot": "sha256:846fd4…", "…": "…" }
}
```

That means existing supply-chain tooling can carry, sign and verify FLUX
evidence without knowing what FLUX is:

```bash
cosign attest-blob --predicate telco-payment-recovery.attestation.json \
  --type https://agenticstiger.github.io/flux/attestation/v1 \
  telco-payment-recovery.flux.tgz
```

(in-toto digests are bare hex keyed by algorithm; the FLUX manifest's own
`sha256:`-prefixed form is internal.)

### Signing is yours

Signatures are detached and transport-agnostic — sign the manifest bytes with
whatever your organisation already runs:

```bash
ssh-keygen -Y sign -f ~/.ssh/id_ed25519 -n flux flux-manifest.json
cosign sign-blob --key cosign.key flux-manifest.json
openssl dgst -sha256 -sign key.pem -out flux-manifest.sig flux-manifest.json
```

Because the manifest commits to the Merkle root, one signature over one small
JSON file covers the entire bundle. FLUX deliberately specifies no key
distribution, no trust store, and no registry: those are organisational
decisions, and a standard that hard-codes them ages badly.
