# ADR 0009: the statistics are a distribution of their own, flux-stats

## Status

Accepted 2026-11-16. **Amended 2026-11-17:** the record reader's pure half
moves into flux-stats too, as `flux_stats.reading`, and the fidelity block's
grammar follows as `flux_stats.fidelity` (see the amendments below).

## Context

ADR 0003, as amended on 2026-11-16, says the engine never reads a record of
the data a bundle imitates. A separate profiler reads records only where they
live and emits only aggregates. The profiler is the forge-cli extra
`fluid profile`, and it depends on the statistics alone, so the FLUX
repositories hold no data-access code.

The statistics were already one module: `flux_engine.stats` held one definition
per statistic, the column metrics and the profile document reader, and the
fidelity check's statistic and verifier went through it. It imported the
standard library and two kernel modules, `flux_engine.core.errors` (the
`FLX-nnnn` catalog) and `flux_engine.core.fixedpoint` (the fixed-point grid),
and an import-linter contract and a fresh-interpreter test held that closure.
But the only way to install it was to install the engine, with numpy,
pydantic, jsonschema, cryptography, flux-spec and the rest. A profiler that
runs next to the data should carry none of that.

## Decision

1. **Names.** The distribution is `flux-stats` and the import package is
   `flux_stats`. Both names were free on PyPI on 2026-11-16, and they follow
   `flux-spec` and `flux_spec`.
2. **What moves.** `flux_engine/stats` becomes `flux_stats`, and
   `flux_engine/core/fixedpoint.py` becomes `flux_stats.fixedpoint`. The
   catalog mechanism of `flux_engine/core/errors.py` (the bands, `register`,
   `FluxError`) becomes `flux_stats.errors`. `flux_engine.core.errors` stays:
   it re-exports those same objects and keeps the engine's list of the modules
   that own codes (`ensure_core_codes_loaded`). A process therefore holds one
   catalog and one `FluxError` class, every code and message reads as before,
   and `fluxsim explain` is unchanged.
3. **No aliases.** `flux_engine.stats` was never in a release, so nothing
   re-exports it, and `flux_engine.core.fixedpoint` goes with no shim. Each
   statistic has one name.
4. **Layout.** One repository, one uv workspace. `packages/flux-stats` holds
   its own `pyproject.toml`, a `src/flux_stats` package and its own tests. The
   root `pyproject.toml` declares it as a workspace member and resolves the
   engine's requirement to it, and one `uv.lock` covers both. A change that
   touches both lands in one pull request.
5. **Versions.** Lockstep. One `vX.Y.Z` tag releases both distributions at
   `X.Y.Z`, and the engine depends on exactly that release
   (`flux-stats==X.Y.Z`): its verdicts are computed by these definitions, so a
   range would pair an engine with statistics it was never tested with. The
   release guard refuses a tree or a tag where the engine's version,
   flux-stats's version and the pin disagree. The release workflow builds,
   attests and attaches four files, and uploads flux-stats to PyPI before the
   engine.
6. **Enforcement.** import-linter now has both root packages, and its
   flux_stats contract forbids the whole engine and the modules the kernel
   may not use (`random`, `uuid`, `socket`, `time`, `os`, `secrets`, and
   `hashlib`, which stays `core.canonical`'s). The kernel AST scan reads
   flux_stats too. A fresh interpreter that imports `flux_stats` loads nothing
   outside the standard library. The CI job `flux-stats alone` installs the
   wheel and its test group where no engine is installed and runs the
   package's tests. The packaging smoke installs the flux-stats wheel alone,
   with no index, and reads the example profile.

## Prior art

Checked on 2026-11-16 before choosing (search receipts in the pull request):

- **opentelemetry-python** keeps `opentelemetry-api` and `opentelemetry-sdk`
  in sibling directories with one `pyproject.toml` each, declares them in a
  root `[tool.uv.workspace]`, releases them at one version, and pins the API
  from the SDK exactly (`opentelemetry-api == 1.46.0.dev`).
- **pydantic** moved `pydantic-core` into the pydantic repository (the old
  pydantic-core repository is archived), declares it as a workspace member and
  pins it exactly (`pydantic-core==2.50.0`), without matching version numbers.
- **Apache Airflow** declares `airflow-core` and its other distributions as
  members of one root uv workspace.
- **LangChain** keeps `langchain-core` in `libs/core` with its own version and
  depends on it by range (`langchain-core>=1.8.0,<2.0.0`). That is the
  alternative this ADR does not take, for the reason in decision 5.
- The uv workspace documentation (members, `{ workspace = true }` sources, one
  lockfile) and PyPI's Trusted Publishing documentation (one publisher entry
  per project; a pending publisher for a new name reserves nothing).

