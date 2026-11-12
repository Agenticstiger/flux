# FLUX by Example

The repository ships two CI-validated bundles. The first is a complete universe:
[`examples/telco-payment-recovery/`](https://github.com/Agenticstiger/flux/tree/main/examples/telco-payment-recovery)
— the position paper's worked example, covering **all nineteen kinds plus the
FLUID contract at the seam**.

## The scenario

A telco operator faces a burst of abandoned bill payments threatening
involuntary churn among high-value TV subscribers. Would a fast
payment-recovery treatment save enough at-risk customers to justify building
the underlying real-time signal?

## The cast

| Document | Kind | Role |
|---|---|---|
| `world.flux.yml` | World | 25,000 subscribers, 3 markets, 20% at risk, seeded |
| `persona.flux.yml` | Persona | traits as RFC-01 distributions (scalar + categorical + bounded normal) |
| `segment.flux.yml` | Segment | `lifecycle == 'atrisk' && products.has('tv')` |
| `signal.flux.yml` | Signal | `com.telco.payment.aborted` as a CloudEvents type |
| `detector.flux.yml` | Detector | two aborted payments inside 15 minutes |
| `taxonomy.flux.yml` | JourneyTaxonomy | new → active → atrisk → churned |
| `journey.flux.yml` | Journey | trigger → intervention → per-persona reactions |
| `treatment-fast.flux.yml` | Treatment | the one-tap payment link |
| `treatment-standard.flux.yml` | Treatment | the dunning-letter control arm |
| `channel.flux.yml` / `consent.flux.yml` | Channel, ConsentProfile | consented SMS reach, EU jurisdictions |
| `campaign.flux.yml` | Campaign | treatment × segment × channel × consent |
| `experiment.flux.yml` | Experiment | 50/50 A/B, largest-remainder assignment, RFC-07 governed metric |
| `catalog.flux.yml` / `offer.flux.yml` | Catalog, Offer | the winback offer surface |
| `playback.flux.yml` | Playback | calibrates the World from billing telemetry, PSI drift |
| `module.flux.yml` / `verticalpack.flux.yml` / `blueprint.flux.yml` | Composition | packaging and topology |
| `simulation.flux.yml` | Simulation | the root: fidelity, golden digest, skills, RFC-02 extensions, RFC-03 versioned moduleRef — and the seam |
| `flux.lock` | — | RFC-03 lockfile pinning `module-payment-recovery@^2.1` to 2.1.3 + a content digest |
| `payment-recovery.fluid.yml` | **FLUID DataProduct** | the contract the twin proves and production ships |

## Run it

```bash
python3 scripts/validate.py examples/telco-payment-recovery
# [ok] examples/telco-payment-recovery
```

Then break it on purpose — dangle a ref, skew the experiment weights, deny a
use case in the ConsentProfile that the contract allows — and watch the
validator name the exact document, path and rule. The
[regression suite](https://github.com/Agenticstiger/flux/blob/main/tests/test_regression.py)
does exactly that, 61 times, on every commit.

## Towers: tenant renewal risk

[`examples/towers-tenant-renewal/`](https://github.com/Agenticstiger/flux/tree/main/examples/towers-tenant-renewal)
is a tower company's view of its tenants: mobile operators and internet
providers renting space on its sites across six markets. SLA breaches are
rising. Which tenants are at risk at renewal, and do service credits and
power upgrades win them back? Its World declares `vertical: towers`, and its
Simulation pins the FLUID 0.7.6 seam exactly.

| Document | Kind | Role |
|---|---|---|
| `world.flux.yml` | World | 1,500 tenants in six markets named by ISO country code |
| `persona-*.flux.yml` | Persona | anchor operator, challenger operator, regional ISP |
| `taxonomy.flux.yml` | JourneyTaxonomy | onboarding → active → atrisk → notice → churned |
| `segment.flux.yml` | Segment | at-risk tenants inside the renewal window with chronic breaches |
| `signal-*.flux.yml` | Signal | SLA breach, site outage, billing dispute |
| `detector.flux.yml` | Detector | a chargeable SLA breach followed by another within 30 days |
| `journey-*.flux.yml` | Journey | SLA credit, capex upgrade, dispute credit, per persona |
| `treatment-*.flux.yml` | Treatment | the service credit and the site power upgrade |
| `module.flux.yml` / `verticalpack.flux.yml` | Composition | packaging |
| `simulation.flux.yml` | Simulation | the root, with an exact `fluidVersion: "0.7.6"` pin |
| `tenant-renewal-risk.fluid.yml` | **FLUID DataProduct** | one row per renewal-risk detection, consuming the tower-management data products |

```bash
python3 scripts/validate.py examples/towers-tenant-renewal
# [ok] examples/towers-tenant-renewal
```
