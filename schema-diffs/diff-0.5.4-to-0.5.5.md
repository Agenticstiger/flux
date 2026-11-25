# FLUX Schema Diff: 0.5.4 → 0.5.5

**The FLUX schema only widens its window; the FLUID 0.7.7 preview moves to a
newer pin.** Every FLUX document that validated under 0.5.4 validates under
0.5.5 (regression-asserted). The preview's new pin accepts what the old pin
refused, a versioned table's validity window among it, and refuses three
things the old pin accepted, so a bundle with a 0.7.7 contract can change
result. Under VERSIONING.md (FLUID previews), a pin move ships in a
specification release with this note, and it does not reset the window.

## The FLUID 0.7.7 preview

- `vendor/fluid-preview/fluid-schema-0.7.7.json` moves from
  `Agenticstiger/forge-cli` commit `e88301f72d985a045f88d3ca84fe34367f2934cb`
  to `471c2602bfb1649044fc58fcf2cd0115fa2b6028`, forge-cli's main branch when
  the pin moved, sha256
  `649b9bc59bb509b53d18c2d9ce37fdb253b4da1b88a60191ccf166c4e7fbc0fe`
  (`vendor/fluid-preview/pins.json`). The file is the one forge-cli #1099
  (`18ae44af`) wrote; nothing after it changed the schema. It was re-pinned
  with `scripts/sync-fluid-preview.py --repin 0.7.7 471c2602`, and CI still
  re-creates the file from its pin and fails on any byte difference.
- These forge-cli changes reach the vendored schema:
  - forge-cli #1099 (`18ae44af`): a versioned table's validity window. On the
    `isEnd` dimension, `validityParams.openEnd` is the end an open version
    holds, `null` or a literal of the end column's type, and
    `validityParams.chain` is how a closed version's end meets the same
    entity's next start: `nextStart`, `dayBefore` or `none`. The natural
    entity may carry a `lifecycle` (`activation`, `endMarker`, `currentFlag`,
    the last two a column and a literal, `$defs/columnValue`), and a
    relationship may carry `asOf`, a DATE or TIMESTAMP column of the expose,
    to reach the version valid on it. The old pin refused each of these keys.
  - forge-cli #1056 (`ba7b0758`): `alerts`, the routes that hear about the
    failures, retries, successes and missed SLAs of the DAGs forge-cli
    generates; a route names the scheduler connection that holds its address,
    and no secret.
  - forge-cli #1057 (`99e7b051`) and #1068 (`aa3422e4`): an Iceberg expose's
    `maintenance` (compaction, manifests, snapshot expiry, orphan files and a
    package's actions, on a schedule), with a `runtime` (`$defs/sparkRuntime`)
    for a table no forge-cli build writes, named in place of `build`, never
    beside it.
  - forge-cli #975 (`07ac9da0`), #1015 (`931274a3`) and #1036 (`10da216a`): a
    Spark build may run with `runtime: local`; a stream source may name a
    `deadLetter` sink and a `maxOffsetsPerTrigger`; and an embedded-logic
    build may run a prebuilt PySpark `package` (`$defs/sparkPackage`) in a
    batch Spark build, in place of `sql`, `mapping` and `stream`.
  - forge-cli #984 (`2806623c`): each EMR runtime has its own release label
    form. EMR on EKS names an image of the release, `emr-X.Y.Z-latest` or
    `emr-X.Y.Z-YYYYMMDD`; EMR Serverless and EMR on EC2 name the release,
    `emr-X.Y.Z`. `glueVersion` is refused only beside an EMR runtime.
  - forge-cli #1059 (`44bd291f`), #1062 (`db2ddfa3`) and #1065 (`18674bf8`):
    an Airflow DAG id and task id follow Airflow's own rule: ASCII letters of
    either case, digits, `_`, `.` and `-`, 1 to 250 characters, with nothing
    after the last of them. The old pin took lowercase ids only, with no `.`
    or `-` at either end. `dagId` is optional, and `poolPerOutputTable` puts
    each task that writes an output table in a one-slot pool named after it.
  - forge-cli #958 (`5233b179`): a column type is checked in linear time. The
    pattern accepts the same values as before.
  - forge-cli #1069 (`6b3cd320`): descriptions only.

## What 0.5.4 accepted that 0.5.5 refuses

Each of these validated under 0.5.4 and fails under 0.5.5 with
`fails FLUID 0.7.7 (preview): <path>: ...`:

| Contract | Why the new pin refuses it | Write instead |
|---|---|---|
| An Airflow `dagId` or `taskId` longer than 250 characters | Airflow's own limit | an id of at most 250 characters |
| An Airflow `dagId` or `taskId` that ends with a line break | nothing may follow the id's last character; the old pattern ended in `$`, which a Python validator matches before a final line break | the id without it |
| `runtime: emr-eks` with a `releaseLabel` of the form `emr-X.Y.Z` | EMR on EKS names an image of the release | `emr-X.Y.Z-latest` or `emr-X.Y.Z-YYYYMMDD` |

The refusal names the path. An Airflow block is the contract's
`$.orchestration.airflow` or a build's `execution.orchestration.airflow`, and a
task is in its `tasks` or in a task group's; the Spark label is
`$.builds[i].properties.parameters.spark.releaseLabel`. A contract that
declares a FLUID release, 0.7.3 to 0.7.6, is unaffected: those files are
vendored unchanged.

## Envelope / window

- `fluxVersion` enum widens to
  `["0.3.0", "0.4.0", "0.4.1", "0.5.0", "0.5.1", "0.5.2", "0.5.3", "0.5.4", "0.5.5"]`.
- `$id` → `flux-schema-0.5.5.json`; `flux-schema-latest.json` aliases 0.5.5;
  UI hints regenerate as `flux-ui-hints-0.5.5.json`.
- `Simulation.emits[].fluidVersion` is unchanged:
  `["0.7.3", "0.7.4", "0.7.5", "0.7.6", "0.7.7"]`, and only the exact pin
  `"0.7.7"` selects the preview.
- `flux-enforcement-0.5.0.json` and `flux-manifest-0.5.0.json` are unchanged:
  0.5.5 changes no enforcement or bundle contract.

## Compatibility

- `flux-schema-0.5.4.json` is immutable and refuses `fluxVersion: "0.5.5"`,
  and the two files differ in their id, the version their description names
  and the window alone (regression-asserted).
- A bundle's 0.7.7 contracts are checked against the preview this release
  vendors, whatever `fluxVersion` its FLUX documents pin. A bundle that pins
  `fluxVersion: "0.5.2"` and holds one of the three refused forms validated
  under flux-spec 0.5.4 and fails under 0.5.5; the suite asserts each
  refusal, and that the new pin accepts the keys listed above.
- `verify` re-validates a pack the same way. A pack that flux-spec 0.5.4 made
  from such a contract no longer verifies under 0.5.5: it reports
  `bundle no longer validates against flux-schema-0.5.4.json` and names the
  path (regression-asserted for a DAG id of 251 characters). Verify that pack
  with flux-spec 0.5.4, which carries the old pin. To get a pack that 0.5.5
  verifies, fix the contract and make a new pack, whose manifest needs a new
  signature. A pack whose contracts use none of the refused forms verifies as
  before, and a 0.5.4 pack of the example verifies (regression-asserted).
