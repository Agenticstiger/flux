# Changelog

## Unreleased

- **A number that is not finite never satisfies a gate, in the validator or
  in the enforcement gate.** A NaN is neither above nor below anything, so a
  comparison written the other way passes it: `credibility: .nan` satisfied a
  Simulation's `minCredibility`, and a NaN in a weight, a persona's levels or
  its `min` and `max` passed the sum and range checks. `decide` raised
  `FloatDomainError` out of the gate on a policy that held one, and ignored a
  skill whose `tokenBudget` was not a number.
  - `load_yaml_docs` refuses a float that is not finite (`.nan`, `.inf`, or a
    number past what a float holds, such as `1.0e+400`), one that is no decimal
    number (an exponent past what a decimal holds, `0.e-99999999999999999999`)
    and one that needs more than 1,000 digits written out (`1.0e-1001`, and
    `0.e-10000000`, whose scale is spelled in full), as `unreadable YAML` with
    its line and column, in the words of the FLUX engine's read. A zero counts
    the digits its scale spells.
  - Every numeric gate of the validator is written the way a NaN fails it
    (`not x <= limit`, not `x > limit`): the sums of weights, levels and mixes,
    a persona's `min` below `max`, a skill's budget against its policy's, and
    a Simulation's `minCredibility`, which also ignores a credibility that is
    not finite. The validator reads a float, so a sexagesimal number, which the
    engine refuses, still reads here, as a float.
  - `decide` answers where it raised or let a skill through. A policy that
    RFC 8785 cannot write (a number that is not finite, an integer past 2^53-1, a
    key that is not a string, bytes, text that is not valid Unicode, nesting
    too deep) is `INVALID_POLICY`, with the cause in words, and its decision
    names the digest of `{}`, as for a policy that is not an object. A skill
    whose `tokenBudget` is present and not an integer (a NaN, an infinity,
    text, `null`) is `INVALID_POLICY`, where it narrowed nothing, and so is a
    skill that is not an object, where `decide` raised or, for `[]`, `false`, `0`
    and `""`, read it as no skill; `{}` is still a skill that names no budget. An integer budget of
    any size is read as it was, and `min(skill, policy)` still keeps it from
    widening. A request is decided as before. Three new conformance vectors pin
    the skill (37 in all); a number that is not finite has no spelling in JSON
    that every parser reads (some refuse `1e999` as out of range), so the
    reference gate's own checks pin those.
  - `verify` refuses a manifest that holds `NaN`, `Infinity` or a number past
    what a float holds, which JSON does not have.
- **A scalar PyYAML cannot build is unreadable YAML, and `validate`, `pack` and
  `verify` report a hostile bundle instead of raising.** PyYAML raised
  `ValueError` for `!!int abc`, `!!float ZZZ` and an integer of more than 4300
  digits, `IndexError` for `!!int ''`, `KeyError` for `!!bool maybe` and
  `OverflowError` for a sexagesimal float of 175 parts or more, out of a read
  that says it never raises. A document of a shape no check expected, or that
  holds a value JSON has no spelling for, raised from the checks after it.
  - `load_yaml_docs` now reports each of those scalars as `unreadable YAML`,
    placed by line and column, in the words of the FLUX engine's read. An
    integer is too long when its value has more than 4300 digits: a decimal
    spelling is counted before `int()` is called, and a hex, octal or binary
    one, which forms at any length and then broke the first message that
    spelled it, once it is built.
  - RFC 8785 cannot write a NaN or an infinity, an integer past JSON's range, a
    key that is not a string or that UTF-16 cannot hold, or a value JSON has no
    spelling for (`!!binary`, `!!set`). A free-form field of a valid document
    can hold any of them, and the digest of a locked module, and of the
    contract a Simulation emits for its provenance, raised. Such a document is
    now reported once as one that "cannot be digested".
  - YAML can build a string that UTF-8 cannot hold (`"\ud800"`, a lone
    surrogate), and a message that spelled one made `print` raise out of the
    three commands. A line is now written with it as its escape.
  - The checks read fields that no schema describes: a Module's
    `config.measures`, and the FLUID contracts, whose `exposes` and
    `policy.agentPolicy.allowedUseCases` no FLUX schema covers. A value of the
    wrong shape in one raised `TypeError` or `AttributeError`. Each is now read
    where it is: a Module whose `measures` is not a list declares none, a
    contract whose `exposes` is not a list has none, and a contract whose
    `allowedUseCases` cannot be read as a list of names is an error where a
    ConsentProfile gates it, so it is never an allow-list with nothing in it. A
    read that nobody guarded is reported by `Bundle.run()` as the check that
    could not make it, which fails the bundle.
  - `verify` reports an integer of more than 4300 digits in the manifest, which
    `json` refuses with a plain `ValueError`, not a `JSONDecodeError`.
  - A sweep puts 15 shapes in place of every node of an example's contract,
    lockfile and Module configs and runs the checks on them, and a seeded fuzz
    puts a hostile spelling in place of a scalar or a key of an example bundle,
    reads it and, for one case in four, packs it and verifies an archive that
    holds it. Nothing may raise, and no check may report that it could not read
    the bundle. Every bundle that validated before validates the same, apart
    from one that holds an integer of more than 4300 digits, which an
    interpreter set to allow it read.
