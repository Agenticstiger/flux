# From your data to a synthetic copy

You have a table of real records and want synthetic rows that follow the same
contract and the same aggregate numbers, made without the engine ever reading
one of those records. This guide takes you there in six steps:

1. install the tools;
2. get a FLUID contract from a data file with `fluid init --discover`;
3. profile the data where it lives with `fluid profile`;
4. write a FLUX Simulation from the profile's numbers;
5. pin the profile's digest in the Simulation;
6. generate the rows with `fluxsim run` and check them with `fluxsim verify`,
   then pack them with `fluxsim ship`.

Two documents travel from the data to the engine: the contract, which holds
the schema, and the profile, which holds aggregates. The engine reads those and
never a record.

::: warning What works today
- `fluid profile` (step 3) and the engine's support for a profile (steps 5 and
  6) are on the `main` branches of forge-cli and flux-engine, not in a release
  yet. The other steps work with the released packages.
- The engine cannot yet pass a run checked against a profile that
  `fluid profile` wrote, so `ship` withholds it. Step 6 says why, and shows how
  to ship today with a slice of your records instead.
:::

## 1. Install

| Package | Latest on PyPI | Used here for | Status |
|---|---|---|---|
| `flux-spec` | 0.5.2 | validating the bundle (the engine installs it) | released |
| `flux-sim-engine` | 0.5.0 | `fluxsim validate`, `run`, `verify` and `ship` | released; the `--profile` option and the `profile` pin are on `main` only until the next release |
| `data-product-forge` | 0.30.1 | `fluid init --discover` and `fluid profile` | `--discover` released; `fluid profile` on `main` only until the next release |
| `flux-stats` | 0.0.1, a placeholder with no code | the statistics behind `fluid profile` and the engine | on `main` only, installed from flux-engine's repository |

The engine needs Python 3.11 or newer. The released packages cover steps 2 and
4, and step 6 with a slice of your records:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install flux-sim-engine "data-product-forge[local]"
```

For steps 3 and 5, and step 6 with a profile, install both tools from `main`,
each in an environment of its own: each installs flux-stats from a commit of its
own. `pip` needs `git` for these.

```bash
python3 -m venv .venv-forge
.venv-forge/bin/pip install "data-product-forge[profile] @ git+https://github.com/Agenticstiger/forge-cli.git"
.venv-forge/bin/pip install -r https://raw.githubusercontent.com/Agenticstiger/forge-cli/main/requirements/flux-stats.txt
```

The second line installs flux-stats at the commit forge-cli names. If it is
missing, `fluid profile` stops before it reads anything and prints the command.

```bash
python3 -m venv .venv-engine
.venv-engine/bin/pip install \
  "flux-stats @ git+https://github.com/Agenticstiger/flux-engine.git#subdirectory=packages/flux-stats" \
  "flux-sim-engine @ git+https://github.com/Agenticstiger/flux-engine.git"
```

With these, run `fluid` from `.venv-forge` and `fluxsim` from `.venv-engine`:
activate one at a time (`. .venv-forge/bin/activate`), or call the command by
its path (`.venv-engine/bin/fluxsim`). The commands below are written bare.
`fluxsim --version` prints 0.5.0 for both engines. `fluxsim verify --help`
lists `--profile` only on the one built from `main`.

## 2. Get a FLUID contract from your data

Put your file in a folder of its own, here `data/orders.parquet`.

::: details No data at hand? Make the file this guide uses first.
The numbers below come from 600 made-up orders. DuckDB comes with
`data-product-forge[local]` and with its `[profile]` extra:

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

*Needs forge-cli from `main` until its next release: run it from `.venv-forge`.*

Run the profiler inside the environment that holds the data. It reads every
record once and writes only aggregates that passed its output checks:

```bash
fluid profile contract.orders.fluid.yaml --expose orders \
    --source data/orders.parquet --out orders.profile.json
```

```text
Profiled exposes[orders]: 4 columns, 13 values published, 7 withheld.
Withheld, by CL_CONF_STATUS code: A (small count) 7.
Wrote /work/orders.profile.json (readable by you alone; read it before you share it).
Pin it in the FLUX Simulation:
  profile: {digest: sha256:0913d5e6103f87bcfb15cf2669c68ee6a85eacf6d7fd2f4dfcc394ab61bb1ad8}
```

Your digest will differ: the document names the forge-cli build that wrote it.
For the sample data, the profile holds these values:

| Column | Published | Withheld |
|---|---|---|
| the table | `rowCount` 600 | |
| `order_id` | `count` 600, `distinctCount` 600 | `nullCount` |
| `country` | `count` 600, `distinctCount` 5 | `nullCount` |
| `amount` | `count` 600, `distinctCount` 10, `min` 10, `max` 100, quartiles 20, 35 and 50, `sum` 27750 | `nullCount` |
| `created_at` | `count` 600, `distinctCount` 310 | `nullCount`, `min`, `max`, quartiles |

Some of that is the output checks at work. Every published count is rounded to
a multiple of 5, so the 4 countries read as 5 and the 12 distinct amounts as
10. A null count of zero is withheld, because a zero counts as disclosive. A
`min`, `max` or quantile is published only when at least 10 records hold that
exact value, and no instant in `created_at` is held by 10 orders.

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

The engine checks a run against a profile, but it does not generate rows from
one yet. You write the declarations, by hand or with a small script: each
published number becomes a declaration, and where the profile withheld a
number, you choose one and say so.

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

*Needs the engine from `main` until its next release: run it from `.venv-engine`.*

Copy the line `fluid profile` printed into the Simulation's
`com.agentics.flux/1` namespace, indented to sit beside `emits`:

```yaml
extensions:
  com.agentics.flux/1:
    profile: {digest: sha256:0913d5e6103f87bcfb15cf2669c68ee6a85eacf6d7fd2f4dfcc394ab61bb1ad8}
    emits:
      orders:
        rows: 600
        # the rest as in step 4
