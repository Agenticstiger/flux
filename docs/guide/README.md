# Introduction

FLUX — the *Flow Language for Universe eXperimentation* — is an open, declarative
specification for describing **synthetic customer universes**: the population,
commerce surface, behaviours, activations, and simulations of a governed
digital twin.

It exists so a business question — *"how many at-risk TV customers in a given
market would a payment-recovery campaign save?"* — can be answered without
hand-coding a bespoke data generator, pipeline and dashboard for every
question. You **declare** the world and the scenario; a FLUX toolchain
compiles, validates, materialises and streams it.

## Why not just build the real thing?

Enterprises rebuilding themselves "from the core to the customer" stall in the
same place: the ambition is a real-time, contextual customer experience, but
the estate that must feed it is a decade of accreted systems that cannot be
safely re-platformed at once. The missing capability is *the ability to know,
with evidence and before you build, which signals are worth extracting from
the core — and to ship them under a contract that survives the estate changing
underneath.*

FLUX supplies the discovery half of that capability. The delivery half is
[FLUID](https://open-data-protocol.github.io/fluid/), the data-product
contract standard. They interlock at exactly one seam:

1. **Discover in the twin.** Run candidate rules against a synthetic
   population. Measure outcomes. Keep the winners.
2. **Prove under contract.** The winning rule is exercised against a FLUID
   contract in the twin — conformance, quality, consent reach and sovereignty
   checked offline, with no production exposure.
3. **Ship the same contract.** Because the contract proven in the twin *is* a
   FLUID document, promoting to production is not a re-implementation. The
   same file is wrapped around the real estate.

The economic consequence: **capital is committed to building a data product
only after evidence says it matters, and the thing that ships is the thing
that was proven.**

## What a FLUX universe is made of

Nineteen document kinds in six families — population, commerce, behaviour,
activation, calibration, composition — each a small YAML document sharing one
envelope. See [The Six Families](/flux/concepts/families) and the
[full kind reference](/flux/schema/kinds).

## Status

FLUX is a **v0.3.0 working draft** under Apache 2.0. Pre-1.0, minor versions
may break; every release ships a schema diff and a regression suite. Start
with the [Quickstart](/flux/guide/quickstart).