## Consequences

- `pip install flux-stats` installs the statistics with no third-party
  dependency, once a release carries it. `pip install flux-sim-engine`
  installs both. The engine's core gains no third-party dependency.
- The name `flux-stats` was free on PyPI, and the engine's exact pin would
  have made a squatted release run code on any plain-pip install from source.
  The owner registered it on 2026-11-16, before this change went public, with a
  placeholder 0.0.1 that holds no code. Before the first release that carries
  flux-stats, its trusted publisher has to name this repository's release
  workflow (docs/RELEASING.md).
- Installing from a checkout with pip names the member first
  (`pip install -e packages/flux-stats -e ".[dev]"`); `uv sync` needs nothing
  extra. CI, the nightly and the release workflow do the former.
- mutmut 3.8.1 names a mutant by its path and strips only a `src/` prefix, so
  the weekly run mutates flux-stats from `packages/flux-stats`, against that
  package's own tests, and the engine's modules from the root as before. The
  floors of `flux_stats.fixedpoint`, `flux_stats.definitions` and
  `flux_stats.registry` are now held by the suite that ships with the package.
- flux-stats supports Python 3.10 and newer, one release below the engine's
  floor (founder, 2026-11-16): `fluid profile` runs inside forge-cli, which still
  supports 3.10. The CI job `flux-stats alone` runs on 3.10, so nothing newer
  creeps in, and the floor rises when forge-cli drops 3.10.
- `--committed-slice`, the engine's one path that reads records, stays in the
  engine until `fluid profile` can profile a slice file.

## Amendment of 2026-11-17

The founder decided on 2026-11-17 that the record reader's pure half moves
too, in a pull request of its own after the first.

1. **What moves.** `flux_stats.reading` holds how the fidelity check reads a
   record: the cell a column names, refusing an absent column (`cell`); a
   number as the exact rational it spells (`exact`); a range column's value,
   a number or an instant (`read_exact`), checked against the declared range
   and put on the grid (`encode_value`); a category as its NFC string
   (`category`); the declared levels in their one order (`level_cells`); the
   null policy (`NullPolicy`, `read_column`, `read_pairs`); and the groups
   (`group_keys`, `UNGROUPED`). With it go `nfc` and `parse_rfc3339_ms`,
   which it calls, `ValueDomain`, and the two codes it raises that the engine
   registered, `FLX-5022` and `FLX-5031`, with their titles and explanations
   unchanged. Each function asks a column only for what it reads: a name
   (`NamedColumn`) to read a cell or a category, a name and a domain
   (`ValueColumn`) to read a range column's value, and the five attributes of
   `Column` for the record-set readers. No signature carries one of the
   engine's compiled types, and a profiler, which declares no range, reads a
   value without inventing one.
2. **What stays.** The engine's names for these are imports of the same
   objects: `parse_rfc3339_ms` and `FLX_5022` in `flux_engine.core.clock`,
   `nfc` in `flux_engine.core.canonical`, `NullPolicy` and `ValueDomain` in
   `flux_engine.concordance.predicate`, `FLX_5031` in
   `flux_engine.concordance.errors`, and `encode_value`, `level_cells`, `Row`
   and `UNGROUPED` in the boundary's statistic module. Some forty engine
   modules and tests call them, and keeping the names keeps one
   implementation without touching any of them, as `flux_engine.core.errors`
   does for the catalog. Which columns a property reads and which definition
   measures them stays in the engine (`compute_property_statistic`), and so
   does the boundary, which reaches the records.
3. **One change of behaviour.** `parse_rfc3339_ms` reads the pattern's groups
   into the `datetime` constructor instead of calling
   `datetime.fromisoformat`, whose accepted forms differ between Python
   versions: 3.10 refuses `Z` and a fraction of other than 3 or 6 digits, and
   3.14 accepts hour 24. On 3.11 to 3.13, the versions the engine is tested
   on, it returns what it returned before, value for value and refusal for
   refusal, on the 198,219 inputs of the pull request's differential check,
   and it returns the same on 3.10 and 3.14. A date-time whose instant falls
   outside the years 1 to 9999 once moved to UTC
   (`0001-01-01T00:00:00+00:01`) used to escape as an `OverflowError`; it is
   now refused with `FLX-5022`.

