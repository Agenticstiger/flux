# Decision records

Each record says what was decided, why, and what else was considered. A record keeps the
text of its date; a later change is written into it as a dated amendment.

- [ADR 0001](./0001-diverge-from-mesa.md): diverge from Mesa for the simulation substrate. Accepted.
- [ADR 0002](./0002-flux-expr-diverges-from-cel.md): flux-expr/1 diverges from CEL. Accepted.
- [ADR 0003](./0003-sdv-bsl-and-aggregate-only-rule.md): calibrate from aggregates only, with no SDV and no fitting to records. Accepted, amended 2026-11-11 and 2026-11-16.
- [ADR 0004](./0004-concordia-tinytroupe-adapt-the-pattern.md): adapt the patterns of Concordia and TinyTroupe, and depend on neither. Accepted.
- [ADR 0005](./0005-depend-on-flux-spec.md): depend on `flux_spec` rather than reimplement it. Accepted, amended 2026-09-07 and again since.
- [ADR 0006](./0006-input-digest-is-a-closed-set.md): `inputDigest` covers a closed set of files, and the loader refuses anything else. Accepted.
- [ADR 0008](./0008-flux-expr-2-derived-columns-and-rules.md): flux-expr/2 implements FLUID SQL/1 and adds FLUX's extensions, and flux-expr/1 is unchanged. Accepted.
- [ADR 0009](./0009-flux-stats-distribution.md): the statistics are a distribution of their own, flux-stats. Accepted, amended 2026-11-17.
