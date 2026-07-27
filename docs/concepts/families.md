# The Six Families

A FLUX universe is assembled from **nineteen document kinds**, clustered into
six families by responsibility. This factoring is what turns an open-ended
"build me a simulation" problem into a bounded, composable vocabulary.

| Family | Kinds | Question it answers |
|---|---|---|
| **Population** | World, Persona, Segment | *Who* is in the universe |
| **Commerce** | Catalog, Offer, Channel, ConsentProfile | *What* can be sold and *how* it can be reached |
| **Behaviour** | Journey, JourneyTaxonomy, Signal, Detector | *What happens* and *what to watch for* |
| **Activation** | Campaign, Treatment, Experiment | *What we do* about it |
| **Calibration** | Playback | *How the twin stays honest* |
| **Composition** | Simulation, Module, Blueprint, VerticalPack | *How it assembles* and *travels* |

The kinds are not a flat list; they form a **metamodel** in which each kind
references others through named, validated links. `Simulation` is the
composition root: it names a `World`, the `Personas`, `Signals`, `Campaigns`
and `Experiments` that run, and the `Modules` that provide capability — and it
*emits* a FLUID contract at the seam. Every arrow is a reference the
[offline validator](/flux/schema/anatomy#the-offline-validator) resolves, so a
well-formed universe has no dangling links.

<MermaidLazy>

```mermaid
flowchart TB
    FC["FLUID contract"]:::seam
    SIM["Simulation"]:::comp
    W["World"]:::pop
    P["Persona"]:::pop
    SEG["Segment"]:::pop
    SIG["Signal"]:::beh
    DET["Detector"]:::beh
    J["Journey"]:::beh
    JT["JourneyTaxonomy"]:::beh
    CAM["Campaign"]:::act
    TR["Treatment"]:::act
    EXP["Experiment"]:::act
    CH["Channel"]:::com
    CP["ConsentProfile"]:::com
    OF["Offer"]:::com
    CAT["Catalog"]:::com
    PB["Playback"]:::cal

    SIM -- "emits (ref)" --> FC
    SIM --> W
    SIM --> P
    SIM --> SEG
    SIM --> SIG
    SIM --> CAM
    SIM --> EXP
    DET -- "pattern" --> SIG
    J -- "trigger" --> SIG
    J -- "taxonomyRef" --> JT
    J -- "intervention" --> TR
    CAM --> TR
    CAM --> SEG
    CAM -- "channel" --> CH
    CAM -- "consent" --> CP
    EXP -- "variants" --> TR
    OF -- "from" --> CAT
    PB -- "calibrates" --> W

    classDef pop fill:#1d3557,stroke:#89b4fa,color:#e8ecf6
    classDef com fill:#4a2b12,stroke:#ffb454,color:#ffe9cf
    classDef beh fill:#12402e,stroke:#57d9a3,color:#dcf5ea
    classDef act fill:#3a1d4d,stroke:#c792ea,color:#f0e4fa
    classDef cal fill:#40323a,stroke:#f2a7c3,color:#fde8f0
    classDef comp fill:#20242e,stroke:#aab3c5,color:#eef1f7
    classDef seam fill:#4a1d12,stroke:#f0692e,color:#ffe3d6
```

</MermaidLazy>

## One envelope, nineteen shapes

Every kind shares the same envelope — aligned field-for-field with FLUID's:

```yaml
fluxVersion: "0.3.0"     # pinned spec version
kind: Persona            # one of the nineteen
id: pragmatic-family     # unique in the bundle; the target of refs
name: Pragmatic Family
metadata:
  owner:
    team: growth-lab     # accountable owner — required, as in FLUID
spec:                    # kind-specific block, closed and typed
  ...
```

Any kind may additionally declare **`agentPolicy`** and **`skills`** — the
uniform agentic extension point ([details](/flux/concepts/determinism-governance#governed)).

Per-kind field reference: **[The Nineteen Kinds](/flux/schema/kinds)**.
