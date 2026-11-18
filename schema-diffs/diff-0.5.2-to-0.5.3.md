# FLUX Schema Diff: 0.5.2 → 0.5.3

**The FLUX schema only widens its window; the FLUID 0.7.7 preview moves to a
newer pin.** Every FLUX document that validated under 0.5.2 validates under
0.5.3 (regression-asserted). The preview's new pin accepts things the old pin
refused, and refuses enum lists that the old pin's looser pattern accepted, so
a bundle with a 0.7.7 contract can change result. Under VERSIONING.md (FLUID
previews), a pin move ships in a specification release with this note, and it
does not reset the window.

## The FLUID 0.7.7 preview

- `vendor/fluid-preview/fluid-schema-0.7.7.json` moves from
  `Agenticstiger/forge-cli` commit `32fce8e3ae0a5bcb104af048a6fc67938c198f31`
  to `e88301f72d985a045f88d3ca84fe34367f2934cb`, sha256
  `24c5858a43b55e03c53080f084384f1157e087b8c806c63acffb64636288ffc4`
  (`vendor/fluid-preview/pins.json`). It was re-pinned with
  `scripts/sync-fluid-preview.py --repin 0.7.7 e88301f7`, and CI still
  re-creates the file from its pin and fails on any byte difference.
- Three forge-cli changes reach the vendored schema:
  - forge-cli #932 (`4fa06519`): a column may carry `protobuf.field`, its field
    number in the `.proto` that forge-cli generates when a topic's value is
    Protobuf. It is an integer from 1 to 536870911, outside 19000 to 19999,
    which Protobuf reserves. The old pin refused `protobuf` on a column.
  - forge-cli #938 (`66dc2088`): a `schemaRegistry` block of kind `confluent`
    may set `rules: true`, which registers the expose's error-severity row
    checks as Confluent data-contract rules. A `glue` block is refused it. The
    old pin refused `rules` on either kind.
  - forge-cli #952 (`e88301f7`): an `enum(...)` type lists its levels
    comma-separated. A level is a word list, as before
    (`enum(IE, United Kingdom)`), or a quoted string that holds any character
    but a control character, with its own quote doubled as in SQL:
    `enum('Dr.', '>10000', 'O''Brien', 'a, b')`. The old pin admitted only
    letters, digits, `_`, `-`, quotes, commas and whitespace between the
    parentheses, so it refused a dot or a `>` in a level.

## What 0.5.2 accepted that 0.5.3 refuses

The new pin reads an `enum(...)` type as comma-separated levels, each a word
list or a quoted string without control characters. The old pin's pattern was
looser, so a 0.7.7 contract with another kind of list validated under 0.5.2
and fails under 0.5.3 with
`fails FLUID 0.7.7 (preview): $.exposes[i].contract.schema[j].type: ... is not valid under any of the given schemas`.
For example:

| Type | Why the new pin refuses it | Write instead |
|---|---|---|
| `enum('a' 'b')` | the levels are not separated by commas | `enum('a', 'b')` |
| `enum(a,,b)`, `enum(,a)` | a level is empty | `enum(a, b)`, `enum(a)` |
| `enum(a, b,)` | a trailing comma leaves an empty level | `enum(a, b)` |
| `enum('a'b)` | text follows a closing quote | `enum('ab')` |
| a quoted level that holds a control character: a tab, a newline, or a C1 control such as U+0085 | a quoted level holds no control character | the level without it, such as `enum('a b')` |

A contract that declares a FLUID release, 0.7.3 to 0.7.6, is unaffected: those
files are vendored unchanged.

## Envelope / window

- `fluxVersion` enum widens to
  `["0.3.0", "0.4.0", "0.4.1", "0.5.0", "0.5.1", "0.5.2", "0.5.3"]`.
- `$id` → `flux-schema-0.5.3.json`; `flux-schema-latest.json` aliases 0.5.3;
  UI hints regenerate as `flux-ui-hints-0.5.3.json`.
- `Simulation.emits[].fluidVersion` is unchanged:
  `["0.7.3", "0.7.4", "0.7.5", "0.7.6", "0.7.7"]`, and only the exact pin
  `"0.7.7"` selects the preview.
- `flux-enforcement-0.5.0.json` and `flux-manifest-0.5.0.json` are unchanged:
  0.5.3 changes no enforcement or bundle contract.

## Compatibility

- `flux-schema-0.5.2.json` is immutable and refuses `fluxVersion: "0.5.3"`
  (regression-asserted).
- A bundle's 0.7.7 contracts are checked against the preview this release
  vendors, whatever `fluxVersion` its FLUX documents pin. A bundle that pins
  `fluxVersion: "0.5.2"` and holds `enum('a' 'b')` validated under flux-spec
  0.5.2 and fails under 0.5.3; the suite asserts the refusal.
- `verify` re-validates a pack the same way. A pack that flux-spec 0.5.2 made
  from such a contract no longer verifies under 0.5.3: it reports
  `bundle no longer validates against flux-schema-0.5.2.json` and names the
  type (regression-asserted). Verify that pack with flux-spec 0.5.2, which
  carries the old pin. For a pack that 0.5.3 verifies, fix the contract and
  make a new pack, whose manifest needs a new signature. A pack whose
  contracts use none of the refused forms verifies as before.
