# From your data to a synthetic copy

You have a table of real records and want synthetic rows that follow the same
contract and the same aggregate numbers, made without the engine ever reading
one of those records. This guide takes you there in six steps:

1. install the tools;
2. get a FLUID contract from a data file with `fluid init --discover`;
3. profile the data where it lives with `fluid profile`;
4. write a FLUX Simulation from the profile's numbers;
5. pin the profile's digest in the Simulation;
6. generate the rows with `fluxsim run`, check them with `fluxsim verify`, and
   pack them with `fluxsim ship`.

Two documents travel from the data to the engine: the contract, which holds
the schema, and the profile, which holds aggregates. The engine reads those and
never a record.

::: tip What a profile checks today
`fluid profile` writes, for each number column, the statistic a FLUX `mean`
property is checked against, unless the output checks withhold it, so this
guide's run is checked and packed against the profile alone. A property that
needs another statistic, such as a `support` property or a mean over a date or
timestamp column, needs `fluid profile --bundle`, which shipped in
data-product-forge 0.32.0. Step 6 shows it, and how to check a property against
a slice of your records instead.
:::

## 1. Install

| Package | Latest on PyPI | Used here for | Status |
|---|---|---|---|
| `flux-spec` | 0.5.4 | validating the bundle (the engine installs it) | released |
| `flux-sim-engine` | 0.10.0 | `fluxsim validate`, `run`, `verify` and `ship` | released; reads a profile from 0.6.0 |
| `data-product-forge` | 0.39.0 | `fluid init --discover` and `fluid profile` | released; `fluid profile` from 0.31.0 |
| `flux-stats` | 0.10.0 | the statistics behind the engine and `fluid profile` | released with the engine, at its version; the `[profile]` extra installs it |

The engine needs Python 3.11 or newer. One environment holds both tools:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install flux-sim-engine 'data-product-forge[profile]>=0.31.0'
```

The `[profile]` extra brings DuckDB, which `fluid init --discover` and
`fluid profile` read files with, and flux-stats, which forms every statistic
the profile holds; the engine uses the same flux-stats. Every command below,
the Python snippets included, runs in this environment.

This environment gets the latest of each: flux-sim-engine 0.10.0,
data-product-forge 0.39.0 and flux-stats 0.10.0. flux-sim-engine 0.10.0 needs
flux-stats 0.10, which the `[profile]` extra of data-product-forge accepts from
0.9 up to 1.0, so the engine and `fluid profile` use the same flux-stats. Every
step of this guide runs on them.

## 2. Get a FLUID contract from your data

Put your file in a folder of its own, here `data/orders.parquet`.

::: details No data at hand? Make the file this guide uses first.
The numbers below come from 600 made-up orders. DuckDB comes with the
`[profile]` extra:

```python
# make_orders.py: run it with `mkdir -p data && python3 make_orders.py`
import duckdb

duckdb.sql("""
    COPY (
        SELECT
            printf('ord-%05d', i) AS order_id,
            ['DE', 'DE', 'DE', 'DE', 'FR', 'FR', 'FR', 'GB', 'GB', 'IE'][i % 10 + 1] AS country,
            CAST([10, 25, 40, 90][i % 4 + 1] + i % 3 * 5 AS DECIMAL(10, 2)) AS amount,
            TIMESTAMP '2026-07-01' + to_hours(i * 7 % 2184) AS created_at
        FROM range(1, 601) AS t(i)
    ) TO 'data/orders.parquet' (FORMAT parquet)
""")
```
:::

Then let forge-cli read its schema:

```bash
fluid init orders --discover "file://$PWD/data"
```

```text
  ✓ contract.orders.fluid.yaml  (4 cols)
