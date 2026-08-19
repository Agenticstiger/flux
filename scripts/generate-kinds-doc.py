#!/usr/bin/env python3
"""Generate docs/schema/kinds.md from the current FLUX schema.

Deterministic: the page is committed, and regenerating from the same schema is
byte-stable. Run after any schema change:

    python3 scripts/generate-kinds-doc.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((REPO / "schema" / "flux-schema-0.5.0.json").read_text())
OUT = REPO / "docs" / "schema" / "kinds.md"

FAMILIES = {
    "Population": ["World", "Persona", "Segment"],
    "Commerce": ["Catalog", "Offer", "Channel", "ConsentProfile"],
    "Behaviour": ["Journey", "JourneyTaxonomy", "Signal", "Detector"],
    "Activation": ["Campaign", "Treatment", "Experiment"],
    "Calibration": ["Playback"],
    "Composition": ["Simulation", "Module", "Blueprint", "VerticalPack"],
}


def deref(node):
    if isinstance(node, dict) and "$ref" in node:
        name = node["$ref"].split("/")[-1]
        merged = dict(SCHEMA["$defs"][name])
        merged.setdefault("_defName", name)
        for k, v in node.items():
            if k != "$ref":
                merged[k] = v
        return merged
    return node


def type_label(node):
    node = deref(node)
    t = node.get("type")
    if "_defName" in node:
        return f"`{node['_defName']}`"
    if t == "array":
        items = deref(node.get("items", {}))
        inner = items.get("_defName") or items.get("type", "object")
        return f"array of `{inner}`"
    if isinstance(t, list):
        return " \\| ".join(f"`{x}`" for x in t)
    if "enum" in node:
        return "enum"
    if "const" in node:
        return f"const `{node['const']}`"
    if "anyOf" in node:
        return "anyOf"
    return f"`{t or 'object'}`"


def constraints(node):
    node = deref(node)
    bits = []
    if "enum" in node:
        bits.append(", ".join(f"`{v}`" for v in node["enum"]))
    if "const" in node:
        bits.append(f"const `{node['const']}`")
    for key, fmt in [
        ("minimum", "min {}"), ("maximum", "max {}"), ("exclusiveMinimum", "> {}"),
        ("minItems", "minItems {}"), ("minProperties", "minProperties {}"),
        ("minLength", "minLength {}"), ("pattern", "pattern `{}`"),
    ]:
        if key in node and key != "pattern":
            bits.append(fmt.format(node[key]))
    if node.get("uniqueItems"):
        bits.append("unique")
    if "default" in node:
        bits.append(f"default `{node['default']}`")
    return "; ".join(bits)


def field_rows(props, required, prefix=""):
    rows = []
    for name, raw in props.items():
        node = deref(raw)
        path = f"{prefix}{name}"
        req = "**yes**" if name in required else "no"
        desc = (node.get("description") or "").split(". ")[0].rstrip(".")
        rows.append((path, type_label(raw), req, constraints(raw), desc))
        inner = node.get("properties")
        if inner:
            rows.extend(field_rows(inner, node.get("required", []), prefix=f"{path}."))
        elif node.get("type") == "array":
            items = deref(node.get("items", {}))
            if items.get("properties"):
                rows.extend(field_rows(items["properties"], items.get("required", []), prefix=f"{path}[]."))
    return rows


def branch_for(kind):
    for branch in SCHEMA["allOf"]:
        if branch.get("if", {}).get("properties", {}).get("kind", {}).get("const") == kind:
            return branch["then"]["properties"]["spec"]
    raise KeyError(kind)


def main():
    lines = [
        "# The Nineteen Kinds",
        "",
        "> Generated from",
        "> [`flux-schema-0.5.0.json`](https://agenticstiger.github.io/flux/schema/flux-schema-0.5.0.json)",
        "> by `scripts/generate-kinds-doc.py` — do not edit by hand.",
        "",
        "Every kind shares the [common envelope](/flux/schema/anatomy#the-envelope);",
        "the tables below describe each kind's `spec`. Fields ending in `Ref`",
        "(and `refList` fields) must resolve to a document of the right kind in the",
        "same bundle — enforced by the [offline validator](/flux/schema/anatomy#the-offline-validator).",
        "",
    ]
    for family, kinds in FAMILIES.items():
        lines += [f"## {family}", ""]
        for kind in kinds:
            spec = branch_for(kind)
            lines += [f"### {kind}", ""]
            req = spec.get("required", [])
            head = []
            if req:
                head.append("required: " + ", ".join(f"`{r}`" for r in req))
            if "minProperties" in spec:
                head.append(f"at least {spec['minProperties']} field")
            if head:
                lines += ["*" + " — ".join(head) + "*", ""]
            lines += [
                "| Field | Type | Required | Constraints | Description |",
                "|---|---|---|---|---|",
            ]
            for path, typ, r, cons, desc in field_rows(spec.get("properties", {}), req):
                lines.append(f"| `{path}` | {typ} | {r} | {cons} | {desc} |")
            lines.append("")
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT.relative_to(REPO)} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