- **The validator bounds what a YAML document writes out and how deep it
  nests, and caps the messages it prints.** PyYAML builds an alias as a shared
  reference, so a document of a kilobyte could stand for billions of values:
  ten levels of ten aliases write out eleven billion. The schema check walked
  every one of them and the error it raised spelled the value out, so one
  message could run to gigabytes, and `verify` printed it whole. A merge key
  copies the pairs of the mappings it merges as the mapping is built, so ten
  levels of ten merge keys took minutes and gigabytes.
  - `load_yaml_docs` now measures each document once it is composed, before
    anything is built from it. A document that writes out more than 1,000,000
    values once its aliases and merge keys are written out, that nests deeper
    than 64 levels (the document itself being level 1), or that holds itself
    through an alias, is reported as `unreadable YAML`, with its line and
    column. As for a file that is not UTF-8, none of that file's documents is
    returned. These are the bounds the FLUX engine's read holds a document to,
    each counted per document. They apply to every YAML file the validator
    reads: FLUX and FLUID documents and `flux.lock`. A document inside the
    bounds reads as before: every example validates and packs to the same
    bytes.
  - Two more bounds cover what the engine's read does not count. A merge key
    that names empty mappings writes out nothing, yet PyYAML visits each of
    them for every mapping that holds the key: a thousand mappings that each
    merge a list of a thousand empty ones cost a million visits. The merge
    keys of one document may name at most 1,000,000 mappings in all, counted
    once for each mapping that holds the key. And a string is one value
    however long it is, so a document of 58 KB that held 2,000 aliases of one
    50,000 character string made a schema message of 100 MB. A document may
    write out at most 64 MiB of characters, aliases and merge keys written
    out. A document that uses no alias writes out no more than its text
    holds, so only one of that size is refused. A document inside the bound
    on values reaches the bound on merge keys only by naming empty mappings.
  - A validator message keeps at most 1,000 characters, and the name of the
    document it is about 200. A longer one keeps its start and its end around a
    count of what is left out, because jsonschema writes the value it refuses
    first and its verdict last. `scripts/validate.py` and `pack` print no
    message line past 2,000 characters, and neither does `verify`, whatever an
    archive holds: a manifest value, a member path.
- **`verify` reports deep nesting, a NUL byte in a path and a malformed PAX
  header, instead of raising them.**
  - json and PyYAML read a nested array or mapping by recursion. So a pack's
    manifest, or a bundle document, nested past the interpreter's recursion
    limit raised `RecursionError` out of `verify`. Now `verify` reports
    `flux-manifest.json is nested too deeply to read`. The validator reports
    such a document as `unreadable YAML: nested too deeply to read`, in
    `scripts/validate.py` too.
  - A PAX path record holding a NUL byte raised `ValueError` from the
    filesystem as the member was extracted. Such a path is now refused as an
    unsafe archive path before anything is extracted.
  - tarfile raised `ValueError`, not a `ReadError`, for a PAX header it cannot
    parse, such as a malformed GNU sparse map. `verify` now reports that as
    `not a readable gzip archive`.