Consequences of the amendment:

- `fluid profile` reads a value by calling these functions, so forge-cli
  implements no reading of its own.
- The weekly mutation run mutates `flux_stats.reading` with flux-stats's own
  tests, at the reader's floor of 95%.
- ADR 0003's one exception stands. The boundary still reads committed
  records inside the engine, and the engine depends on flux-stats, so
  installing the engine still installs a record reader.
- Two risks moved with the code. The first is closed: `exact` formed the
  `Fraction` of a decimal before anything bounded its size, so a cell such as
  `1e99999999999` took unbounded time and memory, as it did in the engine's
  reader. Since a follow-up on 2026-11-17, before forge-cli reads with the
  module and before any release carries it, `exact` refuses a number that
  needs more than 1000 digits written out (`FLX-5005`), counted by
  `digits_written_out`, the declaration reader's own count, before forming
  it. The second stays open: `nfc` normalises with the running Python's
  Unicode database (13.0 on 3.10, 16.0 on 3.14), so a string holding a
  character newer than one of two Pythons can be keyed differently by each.
  A follow-up records the Unicode version with a profile and with a run.
- The parser keeps one leniency of the call it replaces, so that no value
  changes: an offset's minutes are added to its hours, so `+00:60` reads as
  `+01:00` where RFC 3339 caps the minutes at 59. Tightening it is a change of
  behaviour of its own.

## Amendment of 2026-11-17: the fidelity block

The founder decided on 2026-11-17 that the fidelity block's grammar moves too,
in a pull request of its own after the reader's.

1. **What moves.** `flux_stats.fidelity` holds how a Simulation's fidelity
   block is read: the expose it is checked against (`ExposeSchema`,
   `DeclaredExpose`, `expose_from_contract`), the closed sets (`ColumnKind`,
   `PropertyKind`, `ToleranceKind`, `FailureAction`), the declarations
   (`Encoding`, `RecordsRange`, `ColumnDeclaration`, `Tolerance`,
   `PropertyDeclaration`, `Budget`, `FidelityBlock`), the one key set of a
   column (`COLUMN_KEYS`), `read_support_levels`, `parse_duration_ms`,
   `require_number_length` and `parse_fidelity_block`. With it go
   `declared_enum_values`, which reads the levels of an `enum(...)` type and
   which `support: declared` calls, and the codes the grammar raises, `FLX-3001`,
   `FLX-5030`, `FLX-5032`, `FLX-5033` and `FLX-5034`, with their titles and
   explanations unchanged. The module takes `nfc` and `parse_rfc3339_ms` from
   `flux_stats.reading` and `FluxError` from `flux_stats.errors`, which are the
   objects the engine already re-exported.
2. **What stays.** The engine's names for these are imports of the same
   objects: every name of `flux_engine.concordance.predicate`, the four codes
   in `flux_engine.concordance.errors`, and `FLX-3001` and
   `declared_enum_values` in `flux_engine.seam.contract`. No engine module or
   test changes its imports. Which columns a property reads and which
   definition measures them stays in the engine (`compute_property_statistic`,
   which also keeps the `records.min` floors and the property ids).
3. **The per-group measurement moves with it.** `measure_group` forms one group
   of one property from the parsed `PropertyDeclaration`, the declared columns
   and the grid: support with its `maxCardinality` refusal, a level histogram
   with its refusal of a value outside the support, a correlation from its
   pairs, and a mean, a histogram on edges put on the grid, or a quantile from
   the encoded values. It was the boundary's `_group_statistic`, which read
   nothing of its compiled property but the declaration. The boundary calls it,
   with the same codes and messages.
4. **No change of behaviour.** The code is moved, not rewritten, and
   `fluxsim explain` prints the same text for each code.

Consequences of the amendment:

- A profiler such as forge-cli's `fluid profile --bundle` reads a Simulation's
  fidelity block with `flux_stats.fidelity` and forms each group of a property
  with `measure_group`, so it implements no parser and no group reader of its
  own.
- The weekly mutation run gains `flux_stats.fidelity`, mutated with
  flux-stats's own tests. Its floor is the 75% target until a first run
  records its kill rate, and it rises when that rate is known.
- `import flux_stats` now loads the module, so every code it registers is in
  the catalog without the engine; the closure a fresh interpreter loads grows by
  one module and stays standard library only.
