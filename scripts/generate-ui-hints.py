#!/usr/bin/env python3
"""Generate schema/flux-ui-hints-<version>.json (RFC-08).

The UI-hints artifact lets any editor render a form for a FLUX document
without hand-coding per-kind knowledge: widget types are derived
mechanically from the JSON Schema (enum -> select, 0..1 number -> slider,
ref -> reference picker, ...), while titles, summaries and field ordering
come from the curated overlay below. Regenerate after any schema change:

    python3 scripts/generate-ui-hints.py

Deterministic and committed, like the kinds reference.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VERSION = "0.5.0"
SCHEMA = json.loads((REPO / "schema" / f"flux-schema-{VERSION}.json").read_text())
OUT = REPO / "schema" / f"flux-ui-hints-{VERSION}.json"

KIND_META = {
    "World": ("Population", "The synthetic population: size, lifecycle mix, markets, dials", "world.flux.yml"),
    "Persona": ("Population", "An identity archetype: demographics, traits, worldview", "persona.flux.yml"),
    "Segment": ("Population", "A query selecting personas from the population", "segment.flux.yml"),
    "Catalog": ("Commerce", "The sellable items and their attributes", "catalog.flux.yml"),
    "Offer": ("Commerce", "Priced offer over a catalog", "offer.flux.yml"),
    "Channel": ("Commerce", "A reachable channel and its rate limits", "channel.flux.yml"),
    "ConsentProfile": ("Commerce", "Jurisdictions and use-case consent constraints", "consent.flux.yml"),
    "Journey": ("Behaviour", "Trigger, intervention and per-persona reactions", "journey.flux.yml"),
    "JourneyTaxonomy": ("Behaviour", "The lifecycle state machine journeys move through", "taxonomy.flux.yml"),
    "Signal": ("Behaviour", "A CloudEvents-typed event the twin emits or watches", "signal.flux.yml"),
    "Detector": ("Behaviour", "A windowed pattern over signals", "detector.flux.yml"),
    "Campaign": ("Activation", "Treatment x segment x channel x consent", "campaign.flux.yml"),
    "Treatment": ("Activation", "The action taken when a campaign fires", "treatment-fast.flux.yml"),
    "Experiment": ("Activation", "Weighted variants, assignment method, governed metrics", "experiment.flux.yml"),
    "Playback": ("Calibration", "Fits the World to observed telemetry; reports drift", "playback.flux.yml"),
    "Simulation": ("Composition", "The root: world, fidelity, composition refs and the FLUID seam", "simulation.flux.yml"),
    "Module": ("Composition", "A reusable capability bundle bound to the four ports", "module.flux.yml"),
    "Blueprint": ("Composition", "Topology of documents as a reviewable graph", "blueprint.flux.yml"),
    "VerticalPack": ("Composition", "Industry packaging of modules", "verticalpack.flux.yml"),
}

FAMILY_ORDER = ["Population", "Commerce", "Behaviour", "Activation", "Calibration", "Composition"]


def deref(node):
    if isinstance(node, dict) and "$ref" in node:
        name = node["$ref"].split("/")[-1]
        merged = dict(SCHEMA["$defs"][name])
        merged["_defName"] = name
        merged.update({k: v for k, v in node.items() if k != "$ref"})
        return merged
    return node


def widget_for(raw):
    node = deref(raw)
    d = node.get("_defName")
    if d in ("ref",):
        return {"widget": "reference"}
    if d == "versionedRef":
        return {"widget": "reference", "versioned": True}
    if d == "trait":
        return {"widget": "trait-distribution", "modes": ["scalar", "categorical", "normal"]}
    if d == "semanticRef":
        return {"widget": "semantic-measure"}
    if d in ("refList",):
        return {"widget": "reference-list"}
    if d == "unitInterval":
        return {"widget": "slider", "min": 0, "max": 1, "step": 0.01}
    if d == "rfc3339":
        return {"widget": "datetime"}
    if d == "currencyCode":
        return {"widget": "currency"}
    t = node.get("type")
    if "enum" in node:
        return {"widget": "select", "options": node["enum"]}
    if "const" in node:
        return {"widget": "constant", "value": node["const"]}
    if t == "boolean":
        return {"widget": "toggle"}
    if t == "integer":
        w = {"widget": "number", "integer": True}
        if "minimum" in node:
            w["min"] = node["minimum"]
        return w
    if t == "number":
        return {"widget": "number"}
    if t == "array":
        return {"widget": "list"}
    if t == "object" or "properties" in node:
        return {"widget": "group"}
    return {"widget": "text"}


def field_hints(props, required, prefix=""):
    hints = {}
    for name, raw in props.items():
        node = deref(raw)
        path = f"{prefix}{name}"
        h = widget_for(raw)
        h["required"] = name in required
        desc = node.get("description")
        if desc:
            h["help"] = desc.split(". ")[0].rstrip(".") + "."
        hints[path] = h
        if node.get("properties"):
            hints.update(field_hints(node["properties"], node.get("required", []), f"{path}."))
        elif node.get("type") == "array":
            items = deref(node.get("items", {}))
            if items.get("properties"):
                hints.update(field_hints(items["properties"], items.get("required", []), f"{path}[]."))
    return hints


def branch_for(kind):
    for branch in SCHEMA["allOf"]:
        if branch.get("if", {}).get("properties", {}).get("kind", {}).get("const") == kind:
            return branch["then"]["properties"]["spec"]
    raise KeyError(kind)


def main():
    kinds = {}
    for kind in SCHEMA["properties"]["kind"]["enum"]:
        family, summary, example = KIND_META[kind]
        spec = branch_for(kind)
        kinds[kind] = {
            "title": kind,
            "family": family,
            "order": FAMILY_ORDER.index(family),
            "summary": summary,
            "example": f"examples/telco-payment-recovery/{example}",
            "fields": field_hints(spec.get("properties", {}), spec.get("required", [])),
        }
    artifact = {
        "uiHintsVersion": VERSION,
        "schema": f"https://agenticstiger.github.io/flux/schema/flux-schema-{VERSION}.json",
        "description": "RFC-08 UI hints: enough metadata for any editor to render a form per kind. Widgets are derived from the schema; titles/summaries/ordering are curated. Not normative — validation authority stays with the JSON Schema.",
        "envelope": {
            "id": {"widget": "text", "required": True},
            "name": {"widget": "text", "required": True},
            "description": {"widget": "textarea", "required": False},
            "metadata.owner.team": {"widget": "text", "required": True},
            "extensions": {"widget": "namespace-map", "required": False,
                           "help": "Dialect fields under a versioned namespace (RFC-02)."},
        },
        "kinds": kinds,
    }
    OUT.write_text(json.dumps(artifact, indent=2) + "\n")
    total = sum(len(k["fields"]) for k in kinds.values())
    print(f"wrote {OUT.relative_to(REPO)} — {len(kinds)} kinds, {total} field hints")


if __name__ == "__main__":
    main()