- **`verify` reports a broken gzip stream, and stops reading headers at its
  caps.** An archive whose gzip stream was cut short raised gzip's `EOFError`
  out of `verify`, and one whose stream was corrupt raised `zlib.error`,
  though `verify` reports every problem and never raises. Both are now
  reported as `not a readable gzip archive`, as a broken header already was.
  `verify` also listed every header of an archive before it checked the member
  cap, so an archive of any number of members was read through in full first.
  It now counts the member and byte caps as it reads each header, and refuses
  the archive at the first header past one. The refusal says `at least`: the
  rest of the archive is not read. An archive within the caps verifies as
  before.
- **The supply-chain check digests each locked document once.** It took a
  versioned ref's target's content digest once per ref, so a bundle of many
  short refs to one large document paid for that document's whole size once per
  ref. Each target is now digested once per check, and every ref is checked
  against that digest as before, with the same errors.
- **The validator reads every file as UTF-8, whatever the host's locale.**
  `flux_spec.validate.load_yaml_docs` opened a bundle's files in the locale's
  encoding, while the FLUX engine reads them as UTF-8 and takes its digests over
  that text. On a host whose locale is not UTF-8, the validator could check
  another document than the one the engine runs: a byte that UTF-8 reads inside
  a comment can end the comment in another encoding, and the rest of its line
  becomes a key the engine never reads. A file that is not UTF-8 is now reported
  as unreadable YAML, instead of raising `UnicodeDecodeError`. The JSON files
  `flux_spec` reads (schemas, a pack's manifest, the enforcement vectors) are
  read as UTF-8 too, and `verify` reports a manifest that is not UTF-8 instead
  of raising. On a UTF-8 host, every bundle that validated before validates the
  same.
- **`Bundle._guarded` is documented as the seam of a subclass that refuses a
  bundle with an exception of its own.** `run()` reports what `load` and each
  check raise, so the FLUX engine's `SeamBundle`, which raises its own refusal
  from `load` and from `check_supply_chain`, overrides `_guarded` to let it out.
  The `Bundle` and `_guarded` docstrings say so, and a regression check holds
  it in place: every step runs through `_guarded`, and a subclass's override
  lets its exception out of `run()`. No behaviour changes.

## 0.5.3 - 2026-11-18

Specification 0.5.3
([schema-diffs/diff-0.5.2-to-0.5.3.md](schema-diffs/diff-0.5.2-to-0.5.3.md)).
The FLUX schema only widens its window. The FLUID 0.7.7 preview is re-pinned
from forge-cli commit `32fce8e3` to `e88301f7` (`vendor/fluid-preview/pins.json`,
sha256 `24c5858a`), and three forge-cli changes reach the vendored schema:

- forge-cli #932 (`4fa06519`): a column may carry `protobuf.field`, its field
  number in the `.proto` forge-cli generates when a topic's value is Protobuf,
  an integer from 1 to 536870911 outside the reserved 19000 to 19999.
- forge-cli #938 (`66dc2088`): a `schemaRegistry` block of kind `confluent` may
  set `rules: true`, which registers the expose's error-severity row checks as
  Confluent data-contract rules. A `glue` block is refused one.
- forge-cli #952 (`e88301f7`): an `enum(...)` level may be a quoted string that
  holds any character but a control character (a comma, a parenthesis, a dot
  and `>` included), with its own quote doubled (`'O''Brien'`), or a word list
  as before. A list that is not comma-separated levels, such as
  `enum('a' 'b')`, `enum(a,,b)` or `enum(a, b,)`, and a quoted level holding a
  control character, such as a tab or a newline, validated under the old pin
  and are refused under the new one.
- **schema**: `schema/flux-schema-0.5.3.json`, with the `fluxVersion` window
  `["0.3.0", "0.4.0", "0.4.1", "0.5.0", "0.5.1", "0.5.2", "0.5.3"]`;
  `flux-schema-latest.json` aliases it, the UI hints regenerate as
  `flux-ui-hints-0.5.3.json`, and `flux_spec.SCHEMA_VERSION` and the package
  version are `0.5.3`.
- **evidence packs**: `verify` checks a pack's 0.7.7 contracts against the
  preview this release carries, so a pack that 0.5.2 made from a contract with
  one of the refused enum lists no longer verifies. Verify it with flux-spec
  0.5.2.
- **policy**: VERSIONING.md says that a preview's pin move does not reset the
  window, even when the new pin refuses what the old one accepted, and that a
  pack it refuses verifies with the release that made it.
- **tests**: the regression suite checks that a 0.7.7 contract, in a bundle
  that pins `fluxVersion: "0.5.2"`, may carry quoted enum levels with
  punctuation, `protobuf.field` and `rules` on a Confluent registry; that enum
  lists which are not comma-separated levels, quoted levels holding a control
  character, a reserved or zero field number and `rules` on a Glue registry
  are refused; that a pack made while the preview admitted `enum('a' 'b')` no
  longer verifies; that a 0.5.2 pack of the example verifies; and that the
  immutable 0.5.2 file refuses `fluxVersion: "0.5.3"`.

## 0.5.2 - 2026-11-17

Specification 0.5.2, additive
([schema-diffs/diff-0.5.1-to-0.5.2.md](schema-diffs/diff-0.5.1-to-0.5.2.md)):

- **seam**: the FLUID 0.7.7 preview, which carries expose relationships
  (composite keys included) and validity windows, is vendored verbatim in
  `vendor/fluid-preview/fluid-schema-0.7.7.json`, pinned in
  `vendor/fluid-preview/pins.json` to forge-cli commit `32fce8e3` and the
  sha256 of its bytes. `Simulation.emits[].fluidVersion` accepts the exact pin
  `"0.7.7"`; a range never selects a preview, and the validator refuses one
  that would, with the fix in the message.
- **schema**: `schema/flux-schema-0.5.2.json`, with the `fluxVersion` window
  `["0.3.0", "0.4.0", "0.4.1", "0.5.0", "0.5.1", "0.5.2"]`;
  `flux-schema-latest.json` aliases it and `flux_spec.SCHEMA_VERSION` is
  `0.5.2`. The package version is `0.5.2`.
- **tooling**: `scripts/sync-fluid-preview.py` re-creates every preview from
  its pin and checks the sha256 (`--repin VERSION COMMIT` moves a pin), and a
  CI job fails when the committed copy differs from what the pin names. The
  wheel ships the previews under `flux_spec/data/vendor/fluid-preview/`.
- **docs**: VERSIONING.md says how a FLUID preview is vendored, selected,
  re-pinned and replaced by its release.
- **tests**: the regression suite checks the pin (bytes, commit, path, one pin
  per file), the exact 0.7.7 pin, a 0.7.7 contract with a composite-key
  relationship, a broken one, the range refusal, a 0.7.6 contract that uses
  relationships, a moved key changing the contract digest, and that the
  immutable 0.5.1 file still refuses the pin.

- **examples**: the towers contract declares `tenancy_count`,
  `chronic_sla_breaches` and `months_to_lease_expiry` as `INTEGER` instead of
  `DECIMAL(10,0)` and `DECIMAL(6,0)`, and `simulation.flux.yml` re-pins its
  `provenance.contractDigest`. The decimal types were a workaround for an
  engine that refused a drawn count in an `INTEGER` column;
  [flux-engine#19](https://github.com/Agenticstiger/flux-engine/pull/19)
  removes that limit.

- **bundle**: `verify` re-validates a pack against the schema its manifest's
  `schemaId` names, when that schema is inside the compatibility window, so a
  pack made by flux-spec 0.5.0 or 0.5.1 verifies under this release without a
  re-pack (a re-pack would break a detached signature over the manifest).
  Until now `verify` refused every `schemaId` but the current one, so each
  release broke the packs made by the one before, every `fluxsim ship`
  archive included. An id outside the window is refused with the versions the
  toolchain accepts, and the `[ok]` report names the schema it re-validated
  against. VERSIONING.md states the rule. The regression suite packs the
  example the way 0.5.0 and 0.5.1 did and verifies it, checks that the named
  schema is the one applied, and refuses the 0.2.0 draft, a newer release and
  a reset window; each archive attack now checks the reason it was refused.
  The wheel smoke test checks that the installed package ships every schema
  in the window.
- **bundle**: `pack` refuses a bundle that holds a symlink, before it reads
  anything, the way `verify` refuses a link inside an archive and flux-engine
  refuses one before it packs. `pack` used to read through a linked file, so
  the target's bytes (an ssh key, a `.env`) went into the archive, and it left
  a linked directory out without a word. It also opens `flux-manifest.json`
  with `O_NOFOLLOW` where the platform has it, so a link that appears after
  that check fails the pack instead of overwriting the file it points to, and
  a manifest it cannot write is a `[FAIL]` line, not a traceback. A manifest
  it creates is owner-only (0600); the archive entry keeps its fixed mode.
- **tests**: `verify`'s refusals of an archive member with `..`, an absolute
  path, a symlink, a hard link, a FIFO or a file beside the bundle directory,
  and of an archive above the member cap, are each pinned by their message.
  Until now none of them was exercised.

## 0.5.1 - 2026-11-12

Specification 0.5.1, additive
([schema-diffs/diff-0.5.0-to-0.5.1.md](schema-diffs/diff-0.5.0-to-0.5.1.md)):

- **seam**: FLUID 0.7.6 is vendored (`vendor/fluid/fluid-schema-0.7.6.json`,
  verbatim from FLUID), and `Simulation.emits[].fluidVersion` accepts the
  exact pin `"0.7.6"`.
- **schema**: `schema/flux-schema-0.5.1.json`, with the `fluxVersion` window
  `["0.3.0", "0.4.0", "0.4.1", "0.5.0", "0.5.1"]`; `flux-schema-latest.json`
  aliases it, and `flux_spec.SCHEMA_VERSION` and the package version are
  `0.5.1`.
- **examples**: `examples/towers-tenant-renewal/`, tenant renewal risk at a
  tower company, emitting for a FLUID 0.7.6 contract.
- **tests**: the regression suite checks the exact 0.7.6 pin, the towers
  bundle, a broken 0.7.6 contract, and that the immutable 0.5.0 file still
  refuses the pin.

## 0.5.0.post1 - 2026-11-11

Packaging only. The specification and the schema are unchanged:
`flux_spec.SCHEMA_VERSION` stays `0.5.0` and `schema/flux-schema-0.5.0.json` is
still the current schema. A `.postN` release republishes the same specification
with corrected package metadata (see [VERSIONING.md](VERSIONING.md)).

- **packaging**: the package page on PyPI now says `pip install flux-spec` and the
  `python3 -m flux_spec.validate|enforce|bundle` modules, where 0.5.0 still said
  "not yet on PyPI". `flux_spec` is the importable package behind
  `scripts/validate.py`, `scripts/enforce.py` and `scripts/bundle.py` (thin shims,
  no behaviour change); 0.5.0 was its first upload, on 2026-11-11.
- **release**: the release workflow accepts a `vX.Y.Z.postN` tag. It checks the full
  version against `pyproject.toml` and `flux_spec.__version__`, and the version
  without `.postN` against `SCHEMA_VERSION` and the schema file. A plain `vX.Y.Z`
  tag is checked as before, and `tests/test_release_guard.py` runs the guard
  against both.
- **docs**: an Engine section (`/engine/`) with the documentation of the FLUX
  Simulation Engine, copied from its repository
  (`Agenticstiger/flux-engine`). The README, the guide and the roadmap pages now
  point at the published packages and the current version.

## 0.5.0 — 2026-08-20

Additive; ships RFC-04 and RFC-09 — **all nine vNext RFCs are now shipped**
([schema-diffs/diff-0.4.1-to-0.5.0.md](schema-diffs/diff-0.4.1-to-0.5.0.md)):

- **RFC-04 — enforcement decision contract**: `schema/flux-enforcement-0.5.0.json`,
  the reference gate `scripts/enforce.py`, and 34 published conformance
  vectors pinning allow/reasonCode/policyDigest. Normative check order,
  fail-closed defaults (off-spec policies are rejected, not reinterpreted),
  JSON-semantic integers, NFC-normalised identifiers, skills that narrow but
  never widen, and RFC 8785 (JCS) canonical digests. A meta-test asserts six
  deliberately-broken gates fail the suite.
- **RFC-09 — signed evidence bundles**: `schema/flux-manifest-0.5.0.json` and
  `scripts/bundle.py`. Deterministic archives, per-file digests, a Merkle
  root, and an attestation `verify` recomputes from scratch. Detached
  signing over the manifest; offline bundlers never claim the runtime profile.
- `fluxVersion` window `["0.3.0", "0.4.0", "0.4.1", "0.5.0"]`; regression
  suite grows to 132 checks; CI runs the vectors and a bundle round-trip.
- Prior art adopted rather than reinvented: RFC 6962 Merkle domain separation,
  RFC 8785 canonical JSON, reproducible-builds.org archive recipe, in-toto
  Statements, and Cedar's authorization model. New dependency: `rfc8785`.

## 0.4.1 — 2026-08-20

Additive; ships RFC-05 and RFC-06
([schema-diffs/diff-0.4.0-to-0.4.1.md](schema-diffs/diff-0.4.0-to-0.4.1.md)):

- **RFC-05 — credibility scorecard**: `Playback.spec.scorecard` (grade A–F,
  interval coverage, required `credibility`) plus the seam gate
  `emits[].minCredibility` — an untrustworthy twin cannot ship a contract.
- **RFC-06 — seam ranges + provenance**: `fluidVersion` accepts semver ranges
  resolved against the vendored set; `emits[].provenance.contractDigest`
  binds the proven contract bytes to the shipped ones (validator-enforced),
  `outputDigest` reserved for engine attestation.
- `fluxVersion` window `["0.3.0", "0.4.0", "0.4.1"]`; regression suite grows
  to 97 checks.

## 0.4.0 — 2026-08-19

Additive; ships the first five vNext RFCs
([schema-diffs/diff-0.3.0-to-0.4.0.md](schema-diffs/diff-0.3.0-to-0.4.0.md)):

- **RFC-01 — trait distributions**: Persona traits are scalars or typed
  categorical / bounded-normal distributions, validator sum- and bounds-checked.
- **RFC-02 — versioned extension port**: optional `extensions` envelope
  object keyed by `<reverse-dns>/<major>` namespaces (or `x-*`); dialects
  extend legally while the core stays closed.
- **RFC-03 — module supply chain**: `ref@semver-range` on moduleRefs/modules,
  envelope `version`, and a `flux.lock` binding every versioned ref to an
  exact version + content digest (validator-enforced).
- **RFC-07 — semantic-model port**: `semanticRef` on Experiment metrics,
  resolved against measures declared by a Module binding `ossie-model`.
- **RFC-08 — UI hints**: generated `schema/flux-ui-hints-0.4.0.json` for
  form-based authoring tools.
- `fluxVersion` window `["0.3.0", "0.4.0"]` — every 0.3.0 document stays
  valid; regression suite grows to 85 checks.

## 0.3.0 — 2026-07-27

First open-source release (Apache 2.0). Breaking rework of the pre-release
0.2.0 draft; full details in
[schema-diffs/diff-0.2.0-to-0.3.0.md](schema-diffs/diff-0.2.0-to-0.3.0.md).

Highlights:

- **FLUID seam rebuilt**: `Simulation.emits[]` now references a `.fluid.yml`
  contract (`productRef` + `exposeId` + pinned `fluidVersion`) validated
  against vendored FLUID schemas, replacing an embedded stub whose required
  `promise` field never existed in FLUID.
- **Hard validation**: JSON Schema 2020-12, closed objects everywhere,
  `required: ["kind"]` dispatch, typed refs, floors and patterns throughout.
- **Envelope aligned with FLUID**: top-level `id`/`name`, required
  `metadata.owner`, camelCase.
- **Paper promises delivered in schema**: root-level `agentPolicy` + `skills`
  on every kind, `sovereignty`, Simulation composition refs, fidelity modes,
  golden-regression anchor, CloudEvents attributes on Signal, `Module.binds`
  ports, Playback calibration + drift.
- **Offline reference validator** (`scripts/validate.py`) and a 61-check
  regression suite pinning every closed gap.

## 0.2.0 — pre-release draft

Internal draft described by the July 2026 position paper. Never released.
Preserved at `schema/flux-schema-0.2.0.json` for the diff record.