✓ Emitted 1 contract(s). Next: `fluid validate <file>`.
```

`--discover` writes one contract per file, with the columns and types it found
and no records. It also records where it found them, the folder's full path.
The project name, `orders`, goes into the product id, `bronze.orders.orders`.
The part the next steps use is the expose:

```yaml
# contract.orders.fluid.yaml (abridged)
fluidVersion: 0.7.6
kind: DataProduct
id: bronze.orders.orders
exposes:
- exposeId: orders
  kind: table
  contract:
    schema:
    - name: order_id
      type: varchar
      required: false
    - name: country
      type: varchar
      required: false
    - name: amount
      type: decimal(10,2)
      required: false
    - name: created_at
      type: timestamp
      required: false
```

Read the contract before you go on, and correct what a schema cannot tell, such
as which columns are required. The
[`fluid init` page](https://agenticstiger.github.io/forge_docs/cli/init.html)
lists every source `--discover` reads.

## 3. Profile the data where it lives

Run the profiler inside the environment that holds the data. It reads every
record once and writes only aggregates that passed its output checks:

```bash
fluid profile contract.orders.fluid.yaml --expose orders \
    --source data/orders.parquet --out orders.profile.json
```

```text
Profiled exposes[orders]: 4 columns, 17 values published, 10 withheld.
Withheld, by the check (CL_CONF_STATUS code): A (small count) 10.
The document writes C for every withheld group and cell of a histogram or a quantile, whatever withheld it, so its code says nothing of its size.
Fidelity statistics: mean/1 of 'amount'; quantile/2 of 'amount' at level 0.25 over 70 bins; quantile/2 of 'amount' at level 0.5 over 70 bins; quantile/2 of 'amount' at level 0.75 over 70 bins, on fractionalBits 16 (the fidelity block must declare the same).
Withheld whole, so a run that checks them scores them censored: quantile/2 of 'created_at' at level 0.25 over 202 bins; quantile/2 of 'created_at' at level 0.5 over 202 bins; quantile/2 of 'created_at' at level 0.75 over 202 bins.
Wrote /work/orders.profile.json (readable by you alone; read it before you share it).
Pin it in the FLUX Simulation:
  profile: {digest: sha256:0370f0ad5869dade208f2e97c11dd1988ba75a78f7ec1e6952b2bb4e480d2158}
