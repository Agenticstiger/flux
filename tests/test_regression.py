#!/usr/bin/env python3
"""Regression suite for flux-schema-0.3.0.

Every SCHEMA_REJECTS case below validated silently against flux-schema-0.2.0
(the false-passes found in the pre-open-sourcing review). 0.3.0 must reject
them all. VALIDATOR_REJECTS cases pass the schema but must be caught by the
offline reference validator's cross-document checks.

Run: python3 tests/test_regression.py   (exit 0 = green)
"""

from __future__ import annotations

import contextlib
import copy
import functools
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import tracemalloc
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from validate import Bundle, canonical_digest  # noqa: E402
import enforce  # noqa: E402
import bundle as bundle_tool  # noqa: E402

SCHEMA = json.loads((REPO / "schema" / "flux-schema-latest.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
WINDOW = SCHEMA["properties"]["fluxVersion"]["enum"]   # the compatibility window (VERSIONING.md)
SCHEMA_ID_BASE = SCHEMA["$id"].rsplit("/", 1)[0]
EXAMPLES = REPO / "examples" / "telco-payment-recovery"
TOWERS_EXAMPLE = REPO / "examples" / "towers-tenant-renewal"


def envelope(kind, doc_id="doc-under-test", *, flux_version="0.3.0", **spec):
    return {
        "fluxVersion": flux_version,
        "kind": kind,
        "id": doc_id,
        "name": "Doc under test",
        "metadata": {"owner": {"team": "qa"}},
        "spec": spec,
    }


WORLD_SPEC = {
    "seed": 42,
    "population": {"size": 25000, "lifecycleMix": {"active": 0.8, "churned": 0.2}},
}

sim_fluid_style_ref = envelope(
    "Simulation",
    worldRef="q3-retention-world",
    emits=[{"productRef": "PaymentRecovery_V1", "exposeId": "x", "fluidVersion": "0.7.5"}],
)
sim_lowercase_tz = envelope(
    "Simulation",
    worldRef="w",
    timeBounds={"start": "2026-07-01t00:00:00z", "end": "2026-09-30t23:59:59z"},
    emits=[{"productRef": "p", "exposeId": "x", "fluidVersion": "0.7.5"}],
)

envelope_040 = functools.partial(envelope, flux_version="0.4.0")


ext_ns = envelope_040("Segment", query="x")
ext_ns["extensions"] = {
    "com.acme.flux/1": {"semanticRef": "semantic/customer-360", "audit": {"retentionDays": 365}}
}
ext_vendor = envelope_040("Segment", query="x")
ext_vendor["extensions"] = {"x-acme": {"anything": True}}

ext_bad_key = envelope_040("Segment", query="x")
ext_bad_key["extensions"] = {"acme": {"no": "namespace-version"}}
ext_scalar = envelope_040("Segment", query="x")
ext_scalar["extensions"] = {"com.acme.flux/1": "not-an-object"}
ext_empty = envelope_040("Segment", query="x")
ext_empty["extensions"] = {}

persona_dists = envelope_040(
    "Persona",
    traits={
        "digitalFluency": 0.7,
        "priceSensitivity": {"dist": "categorical", "levels": {"low": 0.2, "medium": 0.5, "high": 0.3}},
        "monthlySpend": {"dist": "normal", "mean": 42.0, "stddev": 11.0, "min": 0},
    },
)
sim_versioned_ref = envelope_040(
    "Simulation",
    worldRef="w",
    moduleRefs=["churn-detector@^2.1", "retention-treatment@3.0.4"],
    emits=[{"productRef": "p", "exposeId": "x", "fluidVersion": "0.7.5"}],
)
exp_semantic = envelope_040(
    "Experiment",
    variants=[{"name": "a", "weight": 1.0, "treatmentRef": "t"}],
    metrics=[{"name": "saved_customers", "semanticRef": "telco/saved_customers"}],
)

versioned_doc = envelope_040("Module", resources=["sig-x"])
versioned_doc["version"] = "2.1.3"


envelope_041 = functools.partial(envelope, flux_version="0.4.1")


PLAYBACK_BASE = {
    "worldRef": "w",
    "sourceStream": "kafka://events.v1",
    "personaMapping": [{"behaviorPattern": "x >= 1", "mapToPersona": "p"}],
}
pb_scorecard = envelope_041("Playback", **PLAYBACK_BASE,
    scorecard={"backtestWindow": "P90D", "grade": "B", "intervalCoverage": 0.92, "credibility": 0.78})
pb_bad_grade = envelope_041("Playback", **PLAYBACK_BASE,
    scorecard={"grade": "G", "credibility": 0.5})
pb_no_credibility = envelope_041("Playback", **PLAYBACK_BASE,
    scorecard={"grade": "A"})
pb_bad_window = envelope_041("Playback", **PLAYBACK_BASE,
    scorecard={"backtestWindow": "90days", "grade": "A", "credibility": 0.9})

DIGEST64 = "sha256:" + "ab12" * 16
sim_range_prov = envelope_041(
    "Simulation", worldRef="w",
    emits=[{"productRef": "p", "exposeId": "x", "fluidVersion": "^0.7.3",
            "minCredibility": 0.7,
            "provenance": {"contractDigest": DIGEST64, "outputDigest": DIGEST64}}],
)
sim_unvendored_exact = envelope_041(
    "Simulation", worldRef="w",
    # 0.7.7 is vendored as a preview since 0.5.2; 0.7.8 is vendored nowhere
    emits=[{"productRef": "p", "exposeId": "x", "fluidVersion": "0.7.8"}],
)


envelope_051 = functools.partial(envelope, flux_version="0.5.1")


# 0.5.1: the seam window widens to the newly vendored FLUID 0.7.6
sim_exact_076 = envelope_051(
    "Simulation", worldRef="w",
    emits=[{"productRef": "p", "exposeId": "x", "fluidVersion": "0.7.6"}],
)


envelope_052 = functools.partial(envelope, flux_version="0.5.2")


# 0.5.2: the seam window gains the FLUID 0.7.7 preview, selected by an exact pin
sim_exact_077 = envelope_052(
    "Simulation", worldRef="w",
    emits=[{"productRef": "p", "exposeId": "x", "fluidVersion": "0.7.7"}],
)


envelope_053 = functools.partial(envelope, flux_version="0.5.3")


# 0.5.3: the window widens, and the FLUID 0.7.7 preview moves to a newer pin
sim_exact_077_053 = envelope_053(
    "Simulation", worldRef="w",
    emits=[{"productRef": "p", "exposeId": "x", "fluidVersion": "0.7.7"}],
)
sim_garbage_range = envelope_041(
    "Simulation", worldRef="w",
    emits=[{"productRef": "p", "exposeId": "x", "fluidVersion": "banana"}],
)
sim_bad_digest = envelope_041(
    "Simulation", worldRef="w",
    emits=[{"productRef": "p", "exposeId": "x", "fluidVersion": "0.7.5",
            "provenance": {"contractDigest": "sha256:short"}}],
)

CASES_PASS = {
    "0.5.3: a 0.5.3 document pins the FLUID 0.7.7 preview exactly": sim_exact_077_053,
    "0.5.2: exact FLUID 0.7.7 (preview) pin at the seam": sim_exact_077,
    "0.5.1: exact FLUID 0.7.6 pin at the seam": sim_exact_076,
    "RFC-05: playback scorecard": pb_scorecard,
    "RFC-06: seam range + provenance + minCredibility": sim_range_prov,
    "RFC-01: scalar + categorical + normal traits": persona_dists,
    "RFC-01: versioned document envelope": versioned_doc,
    "RFC-03: semver-ranged moduleRefs": sim_versioned_ref,
    "RFC-07: semanticRef on experiment metric": exp_semantic,
    "RFC-02: namespaced extensions on a 0.4.0 doc": ext_ns,
    "RFC-02: x-vendor extensions key": ext_vendor,
    "baseline world": envelope("World", **copy.deepcopy(WORLD_SPEC)),
    "channel extension type x-whatsapp": envelope("Channel", type="x-whatsapp"),
    "hyphenated channel extension type": envelope("Channel", type="x-whatsapp-business"),
    "FLUID-grammar productRef at seam (uppercase/underscore)": sim_fluid_style_ref,
    "single-label CloudEvents type": envelope("Signal", source="urn:x", type="payment"),
    "mixed-case producer CloudEvents type": envelope(
        "Signal", source="urn:x", type="Microsoft.Storage.BlobCreated"
    ),
    "lowercase t/z RFC3339 timestamps": sim_lowercase_tz,
}

# --- documents that 0.2.0 wrongly accepted; 0.3.0 must reject -------------

w_typo = envelope("World", **copy.deepcopy(WORLD_SPEC))
w_typo["spec"]["population"]["lifecycle_mux"] = {"zombie": 9.9}

w_temp = envelope("World", **copy.deepcopy(WORLD_SPEC))
w_temp["spec"]["temperature"] = {"engagement": "very hot", "campaignResponse": -33}

w_smuggle = envelope("World", **copy.deepcopy(WORLD_SPEC))
w_smuggle["spec"]["treatmentRef"] = "tr-x"

old_envelope = {
    "fluxVersion": "0.3.0",
    "kind": "Segment",
    "metadata": {"id": "seg-old", "name": "0.2.0-style envelope"},
    "spec": {"query": "lifecycle == 'atrisk'"},
}

sim_base = {
    "worldRef": "q3-retention-world",
    "emits": [
        {"productRef": "telco.gold.x", "exposeId": "x", "fluidVersion": "0.7.5"}
    ],
}
sim_old_seam = envelope("Simulation", **copy.deepcopy(sim_base))
sim_old_seam["spec"]["emits"] = [
    {"exposeId": "x", "contract": {"fluidVersion": "banana", "kind": "DataProduct", "promise": {}}}
]
sim_empty_emits = envelope("Simulation", worldRef="w", emits=[])
sim_bad_fluid_version = envelope("Simulation", **copy.deepcopy(sim_base))
sim_bad_fluid_version["spec"]["emits"][0]["fluidVersion"] = "banana"
sim_bad_dates = envelope("Simulation", **copy.deepcopy(sim_base))
sim_bad_dates["spec"]["timeBounds"] = {"start": "not-a-date", "end": "yesterday-ish"}

skills_no_policy = envelope("Persona", traits={"digitalFluency": 0.5})
skills_no_policy["skills"] = [
    {"name": "trait-synth", "skillRef": "flux.skills.trait_synth", "purpose": "variation"}
]

unknown_top = envelope("Segment", query="x")
unknown_top["surprise"] = True

CASES_REJECT = {
    "typo'd population key (lifecycle_mux)": w_typo,
    "garbage temperature values": w_temp,
    "campaign field smuggled into World spec": w_smuggle,
    "wrong-kind spec (Persona doc with Campaign spec)": envelope(
        "Persona", treatmentRef="t", segmentRef="s", channelRef="c", consentRef="p"
    ),
    "empty ConsentProfile spec": envelope("ConsentProfile"),
    "empty Journey spec": envelope("Journey"),
    "0.2.0 envelope (id/name under metadata)": old_envelope,
    "kind missing": {k: v for k, v in envelope("World", **copy.deepcopy(WORLD_SPEC)).items() if k != "kind"},
    "kind lowercase 'world'": {**envelope("World", **copy.deepcopy(WORLD_SPEC)), "kind": "world"},
    "0.2.0 embedded-contract seam with fictional 'promise'": sim_old_seam,
    "Simulation with empty emits": sim_empty_emits,
    "unvendored fluidVersion at seam": sim_bad_fluid_version,
    "non-RFC3339 timeBounds": sim_bad_dates,
    "Experiment with empty variants": envelope("Experiment", variants=[]),
    "Experiment variant missing weight/treatmentRef": envelope("Experiment", variants=[{"name": "a"}]),
    "empty-string campaign refs": envelope(
        "Campaign", treatmentRef="", segmentRef="", channelRef="", consentRef=""
    ),
    "negative detector window": envelope("Detector", timeWindowMs=-500, pattern=[{"signalRef": "s"}]),
    "detector pattern of bare strings (0.2.0 shape)": envelope(
        "Detector", timeWindowMs=1000, pattern=["payment.aborted"]
    ),
    "negative channel rate limit": envelope("Channel", type="sms", rateLimitPerSecond=-100),
    "closed-enum channel type without x- prefix": envelope("Channel", type="whatsapp"),
    "negative offer amount + garbage currency": envelope(
        "Offer", catalogRef="c", pricing={"amount": -9.99, "currency": "banana"}
    ),
    "duplicate taxonomy states": envelope(
        "JourneyTaxonomy", states=["a", "a", "a"], transitions=[{"from": "a", "to": "a"}]
    ),
    "taxonomy transition missing 'to'": envelope(
        "JourneyTaxonomy", states=["a", "b"], transitions=[{"from": "a"}]
    ),
    "Blueprint topology with no nodes": envelope("Blueprint", topology={}),
    "Module with empty resources": envelope("Module", resources=[]),
    "skills without agentPolicy": skills_no_policy,
    "unknown top-level property": unknown_top,
    "metadata without owner": {
        **envelope("Segment", query="x"), "metadata": {"annotations": {"a": "b"}}
    },
    "impossible calendar date (month 13, hour 25)": {
        **envelope("Segment", query="x"),
        "metadata": {"owner": {"team": "qa"}, "createdAt": "2026-13-45T25:61:61Z"},
    },
    "trailing-separator id (illegal in FLUID grammar)": envelope("Segment", "recovery-", query="x"),
    "duplicate seam entries in emits": envelope(
        "Simulation",
        worldRef="w",
        emits=[
            {"productRef": "p", "exposeId": "x", "fluidVersion": "0.7.5"},
            {"productRef": "p", "exposeId": "x", "fluidVersion": "0.7.5"},
        ],
    ),
    "empty-string personaReactions key": envelope(
        "Journey",
        trigger={"signalRef": "s"},
        personaReactions={"": {"successProbability": 0.5}},
    ),
    "zero-information Persona spec ({'worldview': {}})": envelope("Persona", worldview={}),
    "RFC-02: extension key without namespace/version": ext_bad_key,
    "RFC-02: non-object extension value": ext_scalar,
    "RFC-02: empty extensions object": ext_empty,
    "RFC-01: unknown dist name": envelope_040(
        "Persona", traits={"x": {"dist": "poisson", "lambda": 3}}
    ),
    "RFC-01: categorical level above 1": envelope_040(
        "Persona", traits={"x": {"dist": "categorical", "levels": {"a": 1.5}}}
    ),
    "RFC-01: normal missing stddev": envelope_040(
        "Persona", traits={"x": {"dist": "normal", "mean": 5}}
    ),
    "RFC-03: garbage version range": envelope_040(
        "Simulation", worldRef="w", moduleRefs=["mod@banana"],
        emits=[{"productRef": "p", "exposeId": "x", "fluidVersion": "0.7.5"}],
    ),
    "RFC-03: malformed envelope version": {**versioned_doc, "version": "2.1"},
    "RFC-07: semanticRef without model/measure shape": envelope_040(
        "Experiment",
        variants=[{"name": "a", "weight": 1.0, "treatmentRef": "t"}],
        metrics=[{"name": "m", "semanticRef": "no-slash"}],
    ),
    "RFC-05: unknown grade letter": pb_bad_grade,
    "RFC-05: scorecard without credibility": pb_no_credibility,
    "RFC-05: non-ISO backtest window": pb_bad_window,
    "RFC-06: unvendored exact fluidVersion": sim_unvendored_exact,
    "RFC-06: garbage version range": sim_garbage_range,
    "RFC-06: malformed provenance digest": sim_bad_digest,
}

# --- bundle mutations the schema cannot see; validator must catch ----------


def mutate_yaml(bundle: Path, filename: str, fn):
    path = bundle / filename
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    fn(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def _dangling_ref(d):
    d["spec"]["treatmentRef"] = "tr-does-not-exist"


def _wrong_kind_ref(d):
    d["spec"]["consentRef"] = "ch-sms-primary"  # a Channel, not a ConsentProfile


def _bad_weights(d):
    for v in d["spec"]["variants"]:
        v["weight"] = 0.9


def _bad_transition(d):
    d["spec"]["transitions"].append({"from": "atrisk", "to": "nirvana"})


def _bad_mix(d):
    d["spec"]["population"]["lifecycleMix"] = {"active": 0.5, "churned": 0.2}


def _bad_expose(d):
    d["spec"]["emits"][0]["exposeId"] = "no-such-expose"


def _break_fluid(d):
    del d["exposes"]


def _bad_skill_model(d):
    d["skills"][0]["model"] = "gpt-oss-999b"


def _bad_time_order(d):
    d["spec"]["timeBounds"] = {"start": "2026-09-30T00:00:00Z", "end": "2026-07-01T00:00:00Z"}


def _payload_with_reflike_keys(d):
    # user data inside a free-form payload must NOT be treated as references
    d["spec"]["payloadTemplate"]["resources"] = ["not-a-ref", "also-not-a-ref"]
    d["spec"]["payloadTemplate"]["nodes"] = ["decoy"]


def _consent_violation(d):
    # contract expose allows a use case the gating ConsentProfile denies
    d["exposes"][0]["policy"] = {"agentPolicy": {"allowedUseCases": ["advertising", "payment_recovery"]}}


def _bad_levels_sum(d):
    d["spec"]["traits"]["priceSensitivity"]["levels"] = {"low": 0.5, "high": 0.4}


def _bad_normal_bounds(d):
    d["spec"]["traits"]["monthlySpend"]["max"] = -5


def _unsatisfied_range(d):
    d["spec"]["moduleRefs"] = ["module-payment-recovery@^9.9"]


def _digest_drift(d):
    # changing the module's content must break the lock digest
    d["spec"]["resources"].append("offer-sport-pack")


def _unknown_measure(d):
    d["spec"]["metrics"][0]["semanticRef"] = "telco/invented_metric"


def _unbind_semantic_port(d):
    d["spec"]["binds"] = [b for b in d["spec"]["binds"] if b.get("port") != "ossie-model"]


def _raise_credibility_bar(d):
    d["spec"]["emits"][0]["minCredibility"] = 0.95  # scorecard reports 0.78


def _drop_scorecard(d):
    del d["spec"]["scorecard"]


def _unsatisfiable_fluid_range(d):
    d["spec"]["emits"][0]["fluidVersion"] = "^0.8.0"


def _contract_digest_drift(d):
    # changing the contract must break the seam provenance binding
    d["exposes"][0]["contract"]["schema"].append({"name": "smuggled_column", "type": "STRING"})


VALIDATOR_REJECTS = {
    "dangling treatmentRef": ("campaign.flux.yml", _dangling_ref, "dangling reference"),
    "ref resolving to wrong kind": ("campaign.flux.yml", _wrong_kind_ref, "expected ConsentProfile"),
    "experiment weights sum 1.8": ("experiment.flux.yml", _bad_weights, "weights sum"),
    "transition to undeclared state": ("taxonomy.flux.yml", _bad_transition, "not a declared state"),
    "lifecycleMix sums to 0.7": ("world.flux.yml", _bad_mix, "lifecycleMix sums"),
    "seam exposeId not in FLUID doc": ("simulation.flux.yml", _bad_expose, "is not an expose"),
    "FLUID doc invalid at seam": ("payment-recovery.fluid.yml", _break_fluid, "fails FLUID 0.7.5"),
    "skill model outside agentPolicy": ("simulation.flux.yml", _bad_skill_model, "not in agentPolicy.allowedModels"),
    "timeBounds start after end": ("simulation.flux.yml", _bad_time_order, "must precede"),
    "contract laxer than gating ConsentProfile": ("payment-recovery.fluid.yml", _consent_violation, "denied by ConsentProfile"),
    "RFC-01: categorical levels sum 0.9": ("persona.flux.yml", _bad_levels_sum, "levels sums"),
    "RFC-01: normal min above max": ("persona.flux.yml", _bad_normal_bounds, "must be below max"),
    "RFC-03: locked version outside range": ("simulation.flux.yml", _unsatisfied_range, "does not satisfy"),
    "RFC-03: module content drift breaks digest": ("module.flux.yml", _digest_drift, "digest mismatch"),
    "RFC-07: measure not in bound model": ("experiment.flux.yml", _unknown_measure, "not declared"),
    "RFC-07: semantic port unbound": ("module.flux.yml", _unbind_semantic_port, "no Module binds the ossie-model port"),
    "RFC-05: credibility below the seam gate": ("simulation.flux.yml", _raise_credibility_bar, "below the required minCredibility"),
    "RFC-05: gate set but no scorecard": ("playback.flux.yml", _drop_scorecard, "no Playback scorecard calibrates"),
    "RFC-06: range no vendored version satisfies": ("simulation.flux.yml", _unsatisfiable_fluid_range, "no vendored FLUID version satisfies"),
    "RFC-06: contract drift breaks provenance": ("payment-recovery.fluid.yml", _contract_digest_drift, "contractDigest mismatch"),
}


def _setup_missing_lock(bundle: Path):
    (bundle / "flux.lock").unlink()


# --- malformed input must produce clean error strings, never tracebacks ----


def _setup_malformed_yaml(bundle: Path):
    (bundle / "broken.flux.yml").write_text("kind: [unclosed\n  - {", encoding="utf-8")


def _setup_non_mapping_doc(bundle: Path):
    (bundle / "scalar.flux.yml").write_text("just a string, not a document\n", encoding="utf-8")


def _setup_dup_fluid_ids(bundle: Path):
    src = (bundle / "payment-recovery.fluid.yml").read_text(encoding="utf-8")
    (bundle / "copy.fluid.yml").write_text(src, encoding="utf-8")


def _setup_flux_fluid_collision(bundle: Path):
    doc = yaml.safe_load((bundle / "payment-recovery.fluid.yml").read_text(encoding="utf-8"))
    doc["id"] = "q3-retention-world"  # collides with the World flux doc
    (bundle / "collide.fluid.yml").write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def _setup_orphan_invalid_fluid(bundle: Path):
    (bundle / "orphan.fluid.yml").write_text(
        'fluidVersion: "0.7.5"\nkind: DataProduct\nid: orphan.broken\nname: Orphan\n'
    , encoding="utf-8")


def _setup_schema_invalid_no_crash(bundle: Path):
    # the exact shapes that crashed the pre-review validator: skills without
    # agentPolicy, string tokenBudget, string lifecycleMix value, scalar timeBounds
    (bundle / "crashers.flux.yml").write_text(
        "\n---\n".join(
            [
                'fluxVersion: "0.3.0"\nkind: Persona\nid: crash-a\nname: A\nmetadata: {owner: {team: qa}}\n'
                "skills:\n  - {name: s, skillRef: r, purpose: p}\nspec: {traits: {x: 0.5}}",
                'fluxVersion: "0.3.0"\nkind: World\nid: crash-b\nname: B\nmetadata: {owner: {team: qa}}\n'
                "spec:\n  seed: 1\n  population: {size: 10, lifecycleMix: {active: banana}}",
                'fluxVersion: "0.3.0"\nkind: Simulation\nid: crash-c\nname: C\nmetadata: {owner: {team: qa}}\n'
                'spec:\n  worldRef: q3-retention-world\n  timeBounds: "2026"\n'
                '  emits: [{productRef: telco.gold.payment_recovery_moment, exposeId: payment_recovery_moment, fluidVersion: "0.7.5"}]',
            ]
        )
    , encoding="utf-8")


VALIDATOR_ROBUSTNESS = {
    "malformed YAML": (_setup_malformed_yaml, "unreadable YAML"),
    "non-mapping document": (_setup_non_mapping_doc, "not a mapping"),
    "duplicate FLUID ids": (_setup_dup_fluid_ids, "duplicate FLUID document id"),
    "flux/fluid id collision": (_setup_flux_fluid_collision, "collides with"),
    "orphan invalid .fluid.yml still validated": (_setup_orphan_invalid_fluid, "fails FLUID 0.7.5"),
    "schema-invalid shapes yield errors, not tracebacks": (_setup_schema_invalid_no_crash, "schema:"),
    "RFC-03: versioned refs without a lockfile": (_setup_missing_lock, "no flux.lock"),
}


# --- 0.5.2: the FLUID 0.7.7 preview --------------------------------------------

PREVIEW_DIR = REPO / "vendor" / "fluid-preview"
RELEASE_DIR = REPO / "vendor" / "fluid"
TOWERS_CONTRACT = "tenant-renewal-risk.fluid.yml"
TOWERS_SIMULATION = "simulation.flux.yml"

#: The towers renewal-risk rows join a tenant table on a composite key: a
#: tenant is one operator in one market.
COMPOSITE_KEY = {
    "name": "risk_to_tenant",
    "to": "tenant",
    "fromColumns": ["tenant_id", "country"],
    "toColumns": ["tenant_id", "country"],
    "cardinality": "many_to_one",
    "joinType": "inner",
}


def _load_sync_tool():
    spec = importlib.util.spec_from_file_location("sync_fluid_preview", REPO / "scripts" / "sync-fluid-preview.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _with_relationship(contract: dict, fluid_version: str, relationship: dict) -> None:
    """Give the towers contract a tenant expose and *relationship* to it."""
    contract["fluidVersion"] = fluid_version
    risk = contract["exposes"][0]
    tenant = {
        "exposeId": "tenant",
        "kind": "table",
        "contract": {
            "schema": [
                {"name": "tenant_id", "type": "STRING", "required": True},
                {"name": "country", "type": "STRING", "required": True},
                {"name": "tenant_segment", "type": "STRING", "required": True},
            ]
        },
        "binding": copy.deepcopy(risk["binding"]),
    }
    tenant["binding"]["location"]["table"] = "tenant"
    contract["exposes"].append(tenant)
    risk["semantics"] = {"relationships": [relationship]}


def _towers_on(bundle: Path, fluid_version: str, emit_pin: str, relationship: dict = COMPOSITE_KEY,
               change=None) -> None:
    """The towers bundle with its contract on *fluid_version*, carrying a
    relationship and any *change*, and its emit pinned to *emit_pin* with a
    re-pinned digest."""
    shutil.copytree(TOWERS_EXAMPLE, bundle)
    contract_path = bundle / TOWERS_CONTRACT
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    _with_relationship(contract, fluid_version, copy.deepcopy(relationship))
    if change is not None:
        change(contract)
    contract_path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")

    def pin(sim):
        sim["fluxVersion"] = "0.5.2"
        emit = sim["spec"]["emits"][0]
        emit["fluidVersion"] = emit_pin
        emit["provenance"]["contractDigest"] = "sha256:" + canonical_digest(contract)

    mutate_yaml(bundle, TOWERS_SIMULATION, pin)


def _move_key(d):
    # the contract changes after the Simulation pinned its digest: the
    # composite key's column order is swapped on both sides
    rel = d["exposes"][0]["semantics"]["relationships"][0]
    rel["fromColumns"].reverse()
    rel["toColumns"].reverse()


def _accepted_fluid_versions(schema_bytes: bytes) -> list:
    """The fluidVersion values a FLUID schema accepts; none when it is not one."""
    try:
        return json.loads(schema_bytes)["properties"]["fluidVersion"]["enum"]
    except (ValueError, KeyError, TypeError):
        return []


def _check_preview_pins(pins: list[dict]) -> list[str]:
    """Every preview file has one pin, and the pin names its bytes."""
    problems = []
    files = sorted(p.name for p in PREVIEW_DIR.glob("fluid-schema-*.json"))
    if sorted(pin["file"] for pin in pins) != files:
        problems.append(f"pinned files {sorted(pin['file'] for pin in pins)} != vendored files {files}")
    releases = {p.stem.replace("fluid-schema-", "") for p in RELEASE_DIR.glob("fluid-schema-*.json")}
    for pin in pins:
        path = PREVIEW_DIR / pin["file"]
        if path.is_symlink():
            problems.append(f"{pin['file']} is a symlink, not a vendored copy")
        data = path.read_bytes() if path.is_file() else b""
        if hashlib.sha256(data).hexdigest() != pin["sha256"]:
            problems.append(f"{pin['file']} bytes do not match the pinned sha256 (re-run scripts/sync-fluid-preview.py)")
        if (pin["repository"], pin["path"]) != ("https://github.com/Agenticstiger/forge-cli", f"fluid_build/schemas/{pin['file']}"):
            problems.append(f"{pin['file']} is not pinned to forge-cli's fluid_build/schemas/: {pin['repository']} {pin['path']}")
        if pin["fluidVersion"] in releases:
            problems.append(f"FLUID {pin['fluidVersion']} is vendored as a release and as a preview")
        if pin["fluidVersion"] not in _accepted_fluid_versions(data):
            problems.append(f"{pin['file']} does not accept fluidVersion {pin['fluidVersion']}")
    return ["[preview] pins do not name the vendored previews: " + "; ".join(problems)] if problems else []


def _check_seam_window(pins: list[dict]) -> list[str]:
    """The seam window is exactly the vendored FLUID versions, releases and previews."""
    simulation = next(
        branch["then"] for branch in SCHEMA["allOf"]
        if branch.get("if", {}).get("properties", {}).get("kind", {}).get("const") == "Simulation"
    )
    window = simulation["properties"]["spec"]["properties"]["emits"]["items"]["properties"]["fluidVersion"]["anyOf"][0]["enum"]
    releases = {p.stem.replace("fluid-schema-", "") for p in RELEASE_DIR.glob("fluid-schema-*.json")}
    vendored = sorted(releases | {pin["fluidVersion"] for pin in pins})
    if sorted(window) != vendored:
        return [f"[preview] the seam window {window} is not exactly the vendored FLUID versions {vendored}"]
    return []


def _check_bad_pins(sync_tool, good: dict) -> list[str]:
    """A pin that could move, or point outside its repository, is refused."""
    failures = []
    for label, change in {
        "a branch for a commit": {"commit": "main"},
        "a short commit": {"commit": good.get("commit", "")[:12]},
        "a path that climbs out of the repository": {"path": "fluid_build/../../etc/fluid-schema-0.7.7.json"},
        "a repository that is not on GitHub": {"repository": "https://example.com/forge-cli"},
        "an owner that is only dots": {"repository": "https://github.com/../forge-cli"},
        "a commit with a trailing newline": {"commit": good.get("commit", "") + "\n"},
        "a file that does not hold its version": {"fluidVersion": "0.7.8"},
    }.items():
        try:
            sync_tool.check_pin({**good, **change})
        except sync_tool.PinError:
            continue
        failures.append(f"[preview] check_pin accepted {label}")
    return failures


def _check_sync_refusals(sync_tool) -> list[str]:
    """A pins file that is not JSON, and bytes that are not a FLUID schema, are refused."""
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        broken = Path(tmp) / "pins.json"
        broken.write_text("{", encoding="utf-8")
        try:
            sync_tool.load_pins(broken)
            failures.append("[preview] load_pins accepted a pins file that is not JSON")
        except sync_tool.PinError:
            pass
    pin = {"path": "p", "commit": "c", "fluidVersion": "0.7.7"}
    for label, data in {"not JSON": b"{", "no fluidVersion enum": b"{}",
                        "another version": b'{"properties": {"fluidVersion": {"enum": ["0.7.6"]}}}'}.items():
        try:
            sync_tool.check_schema(pin, data)
            failures.append(f"[preview] check_schema accepted bytes that are {label}")
        except sync_tool.FetchError:
            pass
    return failures


def check_fluid_previews() -> list[str]:
    """The pins name the vendored bytes, the seam window is exactly the vendored
    set, and the immutable 0.5.1 file still refuses the preview pin."""
    sync_tool = _load_sync_tool()
    try:
        pins = sync_tool.load_pins(PREVIEW_DIR / "pins.json")
    except Exception as exc:  # noqa: BLE001 - a bad pin file is the failure
        return [f"[preview] pins.json does not load: {type(exc).__name__}: {exc}"]
    failures = _check_preview_pins(pins) + _check_seam_window(pins) + _check_bad_pins(sync_tool, pins[0] if pins else {})
    failures += _check_sync_refusals(sync_tool)
    # released schema files are immutable: 0.5.1 still refuses the 0.7.7 pin
    schema_051 = Draft202012Validator(json.loads((REPO / "schema" / "flux-schema-0.5.1.json").read_text(encoding="utf-8")))
    if not list(schema_051.iter_errors({**sim_exact_077, "fluxVersion": "0.5.1"})):
        failures.append("[schema] an exact FLUID 0.7.7 pin should fail the immutable 0.5.1 schema")
    return failures


def check_preview_bundles(flux_validator) -> list[str]:
    """An exact pin selects the 0.7.7 preview and a composite-key relationship
    validates; a moved key changes the digest; a broken relationship fails the
    preview schema; a range never selects it; a 0.7.6 contract cannot carry
    relationships."""
    failures = []
    cases = {
        "exact": ("0.7.7", "0.7.7", COMPOSITE_KEY),
        "broken": ("0.7.7", "0.7.7", {k: v for k, v in COMPOSITE_KEY.items() if k != "cardinality"}),
        "range": ("0.7.7", "^0.7.3", COMPOSITE_KEY),
        "0.7.6": ("0.7.6", "0.7.6", COMPOSITE_KEY),
    }
    expected = {
        "broken": (lambda e: "fails FLUID 0.7.7 (preview)" in e and "'cardinality' is a required property" in e,
                   "a relationship without a cardinality passed the 0.7.7 preview"),
        "range": (lambda e: "a range never selects a preview" in e and 'pin fluidVersion "0.7.7" exactly' in e,
                  "a range selected the 0.7.7 preview"),
        "0.7.6": (lambda e: "fails FLUID 0.7.6" in e and "relationships" in e, "a 0.7.6 contract carried relationships"),
    }
    for label, (fluid_version, emit_pin, relationship) in cases.items():
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            _towers_on(bundle, fluid_version, emit_pin, relationship=relationship)
            errors = Bundle(bundle, flux_validator).run()
            if label == "exact":
                if errors:
                    failures.append(f"[validator] an exact 0.7.7 pin with a composite-key relationship failed: {errors[:5]}")
                mutate_yaml(bundle, TOWERS_CONTRACT, _move_key)
                errors = Bundle(bundle, flux_validator).run()
                if not any("provenance.contractDigest mismatch" in e for e in errors):
                    failures.append(f"[validator] a moved key left the contract digest unchanged: {errors[:3]}")
                continue
            matches, message = expected[label]
            if not any(matches(e) for e in errors):
                failures.append(f"[validator] {message}: {errors[:3]}")
    return failures


# --- 0.5.3: the FLUID 0.7.7 preview re-pinned to forge-cli e88301f7 ----------

def _column(field: str, value, column: int = 4):
    """Set *field* on one column of the towers contract (4 is country, 0 is tenant_id)."""
    def change(contract):
        contract["exposes"][0]["contract"]["schema"][column][field] = value
    return change


def _registry(kind: str, **extra):
    """Give the towers expose a schema registry of *kind*: Confluent is
    addressed by a url, Glue by a registry name."""
    def change(contract):
        registry = {"kind": kind, "subject": "tenant_renewal_risk", **extra}
        if kind == "confluent":
            registry["url"] = "https://registry.example.com"
        else:
            registry["registryName"] = "towers"
        contract["exposes"][0]["binding"].setdefault("properties", {})["registry"] = registry
    return change


#: What the e88301f7 pin accepts in a 0.7.7 contract. The 32fce8e3 pin that
#: flux-spec 0.5.2 carried refused the punctuation in the first two levels,
#: protobuf on a column and rules on a registry (schema-diffs/diff-0.5.2-to-0.5.3.md).
REPIN_ACCEPTS = {
    "quoted enum levels holding punctuation and a doubled quote": _column("type", "enum('Dr.', '>10000', 'O''Brien', 'a, b')"),
    "a quoted enum level holding parentheses and a slash": _column("type", "enum('(none)', 'a/b')"),
    "double-quoted enum levels": _column("type", 'enum("x", "say ""hi""")'),
    "an enum of word lists, as before": _column("type", "enum(IE, United Kingdom)"),
    "protobuf.field 1": _column("protobuf", {"field": 1}, column=0),
    "protobuf.field 536870911, the largest": _column("protobuf", {"field": 536870911}, column=0),
    "rules on a Confluent registry": _registry("confluent", rules=True),
    "a Glue registry without rules": _registry("glue"),
}

#: What it refuses, and where the preview says so. The enum forms all
#: validated under the 32fce8e3 pin.
REPIN_REFUSES = {
    "enum levels without commas": (_column("type", "enum('a' 'b')"), "$.exposes[0].contract.schema[4].type"),
    "an empty enum level": (_column("type", "enum(a,,b)"), "$.exposes[0].contract.schema[4].type"),
    "a trailing comma in an enum": (_column("type", "enum(a, b,)"), "$.exposes[0].contract.schema[4].type"),
    "text after a closing quote in an enum": (_column("type", "enum('a'b)"), "$.exposes[0].contract.schema[4].type"),
    "a tab inside a quoted enum level": (_column("type", "enum('a\tb')"), "$.exposes[0].contract.schema[4].type"),
    "a newline inside a quoted enum level": (_column("type", "enum('a\nb')"), "$.exposes[0].contract.schema[4].type"),
    "a C1 control character inside a quoted enum level": (_column("type", "enum('a\x85b')"),
                                                          "$.exposes[0].contract.schema[4].type"),
    "protobuf.field 19000, which Protobuf reserves": (_column("protobuf", {"field": 19000}, column=0),
                                                      "$.exposes[0].contract.schema[0].protobuf.field"),
    "protobuf.field 0": (_column("protobuf", {"field": 0}, column=0), "$.exposes[0].contract.schema[0].protobuf.field"),
    "rules on a Glue registry": (_registry("glue", rules=True), "$.exposes[0].binding.properties.registry"),
}


def check_preview_repin(flux_validator) -> list[str]:
    """0.5.3 re-pins the 0.7.7 preview: a 0.7.7 contract in a bundle that pins
    fluxVersion 0.5.2 is checked against the new pin, which accepts and refuses
    what REPIN_ACCEPTS and REPIN_REFUSES list; and the immutable 0.5.2 schema
    refuses a 0.5.3 document."""
    failures = []
    for label, change in REPIN_ACCEPTS.items():
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            _towers_on(bundle, "0.7.7", "0.7.7", change=change)
            errors = Bundle(bundle, flux_validator).run()
            if errors:
                failures.append(f"[preview] the 0.7.7 preview refused {label}: {errors[:3]}")
    for label, (change, where) in REPIN_REFUSES.items():
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            _towers_on(bundle, "0.7.7", "0.7.7", change=change)
            errors = Bundle(bundle, flux_validator).run()
            if not any(f"fails FLUID 0.7.7 (preview): {where}" in e for e in errors):
                failures.append(f"[preview] the 0.7.7 preview did not refuse {label} at {where}: {errors[:3]}")
    # released schema files are immutable: 0.5.2 refuses a 0.5.3 document
    schema_052 = Draft202012Validator(json.loads((REPO / "schema" / "flux-schema-0.5.2.json").read_text(encoding="utf-8")))
    if not list(schema_052.iter_errors(sim_exact_077_053)):
        failures.append("[schema] a 0.5.3 document should fail the immutable 0.5.2 schema (fluxVersion window)")
    return failures


def check_pack_from_looser_preview(flux_validator) -> list[str]:
    """verify reads the preview the running release carries (VERSIONING.md,
    FLUID previews): a pack made while the 0.7.7 preview admitted
    enum('a' 'b'), as flux-spec 0.5.2's 32fce8e3 pin did, no longer verifies,
    and says why."""
    validate_impl = sys.modules[Bundle.__module__]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # a stand-in for the old pin: this preview with the column type left
        # open, so the pack step accepts enum('a' 'b') as 0.5.2 did
        looser = json.loads((PREVIEW_DIR / "fluid-schema-0.7.7.json").read_text(encoding="utf-8"))
        looser["$defs"]["column"]["properties"]["type"] = {"type": "string"}
        looser_dir = tmp / "looser-preview"
        looser_dir.mkdir()
        (looser_dir / "fluid-schema-0.7.7.json").write_text(json.dumps(looser), encoding="utf-8")
        source = tmp / "source"
        _towers_on(source, "0.7.7", "0.7.7", change=_column("type", "enum('a' 'b')"))
        real = validate_impl.FLUID_PREVIEW_DIR
        validate_impl.FLUID_PREVIEW_DIR = looser_dir
        try:
            rc, archive = _pack_as("0.5.2", source, tmp / "bundle", tmp / "dist")
        finally:
            validate_impl.FLUID_PREVIEW_DIR = real
        if rc != 0:
            return ["[bundle] could not pack enum('a' 'b') under a looser 0.7.7 preview, so its refusal is untested"]
        rc, said = _verify_output(archive, flux_validator)
        expected = ("bundle no longer validates against flux-schema-0.5.2.json",
                    "fails FLUID 0.7.7 (preview): $.exposes[0].contract.schema[4].type")
        if rc == 0 or not all(fragment in said for fragment in expected):
            return [f"[bundle] a pack made under a looser 0.7.7 preview was not refused for its enum: {said.strip()}"]
    return []


def _repack(work: Path, out: Path, mutate, flux_validator):
    """Rebuild a packed archive, applying `mutate(members) -> members`."""
    bundle_tool.pack(work, out, flux_validator)
    src_path = out / f"{work.name}.flux.tgz"
    entries = []
    with tarfile.open(src_path, "r:gz") as src:
        for m in src.getmembers():
            entries.append((m.name, src.extractfile(m).read()))
    entries = mutate(entries)
    attacked = out / "attacked.flux.tgz"
    with tarfile.open(attacked, "w:gz") as dst:
        for name, data in entries:
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(data), 0, 0o644
            dst.addfile(info, io.BytesIO(data))
    return attacked


def _edit_manifest(entries, fn):
    out = []
    for name, data in entries:
        if name.endswith(bundle_tool.MANIFEST_NAME):
            doc = json.loads(data)
            fn(doc)
            data = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode()
        out.append((name, data))
    return out


def _lie(field, value):
    return lambda entries: _edit_manifest(entries, lambda m: m.__setitem__(field, value))


def _verify_output(archive, flux_validator):
    """verify's exit code and what it printed, so a refusal's reason is checked too."""
    said = io.StringIO()
    with contextlib.redirect_stdout(said):
        rc = bundle_tool.verify(archive, flux_validator)
    return rc, said.getvalue()


def _pack_as(version, source, work, out):
    """Pack *source* the way flux-spec *version* did: that release's schema
    validates it and its $id is the schemaId (pack is otherwise unchanged)."""
    schema_path = REPO / "schema" / f"flux-schema-{version}.json"
    then = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")), format_checker=FormatChecker())
    shutil.copytree(source, work)
    current = bundle_tool.SCHEMA_PATH
    bundle_tool.SCHEMA_PATH = schema_path
    try:
        rc = bundle_tool.pack(work, out, then)
    finally:
        bundle_tool.SCHEMA_PATH = current
    return rc, out / f"{work.name}.flux.tgz"


def check_packs_across_releases(flux_validator) -> list[str]:
    """RFC-09 across releases: a pack names the schema it was validated against
    (schemaId), and verify re-validates against that schema while it is inside
    this toolchain's compatibility window (VERSIONING.md). Re-packing is no
    remedy: it changes the manifest bytes a detached signature covers."""
    failures = []
    accepted = bundle_tool.accepted_schemas()
    if [version for version, _ in accepted.values()] != WINDOW or any(
        schema_id != f"{SCHEMA_ID_BASE}/flux-schema-{version}.json" for schema_id, (version, _) in accepted.items()
    ):
        failures.append(f"[bundle] the window {WINDOW} does not resolve to one shipped schema per version: {sorted(accepted)}")

    # the releases that shipped the bundler before this one: their packs are in the wild
    for version in ("0.5.0", "0.5.1", "0.5.2"):
        with tempfile.TemporaryDirectory() as tmp:
            work, out = Path(tmp) / "bundle", Path(tmp) / "dist"
            rc, archive = _pack_as(version, EXAMPLES, work, out)
            named = json.loads((work / bundle_tool.MANIFEST_NAME).read_text(encoding="utf-8"))["schemaId"] if rc == 0 else None
            if named != f"{SCHEMA_ID_BASE}/flux-schema-{version}.json":
                failures.append(f"[bundle] could not pack the example the way flux-spec {version} did (schemaId {named})")
                continue
            rc, said = _verify_output(archive, flux_validator)
            if rc != 0 or f"re-validated against flux-schema-{version}.json" not in said:
                failures.append(f"[bundle] a pack made under the {version} schema does not verify: {said.strip()}")
    return failures


def check_schema_id_refusals(flux_validator) -> list[str]:
    """The schemaId picks the schema that re-validates, and only inside the
    window; the window is read from the current schema, never restated."""
    failures = []
    accepted_versions = f"compatibility window (FLUX {', '.join(WINDOW)})"
    lies = {
        # the towers bundle pins fluxVersion 0.5.1 and FLUID 0.7.6, which the 0.5.0 schema refuses
        "0.5.0 for the towers bundle": (TOWERS_EXAMPLE, "0.5.0", "no longer validates against flux-schema-0.5.0.json"),
        # outside the window: the 0.2.0 draft before it, and a release after this toolchain
        "the 0.2.0 draft": (EXAMPLES, "0.2.0", accepted_versions),
        "a release this toolchain predates": (EXAMPLES, "9.9.9", accepted_versions),
    }
    for label, (source, version, expected) in lies.items():
        with tempfile.TemporaryDirectory() as tmp:
            work, out = Path(tmp) / "bundle", Path(tmp) / "dist"
            shutil.copytree(source, work)
            claims = _lie("schemaId", f"{SCHEMA_ID_BASE}/flux-schema-{version}.json")
            rc, said = _verify_output(_repack(work, out, claims, flux_validator), flux_validator)
            if rc == 0 or expected not in said:
                failures.append(f"[bundle] a schemaId naming {label} was not refused with '{expected}': {said.strip()}")

    # a breaking release that resets the window refuses a 0.5.1 pack and names what it accepts
    with tempfile.TemporaryDirectory() as tmp:
        work, out = Path(tmp) / "bundle", Path(tmp) / "dist"
        _, archive = _pack_as("0.5.1", EXAMPLES, work, out)
        reset = copy.deepcopy(SCHEMA)
        reset["properties"]["fluxVersion"]["enum"] = [WINDOW[-1]]
        reset_path = Path(tmp) / "flux-schema-latest.json"
        reset_path.write_text(json.dumps(reset), encoding="utf-8")
        current = bundle_tool.SCHEMA_PATH
        bundle_tool.SCHEMA_PATH = reset_path
        try:
            rc, said = _verify_output(archive, flux_validator)
        finally:
            bundle_tool.SCHEMA_PATH = current
        if rc == 0 or f"compatibility window (FLUX {WINDOW[-1]})" not in said:
            failures.append(f"[bundle] a reset window did not refuse a pack made before it: {said.strip()}")
    return failures


def check_pack_refuses_symlinks(flux_validator) -> list[str]:
    """pack refuses a link anywhere in the bundle before reading through it: a
    linked file would put its target's bytes into a signed archive, and a
    planted flux-manifest.json link would aim the manifest write at its target."""
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        outside = Path(tmp) / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("TOP-SECRET\n", encoding="utf-8")
        cases = {
            "a linked file outside the bundle": ("notes.txt", secret),
            "a linked directory": ("more", outside),
            "a planted flux-manifest.json link": (bundle_tool.MANIFEST_NAME, secret),
        }
        for i, (label, (name, target)) in enumerate(cases.items()):
            work, out = Path(tmp) / f"bundle{i}", Path(tmp) / f"dist{i}"
            shutil.copytree(EXAMPLES, work)
            (work / name).unlink(missing_ok=True)   # a manifest left by an earlier pack of the example
            (work / name).symlink_to(target)
            said = io.StringIO()
            with contextlib.redirect_stdout(said):
                rc = bundle_tool.pack(work, out, flux_validator)
            refused = rc != 0 and f"unsupported bundle entry (symlink): {name}" in said.getvalue()
            if not refused or out.exists() or secret.read_text(encoding="utf-8") != "TOP-SECRET\n":
                failures.append(f"[bundle] pack did not refuse {label} before reading it: {said.getvalue().strip()}")
    return failures


def check_manifest_write_never_follows_a_link(flux_validator) -> list[str]:
    """The manifest write itself opens with O_NOFOLLOW (POSIX): a link that
    appears after pack's symlink refusal fails the pack, never its target."""
    if not hasattr(os, "O_NOFOLLOW"):
        return []
    with tempfile.TemporaryDirectory() as tmp:
        victim = Path(tmp) / "victim.txt"
        victim.write_text("untouched\n", encoding="utf-8")
        work, out = Path(tmp) / "bundle", Path(tmp) / "dist"
        shutil.copytree(EXAMPLES, work)
        (work / bundle_tool.MANIFEST_NAME).unlink(missing_ok=True)
        (work / bundle_tool.MANIFEST_NAME).symlink_to(victim)
        scan = bundle_tool._symlink_entries
        bundle_tool._symlink_entries = lambda directory: []   # as if the link appeared after the scan
        said = io.StringIO()
        try:
            with contextlib.redirect_stdout(said):
                rc = bundle_tool.pack(work, out, flux_validator)
        finally:
            bundle_tool._symlink_entries = scan
        if rc == 0 or f"cannot write {bundle_tool.MANIFEST_NAME}" not in said.getvalue() or victim.read_text(encoding="utf-8") != "untouched\n":
            return [f"[bundle] the manifest write followed a planted link: {said.getvalue().strip()}"]
    return []


def _member(name: str, kind=tarfile.REGTYPE, linkname: str = "") -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.type, info.linkname, info.mode = kind, linkname, 0o644
    info.size = 1 if kind == tarfile.REGTYPE else 0
    return info


def _append_member(work: Path, out: Path, member: tarfile.TarInfo, flux_validator) -> Path:
    """The packed archive plus one more member, as an attacker would add it."""
    bundle_tool.pack(work, out, flux_validator)
    attacked = out / "attacked.flux.tgz"
    with tarfile.open(out / f"{work.name}.flux.tgz", "r:gz") as src, tarfile.open(attacked, "w:gz") as dst:
        for m in src.getmembers():
            dst.addfile(m, src.extractfile(m))
        dst.addfile(member, io.BytesIO(b"x") if member.isfile() else None)
    return attacked


def check_verify_refuses_unsafe_members(flux_validator) -> list[str]:
    """verify's _extract_safely refusals, each pinned by its message, with
    nothing written outside verify's own scratch directory."""
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        # verify's scratch directory goes under `scratch`, so bundle/../../escape.txt
        # would land at scratch/escape.txt if the refusal ever stopped working
        scratch, escape = Path(tmp) / "scratch", Path(tmp) / "absolute-escape.txt"
        scratch.mkdir()
        attacks = {
            "a member with ..": (_member("bundle/../../escape.txt"), "unsafe archive path: bundle/../../escape.txt"),
            "an absolute member": (_member(str(escape)), f"unsafe archive path: {escape}"),
            "a symlink member": (_member("bundle/link", tarfile.SYMTYPE, "/etc/passwd"),
                                 "unsupported archive entry (symlink): bundle/link"),
            "a hard link member": (_member("bundle/hard", tarfile.LNKTYPE, "bundle/world.flux.yml"),
                                   "unsupported archive entry"),
            "a FIFO member": (_member("bundle/fifo", tarfile.FIFOTYPE), "unsupported archive entry (special): bundle/fifo"),
            "a file beside the bundle directory": (_member("bundle"), "entry outside the bundle directory: bundle"),
        }
        for i, (label, (member, expected)) in enumerate(attacks.items()):
            work, out = Path(tmp) / f"w{i}" / "bundle", Path(tmp) / f"d{i}"
            shutil.copytree(EXAMPLES, work)
            attacked = _append_member(work, out, member, flux_validator)
            tempfile.tempdir = str(scratch)
            try:
                rc, said = _verify_output(attacked, flux_validator)
            except Exception as exc:  # noqa: BLE001 (a traceback is the failure)
                failures.append(f"[bundle] CRASHED ({type(exc).__name__}: {exc}) on {label}")
                continue
            finally:
                tempfile.tempdir = None
            escaped = [p for p in (escape, scratch / "escape.txt") if p.exists()]
            if rc == 0 or expected not in said or escaped:
                failures.append(f"[bundle] verify did not refuse {label} with '{expected}': {said.strip()}")
            for path in escaped:   # so one broken refusal does not fail the cases after it
                path.unlink()

        work, out = Path(tmp) / "capped" / "bundle", Path(tmp) / "capped-dist"
        shutil.copytree(EXAMPLES, work)
        bundle_tool.pack(work, out, flux_validator)
        cap = bundle_tool.MAX_MEMBERS
        bundle_tool.MAX_MEMBERS = 5
        try:
            rc, said = _verify_output(out / "bundle.flux.tgz", flux_validator)
        finally:
            bundle_tool.MAX_MEMBERS = cap
        if rc == 0 or "members, above the 5 cap" not in said:
            failures.append(f"[bundle] verify did not refuse an archive above the member cap: {said.strip()}")
    return failures


def _first_flip_raising(data: bytes, error: type) -> bytes | None:
    """*data* with its first single-byte flip past the gzip header that makes
    reading the archive's headers raise *error*, or None if no flip does."""
    for i in range(10, len(data)):
        flipped = data[:i] + bytes([data[i] ^ 0xFF]) + data[i + 1:]
        try:
            with tarfile.open(fileobj=io.BytesIO(flipped), mode="r:gz") as tar:
                tar.getmembers()
        except error:
            return flipped
        except Exception:  # noqa: BLE001 (another refusal: not the flip this needs)
            continue
    return None


def check_verify_stops_at_its_caps_and_reports_a_broken_stream(flux_validator) -> list[str]:
    """verify counts its member and byte caps as it reads each header, and
    reports an archive whose gzip stream is cut short or corrupt.

    Listing every header before the member cap was checked read an archive of
    any number of headers in full. A cut stream raised gzip's EOFError, and a
    corrupt one zlib.error, out of a function that says it never raises.
    """
    import zlib

    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        work, out = Path(tmp) / "bundle", Path(tmp) / "dist"
        shutil.copytree(EXAMPLES, work)
        bundle_tool.pack(work, out, flux_validator)
        archive = out / "bundle.flux.tgz"

        headers = []
        real_next = tarfile.TarFile.next

        def counting_next(self):
            headers.append(1)
            return real_next(self)

        cap = bundle_tool.MAX_MEMBERS
        bundle_tool.MAX_MEMBERS, tarfile.TarFile.next = 2, counting_next
        try:
            rc, said = _verify_output(archive, flux_validator)
        finally:
            bundle_tool.MAX_MEMBERS, tarfile.TarFile.next = cap, real_next
        if rc == 0 or "members, above the 2 cap" not in said or len(headers) > 6:
            failures.append(f"[bundle] verify read {len(headers)} headers past a member cap of 2: {said.strip()}")

        data = archive.read_bytes()
        broken = {"a gzip stream cut in half": (data[: len(data) // 2], None),
                  # Raised by the read itself, as tarfile up to Python 3.13 lets it
                  # out; 3.14's tarfile turns every flip into a ReadError.
                  "zlib.error from the stream": (data, zlib.error("invalid distance too far back"))}
        corrupt = _first_flip_raising(data, zlib.error)
        if corrupt is not None:
            broken["a corrupt gzip stream"] = (corrupt, None)
        for i, (label, (blob, raised)) in enumerate(broken.items()):
            target = Path(tmp) / f"broken{i}.flux.tgz"
            target.write_bytes(blob)

            def failing_next(self, raised=raised):
                raise raised

            if raised is not None:
                tarfile.TarFile.next = failing_next
            try:
                rc, said = _verify_output(target, flux_validator)
            except Exception as exc:  # noqa: BLE001 (a traceback is the failure)
                failures.append(f"[bundle] CRASHED ({type(exc).__name__}: {exc}) on {label}")
                continue
            finally:
                tarfile.TarFile.next = real_next
            if rc == 0 or "not a readable gzip archive" not in said:
                failures.append(f"[bundle] verify did not report {label}: {said.strip()}")
    return failures


def check_verify_never_raises_on_deep_nesting_or_a_nul_path(flux_validator) -> list[str]:
    """verify reports, and the validator reports, what would otherwise raise.

    json and PyYAML read a nested array by recursion, so a manifest or a
    document nested past the interpreter's recursion limit raised
    RecursionError, and a NUL byte in a PAX path record raised ValueError from
    the filesystem, out of a verify that says it never raises.
    """
    deep_json = b"[" * 200_000 + b"]" * 200_000
    deep_yaml = b"a: " + b"[" * 100_000 + b"]" * 100_000 + b"\n"

    def replacing(name, data):
        return lambda entries: [(n, data if n.endswith("/" + name) else d) for n, d in entries]

    def adding(name, data):
        return lambda entries: entries + [(name, data)]

    attacks = {
        "a manifest nested too deeply": (replacing("flux-manifest.json", deep_json),
                                         "flux-manifest.json is nested too deeply to read"),
        "a document nested too deeply": (adding("bundle/deep.flux.yml", deep_yaml),
                                         "unreadable YAML: nested too deeply to read"),
        "a NUL byte in a long PAX path": (adding("bundle/" + "a" * 120 + "\x00b.flux.yml", b"kind: World\n"),
                                          "holds a NUL byte"),
        "a NUL byte in a non-ASCII PAX path": (adding("bundle/\u00e9\x00b.flux.yml", b"kind: World\n"),
                                               "holds a NUL byte"),
    }
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, (label, (mutate, expected)) in enumerate(attacks.items()):
            work, out = Path(tmp) / f"w{i}" / "bundle", Path(tmp) / f"d{i}"
            shutil.copytree(EXAMPLES, work)
            attacked = _repack(work, out, mutate, flux_validator)
            try:
                rc, said = _verify_output(attacked, flux_validator)
            except Exception as exc:  # noqa: BLE001 (a traceback is the failure)
                failures.append(f"[bundle] CRASHED ({type(exc).__name__}: {str(exc)[:80]}) on {label}")
                continue
            if rc == 0 or expected not in said:
                failures.append(f"[bundle] verify did not report {label} with '{expected}': {said.strip()[:200]}")

        work = Path(tmp) / "deep" / "bundle"
        shutil.copytree(EXAMPLES, work)
        (work / "deep.flux.yml").write_bytes(deep_yaml)
        try:
            errors = Bundle(work, flux_validator).run()
        except Exception as exc:  # noqa: BLE001
            failures.append(f"[validate] CRASHED ({type(exc).__name__}) on a document nested too deeply")
        else:
            if not any("nested too deeply to read" in e for e in errors):
                failures.append(f"[validate] a document nested too deeply was not reported: {errors[:3]}")
    return failures


def check_a_subclass_lets_its_own_refusal_out_of_run_through_the_guard(flux_validator) -> list[str]:
    """`Bundle.run` runs `load` and every check through `_guarded`, and reports what a step raises. A subclass
    that must refuse a bundle with an exception of its own, as the FLUX engine's `SeamBundle` does from `load`
    and from `check_supply_chain`, overrides `_guarded` to let it out of `run` (the pattern is in its
    docstring). That is a contract of this class: a step that ran outside the guard, or a guard under another
    name, would let the engine's refusal be reported as a string, or raise a hostile document's exception out
    of `run`, and this check fails then, in this repository's own CI."""
    class Refusal(Exception):
        pass

    def let_out(self, step):
        refused = []

        @functools.wraps(step)
        def refusing():
            try:
                step()
            except Refusal as exc:
                refused.append(exc)
                raise

        Bundle._guarded(self, refusing)
        if refused:
            raise refused[0]

    steps = ("load", "check_refs", "check_sums_and_sets", "check_traits", "check_supply_chain",
             "check_semantics", "check_agent_policy", "check_fluid_documents", "check_fluid_seam")
    failures = []

    seen = []

    class Watching(Bundle):
        def _guarded(self, step):
            seen.append(step.__name__)
            super()._guarded(step)

    Watching(EXAMPLES, flux_validator).run()
    missing, extra = sorted(set(steps) - set(seen)), sorted(set(seen) - set(steps))
    if missing or extra or len(seen) != len(steps) or seen[:1] != ["load"]:
        failures.append(
            f"[guard] run() must send load first and each check once through _guarded; the steps this check holds "
            f"are `steps` here: add a new check to it, or find the step that runs outside the guard "
            f"(not sent: {missing}; sent but not held: {extra}; sent: {seen})")

    for name in steps:
        def refuse(self, _name=name):
            raise Refusal(_name)

        refuse.__name__ = name  # the guard names the step in its report
        try:
            errors = type("Reporting", (Bundle,), {name: refuse})(EXAMPLES, flux_validator).run()
        except Exception as exc:  # noqa: BLE001 (a raise is the failure)
            failures.append(f"[guard] {name}: the guard let {type(exc).__name__} out of run()")
        else:
            if not any(f"{name} could not read this bundle (Refusal" in e for e in errors):
                failures.append(f"[guard] {name}: the guard did not report the exception of the step: {errors[:2]}")
        try:
            type("LettingOut", (Bundle,), {name: refuse, "_guarded": let_out})(EXAMPLES, flux_validator).run()
        except Refusal as exc:
            if exc.args != (name,):
                failures.append(f"[guard] {name}: the refusal that came out of run() is not the one of the step: {exc.args}")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"[guard] {name}: run() raised {type(exc).__name__}, not the subclass's own exception")
        else:
            failures.append(f"[guard] {name}: a subclass's override did not let its exception out of run()")
    return failures


def _pax_record(key: bytes, value: bytes) -> bytes:
    """One PAX extended-header record: its own length, then ` key=value` and a newline."""
    body = b" " + key + b"=" + value + b"\n"
    length = len(body) + len(str(len(body)))
    while len(str(length)) + len(body) != length:
        length = len(str(length)) + len(body)
    return str(length).encode() + body


def check_verify_reports_a_pax_header_tarfile_cannot_parse(flux_validator) -> list[str]:
    """tarfile raises ValueError, not ReadError, for a GNU sparse map it cannot
    parse, which verify let out though it says it never raises."""
    headers = {
        "a GNU sparse 1.0 header whose map is missing": [
            (b"GNU.sparse.major", b"1"), (b"GNU.sparse.minor", b"0"),
            (b"GNU.sparse.realsize", b"abc"), (b"GNU.sparse.name", b"bundle/z.flux.yml")],
        "a GNU sparse 0.1 map that is not numbers": [
            (b"GNU.sparse.size", b"10"), (b"GNU.sparse.numblocks", b"1"), (b"GNU.sparse.map", b"x,y")],
    }
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, (label, records) in enumerate(headers.items()):
            archive = Path(tmp) / f"sparse{i}.flux.tgz"
            data = b"".join(_pax_record(key, value) for key, value in records)
            with tarfile.open(archive, "w:gz", format=tarfile.PAX_FORMAT) as tar:
                header = tarfile.TarInfo("bundle/PaxHeaders/z")
                header.type, header.size = tarfile.XHDTYPE, len(data)
                tar.addfile(header, io.BytesIO(data))
                member = tarfile.TarInfo("bundle/z.flux.yml")
                member.size = 1
                tar.addfile(member, io.BytesIO(b"x"))
            try:
                rc, said = _verify_output(archive, flux_validator)
            except Exception as exc:  # noqa: BLE001 (a traceback is the failure)
                failures.append(f"[bundle] CRASHED ({type(exc).__name__}: {exc}) on {label}")
                continue
            if rc == 0 or "not a readable gzip archive" not in said:
                failures.append(f"[bundle] verify did not report {label}: {said.strip()[:200]}")
    return failures


def check_reads_bundles_as_utf8(flux_validator) -> list[str]:
    """A bundle's files are read as UTF-8 on every host, and a file that is not UTF-8 is refused.

    The FLUX engine reads a bundle as UTF-8 and takes its digests over that text,
    so the validator must check the same text whatever the host's locale.
    """
    from validate import load_yaml_docs

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        # The read names its encoding, so no locale changes the text it checks.
        path = Path(tmp) / "world.flux.yml"
        path.write_text("kind: World\nname: caf\u00e9\n", encoding="utf-8")
        encodings: list = []
        original = Path.open

        def recording_open(self, *args, **kwargs):
            encodings.append(kwargs.get("encoding"))
            return original(self, *args, **kwargs)

        Path.open = recording_open
        try:
            docs, error = load_yaml_docs(path)
        finally:
            Path.open = original
        if encodings != ["utf-8"]:
            failures.append(f"[utf-8] load_yaml_docs opened a file with encoding {encodings!r}")
        if error or docs != [{"kind": "World", "name": "caf\u00e9"}]:
            failures.append(f"[utf-8] a UTF-8 file read back as {docs!r} ({error})")

        # A file that is not UTF-8 is unreadable YAML, not an exception, and none of
        # its documents is returned, the one before the bad byte included.
        latin = Path(tmp) / "latin.flux.yml"
        latin.write_bytes(b"kind: World\nnote: " + b"x" * 70_000 + b"\n---\nname: caf\xe9\n")
        try:
            docs, error = load_yaml_docs(latin)
        except UnicodeDecodeError as exc:
            failures.append(f"[utf-8] a file that is not UTF-8 raised {exc!r}")
        else:
            if docs or not error or "not UTF-8" not in error:
                failures.append(f"[utf-8] a file that is not UTF-8 gave {docs!r} and {error!r}")

        # Through the validator: a bundle that holds such a file does not validate.
        bundle = Path(tmp) / "bundle"
        shutil.copytree(EXAMPLES, bundle)
        world = bundle / "world.flux.yml"
        world.write_bytes(world.read_bytes() + b"\n# caf\xe9\n")
        errors = Bundle(bundle, flux_validator).run()
        if not any("not UTF-8" in error for error in errors):
            failures.append(f"[utf-8] a bundle holding a file that is not UTF-8 passed: {errors[:3]}")

        # A pack whose manifest is not UTF-8 is reported by verify, which never raises.
        packed = Path(tmp) / "packed"
        with contextlib.redirect_stdout(io.StringIO()):
            bundle_tool.pack(EXAMPLES, packed, flux_validator)
        archive = next(packed.glob("*.flux.tgz"))
        rebuilt = Path(tmp) / "rebuilt.flux.tgz"
        with tarfile.open(archive, "r:gz") as source, tarfile.open(rebuilt, "w:gz") as target:
            for member in source.getmembers():
                data = source.extractfile(member).read() if member.isfile() else None
                if member.isfile() and member.name.endswith("flux-manifest.json"):
                    data = b"\xff" + data
                    member.size = len(data)
                target.addfile(member, io.BytesIO(data) if data is not None else None)
        try:
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                code = bundle_tool.verify(rebuilt, flux_validator)
        except UnicodeDecodeError as exc:
            failures.append(f"[utf-8] verify raised on a manifest that is not UTF-8: {exc!r}")
        else:
            if code != 1 or "not UTF-8 text" not in printed.getvalue():
                failures.append(f"[utf-8] verify gave {code} on a manifest that is not UTF-8")
    return failures


def check_supply_chain_digests_each_target_once(flux_validator) -> list[str]:
    """Many versioned refs to one locked document digest it once, and are each still checked."""
    import validate as validate_module

    failures: list[str] = []
    ranges = ["^2.1", "~2.1", "2.1.3", "^2.0", "~2.1.0"]
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "bundle"
        shutil.copytree(EXAMPLES, bundle)
        refs = [f"module-payment-recovery@{rng}" for rng in ranges]
        mutate_yaml(bundle, "simulation.flux.yml", lambda d: d["spec"].__setitem__("moduleRefs", refs))
        calls: list = []
        original = validate_module.canonical_digest

        def counting(doc):
            calls.append(doc.get("id") if isinstance(doc, dict) else None)
            return original(doc)

        validate_module.canonical_digest = counting
        try:
            errors = Bundle(bundle, flux_validator).run()
        finally:
            validate_module.canonical_digest = original
        if errors:
            failures.append(f"[supply-chain] five refs to one locked module failed: {errors[:3]}")
        if calls.count("module-payment-recovery") != 1:
            failures.append(
                f"[supply-chain] the locked module was digested {calls.count('module-payment-recovery')} times for 5 refs"
            )

        # A wrong digest is still reported for every ref that names the module.
        lock = bundle / "flux.lock"
        lock.write_text(
            lock.read_text(encoding="utf-8").replace("sha256:1a06", "sha256:0000"), encoding="utf-8"
        )
        errors = Bundle(bundle, flux_validator).run()
        mismatches = [error for error in errors if "content digest mismatch" in error]
        if len(mismatches) != len(ranges):
            failures.append(f"[supply-chain] {len(mismatches)} digest mismatches for {len(ranges)} refs")
    return failures


# --- the YAML read is bounded ----------------------------------------------------
#
# PyYAML builds an alias as a shared reference, so a document of a kilobyte can stand for
# billions of values: the schema check walked every one, and the message it raised spelled
# them out. A document that stands for more than 1,000,000 values, or nests deeper than 64
# levels, once its aliases and merge keys are written out, is refused before it is built.
# Those are the bounds the FLUX engine's read holds a document to. Two more bound what the
# engine's does not: the mappings merge keys name, and the characters a document writes out,
# since a string is one value however long it is.

#: One read, run in a child process and reported as JSON. A read that stands for billions of
#: values must fail a check, not exhaust the host that runs it, so each runs where it can be stopped.
_CHILD = r'''
import contextlib, io, json, sys, time, tracemalloc
from pathlib import Path

repo, mode, target = sys.argv[1], sys.argv[2], Path(sys.argv[3])
sys.path.insert(0, repo)
from jsonschema import Draft202012Validator, FormatChecker
from flux_spec import bundle, validate

schema = json.loads((Path(repo) / "schema" / "flux-schema-latest.json").read_text(encoding="utf-8"))
validator = Draft202012Validator(schema, format_checker=FormatChecker())
tracemalloc.start()
started = time.monotonic()
if mode == "read":
    docs, error = validate.load_yaml_docs(target)
    report = {"documents": len(docs), "error": error}
elif mode == "validate":
    errors = validate.Bundle(target, validator).run()
    report = {"errors": [e[:300] for e in errors[:40]], "longest": max(map(len, errors), default=0)}
else:
    said = io.StringIO()
    with contextlib.redirect_stdout(said):
        code = bundle.verify(target, validator)
    lines = said.getvalue().splitlines()
    report = {"code": code, "lines": [line[:300] for line in lines[:12]], "longest": max(map(len, lines), default=0)}
report["seconds"] = round(time.monotonic() - started, 2)
report["peak_mb"] = round(tracemalloc.get_traced_memory()[1] / 1e6, 1)
print(json.dumps(report))
'''


def _megabytes_held(pid: int) -> float:
    """The resident memory of process *pid*, or 0 where `ps` cannot say."""
    try:
        said = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
        return int(said) / 1024 if said else 0.0
    except (OSError, ValueError):
        return 0.0


def _in_a_child(mode: str, target: Path, seconds: float = 30.0, megabytes: float = 512.0) -> dict:
    """Run `_CHILD` on *target* and return its report, or say why it was stopped.

    The child is stopped past *seconds*, or past *megabytes* of memory where `ps` reports it, so
    code that does not refuse the document fails a check where it would otherwise hang or take the
    host's memory."""
    child = subprocess.Popen([sys.executable, "-c", _CHILD, str(REPO), mode, str(target)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    started = time.monotonic()
    while True:
        try:
            out, err = child.communicate(timeout=0.1)
            break
        except subprocess.TimeoutExpired:
            held, took = _megabytes_held(child.pid), time.monotonic() - started
            if held > megabytes or took > seconds:
                child.kill()
                child.communicate()
                return {"killed": f"after {took:.0f}s holding {held:.0f} MB"}
    if child.returncode != 0:
        return {"crashed": (err.strip().splitlines() or [f"exit {child.returncode}"])[-1]}
    return json.loads(out.strip().splitlines()[-1])


def _aliases(levels: int, fan: int = 10) -> str:
    """Anchors a0, a1, ...: each a list of *fan* aliases of the one before it, the first of *fan* scalars.

    Level n writes out (10**(n + 2) - 1) / 9 values: ten levels, about a kilobyte, write out eleven billion."""
    lines = ["a0: &a0 [" + ", ".join(["x"] * fan) + "]"]
    lines += [f"a{i}: &a{i} [" + ", ".join([f"*a{i - 1}"] * fan) + "]" for i in range(1, levels)]
    return "\n".join(lines) + "\n"


def _merges(levels: int, fan: int = 10) -> str:
    """Anchors m0, m1, ...: each a mapping that merges *fan* copies of the one before it, so it copies
    *fan* times as many pairs. Ten levels of ten copy a billion pairs."""
    lines = ["m0: &m0 {k0: x}"]
    lines += [f"m{i}: &m{i} {{<<: [" + ", ".join([f"*m{i - 1}"] * fan) + f"], k{i}: x}}" for i in range(1, levels)]
    return "\n".join(lines) + "\n"


def _empty_merges(hosts: int, parts: int) -> str:
    """*hosts* mappings that each merge one list of *parts* empty mappings. They write out about *hosts* plus
    *parts* values, and PyYAML visits *hosts* times *parts* mappings to build them."""
    return "e: &e {}\ns: &s [" + ", ".join(["*e"] * parts) + "]\nm: [" + ", ".join(["{<<: *s}"] * hosts) + "]\n"


def _written_out(n: int) -> str:
    """A document, in a few hundred bytes, that writes out exactly *n* values (at least 123,456):
    a list that defines five anchored blocks of 11, 111, ... 111,111 values, then enough aliases and
    scalars to make up *n*."""
    assert n >= 123_456
    sizes = (("a5", 111_111), ("a4", 11_111), ("a3", 1_111), ("a2", 111), ("a1", 11))
    lines = ["- &a1 [" + ", ".join(["x"] * 10) + "]"]
    lines += [f"- &a{i} [" + ", ".join([f"*a{i - 1}"] * 10) + "]" for i in range(2, 6)]
    rest = n - 123_456
    for name, size in sizes:
        count, rest = divmod(rest, size)
        lines += [f"- *{name}"] * count
    return "\n".join(lines + ["- x"] * rest) + "\n"


def _flow_levels(levels: int) -> str:
    """A document that nests *levels* levels in flow sequences, the scalar at the bottom included."""
    return "[" * (levels - 1) + "x" + "]" * (levels - 1) + "\n"


def _block_levels(levels: int) -> str:
    """A document that nests *levels* levels in block mappings, the scalar at the bottom included."""
    depth = levels - 1
    return "\n".join(" " * i + ("a: x" if i == depth - 1 else "a:") for i in range(depth)) + "\n"


def _alias_chain(links: int) -> str:
    """Anchors a0 ... a<links>, each a list of the one before it: nesting that is written only in aliases."""
    lines = ["a0: &a0 [x]"] + [f"a{i}: &a{i} [*a{i - 1}]" for i in range(1, links + 1)]
    return "\n".join(lines) + "\n"


def _merged_from_level_three(height: int) -> str:
    """A mapping of *height* levels at level 2, and a mapping at level 3 that merges it: a merge key
    writes the mapping's pairs out at the level of the mapping that holds the key."""
    inner = "[" * (height - 2) + "x" + "]" * (height - 2)
    return f"m: &m {{k: {inner}}}\no: {{h: {{<<: *m}}}}\n"


def _built_size(document) -> tuple[int, int, int]:
    """How many values a built document writes out, a shared object counting each time it is held, how
    many levels it nests, the scalar at the bottom included, and how many characters its strings hold.
    Counted on the built objects, so it does not share a line with the read it checks."""
    memo: dict[int, tuple[int, int, int]] = {}

    def size(item):
        if not isinstance(item, (list, dict)):
            return 1, 1, len(item) if isinstance(item, str) else 0
        if id(item) not in memo:
            parts = item if isinstance(item, list) else [part for pair in item.items() for part in pair]
            sizes = [size(part) for part in parts]
            memo[id(item)] = (1 + sum(v for v, _, _ in sizes), 1 + max((l for _, l, _ in sizes), default=0),
                              sum(c for _, _, c in sizes))
        return memo[id(item)]

    return size(document)


@contextlib.contextmanager
def _patched(module, **constants):
    """Set module-level constants for a block, then put them back as they were, or remove one the module
    did not have: the old code has none of the new bounds, and a check of one must fail there, not crash."""
    missing = object()
    saved = {name: getattr(module, name, missing) for name in constants}
    for name, value in constants.items():
        setattr(module, name, value)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is missing:
                delattr(module, name)
            else:
                setattr(module, name, value)


def _long_string(length: int, holders: int) -> str:
    """One string of *length* characters, held by *holders* aliases: a few dozen KB of text that writes out
    *length* times *holders* characters, and the value count sees *holders* plus a few values."""
    return f's: &s "{"x" * length}"\nl: [' + ", ".join(["*s"] * holders) + "]\n"


def _with_the_long_string(text: str, length: int = 50_000, holders: int = 2_000) -> str:
    """*text*, a World document, with a string of *length* characters defined before it and `labels`, a field
    of strings, holding it *holders* times: the schema refuses it and the unbounded read spelled out all of it."""
    return (f's: &s "{"x" * length}"\n'
            + text.replace("kind: World", "kind: World\nlabels: [" + ", ".join(["*s"] * holders) + "]", 1))


def _with_the_bomb(levels: int, text: str) -> str:
    """*text* with *levels* levels of aliases defined before it. A World document also holds the last of
    them in `labels`, a field of strings, which the schema refuses and the unbounded read spelled out."""
    return _aliases(levels) + text.replace("kind: World", f"kind: World\nlabels: *a{levels - 1}", 1)


def _unfinished(report: dict) -> str:
    """Why a child's report is no report (it was stopped, or it crashed), or ''."""
    if "killed" in report:
        return f"it was stopped {report['killed']}"
    if "crashed" in report:
        return f"it crashed: {report['crashed']}"
    return ""


def _read_here(path: Path) -> dict:
    """What `_CHILD` reports for a read, made in this process: for a document whose read is cheap
    whatever the code, since PyYAML builds an alias as a shared reference."""
    import validate as validate_tool

    tracemalloc.start()
    try:
        started = time.monotonic()
        docs, error = validate_tool.load_yaml_docs(path)
        return {"documents": len(docs), "error": error, "seconds": round(time.monotonic() - started, 2),
                "peak_mb": round(tracemalloc.get_traced_memory()[1] / 1e6, 1)}
    finally:
        tracemalloc.stop()


def check_a_document_that_stands_for_too_much_is_refused_at_the_read(flux_validator) -> list[str]:
    """load_yaml_docs refuses, as an ordinary error and with none of the file's documents, a document
    that writes out more than 1,000,000 values, nests deeper than 64 levels, or holds itself through an
    alias: quickly, and before anything is built from it.

    Ten levels of ten aliases, a kilobyte, stood for eleven billion values, and ten levels of ten merge
    keys copied a billion pairs as the mapping was built. The read, not the message printed later, is
    where they are refused. A merge key of empty mappings writes out nothing and still costs PyYAML a
    visit to each, once for every mapping that holds it: the product is bounded too, and the measure
    that bounds it does not pay that product itself."""
    writes_out = "writes out more than 1000000 values once its aliases and merge keys are written out"
    cases = {
        "ten levels of ten aliases": (_aliases(10), f"{writes_out} (line 6, column 5)"),
        "a list that holds itself": ("x: &s [*s]\n", "holds itself through an alias (line 1, column 4)"),
        "a mapping that merges itself": ("m: &m {<<: *m}\n", "holds itself through an alias (line 1, column 4)"),
        "65 levels of flow sequences": (_flow_levels(65), "nests deeper than 64 levels (line 1, column 65)"),
        "65 levels of block mappings": (_block_levels(65), "nests deeper than 64 levels (line 64, column 64)"),
        "100 levels of flow sequences": (_flow_levels(100), "nests deeper than 64 levels"),
        "65 levels written only in aliases": (_alias_chain(62), "nests deeper than 64 levels"),
        "a merge key that reaches the 65th level": (_merged_from_level_three(63), "nests deeper than 64 levels"),
        "a 50,000 character string held by 2,000 aliases":
            (_long_string(50_000, 2_000), "writes out more than 67108864 characters once its aliases and merge keys are written out (line 2,"),
        "1,001 mappings that each merge a list of 1,000 empty ones":
            (_empty_merges(1001, 1000), "names more than 1000000 mappings in its merge keys (line 3, column"),
        "one file, a small document then a bomb": ("a: 1\n---\n" + _aliases(10), f"{writes_out} (line 8, column 5)"),
    }
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        # The merge bomb is the one read that is not cheap whatever the code: PyYAML copies the pairs of
        # every merged mapping as it builds one, so it runs where it can be stopped.
        merges = {"ten levels of ten merge keys": (_merges(10), f"{writes_out} (line 7, column 5)")}
        for i, (label, (text, expected)) in enumerate({**cases, **merges}.items()):
            path = Path(tmp) / f"case{i}.flux.yml"
            path.write_text(text, encoding="utf-8")
            report = _in_a_child("read", path) if label in merges else _read_here(path)
            if _unfinished(report):
                failures.append(f"[yaml-bounds] the read of {label} did not finish: {_unfinished(report)}")
            elif report["documents"] != 0 or not report["error"] or expected not in report["error"] \
                    or not report["error"].startswith("unreadable YAML: "):
                failures.append(f"[yaml-bounds] {label} was not refused with '{expected}': {report}")
            elif report["seconds"] > 20 or report["peak_mb"] > 64:
                failures.append(f"[yaml-bounds] {label} was refused in {report['seconds']}s and {report['peak_mb']} MB")

        # The mappings a merge key names are worked out once, however many mappings hold the key: the
        # measure costs what the text does, not what PyYAML's visits do. Counted as the digest check counts.
        import validate as validate_tool

        real, calls = getattr(validate_tool, "_merged_parts", None), []
        if real is not None:
            validate_tool._merged_parts = lambda value_node: (calls.append(1), real(value_node))[1]
        try:
            path = Path(tmp) / "shared.flux.yml"
            path.write_text(_empty_merges(1200, 1000), encoding="utf-8")
            _read_here(path)
        finally:
            if real is not None:
                validate_tool._merged_parts = real
        if real is not None and len(calls) > 2:
            failures.append(f"[yaml-bounds] the list that 1,200 mappings merge was worked out {len(calls)} times")
    return failures


def _read_text(text: str, directory: Path):
    """load_yaml_docs on *text*, written to a file in *directory*: its documents and its error."""
    import validate as validate_tool

    path = directory / "doc.flux.yml"
    path.write_text(text, encoding="utf-8")
    return validate_tool.load_yaml_docs(path)


def check_a_document_at_the_bounds_reads_and_one_past_them_is_refused(flux_validator) -> list[str]:
    """999,999 and 1,000,000 values read, 1,000,001 do not; 64 levels read, 65 do not; and what reads is
    what PyYAML builds, as it was, with every example.

    The bounds are counted on what a document writes out, not on its text, so each document here is a
    few hundred bytes. Each is also counted on the objects PyYAML builds from it, which is the count the
    bound is about. They are held per document: a file may hold many."""
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        for n, reads in ((999_999, True), (1_000_000, True), (1_000_001, False)):
            text = _written_out(n)
            counted = _built_size(yaml.safe_load(text))[0]
            docs, error = _read_text(text, Path(tmp))
            if counted != n:
                failures.append(f"[yaml-bounds] the document made for {n} values writes out {counted}")
            elif reads and (error or len(docs) != 1):
                failures.append(f"[yaml-bounds] a document of {n} values did not read: {error}")
            elif not reads and (docs or "writes out more than 1000000 values" not in (error or "")):
                failures.append(f"[yaml-bounds] a document of {n} values was not refused: {docs!r:.80} {error}")

        for label, build, at, past in (("flow sequences", _flow_levels, 64, 65), ("block mappings", _block_levels, 64, 65),
                                       ("aliases", _alias_chain, 61, 62), ("a merge key", _merged_from_level_three, 62, 63)):
            docs, error = _read_text(build(at), Path(tmp))
            built = _built_size(yaml.safe_load(build(at)))[1]
            if error or len(docs) != 1 or built != 64:
                failures.append(f"[yaml-bounds] the document at the bound of {label} did not read ({built} levels built): {error}")
            docs, error = _read_text(build(past), Path(tmp))
            if docs or "nests deeper than 64 levels" not in (error or ""):
                failures.append(f"[yaml-bounds] one level past the bound of {label} was not refused: {docs!r:.80} {error}")

        docs, error = _read_text(_written_out(600_000) + "---\n" + _written_out(600_000), Path(tmp))
        if error or [_built_size(d)[0] for d in docs] != [600_000, 600_000]:
            failures.append(f"[yaml-bounds] two documents of 600,000 values each did not both read: {error}")
    return failures + _failures_reading_as_before()


def check_merge_keys_are_counted_for_each_mapping_that_holds_one(flux_validator) -> list[str]:
    """The mappings a document's merge keys name are counted once for each mapping that holds a key, and a
    mapping written many times through an alias is one mapping. Counted here at 100 instead of 1,000,000."""
    import validate as validate_tool

    aliased = "e: &e {}\ns: &s [" + ", ".join(["*e"] * 10) + "]\nm: [&h {<<: *s}, " + ", ".join(["*h"] * 50) + "]\n"
    cases = (("10 mappings that each merge 10 empty ones", _empty_merges(10, 10), True),
             ("11 mappings that each merge 10 empty ones", _empty_merges(11, 10), False),
             ("one such mapping, written 51 times through an alias", aliased, True))
    failures = []
    with _patched(validate_tool, MAX_YAML_MERGED=100), tempfile.TemporaryDirectory() as tmp:
        for label, text, reads in cases:
            docs, error = _read_text(text, Path(tmp))
            if reads and (error or len(docs) != 1):
                failures.append(f"[yaml-bounds] {label} did not read at a bound of 100: {error}")
            elif not reads and (docs or "names more than 100 mappings in its merge keys" not in (error or "")):
                failures.append(f"[yaml-bounds] {label} was not refused at a bound of 100: {error}")
    return failures


def check_characters_are_counted_each_time_they_are_written_out(flux_validator) -> list[str]:
    """A string is one value however long it is, so its characters are counted as well, each time an alias
    writes it out, and in a key as in a value, and through a merge key. Counted on the built objects too."""
    import validate as validate_tool

    long_string = _long_string(100, 3)
    merged = 's: &s {k: "' + "y" * 50 + '"}\nm: {<<: [*s, *s], z: "' + "z" * 20 + '"}\n'
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        for label, text, shared in (("a string held by 3 aliases", long_string, True), ("a mapping merged twice", merged, False)):
            if shared:
                expected = _built_size(yaml.safe_load(text))[2]
            else:
                # PyYAML builds what a merge key copies once, so count by hand what the merge keys write out:
                # key s and its pair (1 + 50), key m, the pair of s twice (2 * (1 + 50)), and m's own pair (1 + 20).
                expected = 1 + (1 + 50) + 1 + 2 * (1 + 50) + (1 + 20)
            for limit, reads in ((expected, True), (expected - 1, False)):
                with _patched(validate_tool, MAX_YAML_CHARS=limit):
                    docs, error = _read_text(text, Path(tmp))
                if reads and (error or len(docs) != 1):
                    failures.append(f"[yaml-bounds] {label} ({expected} characters) did not read at a bound of {limit}: {error}")
                elif not reads and (docs or f"writes out more than {limit} characters" not in (error or "")):
                    failures.append(f"[yaml-bounds] {label} ({expected} characters) was not refused at a bound of {limit}: {error}")
    return failures


def _failures_reading_as_before() -> list[str]:
    """Aliases and merge keys inside the bounds build what PyYAML builds, and every example reads as it did."""
    import validate as validate_tool

    class Before(yaml.SafeLoader):
        """The loader load_yaml_docs used before its read was bounded."""

    Before.add_constructor("tag:yaml.org,2002:timestamp", lambda loader, node: loader.construct_scalar(node))

    failures = []
    text = "d: &d {a: 1, b: [x, y]}\ne: *d\nf: {<<: *d, c: 2}\ng: [*d, *d]\nh: {<<: [*d, {z: 1}], a: 9}\n"
    with tempfile.TemporaryDirectory() as tmp:
        docs, error = _read_text(text, Path(tmp))
    if error or docs != list(yaml.safe_load_all(text)):
        failures.append(f"[yaml-bounds] aliases and merge keys inside the bounds did not read as PyYAML builds them: {docs} {error}")
    # Merge keys written inside merge keys add no level, so the bound on levels does not limit them; the
    # measure must not be what limits them either, as a stack that grows with the nesting would.
    deep = "{<<: " * 400 + "{k: 1}" + "}" * 400 + "\n"
    try:
        built = yaml.safe_load(deep)
    except RecursionError:
        built = None            # this interpreter cannot build it either: nothing to compare with
    if built is not None:
        with tempfile.TemporaryDirectory() as tmp:
            docs, error = _read_text(deep, Path(tmp))
        if error or docs != [built]:
            failures.append(f"[yaml-bounds] 400 merge keys inside merge keys, which PyYAML builds, did not read: {error}")
    for root in (EXAMPLES, TOWERS_EXAMPLE):
        for path in sorted(root.iterdir()):
            if path.suffix not in (".yml", ".yaml") and path.name != "flux.lock":
                continue
            docs, error = validate_tool.load_yaml_docs(path)
            before = [d for d in yaml.load_all(path.read_text(encoding="utf-8"), Loader=Before) if d is not None]
            if error or json.dumps(docs, sort_keys=True) != json.dumps(before, sort_keys=True):
                failures.append(f"[yaml-bounds] {path.relative_to(REPO)} no longer reads as it did: {error}")
    return failures


def check_the_bounds_hold_through_validate_and_verify(flux_validator) -> list[str]:
    """A bundle holding such a document is reported by the validator, for every kind of file it reads,
    and by verify when the document is in an archive, in short lines and in bounded time and memory."""
    import validate as validate_tool

    max_line = getattr(validate_tool, "MAX_LINE", 2_000)
    expected = "unreadable YAML: a document writes out more than 1000000 values"
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        for label, filename, bomb, expected_here in (
                ("ten levels of aliases in a FLUX document", "world.flux.yml", lambda t: _with_the_bomb(10, t), expected),
                ("ten levels of aliases in a FLUID document", "payment-recovery.fluid.yml", lambda t: _with_the_bomb(10, t), expected),
                ("ten levels of aliases in the lockfile", "flux.lock", lambda t: _with_the_bomb(10, t), expected),
                ("a 50,000 character string held 2,000 times in a FLUX document", "world.flux.yml", _with_the_long_string,
                 "unreadable YAML: a document writes out more than 67108864 characters")):
            work = Path(tmp) / label / "bundle"
            shutil.copytree(EXAMPLES, work)
            (work / filename).write_text(bomb((work / filename).read_text(encoding="utf-8")), encoding="utf-8")
            report = _in_a_child("validate", work, seconds=40)
            if _unfinished(report):
                failures.append(f"[validate] the validator did not finish on {label}: {_unfinished(report)}")
            elif not any(e.startswith(f"{filename}: {expected_here}") for e in report["errors"]):
                failures.append(f"[validate] {label} was not reported: {report['errors'][:2]}")
            elif report["longest"] > max_line or report["seconds"] > 30 or report["peak_mb"] > 128:
                failures.append(f"[validate] {label}: longest message {report['longest']}, "
                                f"{report['seconds']}s, {report['peak_mb']} MB")

        work, out = Path(tmp) / "packed" / "bundle", Path(tmp) / "packed-dist"
        shutil.copytree(EXAMPLES, work)
        attacked = _repack(work, out, lambda entries: [(n, _with_the_bomb(10, d.decode()).encode() if n.endswith("/world.flux.yml") else d)
                                                       for n, d in entries], flux_validator)
        report = _in_a_child("verify", attacked, seconds=40)
        if _unfinished(report):
            failures.append(f"[bundle] verify did not finish on an archive holding ten levels of aliases: {_unfinished(report)}")
        elif report["code"] != 1 or not any(expected in line for line in report["lines"]):
            failures.append(f"[bundle] verify did not report ten levels of aliases: {report['lines'][:3]}")
        elif report["longest"] > len("       ") + max_line or report["seconds"] > 30 or report["peak_mb"] > 128:
            failures.append(f"[bundle] verify on ten levels of aliases: longest line {report['longest']}, "
                            f"{report['seconds']}s, {report['peak_mb']} MB")
    return failures


def check_bounded_keeps_both_ends_of_a_long_message(flux_validator) -> list[str]:
    """bounded() keeps a message that fits, and cuts one that does not in the middle, counting what it left out.

    jsonschema writes the value it refuses first and its verdict last, so the start of a long message says
    where and the end says what is wrong. The result is never longer than its limit."""
    import validate as validate_tool

    bounded = getattr(validate_tool, "bounded", None)
    if bounded is None:
        return ["[messages] flux_spec.validate has no bounded()"]
    failures = []
    text = "start " + "".join(f"{i % 10}" for i in range(9_000)) + " end"
    cut = bounded(text, 100)
    note = re.search(r" \[\.\.\. (\d+) characters not shown \.\.\.\] ", cut)
    if not (note and len(cut) <= 100 and cut.startswith("start ") and cut.endswith(" end")
            and text.startswith(cut[:note.start()]) and text.endswith(cut[note.end():])
            and int(note.group(1)) == len(text) - (len(cut) - len(note.group(0))) and len(cut) > 90):
        failures.append(f"[messages] bounded() did not keep both ends of a long message, counted: {cut!r}")
    if bounded("m" * 100, 100) != "m" * 100 or bounded("m" * 101, 100) == "m" * 101 or bounded("short") != "short":
        failures.append("[messages] bounded() changed a message that fits, or kept one that does not")
    if any(len(bounded("m" * 500, limit)) > limit for limit in (0, 1, 3, 8, 40, 60)):
        failures.append("[messages] bounded() overran a small limit")
    if len(bounded("m" * 100_000)) > getattr(validate_tool, "MAX_MESSAGE", 1_000):
        failures.append("[messages] bounded() does not default to MAX_MESSAGE")
    return failures


def check_validator_messages_are_capped(flux_validator) -> list[str]:
    """No validator message, and no line verify prints, is longer than a few thousand characters.

    Five levels of ten aliases are inside the bounds and spelled out a 92 KB schema message; a document
    id, a manifest value and an archive path can each be any length."""
    import validate as validate_tool

    max_message, max_name = getattr(validate_tool, "MAX_MESSAGE", 1_000), getattr(validate_tool, "MAX_NAME", 200)
    max_line = getattr(validate_tool, "MAX_LINE", 2_000)
    ceiling = max_name + len(": ") + max_message     # a name, a colon and a message
    indent = len("       ")                           # what verify and the validator put before each line
    failures = []

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "spelled-out" / "bundle"
        shutil.copytree(EXAMPLES, work)
        world = work / "world.flux.yml"
        world.write_text(_aliases(5) + world.read_text(encoding="utf-8").replace("kind: World", "kind: World\nlabels: *a4", 1),
                         encoding="utf-8")
        errors = Bundle(work, flux_validator).run()
        labelled = [e for e in errors if "$.labels" in e]
        if max(map(len, errors), default=0) > ceiling:
            failures.append(f"[messages] a schema message of {max(map(len, errors)):,} characters, above {ceiling}")
        elif not (labelled and labelled[0].startswith("world.flux.yml: schema: $.labels: ") and "characters not shown" in labelled[0]
                  and labelled[0].endswith("is not of type 'object'")):
            failures.append(f"[messages] a long schema message lost its start or its verdict: {[e[:60] for e in labelled]}")

        work = Path(tmp) / "long-id" / "bundle"
        shutil.copytree(EXAMPLES, work)
        mutate_yaml(work, "campaign.flux.yml", lambda d: (d.__setitem__("id", "c" * 300_000), _dangling_ref(d)))
        errors = Bundle(work, flux_validator).run()
        if not errors or max(map(len, errors)) > ceiling:
            failures.append(f"[messages] a document id of 300,000 characters made a message of {max(map(len, errors), default=0):,}")

        for label, mutate, expected in (
            ("a manifest value millions of characters long",
             lambda entries: _edit_manifest(entries, lambda m: m.__setitem__("fluxVersions", ["9" * 3_000_000])),
             "violates the manifest schema"),
            ("an archive path thousands of characters long",
             lambda entries: entries + [("bundle/" + "a" * 6_000 + "\x00b.flux.yml", b"kind: World\n")],
             "holds a NUL byte"),
        ):
            work, out = Path(tmp) / label / "bundle", Path(tmp) / f"{label}-dist"
            shutil.copytree(EXAMPLES, work)
            rc, said = _verify_output(_repack(work, out, mutate, flux_validator), flux_validator)
            longest = max(map(len, said.splitlines()), default=0)
            if rc == 0 or expected not in said or longest > indent + max_line:
                failures.append(f"[messages] verify printed a line of {longest:,} characters for {label}: {said.strip()[:120]}")

        # pack prints what it refuses about a linked file the way it prints a validator message
        work = Path(tmp) / "linked" / "bundle"
        shutil.copytree(EXAMPLES, work)
        said = io.StringIO()
        with _patched(bundle_tool, _symlink_entries=lambda directory: ["unsupported bundle entry (symlink): " + "d/" * 3_000 + "x"]), \
                contextlib.redirect_stdout(said):
            rc = bundle_tool.pack(work, Path(tmp) / "linked-dist", flux_validator)
        longest = max(map(len, said.getvalue().splitlines()), default=0)
        if rc == 0 or "unsupported bundle entry (symlink)" not in said.getvalue() or longest > indent + max_line:
            failures.append(f"[messages] pack printed a line of {longest:,} characters for a linked file with a long path")
    return failures


def _scalar_spans(text: str, kind: str = "value") -> list[tuple[int, int]]:
    """The character spans of the scalars of *text*: its "value"s, or its mapping "key"s. A span starts at a
    node's tag or anchor, when it has one."""
    spans: list[tuple[int, int]] = []

    def walk(node, is_key=False):
        if isinstance(node, yaml.ScalarNode):
            if is_key == (kind == "key"):
                spans.append((node.start_mark.index, node.end_mark.index))
        elif isinstance(node, yaml.SequenceNode):
            for item in node.value:
                walk(item)
        elif isinstance(node, yaml.MappingNode):
            for key_node, value_node in node.value:
                walk(key_node, True)
                walk(value_node)

    for root in yaml.compose_all(text):
        walk(root)
    return spans


def _sexagesimal(parts: int) -> str:
    """A YAML 1.1 sexagesimal float of *parts* parts (`1:1:1.0`), which PyYAML builds as a float: the place
    value of the first part is 60 to the power of one less than *parts*."""
    return ":".join(["1"] * (parts - 1)) + ":1.0"


@contextlib.contextmanager
def _default_digit_limit():
    """CPython's own limit on integer text, 4,300 digits, whatever the environment set (PYTHONINTMAXSTRDIGITS):
    the checks that name it expect it."""
    if not hasattr(sys, "set_int_max_str_digits"):
        yield
        return
    saved = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(4300)
    try:
        yield
    finally:
        sys.set_int_max_str_digits(saved)


def check_a_scalar_pyyaml_cannot_build_is_unreadable_yaml_by_its_position(flux_validator) -> list[str]:
    """PyYAML raised a bare ValueError, IndexError or KeyError for a scalar its explicit tag cannot build,
    ValueError for an integer of more than 4300 digits, and OverflowError for a sexagesimal float of 175
    parts or more, out of a read that says it never raises. Each is now unreadable YAML, placed by line and
    column, as the FLUX engine's read refuses them.

    An integer written in hex, octal or binary forms at any length and then broke the first message that
    spelled it, so the length of its value is bounded too."""
    import validate as validate_tool

    integer, flt, boolean = ("a scalar read as an integer has no integer value", "a scalar read as a float has no float value",
                             "a scalar read as a boolean has no boolean value")
    too_long = "an integer of more than 4300 digits is too long to read"
    refused = {
        "a sexagesimal float of 175 parts, which overflows a float": (_sexagesimal(175), flt),
        "the same, with its tag": ("!!float " + _sexagesimal(200), flt),
        "a sexagesimal integer of 3,000 parts, whose value is too long": (":".join(["1"] * 3000), too_long),
        "an integer its tag cannot build": ("!!int abc", integer), "an empty integer": ("!!int ''", integer),
        "a hex integer with no digit": ("0x_", integer), "a sexagesimal integer with a letter": ("!!int 1:x", integer),
        "a float its tag cannot build": ("!!float ZZZ", flt), "an empty float": ("!!float ''", flt),
        "a boolean its tag cannot build": ("!!bool maybe", boolean), "an empty boolean": ("!!bool ''", boolean),
        "a decimal integer of 4,301 digits": ("9" * 4301, too_long), "a negative one": ("-" + "9" * 4301, too_long),
        "a hex integer of 3,600 digits": ("0x" + "f" * 3600, too_long),
        "a binary integer of 15,000 digits": ("0b" + "1" * 15_000, too_long),
    }
    read = {"a decimal integer of 4,300 digits": "9" * 4300, "a hex integer of 3,560 digits": "0x" + "f" * 3560,
            "a sexagesimal float of 174 parts, the most a float holds": _sexagesimal(174),
            # A spelling in a power of two forms at any length: it is the value that is too long to print.
            "a binary integer of 4,301 digits, whose value is short": "0b" + "1" * 4301,
            "an octal integer of 4,301 digits, whose value is short": "0" + "7" * 4301,
            # int() reads each part of a sexagesimal integer on its own: 86 parts of 50 digits are 4,300 in all.
            "a tagged sexagesimal integer of 5,000 digits in parts of 50": "!!int " + ":".join(["1" * 49 + "2"] * 100),
            "the spellings that build": "[0x1f, 0o17, 0b11, 1_000, 1:30:00, 1e3, 1.5e3, yes, no, on, off, ~]"}
    failures = []
    with tempfile.TemporaryDirectory() as tmp, _default_digit_limit():
        for label, (spelling, why) in refused.items():
            try:
                docs, error = _read_text(f"a: 1\nb: {spelling}\n", Path(tmp))
            except Exception as exc:  # noqa: BLE001 (a raise is the failure)
                failures.append(f"[scalars] load_yaml_docs raised {type(exc).__name__} on {label}")
                continue
            if docs or error != f"unreadable YAML: {why} (line 2, column 4)":
                failures.append(f"[scalars] {label} was not refused as '{why}' at (line 2, column 4): {len(docs)} documents, {error}")
        for label, spelling in read.items():
            try:
                docs, error = _read_text(f"a: 1\nb: {spelling}\n", Path(tmp))
            except Exception as exc:  # noqa: BLE001
                failures.append(f"[scalars] load_yaml_docs raised {type(exc).__name__} on {label}")
                continue
            if error or len(docs) != 1:
                failures.append(f"[scalars] {label} did not read: {error}")
        # PyYAML adds a sexagesimal integer up part by part, which costs the square of their number, so one
        # of more parts than the limit has digits is refused before it is built, and that is all it can be.
        built = []
        real_build = yaml.SafeLoader.construct_yaml_int
        with _patched(yaml.SafeLoader, construct_yaml_int=lambda loader, node: built.append(1) or real_build(loader, node)):
            docs, error = _read_text("b: !!int " + ":".join(["1"] * 40_000) + "\n", Path(tmp))
        if docs or error != f"unreadable YAML: {too_long} (line 1, column 4)" or built:
            failures.append(f"[scalars] a sexagesimal integer of 40,000 parts was not refused before it was built: {len(docs)} documents, {error}, built {len(built)}")
        # A later document of the file is placed by its own lines, and none of the file's documents is returned.
        try:
            docs, error = _read_text("a: 1\n---\nb: 2\n---\nc: !!bool maybe\n", Path(tmp))
        except Exception as exc:  # noqa: BLE001
            failures.append(f"[scalars] load_yaml_docs raised {type(exc).__name__} on a later document")
        else:
            if docs or error != f"unreadable YAML: {boolean} (line 5, column 4)":
                failures.append(f"[scalars] a later document with a scalar that cannot build was not refused where it is: {len(docs)} documents, {error}")
    return failures


def check_a_document_that_cannot_be_digested_is_reported_not_raised(flux_validator) -> list[str]:
    """RFC 8785 cannot write a NaN or an infinity, an integer past JSON's range, a key that is not a string,
    or a value JSON has no spelling for. A free-form field of a document that is otherwise valid can hold
    any of them, and the digest of a locked module and of the contract a Simulation emits raised.

    Such a document is reported as one that cannot be digested, once, whatever the number of refs to it.
    The read refuses a NaN and an infinity, so those are put in place of a read, in a document that code
    has put together."""
    hostile = {"an integer past JSON's range": str(2 ** 60), "a binary value": "!!binary aGk=", "a set": "!!set {a, b}"}
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        for label, spelling in hostile.items():
            for where, filename, old, new in (("a locked module", "module.flux.yml", "{ spec: cloudevents/1.0 }", "{ spec: " + spelling + " }"),
                                              ("a locked module, as a key", "module.flux.yml", "{ spec: cloudevents/1.0 }", "{ spec: x, 1: " + spelling + " }")):
                work = Path(tmp) / f"{where}-{label}" / "bundle"
                shutil.copytree(EXAMPLES, work)
                text = (work / filename).read_text(encoding="utf-8")
                assert old in text
                (work / filename).write_text(text.replace(old, new, 1), encoding="utf-8")
                try:
                    errors = Bundle(work, flux_validator).run()
                except Exception as exc:  # noqa: BLE001 (a raise is the failure)
                    failures.append(f"[digest] {where} holding {label} raised {type(exc).__name__}: {str(exc)[:60]}")
                    continue
                if sum("cannot be digested" in e for e in errors) != 1:
                    failures.append(f"[digest] {where} holding {label} was not reported once: {[e[:90] for e in errors][:3]}")
            # The contract a Simulation emits, digested for its provenance, is any YAML document.
            work = Path(tmp) / f"contract-{label}" / "bundle"
            shutil.copytree(EXAMPLES, work)
            fluid = work / "payment-recovery.fluid.yml"
            text = fluid.read_text(encoding="utf-8")
            start, end = _scalar_spans(text)[4]
            fluid.write_text(text[:start] + spelling + text[end:], encoding="utf-8")
            try:
                errors = Bundle(work, flux_validator).run()
            except Exception as exc:  # noqa: BLE001
                failures.append(f"[digest] a contract holding {label} raised {type(exc).__name__}: {str(exc)[:60]}")
                continue
            if not any("cannot be digested" in e and "the contract" in e for e in errors):
                failures.append(f"[digest] a contract holding {label} was not reported: {[e[:90] for e in errors][:3]}")
        # A key is digested too. RFC 8785 refuses one that is not a string (a NaN), and one that UTF-16
        # cannot hold (a lone surrogate) in another way: the second raised a UnicodeEncodeError.
        for label, spelling in {"a lone surrogate": '"\\ud800"'}.items():
            for where, filename, old, new in (
                    ("a locked module", "module.flux.yml", "{ spec: cloudevents/1.0 }", "{ spec: cloudevents/1.0, " + spelling + ": 1 }"),
                    ("a contract", "payment-recovery.fluid.yml", "\nid:", "\n" + spelling + ": 1\nid:")):
                work = Path(tmp) / f"key-{where}-{label}" / "bundle"
                shutil.copytree(EXAMPLES, work)
                text = (work / filename).read_text(encoding="utf-8")
                assert old in text
                (work / filename).write_text(text.replace(old, new, 1), encoding="utf-8")
                try:
                    errors = Bundle(work, flux_validator).run()
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"[digest] {where} holding {label} as a key raised {type(exc).__name__}: {str(exc)[:60]}")
                    continue
                if sum("cannot be digested" in e for e in errors) != 1:
                    failures.append(f"[digest] {where} holding {label} as a key was not reported once: {[e[:90] for e in errors][:3]}")
    for label, value in {"a NaN": float("nan"), "an infinity": float("-inf")}.items():
        for where, check in (("a locked module", "check_supply_chain"), ("a contract", "check_fluid_seam")):
            bundle = Bundle(EXAMPLES, flux_validator)
            bundle.load()
            if where == "a contract":
                next(iter(bundle.fluid_docs.values()))[1]["x"] = value
            else:
                next(d for d in bundle.flux_docs.values() if d.get("kind") == "Module")["spec"]["x"] = value
            bundle.errors = []
            try:
                getattr(bundle, check)()
            except Exception as exc:  # noqa: BLE001 (a raise is the failure)
                failures.append(f"[digest] {where} holding {label} in memory raised {type(exc).__name__}: {str(exc)[:60]}")
                continue
            if sum("cannot be digested" in e for e in bundle.errors) != 1:
                failures.append(f"[digest] {where} holding {label} in memory was not reported once: {[e[:90] for e in bundle.errors][:3]}")
    return failures


#: What a value of the wrong shape can be: none of them is what a document is written to hold.
_SHAPES = (5, None, True, "x", [], {}, [1], [[1]], [{"a": 1}], {"a": 1}, "\ud800", float("nan"), 10 ** 30, {1, 2}, {"\ud800": 1})
_CROSS_CHECKS = ("check_refs", "check_sums_and_sets", "check_traits", "check_supply_chain", "check_semantics",
                 "check_agent_policy", "check_fluid_documents", "check_fluid_seam")


def _node_paths(node, prefix=()):
    """The path to every node below *node*: the keys and indexes that lead to it."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield prefix + (key,)
            yield from _node_paths(value, prefix + (key,))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield prefix + (index,)
            yield from _node_paths(value, prefix + (index,))


def _cross_check_that_raises(bundle, flux_docs, fluid_docs, lock_docs):
    """The name and exception of the first cross-check of *bundle* that raises on these documents, or None.

    The checks are run one by one, not through Bundle.run(), which reports what it could not read instead of
    raising: this finds a read that nobody guarded, which that report would hide."""
    import validate as validate_tool

    real_load = validate_tool.load_yaml_docs
    bundle.errors = []
    bundle.flux_docs, bundle.fluid_docs = flux_docs, fluid_docs
    with _patched(validate_tool, load_yaml_docs=lambda path: (copy.deepcopy(lock_docs), None) if path.name == "flux.lock" else real_load(path)):
        for name in _CROSS_CHECKS:
            try:
                getattr(bundle, name)()
            except Exception as exc:  # noqa: BLE001 (a raise is the failure)
                return f"{name} raised {type(exc).__name__}: {str(exc)[:50]}"
    return None


def check_a_value_of_a_shape_no_check_expected_is_reported_not_raised(flux_validator) -> list[str]:
    """The cross-checks read fields no schema describes: a Module's `config.measures`, and the FLUID contracts,
    which no FLUX schema covers (`exposes`, `policy.agentPolicy.allowedUseCases`). A value of the wrong shape
    in one of them raised TypeError or AttributeError out of Bundle.run(), `pack` and `verify`.

    Each is now read where it is, and what a check could still not read is reported by Bundle.run() as that
    check's. This puts each of 15 shapes in place of every node of the example's contract, of its lockfile and
    of its Modules' configs, and in the places a contract may name that this one does not, and runs the checks
    on them one by one: a read that nobody guarded raises here, which Bundle.run() would report instead."""
    base = Bundle(EXAMPLES, flux_validator)
    base.load()
    sweeper = Bundle(EXAMPLES, flux_validator)   # one for every run, so that its FLUID validators are built once
    lock = list(yaml.safe_load_all((EXAMPLES / "flux.lock").read_text(encoding="utf-8")))
    contract_id, (contract_path, contract) = next(iter(base.fluid_docs.items()))
    failures: list[str] = []

    def put(document, path, value):
        for step in path[:-1]:
            document = document[step]
        document[path[-1]] = value

    def run(label, flux_docs=None, fluid_docs=None, lock_docs=None):
        raised = _cross_check_that_raises(sweeper, flux_docs or base.flux_docs, fluid_docs or base.fluid_docs,
                                          lock if lock_docs is None else lock_docs)
        if raised:
            failures.append(f"[shapes] {label}: {raised}")

    for path in list(_node_paths(contract)):
        for shape in _SHAPES:
            mutated = copy.deepcopy(contract)
            put(mutated, path, copy.deepcopy(shape))
            run(f"the contract's {'.'.join(map(str, path))} as {shape!r:.20}", fluid_docs={contract_id: (contract_path, mutated)})
    for path in list(_node_paths(lock[0])):
        for shape in _SHAPES:
            mutated = copy.deepcopy(lock[0])
            put(mutated, path, copy.deepcopy(shape))
            run(f"the lockfile's {'.'.join(map(str, path))} as {shape!r:.20}", lock_docs=[mutated])
    for module_id, module in base.flux_docs.items():
        if module.get("kind") != "Module":
            continue
        for path in [p for p in _node_paths(module) if "config" in p]:
            for shape in _SHAPES:
                mutated = copy.deepcopy(module)
                put(mutated, path, copy.deepcopy(shape))
                if not list(flux_validator.iter_errors(mutated)):   # as load() does: an invalid document is left out
                    run(f"{module_id}'s {'.'.join(map(str, path))} as {shape!r:.20}", flux_docs={**base.flux_docs, module_id: mutated})
    # What a contract may hold that this one does not: a policy, and the use cases it allows.
    for shape in _SHAPES:
        for label, policy in (("a policy", shape), ("an agentPolicy", {"agentPolicy": shape}),
                              ("allowedUseCases", {"agentPolicy": {"allowedUseCases": shape}})):
            mutated = copy.deepcopy(contract)
            mutated["exposes"][0]["policy"] = copy.deepcopy(policy)
            run(f"{label} of {shape!r:.20}", fluid_docs={contract_id: (contract_path, mutated)})
    # A contract whose allow-list cannot be read cannot be shown to be as strict as the profile that gates it
    # (the example's does): that is an error, and not an allow-list with nothing in it.
    for shape in (5, True, "x", {"advertising": True}, [[1]], [{"a": 1}], [1]):
        for label, policy in (("allowedUseCases", {"agentPolicy": {"allowedUseCases": shape}}), ("an agentPolicy", {"agentPolicy": [shape]})):
            mutated = copy.deepcopy(contract)
            mutated["exposes"][0]["policy"] = copy.deepcopy(policy)
            run(f"{label} of {shape!r:.20}", fluid_docs={contract_id: (contract_path, mutated)})
            if not any("cannot be read as a list of use case names" in error for error in sweeper.errors):
                failures.append(f"[shapes] {label} of {shape!r:.20} was not reported where a ConsentProfile gates the contract")
    # A Module may name its measures as the keys of a mapping: that read before, and reads still.
    for module_id, module in base.flux_docs.items():
        for bind in module["spec"].get("binds", []) if module.get("kind") == "Module" else []:
            declared = (bind.get("config") or {}).get("measures")
            if bind.get("port") == "ossie-model" and isinstance(declared, list):
                mutated = copy.deepcopy(module)
                for changed in mutated["spec"]["binds"]:
                    if changed.get("port") == "ossie-model":
                        changed["config"]["measures"] = {(m if isinstance(m, str) else m["name"]): {"type": "count"} for m in declared}
                run(f"{module_id}'s measures as a mapping", flux_docs={**base.flux_docs, module_id: mutated})
                if any("is not declared by the bound semantic model" in error for error in sweeper.errors):
                    failures.append(f"[shapes] {module_id}'s measures, named as the keys of a mapping, are no longer read")
    return failures


def _strict_stdout(encoding: str = "utf-8"):
    """A stdout that encodes as a terminal's does, and raises for what it cannot encode. A StringIO takes
    anything, so it cannot tell a line that `print` would raise on."""
    return io.TextIOWrapper(io.BytesIO(), encoding=encoding, errors="strict")


def check_a_line_with_a_lone_surrogate_is_printed_not_raised(flux_validator) -> list[str]:
    """YAML can build a string UTF-8 cannot hold: "\\ud800" is a lone surrogate. A message that spells one with
    an f-string (a duplicate document id does) made `print` raise out of validate, pack and verify, which
    print what they find. Such a line is written as its escape."""
    import validate as validate_tool

    failures = []
    if validate_tool.bounded_line("id '\ud800' twice") != "id '\\ud800' twice":
        failures.append("[print] bounded_line did not write a lone surrogate as its escape")
    if len(validate_tool.bounded_line("\ud800" * 5_000)) > validate_tool.MAX_LINE:
        failures.append("[print] a line of lone surrogates, written as their escapes, is longer than MAX_LINE")
    # A stdout that is not UTF-8 lacks more than a surrogate: cp1252, a Windows pipe's, has no CJK.
    for encoding, ident, escaped in (("utf-8", "\\ud800", "\\ud800"), ("cp1252", "\\u65e5\\u672c", "\\u65e5\\u672c")):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "bundle"
            shutil.copytree(EXAMPLES, work)
            fluid = work / "payment-recovery.fluid.yml"
            text = re.sub(r"(?m)^id:.*$", lambda match: f'id: "{ident}"', fluid.read_text(encoding="utf-8"), count=1)
            fluid.write_text(text, encoding="utf-8")
            (work / "second.fluid.yml").write_text(text, encoding="utf-8")
            shown = _strict_stdout(encoding)
            try:
                with contextlib.redirect_stdout(shown):
                    code = validate_tool.main([str(work)])
                    packed = bundle_tool.pack(work, Path(tmp) / "dist", flux_validator)
            except Exception as exc:  # noqa: BLE001 (a raise is the failure)
                failures.append(f"[print] {type(exc).__name__} raised printing a duplicate id that a {encoding} stdout cannot hold: {str(exc)[:60]}")
                continue
            shown.flush()
            said = shown.buffer.getvalue().decode(encoding)
            if code != 1 or packed != 1 or said.count(escaped) < 2:
                failures.append(f"[print] a duplicate id that a {encoding} stdout cannot hold was not reported as its escape by validate ({code}) and pack ({packed}): {said[:200]!r}")
    return failures


def _broken_check(name):
    """A stand in for the cross-check *name* that raises, as one that met a value it was not written for would."""
    def broken(self):
        raise TypeError("a value of no shape this check expected")
    broken.__name__ = name
    return broken


def check_a_check_that_cannot_read_a_bundle_fails_it_instead_of_raising(flux_validator) -> list[str]:
    """Each shape known to raise is read where it is. Bundle._guarded is what keeps one that nobody guarded from
    raising out of validate, pack and verify: a check that raises fails the bundle, by name, and a bundle that
    fails is not packed."""
    failures = []
    for name in ("check_refs", "check_semantics", "check_fluid_seam"):
        with tempfile.TemporaryDirectory() as tmp:
            work, out = Path(tmp) / "bundle", Path(tmp) / "dist"
            shutil.copytree(EXAMPLES, work)
            try:
                with _patched(Bundle, **{name: _broken_check(name)}), contextlib.redirect_stdout(_strict_stdout()):
                    errors = Bundle(work, flux_validator).run()
                    packed = bundle_tool.pack(work, out, flux_validator)
            except Exception as exc:  # noqa: BLE001 (a raise is the failure)
                failures.append(f"[guarded] {name} raised {type(exc).__name__} out of run() or pack: {str(exc)[:60]}")
                continue
            if not any(f"{name} could not read this bundle (TypeError: a value of no shape this check expected)" in e for e in errors):
                failures.append(f"[guarded] a bundle whose {name} raised was not reported by that check: {[e[:100] for e in errors][:2]}")
            if packed == 0 or list(out.glob("*.flux.tgz")):
                failures.append(f"[guarded] a bundle whose {name} could not read it was packed")
    return failures


#: Spellings no real document holds, one for each way PyYAML or what reads after it can fail on a scalar.
_HOSTILE = (
    "!!int abc", "!!int ''", "0x_", "9" * 5000, "-" + "9" * 5000, "0x" + "f" * 5000, str(2 ** 60), "!!float ZZZ", "1e999", ".nan",
    _sexagesimal(175), "!!bool maybe", "!!binary aGVsbG8=", "!!set x", "!!python/object:os.system x", "2026-13-45", '"\\ud800"',
    "'" + "x" * 50_000 + "'", '"\\x00\\x01"', "~",
)
#: Spellings for a mapping key: PyYAML builds a key of any hashable kind, and JSON has only strings.
_HOSTILE_KEYS = ("1", ".nan", "true", "null", "0x10", "!!binary aGk=", '"\\ud800"')


def check_hostile_yaml_never_raises_through_validate_pack_and_verify(flux_validator) -> list[str]:
    """A seeded fuzz: each case puts one hostile spelling in place of one scalar or one mapping key of one file of
    an example bundle (the lockfile and the FLUID contract included), then reads the bundle with Bundle.run(),
    and, for one case in four, packs it and verifies an archive that holds it. Nothing may raise.

    A quarter of such cases raised on the code before this check, from several places: PyYAML's constructors,
    jsonschema's message for a very long integer, RFC 8785's digest, a line that stdout could not encode, and
    an f-string that spelled an integer. What a check could still not read is reported by Bundle.run() as that
    check's, not raised, and this fails for it as well: a read nobody guarded is a bug to fix where it is read."""
    import random

    rng = random.Random(20261119)
    files = sorted(p for p in EXAMPLES.iterdir() if p.suffix in (".yml", ".yaml") or p.name == "flux.lock")
    texts = {p.name: p.read_text(encoding="utf-8") for p in files}
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        clean = Path(tmp) / "clean" / "bundle"
        shutil.copytree(EXAMPLES, clean)
        with contextlib.redirect_stdout(_strict_stdout()):
            bundle_tool.pack(clean, Path(tmp) / "clean-dist", flux_validator)
        with tarfile.open(Path(tmp) / "clean-dist" / "bundle.flux.tgz") as tar:
            members = [(m.name, tar.extractfile(m).read()) for m in tar.getmembers()]
        cases = [(spelling, "value") for spelling in _HOSTILE] + [(spelling, "key") for spelling in _HOSTILE_KEYS]
        for number, (spelling, kind) in enumerate(cases):
            name = rng.choice(files).name
            start, end = rng.choice(_scalar_spans(texts[name], kind))
            hostile = texts[name][:start] + spelling + texts[name][end:]
            where = f"{spelling[:24]!r} for a {kind} of {name}"
            work = Path(tmp) / f"w{number}" / "bundle"
            shutil.copytree(EXAMPLES, work)
            (work / name).write_text(hostile, encoding="utf-8")
            stages = ["run"] + (["pack", "verify"] if number % 4 == 0 else [])
            for stage in stages:
                try:
                    with contextlib.redirect_stdout(_strict_stdout()):
                        if stage == "run":
                            errors = Bundle(work, flux_validator).run()
                            assert all(isinstance(e, str) for e in errors)
                            failures += [f"[fuzz] {e[:110]} on {where}" for e in errors if "could not read this bundle" in e]
                        elif stage == "pack":
                            bundle_tool.pack(work, Path(tmp) / f"d{number}", flux_validator)
                        else:
                            attacked = Path(tmp) / f"a{number}.flux.tgz"
                            with tarfile.open(attacked, "w:gz") as dst:
                                for member, data in members:
                                    data = hostile.encode("utf-8") if member.endswith("/" + name) else data
                                    info = tarfile.TarInfo(member)
                                    info.size, info.mtime, info.mode = len(data), 0, 0o644
                                    dst.addfile(info, io.BytesIO(data))
                            bundle_tool.verify(attacked, flux_validator)
                except Exception as exc:  # noqa: BLE001 (a raise is the failure)
                    failures.append(f"[fuzz] {stage} raised {type(exc).__name__}: {str(exc)[:60]} on {where}")
            shutil.rmtree(work.parent, ignore_errors=True)
    return failures


def check_a_number_that_is_not_finite_or_too_long_is_unreadable_yaml(flux_validator) -> list[str]:
    """The FLUX engine's read refuses a number that is not finite and one that needs more than 1,000 digits
    written out, a zero counting the digits its scale spells, and so does this one, by line and column. A NaN
    is neither above nor below anything, so a gate that compares one passes it: it reached the validator as
    `credibility: .nan` and satisfied a `minCredibility` gate."""
    import validate as validate_tool

    not_finite = "an infinite or not-a-number value has no digest and no ordering"
    too_long = "a number that needs more than 1000 digits written out is too long"
    not_decimal = "a scalar read as a float is not a decimal number"
    refused = {
        "a NaN": (".nan", not_finite), "an infinity": (".inf", not_finite), "a negative infinity": ("-.inf", not_finite),
        "a NaN with its tag": ("!!float nan", not_finite), "an infinity with its tag": ("!!float -Infinity", not_finite),
        "a number past what a float holds": ("1.0e+400", not_finite), "a negative one": ("-1.0e+400", not_finite),
        "a number of 1,002 digits": ("1.0e-1001", too_long), "a zero whose scale is ten million": ("0.e-10000000", too_long),
        "a zero with 1,001 decimals": ("0." + "0" * 1001, too_long), "a negative zero of that scale": ("-0.e-1001", too_long),
        # An exponent past what a decimal holds cannot be counted, and a float of it is 0.0: it was read.
        "a zero whose scale is past what a decimal holds": ("0.e-99999999999999999999", not_decimal),
        "a number of that scale": ("1.0e-99999999999999999999", not_decimal),
        "a zero of that exponent": ("0.0e+99999999999999999999", not_decimal),
        "a tagged number of that scale": ('!!float "1e-99999999999999999999"', not_decimal),
    }
    read = {
        "a zero whose scale is 1,000": "0.e-1000", "a number of 1,000 digits": "1.0e-999", "a large float": "1.5e+300",
        "a zero with a huge exponent": "0.e+99999999", "a negative zero": "-0.0", "underscores": "1_000.5",
        "a sexagesimal float, which the engine refuses and this reads": "1:30.5",
    }
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        for label, (spelling, why) in refused.items():
            try:
                docs, error = _read_text(f"a: 1\nb: {spelling}\n", Path(tmp))
            except Exception as exc:  # noqa: BLE001 (a raise is the failure)
                failures.append(f"[finite] load_yaml_docs raised {type(exc).__name__} on {label}")
                continue
            if docs or error != f"unreadable YAML: {why} (line 2, column 4)":
                failures.append(f"[finite] {label} was not refused as '{why}' at (line 2, column 4): {len(docs)} documents, {error}")
        for label, spelling in read.items():
            docs, error = _read_text(f"a: 1\nb: {spelling}\n", Path(tmp))
            if error or len(docs) != 1:
                failures.append(f"[finite] {label} did not read: {error}")
    return failures


def _errors_of(flux_validator, check, edit):
    """The errors the cross-check *check* of the example bundle reports once *edit* has changed its documents,
    which are put in place as they are, as no gate meets a document that the read refused."""
    bundle = Bundle(EXAMPLES, flux_validator)
    bundle.load()
    docs = copy.deepcopy(bundle.flux_docs)
    edit(docs)
    bundle.flux_docs, bundle.errors = docs, []
    getattr(bundle, check)()
    return bundle.errors


def check_a_number_that_is_not_finite_never_satisfies_a_numeric_gate(flux_validator) -> list[str]:
    """Every numeric gate of the validator is written so that a NaN fails it: a sum compares with `not <=`, not
    `>`, an order with `not <`, a minimum with `not >=`. Each is put a NaN, and an infinity, directly, as no read
    would let one through; and a bundle whose scorecard says `.nan` is refused by the read and does not satisfy
    its Simulation's gate."""
    nan, inf = float("nan"), float("inf")

    def of(kind, docs):
        return next(doc for doc in docs.values() if doc.get("kind") == kind)

    def lifecycle(value):
        return lambda docs: of("World", docs)["spec"]["population"]["lifecycleMix"].__setitem__("new", value)

    def weight(value):
        return lambda docs: of("Experiment", docs)["spec"]["variants"][0].__setitem__("weight", value)

    def level(value):
        return lambda docs: of("Persona", docs)["spec"]["traits"]["priceSensitivity"]["levels"].__setitem__("low", value)

    def maximum(value):
        def edit(docs):
            trait = of("Persona", docs)["spec"]["traits"]["monthlySpend"]
            trait["min"], trait["max"] = 0, value
        return edit

    def credibility(value):
        return lambda docs: of("Playback", docs)["spec"]["scorecard"].__setitem__("credibility", value)

    def minimum(value):
        def edit(docs):
            of("Simulation", docs)["spec"]["emits"][0]["minCredibility"] = value
        return edit

    def skill_budget(value):
        return lambda docs: of("Simulation", docs)["skills"][0].__setitem__("tokenBudget", value)

    # An infinity is above everything, so a maximum of one is in order; it fails the others.
    cases = (
        ("check_sums_and_sets", "population.lifecycleMix sums to", lifecycle, (nan, inf, -inf)),
        ("check_sums_and_sets", "variant weights sum to", weight, (nan, inf, -inf)),
        ("check_traits", "levels sums to", level, (nan, inf, -inf)),
        ("check_traits", "must be below max", maximum, (nan,)),
        ("check_fluid_seam", "minCredibility", credibility, (nan, inf, -inf)),
        ("check_fluid_seam", "minCredibility", minimum, (nan, inf)),
        ("check_agent_policy", "exceeds agentPolicy.tokenBudget", skill_budget, (nan, inf)),
    )
    failures = []
    for check, expected, make, values in cases:
        for value in values:
            try:
                errors = _errors_of(flux_validator, check, make(value))
            except Exception as exc:  # noqa: BLE001 (a raise is the failure)
                failures.append(f"[finite] {check} raised {type(exc).__name__} for {make.__name__}({value})")
                continue
            if not any(expected in error for error in errors):
                failures.append(f"[finite] {check} passed {make.__name__}({value}): {[e[:80] for e in errors][:2]}")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "bundle"
        shutil.copytree(EXAMPLES, work)
        playback = work / "playback.flux.yml"
        playback.write_text(re.sub(r"credibility:\s*[0-9.]+", "credibility: .nan", playback.read_text(encoding="utf-8")), encoding="utf-8")
        errors = Bundle(work, flux_validator).run()
        if not any("not-a-number" in error for error in errors) or not any("minCredibility" in error for error in errors):
            failures.append(f"[finite] a scorecard of .nan was not refused, or satisfied the gate: {[e[:90] for e in errors][:3]}")
    return failures


def check_the_enforcement_gate_answers_a_policy_it_cannot_digest_and_a_skill_it_cannot_read(flux_validator) -> list[str]:
    """RFC 8785 has no spelling for a number that is not finite (JSON has none either: `1e999` is how a
    parser reads one), so a policy that holds one has no policyDigest and is INVALID_POLICY, where `decide`
    raised FloatDomainError out of the gate; so is a policy that holds a value or a key JSON has no spelling
    for, or that nests past what can be written (it raised RecursionError). A skill whose own tokenBudget is
    present and not an integer is INVALID_POLICY, never an unnarrowed policy; an integer of any size or sign
    is read as it was. The request is not digested: the gate reads four of its fields, and decides on those,
    as it did. Every decision names its cause in words, not as the name of an exception; one that echoes a
    request the gate was given as it is, is one a strict JSON writer can write, and the published decision
    contract accepts."""
    nan, inf = float("nan"), float("inf")
    good = {"allowedModels": ["m"], "tokenBudget": 1000}
    req = {"model": "m", "useCase": "u", "tokens": 5, "purpose": "p"}
    deep, nested = [], []
    for _ in range(5000):
        deep = [deep]
    for _ in range(2000):
        nested = [nested]
    cases = {
        "a NaN budget": ({**good, "tokenBudget": nan}, req, None, "INVALID_POLICY"),
        "an infinite budget": ({**good, "tokenBudget": inf}, req, None, "INVALID_POLICY"),
        "a NaN anywhere in the policy": ({**good, "x": nan}, req, None, "INVALID_POLICY"),
        "bytes in the policy": ({**good, "x": b"y"}, req, None, "INVALID_POLICY"),
        "an integer past 2^53 in the policy": ({**good, "x": 2 ** 60}, req, None, "INVALID_POLICY"),
        "an integer of 5,000 digits in the policy": ({**good, "x": 10 ** 5000}, req, None, "INVALID_POLICY"),
        "a key that is not text": ({**good, 1: "x"}, req, None, "INVALID_POLICY"),
        "a lone surrogate key": ({**good, "\ud800": 1}, req, None, "INVALID_POLICY"),
        "a lone surrogate value": ({**good, "x": "\ud800"}, req, None, "INVALID_POLICY"),
        "a policy nested 5,000 deep": ({**good, "x": deep}, req, None, "INVALID_POLICY"),
        "a NaN skill budget": (good, req, {"name": "s", "tokenBudget": nan}, "INVALID_POLICY"),
        "an infinite skill budget": (good, req, {"name": "s", "tokenBudget": inf}, "INVALID_POLICY"),
        "a skill budget that is text": (good, req, {"name": "s", "tokenBudget": "9"}, "INVALID_POLICY"),
        "a skill budget that is null": (good, req, {"name": "s", "tokenBudget": None}, "INVALID_POLICY"),
        "a skill budget that is a boolean": (good, req, {"name": "s", "tokenBudget": True}, "INVALID_POLICY"),
        "a skill that is not an object": (good, req, ["s"], "INVALID_POLICY"),
        "a skill that is an empty list": (good, req, [], "INVALID_POLICY"),
        "a skill that is false": (good, req, False, "INVALID_POLICY"),
        "a skill that is zero": (good, req, 0, "INVALID_POLICY"),
        "a skill that is an empty string": (good, req, "", "INVALID_POLICY"),
        "a skill that is an empty object": (good, req, {}, "ALLOWED"),
        "no skill": (good, req, None, "ALLOWED"),
        "a skill that narrows": (good, req, {"name": "s", "tokenBudget": 10}, "ALLOWED"),
        "a skill that does not name a budget": (good, req, {"name": "s"}, "ALLOWED"),
        "a skill budget above 2^53, which cannot widen": (good, req, {"name": "s", "tokenBudget": 2 ** 60}, "ALLOWED"),
        "a skill budget of zero, which narrows to nothing": (good, req, {"name": "s", "tokenBudget": 0}, "TOKEN_BUDGET_EXCEEDED"),
        "a lone surrogate in a purpose": (good, {**req, "purpose": "\ud83d"}, None, "ALLOWED"),
    }
    # The request is echoed as it is, so no strict JSON writer is asked to write these decisions.
    as_given = {
        "NaN tokens": (good, {**req, "tokens": nan}, None, "INVALID_REQUEST"),
        "a request nested 2,000 deep": (good, {**req, "x": nested}, None, "ALLOWED"),
        "an integer of 5,000 digits in a request": (good, {**req, "x": 10 ** 5000}, None, "ALLOWED"),
    }
    contract = json.loads((REPO / "schema" / "flux-enforcement-0.5.0.json").read_text(encoding="utf-8"))
    decision_validator = Draft202012Validator({"$ref": "#/$defs/decision", "$defs": contract["$defs"]})
    failures = []
    for strict, group in ((True, cases), (False, as_given)):
        for label, (policy, request, skill, expected) in group.items():
            try:
                decision = enforce.decide(policy, request, skill)
                if strict:
                    json.dumps(decision, allow_nan=False)
            except Exception as exc:  # noqa: BLE001 (a raise is the failure)
                failures.append(f"[enforcement] {label}: raised {type(exc).__name__}: {str(exc)[:50]}")
                continue
            if decision["reasonCode"] != expected:
                failures.append(f"[enforcement] {label}: {decision['reasonCode']}, expected {expected}")
            if "Error" in decision["reason"]:
                failures.append(f"[enforcement] {label}: the reason names an exception, not a cause: {decision['reason'][:90]}")
            for error in decision_validator.iter_errors(decision) if strict else ():
                failures.append(f"[enforcement] {label}: the decision violates the contract: {error.message[:60]}")
                break
    wide = enforce.decide(good, req, {"name": "s", "tokenBudget": 2 ** 60})
    if wide.get("effectiveBudget") != 1000:
        failures.append(f"[enforcement] a skill budget above 2^53 widened the policy's: {wide.get('effectiveBudget')}")
    return failures


def main() -> int:
    failures = []

    for label, doc in CASES_PASS.items():
        errors = list(VALIDATOR.iter_errors(doc))
        if errors:
            failures.append(f"[schema] expected PASS but got errors — {label}: {errors[0].message}")

    for label, doc in CASES_REJECT.items():
        if not list(VALIDATOR.iter_errors(doc)):
            failures.append(f"[schema] expected REJECT but passed — {label}")

    # the fixed vacuous-if behavior: kind-absent must yield ONLY the missing-kind error
    kindless = {k: v for k, v in envelope("World", **copy.deepcopy(WORLD_SPEC)).items() if k != "kind"}
    msgs = [e.message for e in VALIDATOR.iter_errors(kindless)]
    if len(msgs) != 1 or "kind" not in msgs[0]:
        failures.append(f"[schema] kind-absent doc should raise exactly 1 error naming 'kind', got {len(msgs)}: {msgs[:3]}")

    flux_validator = VALIDATOR
    for label, (filename, fn, expected_fragment) in VALIDATOR_REJECTS.items():
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            shutil.copytree(EXAMPLES, bundle)
            mutate_yaml(bundle, filename, fn)
            errors = Bundle(bundle, flux_validator).run()
            if not any(expected_fragment in e for e in errors):
                failures.append(
                    f"[validator] expected error containing '{expected_fragment}' — {label}; got: {errors[:3]}"
                )

    # pristine example bundle must stay green end to end
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "bundle"
        shutil.copytree(EXAMPLES, bundle)
        errors = Bundle(bundle, flux_validator).run()
        if errors:
            failures.append(f"[validator] pristine example bundle failed: {errors[:5]}")

    # 0.5.1: the towers example pins FLUID 0.7.6 exactly and stays green, and its
    # 0.7.6 contract is really checked against the 0.7.6 schema, not waved through
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "bundle"
        shutil.copytree(TOWERS_EXAMPLE, bundle)
        errors = Bundle(bundle, flux_validator).run()
        if errors:
            failures.append(f"[validator] pristine towers bundle failed: {errors[:5]}")
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "bundle"
        shutil.copytree(TOWERS_EXAMPLE, bundle)
        mutate_yaml(bundle, "tenant-renewal-risk.fluid.yml", _break_fluid)
        errors = Bundle(bundle, flux_validator).run()
        if not any("fails FLUID 0.7.6" in e for e in errors):
            failures.append(f"[validator] a broken FLUID 0.7.6 contract was not caught: {errors[:3]}")

    # 0.5.2: the FLUID 0.7.7 preview, its pins and the seam's opt-in rule
    failures += check_fluid_previews()
    failures += check_preview_bundles(flux_validator)

    # 0.5.3: the FLUID 0.7.7 preview re-pinned to forge-cli e88301f7
    failures += check_preview_repin(flux_validator)
    failures += check_pack_from_looser_preview(flux_validator)

    # ref-like keys inside free-form payloads must not be flagged
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "bundle"
        shutil.copytree(EXAMPLES, bundle)
        mutate_yaml(bundle, "treatment-fast.flux.yml", _payload_with_reflike_keys)
        errors = Bundle(bundle, flux_validator).run()
        if errors:
            failures.append(f"[validator] free-form payload keys wrongly treated as refs: {errors[:3]}")

    # malformed input: clean bundle errors, never an exception
    for label, (setup, expected_fragment) in VALIDATOR_ROBUSTNESS.items():
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            shutil.copytree(EXAMPLES, bundle)
            setup(bundle)
            try:
                errors = Bundle(bundle, flux_validator).run()
            except Exception as exc:  # noqa: BLE001 — the whole point of the test
                failures.append(f"[validator] CRASHED ({type(exc).__name__}: {exc}) — {label}")
                continue
            if not any(expected_fragment in e for e in errors):
                failures.append(f"[validator] expected error containing '{expected_fragment}' — {label}; got: {errors[:3]}")

    # unquoted YAML timestamps load as strings and validate green
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "bundle"
        shutil.copytree(EXAMPLES, bundle)
        sim = (bundle / "simulation.flux.yml").read_text(encoding="utf-8")
        sim = sim.replace('start: "2026-07-01T00:00:00Z"', "start: 2026-07-01T00:00:00Z")
        sim = sim.replace('end: "2026-09-30T23:59:59Z"', "end: 2026-09-30T23:59:59Z")
        (bundle / "simulation.flux.yml").write_text(sim, encoding="utf-8")
        errors = Bundle(bundle, flux_validator).run()
        if errors:
            failures.append(f"[validator] unquoted timestamps should be green: {errors[:3]}")

    # nonexistent bundle dir: clear message, no glob-silence
    missing_errors = Bundle(Path("/nonexistent/bundle-dir"), flux_validator).run()
    if not any("does not exist" in e for e in missing_errors):
        failures.append(f"[validator] nonexistent dir should say so; got: {missing_errors}")

    # ---- RFC-04: the reference gate matches every conformance vector -------
    VECTORS = REPO / "tests" / "enforcement-vectors.json"
    if enforce.main(["--vectors", str(VECTORS)]) != 0:
        failures.append("[enforcement] conformance vectors did not all pass")

    # every decision must satisfy the published decision contract
    contract = json.loads((REPO / "schema" / "flux-enforcement-0.5.0.json").read_text(encoding="utf-8"))
    decision_validator = Draft202012Validator({"$ref": "#/$defs/decision", "$defs": contract["$defs"]})
    for v in json.loads(VECTORS.read_text(encoding="utf-8"))["vectors"]:
        for e in decision_validator.iter_errors(enforce.decide(v["policy"], v["request"], v.get("skill"))):
            failures.append(f"[enforcement] decision for {v['name']!r} violates the contract: {e.message}")
            break
    # the contract must reject a decision that contradicts itself
    if decision_validator.is_valid({"allow": True, "reasonCode": "MODEL_NOT_ALLOWED",
                                    "reason": "x", "policyDigest": "sha256:" + "0" * 64, "request": {}}):
        failures.append("[enforcement] contract accepts allow=true with a deny reasonCode")

    # THE meta-test: the vector suite must actually constrain conformance.
    # Each gate below is the reference with one real defect; every one must FAIL.
    def _broken(defect):
        def gate(policy, request, skill=None):
            if defect == "fail_open_purpose":       # purposeLimitation defaults to false
                policy = {"purposeLimitation": False, **policy}
            elif defect == "skill_replaces_budget":  # skill widens instead of narrowing
                if skill and enforce.as_int(skill.get("tokenBudget")) is not None:
                    policy = {**policy, "tokenBudget": skill["tokenBudget"]}
                skill = None
            elif defect == "native_int_budget":      # isinstance(x, int) instead of JSON integer
                if isinstance(policy.get("tokenBudget"), float):
                    policy = {k: v for k, v in policy.items() if k != "tokenBudget"}
                    policy["tokenBudget"] = 10 ** 15
            elif defect == "case_insensitive":       # folds case before matching
                request = {**request, "useCase": str(request.get("useCase", "")).lower(),
                           "model": str(request.get("model", "")).lower()}
                policy = {**policy,
                          "allowedModels": [m.lower() for m in policy.get("allowedModels", [])]}
            elif defect == "lenient_policy":         # enforces off-spec policies instead of rejecting
                if enforce.policy_problem(policy):
                    policy = {"allowedModels": policy.get("allowedModels") or ["*"],
                              "tokenBudget": 10 ** 15, "purposeLimitation": False}
            d = enforce.decide(policy, request, skill)
            if defect == "fake_digest":              # no real binding to the policy
                d = {**d, "policyDigest": "sha256:" + "0" * 64}
            return d
        return gate

    for defect in ("fail_open_purpose", "skill_replaces_budget", "native_int_budget",
                   "case_insensitive", "lenient_policy", "fake_digest"):
        broken, _ = enforce.run_vectors(VECTORS, gate=_broken(defect))
        if broken == 0:
            failures.append(f"[enforcement] a gate with defect {defect!r} passes the whole vector suite — "
                            "the suite does not constrain conformance")

    # canonicalisation (RFC 8785): spelling must not change the digest, content must
    base = {"allowedModels": ["modèle-8b"], "tokenBudget": 1000, "purposeLimitation": False}
    respelled = {"purposeLimitation": False, "tokenBudget": 1000.0, "allowedModels": ["modèle-8b"]}
    if enforce.policy_digest(base) != enforce.policy_digest(respelled):
        failures.append("[enforcement] policyDigest changes with key order / number spelling — not canonical")
    if enforce.policy_digest(base) == enforce.policy_digest({**base, "tokenBudget": 1001}):
        failures.append("[enforcement] policyDigest collides across different policies")
    # a skill must not rewrite the digest: it is the DOCUMENT's policy that is attested
    req = {"model": "modèle-8b", "useCase": "u", "tokens": 5}
    with_skill = enforce.decide(base, req, {"name": "s", "tokenBudget": 10})
    if with_skill["policyDigest"] != enforce.policy_digest(base):
        failures.append("[enforcement] policyDigest under a skill does not match the document policy")
    if with_skill.get("effectiveBudget") != 10 or with_skill.get("skillRef") != "s":
        failures.append("[enforcement] narrowing is not recorded as effectiveBudget/skillRef")

    # ---- RFC-09: pack -> verify round-trip, determinism, tamper detection --
    with tempfile.TemporaryDirectory() as tmp:
        work, out = Path(tmp) / "bundle", Path(tmp) / "dist"
        shutil.copytree(EXAMPLES, work)
        if bundle_tool.pack(work, out, flux_validator) != 0:
            failures.append("[bundle] packing the example bundle failed")
        archive = out / f"{work.name}.flux.tgz"
        first = archive.read_bytes()
        if bundle_tool.verify(archive, flux_validator) != 0:
            failures.append("[bundle] verify rejected a freshly packed bundle")
        bundle_tool.pack(work, out, flux_validator)
        if archive.read_bytes() != first:
            failures.append("[bundle] archives are not byte-identical across repacks")

        manifest = json.loads((work / "flux-manifest.json").read_text(encoding="utf-8"))
        if manifest["attestation"]["profile"] != "enterprise":
            failures.append(f"[bundle] expected enterprise profile, got {manifest['attestation']['profile']}")
        if bundle_tool.merkle_root(manifest["files"]) != manifest["merkleRoot"]:
            failures.append("[bundle] merkle root does not match the manifest file list")
        tweaked = dict(manifest["files"])
        first_key = sorted(tweaked)[0]
        tweaked[first_key] = "sha256:" + "0" * 64
        if bundle_tool.merkle_root(tweaked) == manifest["merkleRoot"]:
            failures.append("[bundle] merkle root is insensitive to a changed file digest")

    # tampering with any file inside a packed archive must fail verification
    with tempfile.TemporaryDirectory() as tmp:
        work, out = Path(tmp) / "bundle", Path(tmp) / "dist"
        shutil.copytree(EXAMPLES, work)
        bundle_tool.pack(work, out, flux_validator)
        archive = out / f"{work.name}.flux.tgz"
        tampered = out / "tampered.flux.tgz"
        with tarfile.open(archive, "r:gz") as src, tarfile.open(tampered, "w:gz") as dst:
            for member in src.getmembers():
                data = src.extractfile(member).read()
                if member.name.endswith("world.flux.yml"):
                    data = data.replace(b"size: 25000", b"size: 999999")
                info = tarfile.TarInfo(member.name)
                info.size, info.mtime, info.mode = len(data), 0, 0o644
                dst.addfile(info, io.BytesIO(data))
        if bundle_tool.verify(tampered, flux_validator) == 0:
            failures.append("[bundle] verify accepted a tampered archive")

    # a .sig file smuggled into an archive must be reported as unmanifested
    # (detached signatures belong beside the archive, never inside it)
    with tempfile.TemporaryDirectory() as tmp:
        work, out = Path(tmp) / "bundle", Path(tmp) / "dist"
        shutil.copytree(EXAMPLES, work)
        bundle_tool.pack(work, out, flux_validator)
        archive, smuggled = out / f"{work.name}.flux.tgz", out / "smuggled.flux.tgz"
        with tarfile.open(archive, "r:gz") as src, tarfile.open(smuggled, "w:gz") as dst:
            for member in src.getmembers():
                data = src.extractfile(member).read()
                info = tarfile.TarInfo(member.name)
                info.size, info.mtime, info.mode = len(data), 0, 0o644
                dst.addfile(info, io.BytesIO(data))
            payload = b"arbitrary unmanifested content"
            info = tarfile.TarInfo(f"{work.name}/payload.sig")
            info.size, info.mtime, info.mode = len(payload), 0, 0o644
            dst.addfile(info, io.BytesIO(payload))
        if bundle_tool.verify(smuggled, flux_validator) == 0:
            failures.append("[bundle] verify accepted an archive with an unmanifested .sig payload")

    # the in-toto Statement must describe the archive it was emitted beside
    with tempfile.TemporaryDirectory() as tmp:
        work, out = Path(tmp) / "bundle", Path(tmp) / "dist"
        shutil.copytree(EXAMPLES, work)
        bundle_tool.pack(work, out, flux_validator)
        archive = out / f"{work.name}.flux.tgz"
        statement = json.loads((out / f"{work.name}{bundle_tool.STATEMENT_SUFFIX}").read_text(encoding="utf-8"))
        if statement.get("_type") != "https://in-toto.io/Statement/v1":
            failures.append(f"[bundle] statement _type is not in-toto v1: {statement.get('_type')}")
        subject = (statement.get("subject") or [{}])[0]
        if subject.get("digest", {}).get("sha256") != bundle_tool.sha256_file(archive):
            failures.append("[bundle] in-toto subject digest does not match the archive")
        if not statement.get("predicateType", "").startswith("https://"):
            failures.append("[bundle] in-toto predicateType is not a URI")

    # RFC 6962 domain separation: an interior hash must not be replayable as a leaf
    two = {"a.yml": "sha256:" + "11" * 32, "b.yml": "sha256:" + "22" * 32}
    root_two = bundle_tool.merkle_root(two)
    if bundle_tool.merkle_root({"a.yml": "sha256:" + "11" * 32}) == root_two:
        failures.append("[bundle] merkle root ignores the second entry")
    swapped = {"a.yml": two["b.yml"], "b.yml": two["a.yml"]}
    if bundle_tool.merkle_root(swapped) == root_two:
        failures.append("[bundle] merkle root is blind to swapping two files' digests")

    # ---- RFC-09 negative fixtures: every attack yields [FAIL], never a traceback
    BUNDLE_ATTACKS = {
        "file smuggled outside the bundle directory":
            (lambda e: e + [("stray-payload.bin", b"undeclared")], "one bundle directory"),
        "manifest lies about fluxVersions":
            (_lie("fluxVersions", ["9.9.9"]), "does not match the documents"),
        "manifest lies about schemaId":
            (_lie("schemaId", "https://evil.example/never-published.json"),
             "is not a FLUX schema inside this toolchain's compatibility window"),
        "manifest claims the unclaimable runtime profile":
            (lambda e: _edit_manifest(e, lambda m: m["attestation"].__setitem__("profile", "runtime")),
             "violates the manifest schema"),
        "manifest is not valid JSON":
            (lambda e: [(n, b"{not json" if n.endswith(bundle_tool.MANIFEST_NAME) else d) for n, d in e],
             "not valid JSON"),
        "duplicate archive entries":
            (lambda e: e + [e[0]], "duplicate archive entry"),
        "manifest holds a NaN, which JSON does not have":
            (lambda e: [(n, b'{"merkleRoot": NaN}' if n.endswith(bundle_tool.MANIFEST_NAME) else d) for n, d in e],
             "cannot read archive"),
        "manifest holds a number past what a float holds":
            (lambda e: [(n, b'{"merkleRoot": 1e999}' if n.endswith(bundle_tool.MANIFEST_NAME) else d) for n, d in e],
             "cannot read archive"),
        "manifest holds an integer of more than 4300 digits":
            (lambda e: [(n, b'{"merkleRoot": ' + b"9" * 5000 + b"}" if n.endswith(bundle_tool.MANIFEST_NAME) else d) for n, d in e],
             "cannot read archive" if 0 < getattr(sys, "get_int_max_str_digits", lambda: 0)() < 5_000 else "violates the manifest schema"),
    }
    for label, (mutate, expected) in BUNDLE_ATTACKS.items():
        with tempfile.TemporaryDirectory() as tmp:
            work, out = Path(tmp) / "bundle", Path(tmp) / "dist"
            shutil.copytree(EXAMPLES, work)
            try:
                attacked = _repack(work, out, mutate, flux_validator)
                rc, said = _verify_output(attacked, flux_validator)
            except Exception as exc:  # noqa: BLE001 — a traceback IS the failure
                failures.append(f"[bundle] CRASHED ({type(exc).__name__}: {exc}) — {label}")
                continue
            if rc == 0:
                failures.append(f"[bundle] verify accepted an archive where: {label}")
            elif expected not in said:
                failures.append(f"[bundle] verify refused an archive where {label}, but not for that: {said.strip()}")

    # malformed inputs that never reach the manifest at all
    with tempfile.TemporaryDirectory() as tmp:
        junk = Path(tmp) / "not-an-archive.flux.tgz"
        junk.write_bytes(b"this is not a gzip stream")
        for label, target in {"non-existent archive": Path(tmp) / "missing.tgz",
                              "non-gzip file": junk}.items():
            try:
                if bundle_tool.verify(target, flux_validator) == 0:
                    failures.append(f"[bundle] verify accepted a {label}")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"[bundle] CRASHED on {label} ({type(exc).__name__}: {exc})")

    # a declared-size bomb must be refused before anything is written to disk
    with tempfile.TemporaryDirectory() as tmp:
        work, out = Path(tmp) / "bundle", Path(tmp) / "dist"
        shutil.copytree(EXAMPLES, work)
        bomb = _repack(work, out, lambda e: e + [("bundle/bomb.bin", b"\0" * (2 * 1024 * 1024))], flux_validator)
        original_cap = bundle_tool.MAX_BUNDLE_BYTES
        bundle_tool.MAX_BUNDLE_BYTES = 1024 * 1024
        try:
            if bundle_tool.verify(bomb, flux_validator) == 0:
                failures.append("[bundle] verify accepted an archive above the size cap")
        finally:
            bundle_tool.MAX_BUNDLE_BYTES = original_cap

    failures += check_packs_across_releases(flux_validator)
    failures += check_schema_id_refusals(flux_validator)
    failures += check_pack_refuses_symlinks(flux_validator)
    failures += check_manifest_write_never_follows_a_link(flux_validator)
    failures += check_verify_refuses_unsafe_members(flux_validator)
    failures += check_verify_stops_at_its_caps_and_reports_a_broken_stream(flux_validator)
    failures += check_verify_never_raises_on_deep_nesting_or_a_nul_path(flux_validator)
    failures += check_a_subclass_lets_its_own_refusal_out_of_run_through_the_guard(flux_validator)
    failures += check_verify_reports_a_pax_header_tarfile_cannot_parse(flux_validator)
    failures += check_supply_chain_digests_each_target_once(flux_validator)
    failures += check_reads_bundles_as_utf8(flux_validator)
    failures += check_a_document_that_stands_for_too_much_is_refused_at_the_read(flux_validator)
    failures += check_a_document_at_the_bounds_reads_and_one_past_them_is_refused(flux_validator)
    failures += check_merge_keys_are_counted_for_each_mapping_that_holds_one(flux_validator)
    failures += check_characters_are_counted_each_time_they_are_written_out(flux_validator)
    failures += check_the_bounds_hold_through_validate_and_verify(flux_validator)
    failures += check_bounded_keeps_both_ends_of_a_long_message(flux_validator)
    failures += check_validator_messages_are_capped(flux_validator)
    failures += check_a_scalar_pyyaml_cannot_build_is_unreadable_yaml_by_its_position(flux_validator)
    failures += check_a_document_that_cannot_be_digested_is_reported_not_raised(flux_validator)
    failures += check_a_value_of_a_shape_no_check_expected_is_reported_not_raised(flux_validator)
    failures += check_a_line_with_a_lone_surrogate_is_printed_not_raised(flux_validator)
    failures += check_a_check_that_cannot_read_a_bundle_fails_it_instead_of_raising(flux_validator)
    failures += check_a_number_that_is_not_finite_or_too_long_is_unreadable_yaml(flux_validator)
    failures += check_a_number_that_is_not_finite_never_satisfies_a_numeric_gate(flux_validator)
    failures += check_the_enforcement_gate_answers_a_policy_it_cannot_digest_and_a_skill_it_cannot_read(flux_validator)
    failures += check_hostile_yaml_never_raises_through_validate_pack_and_verify(flux_validator)

    # a bundle that does not validate must never be packed
    with tempfile.TemporaryDirectory() as tmp:
        work, out = Path(tmp) / "bundle", Path(tmp) / "dist"
        shutil.copytree(EXAMPLES, work)
        mutate_yaml(work, "campaign.flux.yml", _dangling_ref)
        if bundle_tool.pack(work, out, flux_validator) == 0:
            failures.append("[bundle] packed a bundle that fails validation")

    # version-window pinning: released schema files are immutable, so a 0.4.0
    # document (extensions or not) must FAIL the 0.3.0 schema file
    old_schema = Draft202012Validator(
        json.loads((REPO / "schema" / "flux-schema-0.3.0.json").read_text(encoding="utf-8")),
        format_checker=FormatChecker(),
    )
    if not list(old_schema.iter_errors(envelope_040("Segment", query="x"))):
        failures.append("[schema] a 0.4.0 document should fail the immutable 0.3.0 schema (fluxVersion window)")
    # additivity (P1): every 0.3.0-pinned document in the example bundle stays
    # valid under the current release — covered by the pristine-bundle check
    # above, asserted here against the old schema too for the reverse direction
    if list(old_schema.iter_errors(envelope("Segment", query="x"))):
        failures.append("[schema] a plain 0.3.0 document should still pass the 0.3.0 schema")
    schema_050 = Draft202012Validator(
        json.loads((REPO / "schema" / "flux-schema-0.5.0.json").read_text(encoding="utf-8")),
        format_checker=FormatChecker(),
    )
    exact_076_as_050 = copy.deepcopy(sim_exact_076)
    exact_076_as_050["fluxVersion"] = "0.5.0"
    if not list(schema_050.iter_errors(exact_076_as_050)):
        failures.append("[schema] an exact FLUID 0.7.6 pin should fail the immutable 0.5.0 schema")

    total = (
        len(CASES_PASS) + len(CASES_REJECT) + 1
        + len(VALIDATOR_REJECTS) + len(VALIDATOR_ROBUSTNESS) + 6
        + 3   # 0.5.1: towers bundle green, broken 0.7.6 contract caught, 0.7.6 refused by 0.5.0
        + 20  # 0.5.2: pins, seam window, 7 bad pins, 4 sync refusals, 0.7.7 green, moved key, broken relationship,
              # range refused, 0.7.6 relationships refused, 0.7.7 refused by 0.5.1
        + 20  # 0.5.3: 8 forms the re-pinned 0.7.7 preview accepts, 10 it refuses, 0.5.3 refused by 0.5.2,
              # a pack made under a looser preview refused
        + 12  # RFC-04: vectors, contract conformance, self-contradiction, 6 broken gates, canonicalisation x3
        + 8   # RFC-09: pack, verify, determinism, profile, merkle x2, tamper, refuse-invalid
        + 6   # RFC-09 prior-art hardening: .sig smuggling, in-toto statement x3, merkle x2
        + 11  # RFC-09 negative fixtures: 8 archive attacks + 2 malformed inputs + size cap
        + 8   # RFC-09 across releases: window resolves, 0.5.0, 0.5.1 and 0.5.2 packs verify, named
              # schema applied, 0.2.0 and a newer release refused, a reset window refuses a 0.5.1 pack
        + 3   # RFC-09 pack refuses a linked file, a linked directory and a planted manifest link
        + 1   # RFC-09 the manifest write never follows a link that appears after that refusal
        + 7   # RFC-09 verify refuses .., absolute, symlink, hard link, FIFO, beside-the-directory
              # members and an archive above the member cap
    )
    if failures:
        print(f"FAIL — {len(failures)}/{total} checks failed")
        for f in failures:
            print(" ", f)
        return 1
    print(f"ok — {total} regression checks green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
