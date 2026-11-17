# flux-expr/2: normative specification (v0.1)

**Status: accepted 2026-11-16 ([ADR 0008](../adr/0008-flux-expr-2-derived-columns-and-rules.md)). The engine
implements the language (`flux_engine.expr2`: §2 to §5, §11 and the language's codes of §12), and nothing reads it
yet: generating from rules and checking runs against them (§6 to §10) come next, so nothing here changes what a
bundle does today.**

flux-expr/2 is the expression language FLUX uses for the rules about valid data that a FLUID contract declares, and
for the FLUX-side rules that only a generator needs. Its **core** is FLUID SQL/1, the SQL expression subset defined by
the FLUID RFC `RFC-data-rules.md` (§2) in the forge-cli repository (Agenticstiger/forge-cli#896). flux-expr/2
implements that subset exactly and is spelled as it is: its grammar, names, types, null rules and functions are the
RFC's, and the RFC's conformance vectors decide what the core accepts and means. On top of the core, flux-expr/2 adds
four **extensions** that FLUID SQL/1 leaves out (RFC §2.7): the previous version of an entity, paths over several
links, aggregates over a parent's children written inside an expression, and windows over a row's siblings. A text
that uses an extension is FLUX's, and never sits in a contract; a form the RFC's subset comes to cover is core, not an
extension.

flux-expr/1 ([EXPR-SPEC](EXPR-SPEC.md)) stays valid and unchanged as a language of its own: its sites, its parser, its
texts, its error codes (`FLX-6001` to `FLX-6005`) and its digests. flux-expr/2 is not a superset of it, and a
flux-expr/1 site that later moves to flux-expr/2 rewrites its texts in SQL spelling. Like flux-expr/1, flux-expr/2 is
**closed**: anything outside the core and the extensions is a parse error (`FLX-6103`), never an extension point.
Growth goes to the RFC's next version for the core and to `flux-expr/3` for the extensions.

## 1. Where texts come from

- **The contract.** A FLUID contract declares, under its contract digest, the rules about valid data that FLUX reads
  and never restates:
  - invariants, at `exposes[].contract.invariants[]`, each a `check`, a `derive` with `expr`, a `derive` with
    `aggregate`, or a `dependency`, with an optional `when` and a band of violating rows (RFC §1);
  - identifier formats (RFC §3) and placeholder values (RFC §4);
  - shared attributes, through one link (`sharedColumns`) or several (`sharedAttribute`, RFC §5).

  Their texts are core texts. The contract carries no language key: its `fluidVersion` names the version, and 0.7.7
  carries FLUID SQL/1. Changing any of them changes the contract digest, and the plan refuses until the Simulation
  pins the new digest.
- **The FLUX document.** A bundle's `com.agentics.flux/1` extension holds what the RFC leaves to FLUX (RFC §1.6): the
  column that a `check`'s bounds or difference form generates, where in its band a run generates, how violating
  values are drawn, prefix weights and placeholder rates, distributions, and run settings. It also holds the
  **FLUX-side rules**: a relation that needs an extension cannot sit in a contract, so it is declared here, as an
  entry that names its grammar in a required `language` key:

  ```yaml
  - id: primary_subscription
    language: flux-expr/2
    derive: is_primary
    expr: row_number() OVER (PARTITION BY account ORDER BY start_date, subscription_id) = 1
  ```

  An entry without `language` is `FLX-6101`, and one whose `language` is not `flux-expr/2` is `FLX-6102`. A FLUX-side
  rule says what the contract can say, so it is `FLX-6209` and belongs in the contract, when it uses none of the four
  extensions, or when its whole value is exactly a contract `derive` with `aggregate` (RFC §1.2): a `COUNT`, `SUM`,
  `MIN` or `MAX` of one child column, with an optional filter written in the core and an optional `ifNone`, as §5 maps
  them. The `row.` and `link.` spellings of §3 are not extensions: they only name what the core's bare names and
  one-hop paths name.
- **flux-expr/1 sites.** `Segment.spec.query` under `queryLanguage: flux-expr/1`, Journey guards and trigger
  conditions, Detector predicates and `Playback.spec.personaMapping[].behaviorPattern` keep taking flux-expr/1 only.
- The plan records, for each text, where it came from (the contract and the invariant's `id`, or the FLUX entry) and
  its canonical text (§11).

## 2. Grammar

The core's grammar is the RFC's (§2.1), and flux-expr/2 parses a FLUID SQL/1 text directly, with no second
spelling. The meaning each construct's tree must have is the one RFC §2.9 gives, written there in flux-expr/1's
notation to pin the null rules. The extensions add
these forms to the core's `primary`, in the same SQL spelling:

```text
ext_primary = ext_path | aggregate | window ;
ext_path    = "previous" , "." , name , [ "." , name ]
            | name , "." , name , "." , name , { "." , name }
            | ( "row" | "link" ) , "." , name , { "." , name } ;   (* FLUX-side spellings, section 3 *)
aggregate   = agg_func , "(" , children , [ "," , expr ] , ")" ;
agg_func    = "COUNT" | "SUM" | "MIN" | "MAX" | "AVG" ;
children    = "CHILDREN" , "." , name , [ "." , name ] ;
window      = win_func , "(" , [ expr , { "," , expr } ] , ")" , "OVER" , "(" , win_spec , ")" ;
win_func    = "ROW_NUMBER" | "RANK" | "DENSE_RANK" | "FIRST_VALUE" | "LAST_VALUE" | "LAG" | "LEAD" ;
win_spec    = "PARTITION" , "BY" , ( name | ext_path ) , "ORDER" , "BY" , sort_key , { "," , sort_key } ;
sort_key    = ( column_ref | ext_path ) , [ "ASC" | "DESC" ] , [ "NULLS" , ( "FIRST" | "LAST" ) ] ;
(* expr, name and column_ref are the core's, RFC §2.1; keywords are case-insensitive, as there *)
```

An aggregate is told by its first argument, a children collection. A window word (`OVER`, `PARTITION`, `BY`,
`ORDER`, `ASC`, `DESC`, `NULLS`, `FIRST`, `LAST`) is a keyword only inside a window clause. A window function without
`OVER`, or `OVER` after an aggregate (an aggregate written as a window), is `FLX-6103`; a reserved word used where it
has no meaning is `FLX-6104`. FLUX applies the core's limits and refusals (RFC §2.1) to every text it reads,
a contract's included, because it reads a pinned contract whether or not a validator has run: at most 4,096 code
points after NFC normalization, at most 64 levels of nesting, and no `;`, `--` or `/*` outside a string or a quoted
name. A level is a level of the syntax tree: a literal or a name is one, and every operator, `NOT`, minus, call,
`CASE` and parenthesis adds one to the deepest part it holds, so `(a)` is two levels and a flat chain of 64 `AND`s is
too deep. `ROUND`'s scale is at most 38, the widest decimal scale of DuckDB, Snowflake, BigQuery and Arrow's
decimal128. Both readings are the maintainers' (2026-11-16), and the RFC takes the same ones. A text that breaks one
is `FLX-6103`, and so is a `ROUND` mode other than the grammar's two terminals, `'HALF_AWAY_FROM_ZERO'` and
`'HALF_TO_EVEN'`, in upper case (RFC §2.1).

## 3. The row scope

A text is evaluated for one row of one expose, its **row**. The core reaches the row's own columns by name and one
link's target by `<relationship>.<column>` (RFC §2.2). The extensions reach the rest:

| Path | Reaches |
|---|---|
| `previous.<column>`, `previous.<relationship>.<column>` | the same column, or path, on this entity's previous version |
| `<rel>.<rel>.<column>` | a column through a chain of to-one relationships |
| `link.<rel>.<column>`, `link.<rel>.<rel>.<column>` | the same, written from the `link` root |
| `row.<column>` | a column of this row, written from the `row` root |
| `CHILDREN.<expose>`, `CHILDREN.<expose>.<relationship>` | the rows of `<expose>` whose relationship points to this row, only as an aggregate's first argument (§5) |

- **Links** are the relationships FLUID 0.7.7 declares on an expose (`exposes[].semantics.relationships[]`). As in the
  core, a link whose `fromColumns` are NULL, or match no row, reaches no row, and every path through it is NULL. As in
  the core (RFC §2.2), no path goes through a relationship whose target declares a validity window until a later
  design names the declaring row's time column (`FLX-6106`).
- **`previous`** exists only on an expose whose entity has versions: FLUID names the entity (the expose's `natural`
  entity) and the validity window (two time dimensions with `validityParams` `isStart` and `isEnd`). The previous
  version is the version of the same entity whose validity starts latest before this version's. On the first version
  every `previous` path is NULL. Elsewhere `previous` is `FLX-6106`.
- **`CHILDREN.<expose>`** names the rows of `<expose>` that point to this row through a relationship declared on
  `<expose>`. When `<expose>` has more than one such relationship, the text names one; none, or several and none
  named, is `FLX-6106`, and so is a children collection used as a plain path.
- **Roots.** In a core text, as RFC §2.2 says, a bare name is always a column and `<name>.<column>` always a
  relationship's column, whatever the names, so a column called `link` or `previous` needs nothing. In a FLUX-side
  text, `row`, `link`, `previous` and `CHILDREN` are roots, and a first name that is both a root and a column or
  relationship of the expose is `FLX-6105`: write `row.<name>` for the column or `link.<name>` for the relationship.
  `row.<column>` and a one-hop `link.<rel>.<column>` are the core's bare name and one-hop path, spelled from a root. A
  name that resolves to nothing is `FLX-6113`.

## 4. Types, numbers, nulls and dates

They are the RFC's (§2.3 to §2.6), and the extensions follow them. In short: six types, with no type for the column
types RFC §2.3 lists as none (`FLX-6111`); exact rationals, with `x / 0` NULL and a static scale that a derived value
must fit (`FLX-6110`); two-valued truth, where a comparison with NULL is FALSE and a NULL bool counts as FALSE where a
predicate is expected; `ROUND(x, s)` rounding ties away from zero, and `ROUND(x, s, 'HALF_TO_EVEN')` to the even
neighbor; strings compared by the code points of their stored text; and `DAYS_BETWEEN`, `MONTHS_BETWEEN` and
`YEARS_BETWEEN` in whole units with an explicit as-of date, which agree with DuckDB 2.0.0's `date_sub` on 40,864 pairs
of dates (ADR 0008). Integer digits are not checked statically: a value too large for its column is `FLX-6112` when
the row is made, and a NULL in a column the contract marks required is the seam's own `FLX-3202`. FLUX reads a
`decimal(p,s)` up to p = 1,000, PostgreSQL's numeric limit and the widest decimal any engine FLUID targets declares; a
wider declaration has no type here (`FLX-6111`), so no contract can make a row's fit cost grow without bound.

Where the RFC's words leave a reading open, flux-expr/2 reads FLUID SQL/1 as forge-cli's `fluid-sql-vectors.json`
does, because the vectors define the subset (RFC §2.9, and §11 below). The `NULL` literal takes its type from a typed
operand beside it: an operand of arithmetic or of a date difference, of `IS [NOT] DISTINCT FROM`, or a value of `CASE`,
`COALESCE`, `LAG` or `LEAD`; it adds nothing to a static scale, so `net * NULL` has `net`'s. Where nothing gives it a
type it is `FLX-6104`: an `IN` item or an operand of a comparison or `BETWEEN` (RFC §2.1), the operand of
`IS [NOT] NULL`, of a minus or of `ROUND`, a place a bool is needed (a predicate, an operand of `NOT`, `AND` or `OR`,
a `WHEN` condition, `COUNT`'s filter), a whole text, and every operand of one construct, as in `NULL + NULL`. SQL's
spelled-out `timestamp with time zone` and `timestamp without time zone` read as `timestamptz` and `timestamp`, and
`bit(1)` as `bit`. A string column's placeholders (RFC §4), values and prefixes that stand in for a real value not
known yet, are exempt from its enum, so comparing the column with one is not `FLX-6109`; everywhere else a
placeholder is an ordinary value.

## 5. The extensions' functions

Each aggregate and window is evaluated once per row of its scope, and its result is reused wherever that row needs it
again, so the work is bounded by the rows read times the size of the text, even where two exposes link to each other.
All of them are total: given type-checked arguments they return a value or NULL, and never raise.

### Aggregates over a parent's children

An aggregate is written on the parent. Its first argument is a children collection, and its second, where it takes
one, is evaluated once per child in that child's row scope. A second argument holds no window and no aggregate over
the same collection, though it may aggregate the child's own children
(`SUM(CHILDREN.subscription, COUNT(CHILDREN.invoice))`). Anything else is `FLX-6107`.

| Call | Result |
|---|---|
| `COUNT(c)` | the number of children; 0 when there are none |
| `COUNT(c, p)` | the number of children for which the predicate `p` is TRUE |
| `SUM(c, x)`, `MIN(c, x)`, `MAX(c, x)` | over the values of `x` that are not NULL; NULL when there are none |
| `AVG(c, x)` | the exact quotient of that sum and that count; NULL when there are none |

`COUNT` has scale 0, `SUM`, `MIN` and `MAX` their value's scale, and `AVG` is unbounded. `MIN` and `MAX` take an
orderable value, and `SUM` and `AVG` a number of bounded scale (`FLX-6110` otherwise), so a sum over many children is a
decimal whose length grows with the number of digits of the count, not with the count. A contract's `derive` with
`aggregate` (RFC §1.2) is read as one of these: `<function>(CHILDREN.<from>.<via>, <column>)`, or with a filter
`<function>(CHILDREN.<from>.<via>, CASE WHEN <filter> THEN <column> END)`; a count as `COUNT(CHILDREN.<from>.<via>)`,
or with a filter `COUNT(CHILDREN.<from>.<via>, <filter>)`; and any of them wrapped in `COALESCE(..., <ifNone>)` when
the contract gives an `ifNone`.

### Windows over a row's siblings

A window is written on the child. `PARTITION BY` names a to-one relationship of the row, written `link.<name>` when the
name is also a column (`FLX-6105` if that name is written bare, `FLX-6106` if it names no to-one relationship). The
partition is every row of the row's expose whose relationship points to the same row, and the rows whose relationship
is NULL form one partition, as in SQL. `ORDER BY` lists sort keys of an orderable type. `ASC` is the default, and NULL
sorts last in both directions unless `NULLS FIRST` is written, which is DuckDB's default. Both clauses are required. A
window's arguments hold no window (`FLX-6107`); an aggregate there is evaluated on the sibling row it reads.

| Call | Result |
|---|---|
| `ROW_NUMBER()` | the row's position in the partition, from 1 |
| `RANK()`, `DENSE_RANK()` | SQL's: tied rows share a rank; `RANK` then skips, `DENSE_RANK` does not |
| `FIRST_VALUE(x)`, `LAST_VALUE(x)` | `x` on the partition's first or last row, NULL included |
| `LAG(x, k, d)`, `LEAD(x, k, d)` | `x` on the row `k` places before or after this one; `k` is a positive integer literal (default 1), and `d`, a literal of `x`'s type or NULL (the default), is returned when there is no such row |

Ranks have scale 0, and the value functions have `x`'s type and scale (with `d`'s, for `LAG` and `LEAD`). A call whose
value arguments are all NULL literals has no type (`FLX-6104`, §4). `FIRST_VALUE` and `LAST_VALUE` read the whole
partition, SQL's `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`; SQL's default frame would end at the
current row and make `LAST_VALUE` the current row's value.

**The order must be total where ties would decide the value.** `ROW_NUMBER`, `FIRST_VALUE`, `LAST_VALUE`, `LAG` and
`LEAD` give a value that depends on how tied rows are ordered, and SQL leaves that order arbitrary. For these five, the
sort keys, together with the partitioning relationship's columns, must name every key column FLUID declares for the
expose (its `primary` entity under `exposes[].semantics.entities[]`), so that no two rows tie. Otherwise the plan
refuses with `FLX-6108`, naming the window and the key columns it is missing; an expose that declares no key cannot
order these five at all. `RANK` and `DENSE_RANK` give tied rows the same value whatever their order.

## 6. Rules: one declaration, two uses

A **rule** is a contract invariant (RFC §1), a shared attribute read as a copy (RFC §5, §9 below), or a FLUX-side
rule. FLUX uses each the same way: every run checks it, and where it determines a column, generation sets that column
so that the rule holds. A FLUX-side rule has a contract invariant's shape (`id`, `check` or `derive` with `expr`,
`when`, and a band) and its own `language: flux-expr/2`. Its `id` is an ASCII identifier, unique among the bundle's
FLUX-side rules, and a contract's ids are unique within that contract; FLUX checks both, since it does not assume a
validator ran (`FLX-6201`). A FLUX-side rule's `check` and `when` are bool (`FLX-6206`).

**The rows a rule covers** are the RFC's (§1.3): the rows where `when` is TRUE, or every row without one. Several
`derive` rules may determine one column, all from the contract or all from the bundle (§9); a row is covered by the
first, in declaration order, whose `when` holds, and a row that none covers takes the column's own source (§9).
No other row is left out: a row on which a compared value is NULL is covered and usually violates the rule. A row on
which a bounds or difference form has a NULL bound is covered, cannot hold, and is generated as infeasible (§7).

**Check.** A run is checked rule by rule, as RFC §1.5 counts violating rows: a `check` row violates when its predicate
is not TRUE, a `derive` row when its column `IS DISTINCT FROM` the value (so a NULL copied from a NULL holds), and a
dependency as §8 counts. The count is compared with the rule's band, one ODCS operator with `unit: rows` or
`unit: percent` (RFC §1.4; without one, no row may violate), so FLUX and every other consumer of the contract reach
one verdict. A failing check is a verdict that the check reports per rule and the ship gate uses; it is not a refusal.
`fluid profile` measures a rule on real data with the same definitions, and is where a band such as "98 % of rows"
comes from.

**Generate.** FLUX generates from four forms. A rule of any other form is checked and generates nothing.

| Form | How the column `c` is set |
|---|---|
| `derive: c` with `expr: e` | as a generated column, to the value of `e`, NULL included, which must fit `c` (`FLX-6110`) |
| `derive: c` with `aggregate` | the same, with the summary of §5 as the value |
| a `check` of bounds form, with the FLUX setting naming `c`: one or two comparisons of `c` with expressions that do not read `c`, joined by `AND` | drawn within the interval (below); `c` is a number, a date or a timestamp |
| a `check` of difference form, with the FLUX setting naming `c`: `k = DAYS_BETWEEN(c, x)`, `k = DAYS_BETWEEN(x, c)`, and the same with `MONTHS_BETWEEN` and `YEARS_BETWEEN` | drawn within the dates for which the difference is `k`, which form an interval |

A bounds or difference value is the second draw of the rule's stream (§7). With declared statistics for `c`, it is
their inverse CDF over the interval for a continuous family (one uniform, as KERNEL-SPEC §4's truncated draws do), or
their levels or bins inside it for a categorical or a histogram. Without them, it is uniform over the interval at the
column's grain (a day for a date, a millisecond for a timestamp, the column's scale for a number), which needs both
ends; an interval open on one side with nothing declared is `FLX-6205`. A FLUX setting that names a column for any
other form of `check` is `FLX-6202`, and so is one whose value side or `when` reads `c`. Rules and dependencies that
reach their own columns through each other form a cycle (`FLX-6208`). When a row's interval is empty, because a bound
is NULL or the bounds cross, or `c`'s statistics put no weight in it, the row cannot hold: it is generated as a
violation (§7) and traced as infeasible.

Each relation below is one rule. The first four are contract invariants; the last three are FLUX-side, because each
needs an extension (a sum of an expression, not of a column, is one no contract `aggregate` writes):

```text
derive: gross       expr: ROUND(net * (1 + tax_rate), 2)
check: activation_date <= first_use_date AND first_use_date <= min_term_end   (generates first_use_date)
derive: age         expr: YEARS_BETWEEN(birth_date, snapshot_date)
derive: is_fast     expr: speed_mbps > product.speed_threshold_mbps
derive: is_primary  expr: ROW_NUMBER() OVER (PARTITION BY account ORDER BY start_date, subscription_id) = 1
derive: line_value  expr: SUM(CHILDREN.invoice_line, quantity * unit_price)
derive: prior_plan  expr: previous.plan_code
```

## 7. Shares below 100 %

A rule whose band allows violating rows is generated at a **target** inside the band: the share of covered rows that
violate it in expectation. The target is the FLUX setting for that rule, which may come from a profile, or the middle
of the band when the bundle sets none; it must lie strictly inside a `percent` band (`FLX-6204` otherwise). Three bands
cannot be met in expectation: a zero-width `percent` band above 0, a `rows` band other than zero violations, and a
dependency band that allows no holding share above one half. FLUX checks such a band and generates no violation for
it, and under a strict run it refuses one that zero violations would fail (`FLX-6204`).

- **The rule's stream.** A rule draws on one stream per row, `<row path> + ("rule", R)`, where `<row path>` is the row's
  own seed-tree path (for a generator emit, SEAM-FIDELITY-SPEC §1's `("sim", sim_id, "gen", exposeId, "row",
  rowIndex)`). `R` is the canonical JSON (KERNEL-SPEC §2) of `["contract", <contract id>, <id>]` for a rule from a
  contract, keyed by both because two contracts may reuse an id, and of `["bundle", <id>]` for a FLUX-side rule. Every
  draw sits at a fixed position of the stream: the first decides whether the row holds, the second is the value a
  bounds or difference form takes (§6), and the next 16 are violation candidates. A draw a row does not need is left
  unused, and no position depends on another draw's outcome, so there is no rejection loop (KERNEL-SPEC §4). A rule
  that allows no violation and has an equality form draws nothing.
- **Which rows violate.** The first draw is `bernoulli(stream, 1 - target)` (KERNEL-SPEC §4, an integer comparison),
  and the row holds when it is true. The streams hang under the rows' own paths, so the rows that violate do not depend
  on how generation is partitioned or how many processes run. The target is met in expectation, which is why the band,
  not the target, is what the check compares with.
- **What a violating row holds.** The 16 candidates are drawn from `c`'s own declared statistics, or from the FLUX
  setting for the rule's violations when it has one, by the kernel's samplers, and the first candidate on which the
  rule does not hold is kept. When none of the 16 is, the engine takes the first value in a fixed order on which the
  rule does not hold: the declared levels in their declared order, or the ends of the declared range, the low end
  first. With no declared statistics and no violation setting, a target above zero is `FLX-6205`. When no candidate
  violates (a bound wider than the column's declared range, say), the row keeps the value that holds and is traced as
  not violated.
- **Tracing.** Every violating row is traced with the rule, the row, the value the rule would have given, the value
  written, and why (`drawn` or `infeasible`). The evidence pack counts the violations per rule as violations injected
  on purpose.
- **Paths and the kernel's table.** Rule streams extend a row's path, and dependency streams (§8) are keyed by their
  `from` value. Like the generator's own row path, these shapes are not in KERNEL-SPEC §3's canonical table, so they
  are derived the way `flux_engine/generator/paths.py` derives the generator's streams, from the run's root with the
  kernel's own primitives. They stay out of the run's seed-path ledger, as the generator's do, so the plan's path check
  (`FLX-2201`) does not see them until the table carries them. `path_label` in `flux_engine/core/seedtree.py` refuses
  a path part that holds a separator, so no column name, id or key can forge another's path. Adding these shapes to the
  table is the `kernelVersion` bump that the generator's row path still waits for, and is not part of this design.

## 8. Functional dependencies

A contract's `dependency` (RFC §1.2) relates rows to each other: equal values in its `from` columns mean equal values
in its `to` columns, and `bothWays` adds the reverse, with one column on each side. FLUX reads it as structure.

- **Coverage and the check** are the RFC's (§1.5). A row with a NULL in a `from` column is not covered, and a NULL in a
  `to` column is a value. For each key, the violating rows are its covered rows minus those that carry its most common
  `to` tuple (the g3 count). With `bothWays`, the forward and the reverse dependency are counted separately, and each
  count meets the band; the reverse count covers the rows whose `from` and `to` columns are both not NULL.
- **The key.** A `from` value is keyed by `K`, the canonical JSON (KERNEL-SPEC §2) of the list of its values, each a
  pair of its type and its text: a number as its exact value in canonical decimal text (no exponent, no leading
  zeros, no trailing zeros after the point, `0` for zero), so equal values are one key whatever their scale, a float
  column's value being read first as the shortest decimal that converts back to the same double (RFC §2.3), and no
  number is ever a JSON number; a date as `YYYY-MM-DD`, a timestamp as its milliseconds written as a string, a
  bool as `true` or `false`, and a string as stored, without normalization. `1` and `'1'` are two keys, and no value
  can forge another's path. Generation and the check group rows by the same key.
- **Generate.** Each distinct key gets its `to` value once, each `to` column drawn from its own declared statistics on
  the path `("sim", <simulation>, "dependency", R, "key", K, <column>)`, with `R` as in §7. Every row with that key
  copies it, wherever the row is generated, so the attribute has one source (§9). Both ways, two keys never share a
  `to` value: the `from` column must have values the plan can list (its declared levels, or the ordinals the
  identifier scheme gives it), and the i-th of them, in canonical order or by ordinal, takes the i-th value of a keyed
  permutation of the `to` column's declared values, drawn on `("sim", <simulation>, "dependency", R, "permutation")`. A
  both-ways dependency whose `from` values cannot be listed, or whose `to` values are fewer, is `FLX-6207`.
- **Violate.** A target above zero picks the violating rows as §7 does, on the stream `<row path> + ("dependency", R)`,
  whose first draw decides whether the row holds. A violating row draws its `to` columns with 16 candidate positions
  for each `to` column: one block per column, in declared order, from the stream's second draw (draws 2 to 17 for the
  first column, 18 to 33 for the second). It keeps the first candidate tuple, the n-th candidate of every column, that
  differs from the key's value; when none does, §7's fixed order applies to the first `to` column. The row is traced.
  A dependency is generated only when its band allows a holding share above one half (§7). One way, a key with few
  rows can have a generated violation as its majority and count it as holding, so the checked share of a generated
  run can be above the generated one, never below it; both ways, the reverse count can move it either way.

## 9. One source per value

Every value has exactly one source. In the contract, a column has at most one among the `derive` invariants on it
(several with `when`s count as one), the `to` side of a `dependency`, a `sharedColumns` entry and membership of a
`sharedAttribute` other than the owner (RFC §5); the validator refuses two. FLUX adds its own sources: the FLUX-side
rules, a scenario mapping, the identifier scheme (which generates only a column with no other source; a format alone
only checks values, RFC §5), the column's own declared statistics, and a type default.

- On the rows a rule or a dependency covers, the column's own statistics are not drawn. They still serve §6's bounds
  and differences and §7's violations, and the fidelity check reads them as it reads any column's
  (SEAM-FIDELITY-SPEC §2).
- A column with two sources across the contract and the bundle is `FLX-6203`, naming both: a FLUX-side rule on a
  column the contract fills, or a scenario mapping on a column that a rule or a dependency determines, whatever their
  `when`s, so the plan decides it without looking at rows. Several `derive` rules on one column are one source.
- A shared attribute is generated once and copied. A `sharedColumns` entry is read as the copy rule
  `derive: <column>`, `expr: <relationship>.<column>`, covering the rows whose link reaches a row; a `sharedAttribute`
  is generated on its owner and copied along the one path to it, covering the rows whose path reaches an owner row
  (RFC §5). The same rules then check that every copy agrees.
- The coverage report and `column-provenance.json` record each source of a column with the `when` that selects it, so
  the record grows from one producer per column to a list of sources. The closed set of (origin, producer) pairs in
  `seam/coverage.py` gains three: `copied` by `rule` for a copy's rows, `derived` by `rule` for any other rule's, and
  `derived` by `dependency`. The source of each is the contract's id with the rule's or dependency's `id`, or the
  bundle's FLUX-side `id`; a copy read from `sharedColumns` is named by its relationship and column, and one read
  from a `sharedAttribute` by the attribute's name. Traces and reports name rules the same way.

## 10. Attribute model, digests and dependencies

- The attribute model grows a version, `attrmodel/2`: attrmodel/1's three scopes unchanged, plus one `row` scope for
  each expose that has a rule. A `row` scope lists the expose's columns with their types and scales, its links (name,
  target expose, columns, cardinality), whether `previous` exists, its children collections and its key columns. It is
  canonical JSON, as attrmodel/1 is, and `fluxsim expr model` prints it.
- A bundle with no rule derives the attrmodel/1 document byte for byte. Dependencies are not expressions and add nothing
  to the model. With no rule and no dependency, a bundle keeps every stream (§7) as well, so its
  `attributeModelDigest`, its `inputDigest` and every digest after them stay where they are.
- A contract's rules are part of the contract, so adding one changes the contract digest, which seeds every stream
  (KERNEL-SPEC §3): every bundle that pins that contract then makes new rows. That is the existing rule for any change
  to a contract.
- An expression draws nothing. It reads no seed-tree path, no clock and no environment, and its value is a function of
  the rows it names. The draws of rules (§6, §7) and dependencies (§8) are the only randomness either adds, each on
  its own stream.
- The checker reports, for each rule, the columns it reads and how each is reached (the row itself, a link, `previous`,
  children or siblings) and the column it determines. The planner orders generation from these and from the key graph.
  A cycle among rules and dependencies is `FLX-6208`; any other cycle is the planner's. A rule reads only what its
  text writes out, so its reach is finite.

## 11. Canonical form and vectors

- The canonical text is what `plan.json` stores, and `unparse(parse(x))` is a fixed point: keywords and function names
  in upper case, names as written and quoted where RFC §2.1 requires it, one space around binary operators, one after a
  comma, the fewest parentheses the grammar needs, and the defaults `ASC` and `NULLS LAST` left out while `DESC` and
  `NULLS FIRST` are written. A FLUX-side text writes `row.<column>` as the bare column, and a path from `link` without
  its `link.`, but keeps `row.` or `link.` where the name that follows it is itself a root (§3). A `PARTITION BY`
  relationship is written bare, or as `link.<name>` where its name is also a column (§5) or a root (§3). So a re-parse
  reads the same names, and `FLX-6105` never fires on a canonical text. A core text writes every name bare, as RFC
  §2.2 reads it. A text whose canonical text would be longer than §2's 4,096 code points is `FLX-6103`, so every
  canonical text parses.
- A core text's tree has a node per construct of RFC §2.1's grammar, with the meaning RFC §2.9 gives, in the shapes of
  `fluid-sql-vectors.json`'s `nodes`: `{"node": "round", "arg", "scale", "mode"}` (the default mode filled in),
  `{"node": "coalesce", "args"}`, `{"node": "date_diff", "unit", "from", "to"}` (unit `day`, `month` or `year`),
  `{"node": "is_null", "operand", "negated"}`, `{"node": "distinct_from", "left", "right", "negated"}`, and `in` and
  `between` with the tested value as `left`; an `IN` item `-1` is one number, one level deep. In a core text
  the roots of §3 are ordinary names. In a FLUX-side text, `row.<column>` and the bare column give one node, and so do
  a path from `link` and the same path written bare, where §3 allows the bare spelling, so the two spellings of one
  name give one tree. The extensions add four nodes:
  `{"node": "path", "root", "parts"}`, `{"node": "children", "expose", "relationship"}`,
  `{"node": "aggregate", "name", "children", "arg"}` and
  `{"node": "window", "name", "args", "partition", "order": [{"key", "desc", "nullsFirst"}]}`. A path's `root` is
  `previous` or `link`. A path of one link that does not start at `previous` is the core's node, so a path node with
  root `link` has two links or more. A window's `partition` is its relationship's name, however it is written. A
  number keeps its digits as written, leading zeros included, as a string, so its declared scale survives, as in
  flux-expr/1; only `ROUND`'s places are read as the integer they name (`02` is `2`).
- The core's conformance vectors are forge-cli's `fluid-sql-vectors.json` (RFC §2.9). flux-engine vendors it unchanged
  as `tests/vectors/fluid-sql-vectors.json`, pinned by its digest, and runs every vector through flux-expr/2's parser,
  checker and evaluator, and every vector must pass: the vectors define the subset, and neither parser does. A
  refusal's reason maps to a code of §12, and three reasons to two codes: `syntax` is `FLX-6103`, or `FLX-6104` for a
  keyword where a name belongs, and `type-mismatch` and `derive-type` are `FLX-6109` and `FLX-6110`, or `FLX-6206`
  where a bool is needed. `tests/vectors/expr2-core-vectors.json` holds flux-engine's further core vectors in the same
  shape, each refusal also naming its code. `expr2-vectors.json` holds the extensions' vectors, in the shape of
  `expr-vectors.json` (EXPR-SPEC §5), with model fragments that describe exposes, links, versions and children, and the
  rows they are evaluated on.
- DuckDB is the test oracle for the semantics borrowed from SQL. Every vector with an aggregate, a window or a date
  difference also runs as a DuckDB query in the test suite and must agree. The query writes out what DuckDB would
  otherwise default: `NULLS LAST`, and the whole-partition frame of `FIRST_VALUE` and `LAST_VALUE`. Division and
  `AVG` are the exception: DuckDB 2.0.0 computes `/` and `avg` over `DECIMAL` in `DOUBLE`, so those vectors are checked
  against the exact rational result. DuckDB is a test dependency only, and the engine never imports it.
- Rule generation is pinned like every other draw, by the run's digests over the rows it writes (KERNEL-SPEC §8).

## 12. Refusals

Every code below is raised at plan time, before any row exists, except `FLX-6112`. They extend the `FLX-6nnn` catalog
that KERNEL-SPEC §13 assigns to the expression language, and `fluxsim explain` prints each one the engine raises:
`FLX-6202` to `FLX-6205`, `FLX-6207` and `FLX-6208` join the catalog with generation from rules (§6 to §9). `FLX-6001` to
`FLX-6005` belong to flux-expr/1 and are never raised for a flux-expr/2 text. FLUX does not assume the RFC's
validator ran on a pinned contract, so it checks what it relies on in contract texts too (the grammar, the limits and
refusals of §2, the names and types it evaluates, and ids within a contract), and these codes cover those checks and
the FLUX-side texts.

| Code | Title |
|---|---|
| `FLX-6101` | a FLUX-side rule declares no `language` |
| `FLX-6102` | the declared `language` is not one this entry accepts |
| `FLX-6103` | outside the core grammar and the extensions, or longer or deeper than §2 allows |
| `FLX-6104` | a reserved word or the NULL literal used where it has no meaning (§4) |
| `FLX-6105` | in a FLUX-side text, a first name is both a root and a column or relationship, or a bare `PARTITION BY` name is also a column |
| `FLX-6106` | a path that does not resolve as written: `previous` on an expose without versions, `CHILDREN.<expose>` with no relationship or several and none named, a children collection used as a path, a partition that is not a to-one relationship, or a relationship whose target declares a validity window |
| `FLX-6107` | an aggregate or window where it is not allowed: an aggregate over something that is not a children collection or nested over the same collection, or a window inside an aggregate's argument or another window's |
| `FLX-6108` | a window whose value depends on ties has an order that is not total |
| `FLX-6109` | a type error, in a contract's text or a FLUX-side one: operands or arguments of the wrong type, a literal outside a closed set, or a literal argument of the wrong form |
| `FLX-6110` | a derived value's type or scale does not fit its column, or a summed or averaged value has an unbounded scale |
| `FLX-6111` | a name for a column that has no FLUID SQL/1 type |
| `FLX-6112` | a value does not fit its column when the row is made: more digits than the column's precision, or outside the column's integer range |
| `FLX-6113` | a name that the row scope does not know |
| `FLX-6201` | a rule or dependency has no `id`, or one that repeats within its contract or among the bundle's FLUX-side rules, or a FLUX-side `id` that is not ASCII letters, digits and underscores starting with a letter |
| `FLX-6202` | a FLUX setting names a column for a `check` that is not of bounds or difference form, or for one whose value side or `when` reads that column |
| `FLX-6203` | a column has two sources across the contract and the bundle (§9) |
| `FLX-6204` | a target outside its band, or, in a strict run, a band that cannot be met in expectation and that zero violations would fail |
| `FLX-6205` | a draw with nothing to draw from: a target above zero for a column with no declared statistics and no violation setting, or a bounds or difference draw over an interval open on one side with no declared statistics |
| `FLX-6206` | a rule's `check`, `expr` of a bool column, or `when` is not bool, in the contract or the bundle |
| `FLX-6207` | a both-ways dependency FLUX cannot generate: `from` values it cannot list, or fewer `to` values |
| `FLX-6208` | rules and dependencies that determine columns in a cycle |
| `FLX-6209` | a FLUX-side rule the contract can carry: one that uses none of the four extensions, or whose whole value is exactly a contract `aggregate`, its filter written in the core |

## 13. Not in flux-expr/2

- in the core, what RFC §2.7 leaves out;
- in the extensions: explicit frames and running totals, aggregates written as windows, `NTH_VALUE`, `NTILE` and the
  percent ranks. They go to `flux-expr/3`;
- rules generated from any form but the four of §6, and both-ways dependencies over more than one column a side;
- flux-expr/2 at today's flux-expr/1 sites, which needs a change to the FLUX specification;
- how a catalogue is declared, the planner's column order and the cycles that run through the key graph alone, and how
  generation is partitioned across roots, each defined with its own feature.
