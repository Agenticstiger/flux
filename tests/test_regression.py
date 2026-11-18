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
import shutil
import sys
import tarfile
import tempfile
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
    failures += check_verify_reports_a_pax_header_tarfile_cannot_parse(flux_validator)
    failures += check_supply_chain_digests_each_target_once(flux_validator)
    failures += check_reads_bundles_as_utf8(flux_validator)

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
        + 9   # RFC-09 negative fixtures: 6 archive attacks + 2 malformed inputs + size cap
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
