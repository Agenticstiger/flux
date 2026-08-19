#!/usr/bin/env python3
"""Regression suite for flux-schema-0.3.0.

Every SCHEMA_REJECTS case below validated silently against flux-schema-0.2.0
(the false-passes found in the pre-open-sourcing review). 0.3.0 must reject
them all. VALIDATOR_REJECTS cases pass the schema but must be caught by the
offline reference validator's cross-document checks.

Run: python3 tests/test_regression.py   (exit 0 = green)
"""

from __future__ import annotations

import copy
import io
import json
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from validate import Bundle  # noqa: E402
import enforce  # noqa: E402
import bundle as bundle_tool  # noqa: E402

SCHEMA = json.loads((REPO / "schema" / "flux-schema-latest.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
EXAMPLES = REPO / "examples" / "telco-payment-recovery"


def envelope(kind, doc_id="doc-under-test", **spec):
    return {
        "fluxVersion": "0.3.0",
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

def envelope_040(kind, doc_id="doc-under-test", **spec):
    d = envelope(kind, doc_id, **spec)
    d["fluxVersion"] = "0.4.0"
    return d


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


def envelope_041(kind, doc_id="doc-under-test", **spec):
    d = envelope(kind, doc_id, **spec)
    d["fluxVersion"] = "0.4.1"
    return d


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
    emits=[{"productRef": "p", "exposeId": "x", "fluidVersion": "0.7.6"}],
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
    doc = yaml.safe_load(path.read_text())
    fn(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


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
    (bundle / "broken.flux.yml").write_text("kind: [unclosed\n  - {")


def _setup_non_mapping_doc(bundle: Path):
    (bundle / "scalar.flux.yml").write_text("just a string, not a document\n")


def _setup_dup_fluid_ids(bundle: Path):
    src = (bundle / "payment-recovery.fluid.yml").read_text()
    (bundle / "copy.fluid.yml").write_text(src)


def _setup_flux_fluid_collision(bundle: Path):
    doc = yaml.safe_load((bundle / "payment-recovery.fluid.yml").read_text())
    doc["id"] = "q3-retention-world"  # collides with the World flux doc
    (bundle / "collide.fluid.yml").write_text(yaml.safe_dump(doc, sort_keys=False))


def _setup_orphan_invalid_fluid(bundle: Path):
    (bundle / "orphan.fluid.yml").write_text(
        'fluidVersion: "0.7.5"\nkind: DataProduct\nid: orphan.broken\nname: Orphan\n'
    )


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
    )


VALIDATOR_ROBUSTNESS = {
    "malformed YAML": (_setup_malformed_yaml, "unreadable YAML"),
    "non-mapping document": (_setup_non_mapping_doc, "not a mapping"),
    "duplicate FLUID ids": (_setup_dup_fluid_ids, "duplicate FLUID document id"),
    "flux/fluid id collision": (_setup_flux_fluid_collision, "collides with"),
    "orphan invalid .fluid.yml still validated": (_setup_orphan_invalid_fluid, "fails FLUID 0.7.5"),
    "schema-invalid shapes yield errors, not tracebacks": (_setup_schema_invalid_no_crash, "schema:"),
    "RFC-03: versioned refs without a lockfile": (_setup_missing_lock, "no flux.lock"),
}


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
        sim = (bundle / "simulation.flux.yml").read_text()
        sim = sim.replace('start: "2026-07-01T00:00:00Z"', "start: 2026-07-01T00:00:00Z")
        sim = sim.replace('end: "2026-09-30T23:59:59Z"', "end: 2026-09-30T23:59:59Z")
        (bundle / "simulation.flux.yml").write_text(sim)
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
    contract = json.loads((REPO / "schema" / "flux-enforcement-0.5.0.json").read_text())
    decision_validator = Draft202012Validator({"$ref": "#/$defs/decision", "$defs": contract["$defs"]})
    for v in json.loads(VECTORS.read_text())["vectors"]:
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

        manifest = json.loads((work / "flux-manifest.json").read_text())
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
        statement = json.loads((out / f"{work.name}{bundle_tool.STATEMENT_SUFFIX}").read_text())
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
    def _repack(work: Path, out: Path, mutate):
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

    BUNDLE_ATTACKS = {
        "file smuggled outside the bundle directory":
            (lambda e: e + [("stray-payload.bin", b"undeclared")], "one bundle directory"),
        "manifest lies about fluxVersions":
            (_lie("fluxVersions", ["9.9.9"]), "does not match the documents"),
        "manifest lies about schemaId":
            (_lie("schemaId", "https://evil.example/never-published.json"), "not this toolchain's schema"),
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
                attacked = _repack(work, out, mutate)
                rc = bundle_tool.verify(attacked, flux_validator)
            except Exception as exc:  # noqa: BLE001 — a traceback IS the failure
                failures.append(f"[bundle] CRASHED ({type(exc).__name__}: {exc}) — {label}")
                continue
            if rc == 0:
                failures.append(f"[bundle] verify accepted an archive where: {label}")

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
        bomb = _repack(work, out, lambda e: e + [("bundle/bomb.bin", b"\0" * (2 * 1024 * 1024))])
        original_cap = bundle_tool.MAX_BUNDLE_BYTES
        bundle_tool.MAX_BUNDLE_BYTES = 1024 * 1024
        try:
            if bundle_tool.verify(bomb, flux_validator) == 0:
                failures.append("[bundle] verify accepted an archive above the size cap")
        finally:
            bundle_tool.MAX_BUNDLE_BYTES = original_cap

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
        json.loads((REPO / "schema" / "flux-schema-0.3.0.json").read_text()),
        format_checker=FormatChecker(),
    )
    if not list(old_schema.iter_errors(envelope_040("Segment", query="x"))):
        failures.append("[schema] a 0.4.0 document should fail the immutable 0.3.0 schema (fluxVersion window)")
    # additivity (P1): every 0.3.0-pinned document in the example bundle stays
    # valid under the current release — covered by the pristine-bundle check
    # above, asserted here against the old schema too for the reverse direction
    if list(old_schema.iter_errors(envelope("Segment", query="x"))):
        failures.append("[schema] a plain 0.3.0 document should still pass the 0.3.0 schema")

    total = (
        len(CASES_PASS) + len(CASES_REJECT) + 1
        + len(VALIDATOR_REJECTS) + len(VALIDATOR_ROBUSTNESS) + 6
        + 12  # RFC-04: vectors, contract conformance, self-contradiction, 6 broken gates, canonicalisation x3
        + 8   # RFC-09: pack, verify, determinism, profile, merkle x2, tamper, refuse-invalid
        + 6   # RFC-09 prior-art hardening: .sig smuggling, in-toto statement x3, merkle x2
        + 9   # RFC-09 negative fixtures: 6 archive attacks + 2 malformed inputs + size cap
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
