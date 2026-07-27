#!/usr/bin/env python3
"""FLUX offline reference validator.

Validates FLUX document bundles: every document against the FLUX JSON Schema,
then the cross-document guarantees the schema alone cannot express:

  * every *Ref resolves to a document of the expected kind (no dangling links)
  * document ids are unique within a bundle
  * World.lifecycleMix and Experiment variant weights sum to 1
  * Experiment variant names are unique
  * JourneyTaxonomy transitions and Blueprint edges stay within their node sets
  * Journey.personaReactions keys resolve to Personas; nextState is a state of
    the referenced taxonomy
  * Simulation.timeBounds.start < end
  * skills bindings respect the document's agentPolicy (model allow-list,
    per-skill token budget)
  * the FLUID seam: Simulation.emits[].productRef resolves to a .fluid.yml in
    the bundle, that document validates against the vendored FLUID schema for
    the pinned fluidVersion, and exposeId is a member of its exposes[]

Usage:
    python3 scripts/validate.py [bundle_dir ...]

With no arguments, validates every directory under examples/.
Runs fully offline: no network, no running engine. Exit code 0 = green.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover
    sys.exit("validate.py requires: pip install jsonschema pyyaml rfc3339-validator")

REPO = Path(__file__).resolve().parent.parent
FLUX_SCHEMA_PATH = REPO / "schema" / "flux-schema-0.3.0.json"
FLUID_VENDOR_DIR = REPO / "vendor" / "fluid"

# *Ref field -> kind it must resolve to (None = any kind)
REF_KINDS = {
    "catalogRef": "Catalog",
    "treatmentRef": "Treatment",
    "segmentRef": "Segment",
    "channelRef": "Channel",
    "consentRef": "ConsentProfile",
    "worldRef": "World",
    "signalRef": "Signal",
    "taxonomyRef": "JourneyTaxonomy",
    "mapToPersona": "Persona",
    "personaRefs": "Persona",
    "segmentRefs": "Segment",
    "signalRefs": "Signal",
    "campaignRefs": "Campaign",
    "experimentRefs": "Experiment",
    "moduleRefs": "Module",
    "modules": "Module",
    "resources": None,
    "nodes": None,
}

# free-form payload objects the ref-walker must not descend into: keys inside
# them are user data, not references
FREE_FORM_KEYS = {"payloadTemplate", "config", "demographics", "attributes", "annotations", "labels"}

SUM_TOLERANCE = 1e-9


def load_yaml_docs(path: Path):
    with path.open() as fh:
        return [d for d in yaml.safe_load_all(fh) if d is not None]


def walk_refs(node, field_path, out):
    """Collect (field_name, ref_value, path) for every *Ref-ish field."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in FREE_FORM_KEYS:
                continue
            here = f"{field_path}.{key}" if field_path else key
            if key in REF_KINDS:
                if isinstance(value, str):
                    out.append((key, value, here))
                elif isinstance(value, list):
                    out.extend((key, v, f"{here}[{i}]") for i, v in enumerate(value) if isinstance(v, str))
            walk_refs(value, here, out)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            walk_refs(item, f"{field_path}[{i}]", out)


