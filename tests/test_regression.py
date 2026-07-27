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
import json
import shutil
import sys
import tempfile
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from validate import Bundle  # noqa: E402

SCHEMA = json.loads((REPO / "schema" / "flux-schema-0.3.0.json").read_text())
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

CASES_PASS = {
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
}


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

    total = (
        len(CASES_PASS) + len(CASES_REJECT) + 1
        + len(VALIDATOR_REJECTS) + len(VALIDATOR_ROBUSTNESS) + 4
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