```

On data-product-forge 0.39.0 the sample data gives this digest. Other data, or
another release, writes another, because the profile names the build that wrote
it. For the sample data, the profile holds these values:

| Column | Published | Withheld |
|---|---|---|
| the table | `rowCount` 600 | |
| `order_id` | `count` 600, `distinctCount` 600 | `nullCount` |
| `country` | `count` 600, `distinctCount` 5 | `nullCount` |
| `amount` | `count` 600, `distinctCount` 10, `min` 10, `max` 100, quartiles 20, 35 and 50, `sum` 27750, and the statistics `mean/1` and `quantile/2` at the quartiles | `nullCount` |
| `created_at` | `count` 600, `distinctCount` 310 | `nullCount`, `min`, `max`, quartiles, and its `quantile/2` statistics |

Some of that is the output checks at work. Every published count is rounded to
a multiple of 5, so the 4 countries read as 5 and the 12 distinct amounts as
10. A null count of zero is withheld, because a zero counts as disclosive. A
`min`, `max` or quantile is published only when at least 10 records hold that
exact value, and no instant in `created_at` is held by 10 orders.

`mean/1` is what a FLUX `mean` property is compared with: the column's count,
rounded to 5 like every count, and its sum on a grid of 2^-16 steps. The grid
is `--fractional-bits`, 16 unless you give another, and the Simulation's
`encoding.fractionalBits` must be the same (step 4 uses 16). `fluid profile`
writes one, ungrouped, for each number column it profiles, and publishes it
only when the column's count and sum are published. For the same columns it
writes `quantile/2` at the quartiles, which a FLUX `quantile` property is
compared with: it publishes the bin that holds the quantile, not the value
([ADR 0012](../engine/adr/0012-a-quantile-is-published-as-the-bin-that-holds-it.md)),
and withholds it, as here for `created_at`, when the checks do.

::: warning Aggregates only, and no privacy guarantee
The profile holds aggregates and nothing else: no record, no sample of records,
no per-record value. The checks are ACRO's defaults: for example, a count below
10 or a zero is withheld, counts are rounded to 5, and a sum that one or two
records dominate is withheld. They are output-checking conventions, not a
privacy or anonymity guarantee. Read the document before you share it.
:::

The [`fluid profile` page](https://agenticstiger.github.io/forge_docs/cli/profile.html)
has every rule and every source it reads. This profile document is not a
conformance profile, nor the FLUID `data_profile` expose that is proposed for
Playback: [Three things called a profile](/flux/concepts/#three-things-called-a-profile)
tells them apart.

## 4. Write the Simulation from the profile's numbers

The engine checks a run against a profile, and from 0.6.2 it can also write
the declarations from one: `fluxsim init` with `--contract` and `--profile`
writes a bundle whose numbers are each labelled by what they rest on, as
[Write a bundle from a profile](../engine/how-to/write-a-bundle-from-a-profile.md)
shows. Here you write them by hand, or with a small script, to see where each
one comes from: each published number becomes a declaration, and where the
profile withheld a number, you choose one and say so.

| From the profile | Into the Simulation |
|---|---|
| `rowCount` 600 | `rows: 600` |
| `order_id`: 600 distinct values in 600 | `unique: true`: an identifier, which the engine derives and never draws |
| `amount`: `min` 10, `max` 100 | `range: { min: "10", max: "100" }` |
| `amount`: quartiles 20, 35 and 50 | bin edges at 10, 20, 35 and 50, with a quarter of the orders in each of those three bins |
| `amount`: `sum` 27750 over `count` 600 | the top quarter in a bin from 95 to 100, and none from 50 to 95 (see below) |
| `country`: about 5 distinct values, no shares | your choice: the four countries you know, at equal weights |
| `created_at`: `min` and `max` withheld | your choice: the quarter the data covers, which is also the run's `timeBounds` |

The quartiles alone would spread the top quarter evenly from 50 to 100, which
averages 75 and puts the overall mean near 40. The `sum` says the mean is
27750 / 600 = 46.25. Drawn evenly, the three lower quarters average 15, 27.5
and 42.5, so the top quarter must average 4 × 46.25 - 15 - 27.5 - 42.5 = 100:
it sits at the `max`. A bin from 95 to 100 is one way to put it there; any
narrow bin at the top gives a mean close to 46.25.

The bundle is a folder of four files. Copy the contract into it, and keep the
data and the profile outside it: a bundle holds only its FLUX and FLUID
documents.

```text
bundle/
  contract.orders.fluid.yaml
  world.flux.yml
  persona.flux.yml
  simulation.flux.yml
```

Every run needs a World with a `vertical` (the engine ships `telco` and
`towers`) and at least one Persona. Here all four columns come from the
Simulation's declarations, so neither changes the rows: a World with another
vertical and size, and a Persona with other traits, give the same bytes.

```yaml
# bundle/world.flux.yml
fluxVersion: "0.5.0"
kind: World
id: orders-world
name: Orders World
metadata:
  owner:
    team: data-platform
spec:
  seed: 42
  vertical: telco
  population:
    size: 600
    lifecycleMix: { active: 1.0 }
```

```yaml
# bundle/persona.flux.yml
fluxVersion: "0.5.0"
kind: Persona
id: persona-buyer
name: Buyer
metadata:
  owner:
    team: data-platform
spec:
  traits:
    digitalFluency: 0.5
```

The Simulation carries the declarations in the engine's extension namespace,
`com.agentics.flux/1`, keyed by the expose they describe:

```yaml
# bundle/simulation.flux.yml
fluxVersion: "0.5.0"
kind: Simulation
id: sim-orders
name: Synthetic orders
metadata:
  owner:
    team: data-platform