class Bundle:
    def __init__(self, directory: Path, flux_validator: Draft202012Validator):
        self.dir = directory
        self.flux_validator = flux_validator
        self.errors: list[str] = []
        self.flux_docs: dict[str, dict] = {}
        self.fluid_docs: dict[str, tuple[Path, dict]] = {}

    def err(self, source, message):
        self.errors.append(f"{source}: {message}")

    def load(self):
        for path in sorted(self.dir.glob("*.flux.yml")) + sorted(self.dir.glob("*.flux.yaml")):
            for doc in load_yaml_docs(path):
                schema_errors = sorted(self.flux_validator.iter_errors(doc), key=lambda e: e.json_path)
                for e in schema_errors:
                    self.err(path.name, f"schema: {e.json_path}: {e.message}")
                doc_id = doc.get("id")
                if not isinstance(doc_id, str):
                    continue
                if doc_id in self.flux_docs:
                    self.err(path.name, f"duplicate document id '{doc_id}'")
                else:
                    self.flux_docs[doc_id] = doc
        for path in sorted(self.dir.glob("*.fluid.yml")) + sorted(self.dir.glob("*.fluid.yaml")):
            for doc in load_yaml_docs(path):
                doc_id = doc.get("id")
                if isinstance(doc_id, str):
                    self.fluid_docs[doc_id] = (path, doc)

    # ---- cross-document checks -------------------------------------------

    def check_refs(self):
        for doc_id, doc in self.flux_docs.items():
            refs: list[tuple[str, str, str]] = []
            walk_refs(doc.get("spec", {}), "spec", refs)
            for field, value, path in refs:
                expected_kind = REF_KINDS[field]
                target = self.flux_docs.get(value)
                if target is None:
                    self.err(doc_id, f"dangling reference {path} -> '{value}' (no such document in bundle)")
                elif expected_kind and target.get("kind") != expected_kind:
                    self.err(doc_id, f"{path} -> '{value}' resolves to kind {target.get('kind')}, expected {expected_kind}")

    def check_sums_and_sets(self):
        for doc_id, doc in self.flux_docs.items():
            kind, spec = doc.get("kind"), doc.get("spec", {})
            if kind == "World":
                mix = spec.get("population", {}).get("lifecycleMix", {})
                if mix and abs(sum(mix.values()) - 1.0) > SUM_TOLERANCE:
                    self.err(doc_id, f"population.lifecycleMix sums to {sum(mix.values())}, expected 1.0")
            elif kind == "Experiment":
                variants = spec.get("variants", [])
                weights = [v.get("weight", 0) for v in variants]
                if variants and abs(sum(weights) - 1.0) > SUM_TOLERANCE:
                    self.err(doc_id, f"variant weights sum to {sum(weights)}, expected 1.0")
                names = [v.get("name") for v in variants]
                if len(names) != len(set(names)):
                    self.err(doc_id, "variant names are not unique")
            elif kind == "JourneyTaxonomy":
                states = set(spec.get("states", []))
                for i, t in enumerate(spec.get("transitions", [])):
                    for end in ("from", "to"):
                        if t.get(end) not in states:
                            self.err(doc_id, f"transitions[{i}].{end} '{t.get(end)}' is not a declared state")
            elif kind == "Blueprint":
                nodes = set(spec.get("topology", {}).get("nodes", []))
                for i, e in enumerate(spec.get("topology", {}).get("edges", [])):
                    for end in ("from", "to"):
                        if e.get(end) not in nodes:
                            self.err(doc_id, f"topology.edges[{i}].{end} '{e.get(end)}' is not a declared node")
            elif kind == "Journey":
                reactions = spec.get("personaReactions", {})
                for persona_id in reactions:
                    target = self.flux_docs.get(persona_id)
                    if target is None or target.get("kind") != "Persona":
                        self.err(doc_id, f"personaReactions key '{persona_id}' does not resolve to a Persona")
                tax_ref = spec.get("taxonomyRef")
                if tax_ref:
                    tax = self.flux_docs.get(tax_ref, {})
                    states = set(tax.get("spec", {}).get("states", []))
                    for persona_id, reaction in reactions.items():
                        nxt = reaction.get("nextState")
                        if nxt and states and nxt not in states:
                            self.err(doc_id, f"personaReactions['{persona_id}'].nextState '{nxt}' is not a state of {tax_ref}")
            elif kind == "Simulation":
                tb = spec.get("timeBounds")
                if tb and tb.get("start", "") >= tb.get("end", ""):
                    self.err(doc_id, f"timeBounds.start {tb.get('start')} must precede end {tb.get('end')}")

    def check_agent_policy(self):
        for doc_id, doc in self.flux_docs.items():
            policy, skills = doc.get("agentPolicy"), doc.get("skills")
            if not skills:
                continue
            allowed = set(policy.get("allowedModels", []))
            budget = policy.get("tokenBudget", 0)
            for i, skill in enumerate(skills):
                model = skill.get("model")
                if model and model not in allowed:
                    self.err(doc_id, f"skills[{i}].model '{model}' is not in agentPolicy.allowedModels")
                sb = skill.get("tokenBudget")
                if sb and sb > budget:
                    self.err(doc_id, f"skills[{i}].tokenBudget {sb} exceeds agentPolicy.tokenBudget {budget}")

    def check_fluid_seam(self):
        fluid_validators: dict[str, Draft202012Validator] = {}
        for doc_id, doc in self.flux_docs.items():
            if doc.get("kind") != "Simulation":
                continue
            for i, emit in enumerate(doc.get("spec", {}).get("emits", [])):
                where = f"spec.emits[{i}]"
                product_ref, expose_id = emit.get("productRef"), emit.get("exposeId")
                fluid_version = emit.get("fluidVersion")
                entry = self.fluid_docs.get(product_ref)
                if entry is None:
                    self.err(doc_id, f"{where}.productRef '{product_ref}' does not resolve to a .fluid.yml document in the bundle")
                    continue
                fluid_path, fluid_doc = entry
                if fluid_version not in fluid_validators:
                    schema_file = FLUID_VENDOR_DIR / f"fluid-schema-{fluid_version}.json"
                    if not schema_file.exists():
                        self.err(doc_id, f"{where}.fluidVersion '{fluid_version}' has no vendored schema in vendor/fluid/")
                        continue
                    fluid_validators[fluid_version] = Draft202012Validator(
                        json.loads(schema_file.read_text()), format_checker=FormatChecker()
                    )
                seam_errors = sorted(fluid_validators[fluid_version].iter_errors(fluid_doc), key=lambda e: e.json_path)
                for e in seam_errors[:10]:
                    self.err(doc_id, f"{where}: contract {fluid_path.name} fails FLUID {fluid_version}: {e.json_path}: {e.message}")
                declared = fluid_doc.get("fluidVersion")
                if declared != fluid_version:
                    self.err(doc_id, f"{where}: pinned fluidVersion {fluid_version} but {fluid_path.name} declares {declared}")
                expose_ids = [e.get("exposeId") for e in fluid_doc.get("exposes", [])]
                if expose_id not in expose_ids:
                    self.err(doc_id, f"{where}.exposeId '{expose_id}' is not an expose of {product_ref} (has: {expose_ids})")

    def run(self) -> list[str]:
        self.load()
        if not self.flux_docs and not self.errors:
            self.err(str(self.dir), "bundle contains no .flux.yml documents")
        self.check_refs()
        self.check_sums_and_sets()
        self.check_agent_policy()
        self.check_fluid_seam()
        return self.errors


def main(argv: list[str]) -> int:
    flux_validator = Draft202012Validator(
        json.loads(FLUX_SCHEMA_PATH.read_text()), format_checker=FormatChecker()
    )
    Draft202012Validator.check_schema(json.loads(FLUX_SCHEMA_PATH.read_text()))

    if argv:
        bundle_dirs = [Path(a) for a in argv]
    else:
        bundle_dirs = sorted(p for p in (REPO / "examples").iterdir() if p.is_dir())

    failed = False
    for directory in bundle_dirs:
        errors = Bundle(directory, flux_validator).run()
        status = "FAIL" if errors else "ok"
        print(f"[{status}] {directory.relative_to(REPO) if directory.is_relative_to(REPO) else directory}")
        for e in errors:
            print(f"       {e}")
        failed = failed or bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
