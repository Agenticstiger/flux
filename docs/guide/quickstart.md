# Quickstart

Author a minimal universe, validate it offline, and cross the FLUID seam — in
about five minutes. No cloud, no running engine.

## 1. Clone and install

```bash
git clone https://github.com/Agenticstiger/flux.git
cd flux
pip install jsonschema pyyaml
```

## 2. Validate the shipped example

```bash
python3 scripts/validate.py examples/telco-payment-recovery
# [ok] examples/telco-payment-recovery
```

That one line just did two layers of work: every document against the
[JSON Schema](https://agenticstiger.github.io/flux/schema/flux-schema-0.3.0.json),
then the cross-document checks — reference resolution, sums, state membership,
agentPolicy bounds, and FLUID seam conformance.

## 3. Author your first World

Create `my-universe/world.flux.yml`:

```yaml
fluxVersion: "0.3.0"
kind: World
id: hello-world
name: Hello World
metadata:
  owner:
    team: my-team
spec:
  seed: 7
  population:
    size: 1000
    lifecycleMix: { active: 0.8, churned: 0.2 }
```

```bash
python3 scripts/validate.py my-universe
# [ok] my-universe
```

Try breaking it — typo `lifecycleMix` to `lifecycle_mix`, or make the mix sum
to 0.9 — and the validator tells you exactly what and where. Unknown fields
are **rejected**, not silently accepted: the validate gate is a hard gate.

## 4. Cross the seam

A `Simulation` emits streams under a FLUID contract by **reference**. Add a
FLUID DataProduct (`my-universe/hello.fluid.yml`):

```yaml
fluidVersion: "0.7.5"
kind: DataProduct
id: demo.gold.hello_stream
name: Hello Stream
metadata:
  owner:
    team: my-team
exposes:
  - exposeId: hello_stream
    kind: stream
    contract:
      schema:
        - name: customer_id
          type: STRING
          required: true
    binding:
      platform: kafka
      format: kafka_topic
      location:
        topic: demo.hello.v1
```

…and a Simulation (`my-universe/sim.flux.yml`):

```yaml
fluxVersion: "0.3.0"
kind: Simulation
id: hello-sim
name: Hello Simulation
metadata:
  owner:
    team: my-team
spec:
  worldRef: hello-world
  emits:
    - productRef: demo.gold.hello_stream
      exposeId: hello_stream
      fluidVersion: "0.7.5"
```

```bash
python3 scripts/validate.py my-universe
# [ok] my-universe
```

The validator resolved `productRef`, validated `hello.fluid.yml` against the
vendored FLUID 0.7.5 schema, and asserted the expose exists. If the FLUID
document were invalid — or the pinned version wrong, or the exposeId missing —
the bundle fails. **What the twin proves is exactly what ships.**

## 5. Use the schema in your editor

Add this line to the top of any `.flux.yml` for instant validation and
completion in VS Code (with the YAML extension) and friends:

```yaml
# yaml-language-server: $schema=https://agenticstiger.github.io/flux/schema/flux-schema-0.3.0.json
```

## Next

- [The Six Families](/flux/concepts/families) — what each kind is for.
- [The FLUID Seam](/flux/concepts/seam) — how discovery hands off to delivery.
- [Examples](/flux/examples/) — the full 19-kind telco universe, annotated.