extensions:
  com.agentics.flux/1:
    emits:
      orders:
        rows: 600
        fidelity:
          encoding: { fractionalBits: 16, rounding: floor }
          records: { min: 10, max: 100000 }
          columns:
            order_id:
              unique: true
            amount:
              range: { min: "10", max: "100" }
              bins: ["10", "20", "35", "50", "95", "100"]
              binWeights: ["1", "1", "1", "0", "1"]
              null: fail
            country:
              support: { values: ["DE", "FR", "GB", "IE"] }
              levels: { DE: "0.25", FR: "0.25", GB: "0.25", IE: "0.25" }
              maxCardinality: 8
              null: fail
            created_at:
              range: { min: "2026-07-01T00:00:00Z", max: "2026-09-30T23:59:59Z" }
              null: fail
          properties:
            - { property: mean, column: amount, tolerance: { type: relative, value: "0.10" } }
          budget: { maxChecksPerState: 20, maxStateAge: P30D }
          failureAction: withholdBundle
spec:
  worldRef: orders-world
  fidelity: deterministic
  seed: 42
  timeBounds: { start: "2026-07-01T00:00:00Z", end: "2026-09-30T23:59:59Z" }
  personaRefs: [persona-buyer]
  emits:
    - productRef: bronze.orders.orders
      exposeId: orders
      fluidVersion: "^0.7.3"
```

A few of those keys need a word:

- `encoding` is the profile's own, so the two compare on the same grid.
- `records` bounds how many records a compared group may hold.
- A fidelity block needs at least one property. The `mean` property says the
  run's mean `amount` must be within 10% of the data's.
- Numbers are strings, exact decimals, and the weights of `levels` add up to 1.

```bash
fluxsim validate bundle
```

```text
bundle: valid -- 3 FLUX document(s), 1 FLUID contract(s), 1 Simulation(s)
```

::: details Or let a script write what the profile can answer
This prints the declarations the published values support, and says which
values you have to choose yourself. It writes the quartile bins; the step from
the `sum` above is yours.

```python
# declare.py: python3 declare.py orders.profile.json orders
import json
import sys

profile, expose = json.load(open(sys.argv[1])), sys.argv[2]
table = profile["tables"][expose]


def value(metrics, name):
    metric = metrics.get(name, {})
    return metric.get("value", metric.get("values")) if metric.get("status") == "F" else None


print(f"rows: {table.get('rowCount', 'withheld: choose one')}")
for name, column in table["columns"].items():
    metrics = column.get("metrics", {})
    count, distinct = value(metrics, "count"), value(metrics, "distinctCount")
    low, high, quartiles = value(metrics, "min"), value(metrics, "max"), value(metrics, "quantiles")
    print(f"{name}:")
    if count is not None and distinct == count:
        print("  unique: true")
    elif column["domain"] != "number" or low is None or high is None:
        print(f"  # a {column['domain']}, about {distinct} distinct values: your choice")
    else:
        levels = sorted(quartiles or {}, key=float)
        edges = [low] + [quartiles[level] for level in levels] + [high]
        bins, weights, carried = [low], [], 0
        for edge in edges[1:]:  # a quantile equal to the edge before it adds to the next bin
            carried += 1
            if edge != bins[-1]:
                bins.append(edge)
                weights.append(carried)
                carried = 0
        if weights:
            weights[-1] += carried
        print(f'  range: {{ min: "{low}", max: "{high}" }}')
        if len(bins) > 1:
            print("  bins: [" + ", ".join(f'"{edge}"' for edge in bins) + "]")
            print("  binWeights: [" + ", ".join(f'"{weight}"' for weight in weights) + "]")
```

```text
rows: 600
amount:
  range: { min: "10", max: "100" }
  bins: ["10", "20", "35", "50", "100"]
  binWeights: ["1", "1", "1", "1"]
country:
  # a category, about 5 distinct values: your choice
created_at:
  # a timestamp, about 310 distinct values: your choice
order_id:
  unique: true
```
:::

## 5. Pin the profile's digest

Copy the line `fluid profile` printed into the Simulation's
`com.agentics.flux/1` namespace, indented to sit beside `emits`:

```yaml
extensions:
  com.agentics.flux/1:
    profile: {digest: sha256:0370f0ad5869dade208f2e97c11dd1988ba75a78f7ec1e6952b2bb4e480d2158}
    emits:
      orders:
        rows: 600
        # the rest as in step 4
