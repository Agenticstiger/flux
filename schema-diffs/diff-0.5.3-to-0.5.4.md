# FLUX Schema Diff: 0.5.3 → 0.5.4

**The FLUX schema only widens its window; the validator's input bounds
tighten.** No constraint of the schema changes: the two files differ in their
`$id`, the version in their description and the window (regression-asserted).
The validator, `pack`, `verify` and the reference enforcement gate refuse input
that is outside the JSON data model or past an implementation limit, where
0.5.3 read it, raised on it, or read it as another input. Under VERSIONING.md
(Input bounds), such a change ships in a specification release with this note,
and it does not reset the window. A document that sits inside the bounds
validates as it did under 0.5.3.

## What 0.5.3 accepted that 0.5.4 refuses

Each row was run on both releases. A refusal names its line and column.

| Input | 0.5.3 | 0.5.4 |
|---|---|---|
| `.nan` where a number may stand: a scorecard's `credibility`, a variant weight, a lifecycle mix value, a persona's trait level or `min`, a Simulation's `minCredibility` | read as a NaN. `validate` and `pack` succeed. A NaN `credibility` satisfied the Simulation's `minCredibility`, and a NaN weight, mix or level passed the sum checks | `unreadable YAML: an infinite or not-a-number value has no digest and no ordering` |
| `.inf`, `-.inf`, or a float past what a double holds (`1.0e+400`), in a field the schema does not bound (a Treatment's `ttlHours`) | read as an infinity; `validate` and `pack` succeed | the same refusal. In a field the schema bounds, such as `credibility`, 0.5.3 already refused them |
| a float that needs more than 1,000 digits written out: `1.0e-1000`, `1.0e-1001`, `0.e-10000000` | read; `validate`, `pack` and `verify` succeed | `unreadable YAML: a number that needs more than 1000 digits written out is too long`. A zero counts the digits its scale spells, and `1.0e-999` still reads |
| a float whose exponent is past what a decimal holds: `0.e-99999999999999999999` | read as `0.0` | `unreadable YAML: a scalar read as a float is not a decimal number` |
| an integer spelled in hex that has more than 4,300 decimal digits: `0x` and 4,000 hex digits | read | `unreadable YAML: an integer of more than 4300 digits is too long to read`. A decimal spelling raised on an interpreter's default limit and read on one set to allow it (`-X int_max_str_digits=0`); it is refused on both now |
| a document that writes out more than 1,000,000 values once its aliases and merge keys are written out: 1,100 aliases of a list of 1,000 values | read | `unreadable YAML: a document writes out more than 1000000 values once its aliases and merge keys are written out` |
| a document nested deeper than 64 levels: 70 inline lists | read | `unreadable YAML: a document nests deeper than 64 levels` |
| a document that holds itself through an alias: `&a [*a]` | read; `pack` and `verify` succeed | `unreadable YAML: a document holds itself through an alias` |
| a document whose merge keys name more than 1,000,000 mappings: 1,100 mappings that each merge 1,000 empty ones | read, in two seconds | `unreadable YAML: a document names more than 1000000 mappings in its merge keys` |
| a document that writes out more than 64 MiB of characters: 2,000 aliases of one 50,000 character string | read, from a file of 58 KB; where the schema refused the field, its message spelled the string out, 100 MB | `unreadable YAML: a document writes out more than 67108864 characters once its aliases and merge keys are written out` |
| a bundle file that is not UTF-8, on a host whose locale is not UTF-8: a Latin-1 byte in a comment | read in the locale's encoding; `validate`, `pack` and `verify` succeed | `unreadable YAML: not UTF-8 text`. On a UTF-8 host 0.5.3 raised `UnicodeDecodeError` |
| `decide` of a skill whose `tokenBudget` is present and not an integer: `"unlimited"`, `null`, `true`, `false`, a NaN, an infinity, `1.5` | `ALLOWED`: the skill narrowed nothing | `INVALID_POLICY`: a skill's tokenBudget, when present, must be an integer |
| `decide` of a skill that is falsy and not an object: `[]`, `false`, `0`, `""` | `ALLOWED`: read as no skill | `INVALID_POLICY`: skill must be an object. `{}` is still a skill that names no budget, and no skill is still none |

Every other number is read as before. A bound is a bound on what the document
writes out: a document under 1,000,000 values, 64 levels, 64 MiB and 1,000
digits per number is unaffected, and so is every example bundle.

## What 0.5.3 raised on, and 0.5.4 reports

None of these was accepted. 0.5.3 raised an exception out of `validate`,
`pack`, `verify` or `decide`. 0.5.4 reports the input, or reads it as one that
declares nothing.

| Input | 0.5.3 | 0.5.4 |
|---|---|---|
| a decimal integer of more than 4,300 digits, `!!int abc`, `!!int ''`, `!!float ZZZ`, `!!bool maybe`, a sexagesimal float of 175 parts or more | `ValueError`, `IndexError`, `KeyError` or `OverflowError` | `unreadable YAML: a scalar read as an integer has no integer value` (and the same for a float, a boolean, a number too long) |
| a locked Module whose free-form field holds `!!set`, `!!binary`, a key that is not a string, an integer past 2^53-1 or a lone surrogate | an RFC 8785 error out of `validate` and `pack` | `cannot be digested (RFC 8785)`, once |
| a Module's `config.measures` that is not a list: `measures: 5` | `TypeError` | read as declaring no measure. A document that names a measure of that Module is refused for naming one the bound model does not declare; a bundle that names none reads |
| a FLUID contract whose `exposes`, `agentPolicy` or `agentPolicy.allowedUseCases` has the wrong shape | `TypeError`, `AttributeError` | refused by the contract's FLUID schema or, where no schema constrains it, reported by the check that reads it: a contract whose `allowedUseCases` is not a list of names is an error where a ConsentProfile gates it, never an allow-list with nothing in it |
| a document nested 2,000 levels deep | `RecursionError` | `unreadable YAML: nested too deeply to read` |
| `verify` of an archive whose gzip stream is cut short or corrupt | `EOFError`, `zlib.error` | `not a readable gzip archive` |
| `verify` of an archive with a PAX path that holds a NUL byte, or a malformed PAX header | `ValueError` | `unsafe archive path`, `not a readable gzip archive` |
| `verify` of a manifest nested 100,000 levels deep, one that holds an integer of more than 4,300 digits, or one that is not UTF-8 | `RecursionError`, `ValueError`, `UnicodeDecodeError` | `flux-manifest.json is nested too deeply to read`, `cannot read archive`, `flux-manifest.json is not UTF-8 text` |
| `verify` of a manifest that holds `NaN`, `Infinity` or `1e999` | refused as a schema violation | `cannot read archive: NaN is not JSON` |
| `decide` of a policy that holds a number that is not finite, an integer past 2^53-1, bytes, a key that is not a string or nesting too deep | `FloatDomainError`, `IntegerDomainError`, `RecursionError` | `INVALID_POLICY`, with the cause in words, and the digest of `{}` |
| `decide` of a skill that is not an object and not falsy: `["s"]`, `"s"`, `5` | `AttributeError` | `INVALID_POLICY` |

The tools' own header lines hold a dash, so on a host whose terminal cannot
encode it `pack` and `verify` raise `UnicodeEncodeError` when they print, in
0.5.3 and in 0.5.4. Set `PYTHONIOENCODING=utf-8`.

A message of the validator keeps at most 1,000 characters and the name of a
document 200, and `pack`, `verify` and `scripts/validate.py` print no line past
2,000 characters; 0.5.3 printed a message of 100 MB for a document of 58 KB.

## Where the validator and the engine's read differ

The FLUX engine reads a number exactly, and the validator reads a float. The
validator therefore refuses a number between what a double holds (about
1.8e308) and the 1,000 digits both allow, which the engine reads: it is not
finite as a float, and an infinity would pass a gate. That is fail-closed. A
sexagesimal float such as `1:30.5`, which the engine refuses, still reads in the
validator, as a float.

## Changes that refuse nothing

- The supply-chain check digests each locked document once.
- `verify` stops reading archive headers at its caps: an archive that declares
  300,000 members is refused after 1.7 seconds, not 35, with the same verdict.
- `Bundle._guarded` is documented as the seam of a subclass that must refuse a
  bundle with an exception of its own, and a regression check holds it in
  place. The validator behaves as before.

## Enforcement

- `flux-enforcement-0.5.0.json` is unchanged. The reference gate answers off-spec
  policy and skill input with `INVALID_POLICY` where 0.5.3 raised or read it as
  another input (the two tables above), under the rule that an off-spec policy
  is rejected and not reinterpreted. A request is decided as before.
- The conformance vectors gain three, 37 in all: a skill whose `tokenBudget` is
  text, a skill that is `[]` and a skill that is `false`, each `INVALID_POLICY`
  with the digest of the policy pinned. A number that is not finite has no
  spelling in JSON that every parser reads (some refuse `1e999` as out of
  range), so the reference gate's own checks pin those cases, not the vectors.

## Where each change came from

| Pull request | Change | Where it shows above |
|---|---|---|
| #32 | the validator reads a bundle as UTF-8 on every host | a file that is not UTF-8; a manifest that is not UTF-8 |
| #33 | the supply-chain check digests each locked document once | changes that refuse nothing |
| #34 | `verify` reports a broken gzip stream and stops reading headers at its caps | what 0.5.3 raised on; changes that refuse nothing |
| #35 | `verify` and the validator report deep nesting, a NUL byte in a path and a malformed PAX header | what 0.5.3 raised on |
| #37 | a document is bounded in what it writes out and in its depth, and messages are capped | what 0.5.3 accepted: the aliases, nesting, self-reference, merge key and 64 MiB rows |
| #38 | a scalar PyYAML cannot build is unreadable YAML, and a hostile bundle is reported | what 0.5.3 raised on; the hex integer row |
| #39 | a number that is not finite never satisfies a gate; the enforcement gate answers off-spec policy and skill input | what 0.5.3 accepted: the number and skill rows; what it raised on; enforcement |
| #40 | the guard's docstring and its regression check | changes that refuse nothing |

The other changes since 0.5.3 are documentation: #31 (the engine's pages) and #36 (a link).

## Envelope / window

- `fluxVersion` enum widens to
  `["0.3.0", "0.4.0", "0.4.1", "0.5.0", "0.5.1", "0.5.2", "0.5.3", "0.5.4"]`.
- `$id` → `flux-schema-0.5.4.json`; `flux-schema-latest.json` aliases 0.5.4;
  UI hints regenerate as `flux-ui-hints-0.5.4.json`.
- `Simulation.emits[].fluidVersion` is unchanged:
  `["0.7.3", "0.7.4", "0.7.5", "0.7.6", "0.7.7"]`, and the FLUID 0.7.7 preview
  keeps the pin it has had since 0.5.3.
- `flux-enforcement-0.5.0.json` and `flux-manifest-0.5.0.json` are unchanged.

## Compatibility

- `flux-schema-0.5.3.json` is immutable and refuses `fluxVersion: "0.5.4"`
  (regression-asserted).
- `validate`, `pack` and `verify` apply the bounds to a bundle whatever
  `fluxVersion` its documents pin. A pack that flux-spec 0.5.3 made from a
  document that one of the first table's rows refuses no longer verifies under
  0.5.4: it reports `bundle no longer validates against flux-schema-0.5.3.json`
  and names the document, as with a FLUID preview's pin move. Verify that pack
  with flux-spec 0.5.3, which made it. To get a pack that 0.5.4 verifies, fix
  the document and make a new pack, which needs a new signature.
- A bundle that sits inside the bounds, and every pack made from one, verifies
  as before.
