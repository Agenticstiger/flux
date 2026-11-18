# Specifications

The normative specifications of the engine: what it must do, rule by rule. They are
reference text, not walkthroughs; the [how-to guides](../how-to/README.md) show many of
the features in use. Tests, vectors and goldens hold their rules.

| Specification | What it fixes |
|---|---|
| [KERNEL-SPEC.md](./KERNEL-SPEC.md) | The kernel: versions, canonical digests, the seed tree, draws, the clock, the emit stream, keys from the contract, value rendering, the trace and the run digest. |
| [SEAM-FIDELITY-SPEC.md](./SEAM-FIDELITY-SPEC.md) | The generator that writes rows in a contract's shape, the fidelity block, the fidelity check and the gate `ship` runs. |
| [EXPR-SPEC.md](./EXPR-SPEC.md) | flux-expr/1, the language of a Segment's query. |
| [EXPR-SPEC-2.md](./EXPR-SPEC-2.md) | flux-expr/2, the language of derived columns and of rules about valid data. The engine implements the language; generating from rules and checking runs against them come next. |
| [PROFILE-SPEC.md](./PROFILE-SPEC.md) | The profile a data owner makes, and how a Simulation pins one. Beside it: [the schema](./profile-1.schema.json) and [an example](./profile-example.json). |
| [SCORECARD-SPEC.md](./SCORECARD-SPEC.md) | The scores of a run against its pinned profile, their thresholds, and the shape flags. Beside it: [the schema](./scorecard-1.schema.json) and [an example](./scorecard-example.json). |
| [SAMPLE-SPEC.md](./SAMPLE-SPEC.md) | Checking a run's means against the profile on a sample of blocks, each with an interval. |
| [PARAMETER-REGISTER-SPEC.md](./PARAMETER-REGISTER-SPEC.md) | The register of what each number a run reads rests on. Beside it: the schemas of format [1-1-0](./parameter-register-1-1.schema.json) and [1-0-0](./parameter-register-1.schema.json), and [an example](./parameter-register-example.json). |