```

The digest is the sha256 of the profile's canonical JSON (RFC 8785), which is
the file exactly as `fluid profile` writes it, so re-indenting the file keeps
its digest. It binds the run to that document: given another profile the plan
refuses to run with [FLX-3110](../engine/reference/errors/FLX-3110.md), and given
none with [FLX-3109](../engine/reference/errors/FLX-3109.md). flux-sim-engine
0.5.0 and earlier accept the pin but do not read it, and their commands have no
`--profile`: use 0.6.0 or later.

## 6. Run, verify, ship

Generate the rows:

```bash
fluxsim run bundle --profile orders.profile.json
```

```text
plan written to .flux/runs/86ef556c067d3a22/plan.json (runId=86ef556c067d3a22, planDigest=sha256:...)
applied to .flux/runs/86ef556c067d3a22 (runDigest=sha256:...)
emitted orders: 600 rows (generator)
run 86ef556c067d3a22 complete
```

The run writes under `.flux/runs/` in the current folder. Each row is a JSON
array in the contract's column order:

```console
$ head -n 3 .flux/runs/*/emits/orders.ndjson
["b6c0f40d5e8728f0344b787a9862436d","FR","97.75","2026-08-07T14:48:13.259Z"]
["fdeed30a5cd97e57affbedb59e991946","FR","48.02","2026-09-20T12:36:08.548Z"]
["0c14a0db78037457eab4a67ef2f7ec54","DE","98.97","2026-07-31T20:29:54.010Z"]
```

The same bundle gives the same bytes on any machine. Your run id, rows and
scores differ from these, because your contract records the path of your data
folder, and the rows depend on the contract's bytes.

Check the run against the contract and the profile. `$(ls -t .flux/runs | head -1)`
names the newest run:

```bash
fluxsim verify bundle --run-id "$(ls -t .flux/runs | head -1)" --profile orders.profile.json
```

```text
reproducible: not checked | validity: not asserted
  ...
  rows: ok
  ...
  fidelity orders: passed -- 1 of 1 declared property within the margin against the pinned profile
  scorecard: overall 0.9916 against profile sha256:0370f0ad... (covers 1 of 4 columns, 0 of 0 relationships)
    dimensions: marginals 0.9916; not measured: structure, joint, crossTable, temporal, invariants, queries, defects
    table orders: 0.9916 (1 of 1 property scored); covers 1 of 4 columns, 0 of 0 relationships
    shape: no flags in 4 profiled columns (3 tests at 1/1000 per run)
```

Three things happened:

- `rows: ok`: the emitted file reads back, with as many rows as the run
  recorded and one value per contract column.
- The `mean` property compared the run's mean `amount` with the profile's
  `mean/1` and landed within its 10% margin. The scorecard turns that into a
  similarity, where 1 is an exact match;
  [SCORECARD-SPEC](../engine/spec/SCORECARD-SPEC.md) defines the scores.
- The shape flags compared each profiled column with the run, for example its
  distinct count against the one the profile allows, and found nothing unlikely.

Pack the run with its evidence:

```bash
fluxsim ship bundle --run-id "$(ls -t .flux/runs | head -1)" --profile orders.profile.json -o out
```

```text
[ok] packed out/bundle.flux.tgz
     ...
shipped out/bundle.flux.tgz
```

The pack holds the rows and the evidence for them, the scorecard included;
[Ship with evidence](../engine/how-to/ship-with-evidence.md) says what is in it.

### When the profile cannot answer a property

`fluid profile` writes one ungrouped `mean/1` for each number column it
profiles, and `quantile/2` at the quartiles, and nothing else the fidelity check
compares. A property that needs another statistic, such as a `support` property over `country` or a `mean` over
`created_at`, is refused against that profile with
[FLX-5037](../engine/reference/errors/FLX-5037.md), which names the statistic the
profile lacks, and `ship` withholds the run.

`fluid profile --bundle`, which shipped in data-product-forge 0.32.0, answers
them. It reads the fidelity block of the bundle's Simulation and writes the
statistic each declared property is compared with: a mean, a histogram over the
declared bins or levels, a support or a quantile, per group where the property
has a `groupBy`. It does not answer a correlation. Declare the properties
first, here a `support` over `country` and a `mean` over `created_at` beside
the `mean` over `amount` in the Simulation of step 4:

```yaml
# under fidelity: in bundle/simulation.flux.yml
properties:
  - { property: mean, column: amount, tolerance: { type: relative, value: "0.10" } }
  - { property: support, column: country, tolerance: { type: count, max: 0 } }
  - { property: mean, column: created_at, tolerance: { type: relative, value: "0.10" } }
```

Then profile again with the bundle:

```bash
fluid profile contract.orders.fluid.yaml --expose orders \
    --source data/orders.parquet --bundle bundle --out orders.profile.json
```

It writes `support/1` of `country` and `mean/1` of `amount` and `created_at`.
Pin the digest it prints in place of the old one, as in step 5, and `verify`
reports `fidelity orders: passed -- 3 of 3 declared properties within the
margin against the pinned profile`.

A `mean` whose sum the output checks withheld, for example because one or two
records dominate it, cannot be scored against any profile, `--bundle` or not.
With this
guide's one property, `verify` then says the pinned profile withheld every group
of every declared property, so nothing was scored, and `ship` withholds the run.

A property the profile still cannot answer, a correlation or one whose
statistic the checks withheld, can be checked against a committed slice
instead: a file of the records themselves, from which the engine forms the
statistics it compares. The engine then reads those records, which
gives up the aggregate-only path this guide follows, so use it only where the
records may reach the engine, on your own machine for example.

1. Take the `profile:` line out of the Simulation: once a profile is pinned,
   `run` and `ship` need it with `--profile`, and with it the check runs
   against the profile.
2. Write the records as one JSON object per line, each decimal as a string and
   each timestamp in RFC 3339 with milliseconds:

   ```python
   # make_slice.py: python3 make_slice.py
   import duckdb

   duckdb.sql("""
       COPY (
           SELECT order_id, country,
                  CAST(amount AS VARCHAR) AS amount,
                  strftime(created_at, '%Y-%m-%dT%H:%M:%S.%gZ') AS created_at
           FROM 'data/orders.parquet'
       ) TO 'orders.ndjson' (FORMAT json)
   """)
   ```

3. Run, verify and ship against the slice:

   ```bash
   fluxsim run bundle
   fluxsim verify bundle --run-id "$(ls -t .flux/runs | head -1)" --committed-slice orders=file://$PWD/orders.ndjson
   fluxsim ship bundle --run-id "$(ls -t .flux/runs | head -1)" --committed-slice orders=file://$PWD/orders.ndjson -o out-slice
   ```

   `verify` reports `fidelity orders: passed`, and `ship` writes
   `out-slice/bundle.flux.tgz`. It packs into a folder of its own: `ship`
   refuses to replace the pack written above in `out`, which holds another
   run's evidence.

Where the records may not reach the engine at all, a property the profile
cannot answer gets no pack: use the rows without one. They follow the contract
and your declarations, and the same bundle gives the same rows again.

A run with neither a profile nor a slice is not checked at all: `fluxsim verify`
says `fidelity orders: declared, not checked -- declares a fidelity block; pass
--committed-slice orders=file://<path> to run the check`, and `fluxsim ship`
withholds the run with `committed-slice.present: orders declares a fidelity
block; ship needs --committed-slice for it`.

## Next

- [Draw a column given another](../engine/how-to/draw-a-column-given-another.md):
  keep the link between two columns, such as the amounts per country.
- [Use the FLUID seam](../engine/how-to/use-the-fluid-seam.md): pin the
  contract's digest, so a changed contract stops the run.
- [The engine tutorial](../engine/tutorial/first-evidence-pack.md): a whole
  evidence pack in five minutes, from the engine's starter bundle.
- [The FLUID Seam](/flux/concepts/seam): how a Simulation refers to a contract.