```

The digest is the sha256 of the profile's canonical JSON (RFC 8785), which is
the file exactly as `fluid profile` writes it, so re-indenting the file keeps
its digest. It binds the run to that document: given another profile the plan
refuses to run with FLX-3110, and given none with FLX-3109. Both codes are new
on the engine's `main`, so their pages reach this site with the next release.
flux-sim-engine 0.5.0 accepts the pin but does not read it, and its commands
have no `--profile`.

## 6. Run, verify, ship

*`--profile` needs the engine from `main` until its next release.*

Generate the rows:

```bash
fluxsim run bundle --profile orders.profile.json
```

```text
plan written to .flux/runs/dc7263d0ac826695/plan.json (runId=dc7263d0ac826695, planDigest=sha256:...)
applied to .flux/runs/dc7263d0ac826695 (runDigest=sha256:...)
emitted orders: 600 rows (generator)
run dc7263d0ac826695 complete
```

The run writes under `.flux/runs/` in the current folder. Each row is a JSON
array in the contract's column order:

```console
$ head -n 3 .flux/runs/*/emits/orders.ndjson
["458b8ff82fe5f8beb5720db41dbd4fac","DE","27.05","2026-07-21T23:05:36.517Z"]
["6508878ce94df9745e2ddbd65e1932d0","GB","19.31","2026-07-27T11:47:09.792Z"]
["080cfb50abb80cb40c05483ec254eeaa","DE","16.78","2026-09-24T22:27:28.569Z"]
```

The same bundle gives the same bytes on any machine. Your run id and rows
differ from these, because your contract records the path of your data folder,
and the rows depend on the contract's bytes.

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
  fidelity orders: failed -- 1 fail-closed condition met against the pinned profile
    property 000:mean:amount (mean of amount): refused, not within the declared margin
    refusal FLX-5037 on property 000:mean:amount: the profile holds no mean/1 statistic over this property's columns with its groupBy, bins, levels and level
  scorecard: overall not measured against profile sha256:0913d5e6...
    ...
    shape: no flags in 4 profiled columns (3 tests at 1/1000 per run)
```

Three things happened:

- `rows: ok`: the emitted file reads back, with as many rows as the run
  recorded and one value per contract column.
- The shape flags compared each profiled column with the run, for example its
  distinct count against the one the profile allows, and found nothing unlikely.
- The `mean` property was refused, with FLX-5037. The engine compares a
  property with a statistic the profile carries for it, such as `mean/1` or a
  histogram over the declared bins. `fluid profile` writes the column metrics
  shown in step 3, and none of those statistics yet.

So `ship`, which packs only a run that passed its checks, withholds this one:

```bash
fluxsim ship bundle --run-id "$(ls -t .flux/runs | head -1)" --profile orders.profile.json -o out
```

```text
withheld: orders
  - profile.properties: 1 fail-closed condition met against the pinned profile
  ...
nothing was written to the output directory
FLX-8001: withheld orders
```

### Ship today, with a slice of your records

Until `fluid profile` writes those statistics, the way to an evidence pack is a
committed slice: a file of the records themselves, from which the engine forms
the statistics it compares. The engine then reads those records, which gives up
the aggregate-only path this guide follows, so use it only where the records
may reach the engine, on your own machine for example. It works with the
released packages.

1. Take the `profile:` line out of the Simulation again: while a profile is
   pinned, the check runs against the profile, slice or no slice.
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
   fluxsim ship bundle --run-id "$(ls -t .flux/runs | head -1)" --committed-slice orders=file://$PWD/orders.ndjson -o out
   ```

   ```text
     ...
     rows: ok
     ...
     fidelity orders: passed
   ```

   ```text
   [ok] packed out/bundle.flux.tgz
        ...
   shipped out/bundle.flux.tgz
   ```

The run's mean amount lands within 10% of the records' (45.83 against 46.25 in
our run), so the `mean` property passes and the pack is written.
[Ship with evidence](../engine/how-to/ship-with-evidence.md) says what the pack
holds. Where the records may not reach the engine at all, use the rows without
a pack: they follow the contract and your declarations, and the same bundle
gives the same rows again.

## Next

- [Draw a column given another](../engine/how-to/draw-a-column-given-another.md):
  keep the link between two columns, such as the amounts per country.
- [Use the FLUID seam](../engine/how-to/use-the-fluid-seam.md): pin the
  contract's digest, so a changed contract stops the run.
- [The engine tutorial](../engine/tutorial/first-evidence-pack.md): a whole
  evidence pack in five minutes, from the engine's starter bundle.
- [The FLUID Seam](/flux/concepts/seam): how a Simulation refers to a contract.
