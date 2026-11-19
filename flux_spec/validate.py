#!/usr/bin/env python3
"""FLUX offline reference validator.

Validates FLUX document bundles: every document against the FLUX JSON Schema,
then the cross-document guarantees the schema alone cannot express:

  * every *Ref resolves to a document of the expected kind (no dangling links)
  * document ids are unique within a bundle (across .flux.yml AND .fluid.yml)
  * World.lifecycleMix and Experiment variant weights sum to 1
  * Experiment variant names are unique
  * JourneyTaxonomy transitions and Blueprint edges stay within their node sets
  * Journey.personaReactions keys resolve to Personas; nextState is a state of
    the referenced taxonomy
  * Simulation.timeBounds.start < end
  * skills bindings respect the document's agentPolicy (model allow-list,
    per-skill token budget)
  * every .fluid.yml in the bundle validates against the vendored FLUID schema
    for its declared fluidVersion (referenced or not): a release in
    vendor/fluid/, or a pinned preview in vendor/fluid-preview/
  * the FLUID seam: Simulation.emits[].productRef resolves to a .fluid.yml in
    the bundle, the pinned fluidVersion matches the document's declaration
    (a semver range never selects a preview; only an exact pin does), and
    exposeId is a member of its exposes[]
  * consent strictness at the seam: an emitted contract's expose
    policy.agentPolicy must not allow a use case denied by any ConsentProfile
    gating the Simulation's campaigns, and (when both enumerate allow-lists)
    must not allow more than the profile allows

Cross-document checks run only on documents that passed schema validation, so
malformed input yields error messages, never tracebacks. Unquoted YAML
timestamps are loaded as strings, matching the schema's RFC 3339 grammar.

Usage:
    python3 scripts/validate.py [bundle_dir ...]

With no arguments, validates every directory under examples/.
Runs fully offline: no network, no running engine. Exit code 0 = green.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import rfc8785
    import yaml
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover
    sys.exit("validate.py requires: pip install jsonschema pyyaml rfc8785")

from ._paths import REPO, schema_dir, vendor_fluid_dir, vendor_fluid_preview_dir

FLUX_SCHEMA_PATH = schema_dir() / "flux-schema-latest.json"
FLUID_VENDOR_DIR = vendor_fluid_dir()
FLUID_PREVIEW_DIR = vendor_fluid_preview_dir()

_FLUID_VERSION = re.compile(r"\d+\.\d+\.\d+")


def fluid_schema_file(version: str) -> Path | None:
    """The vendored FLUID schema for *version*: a release, else a preview, else None.

    Releases live in vendor/fluid/, verbatim from FLUID; previews in
    vendor/fluid-preview/, each pinned to a commit and a sha256 (pins.json).
    """
    if not isinstance(version, str) or not _FLUID_VERSION.fullmatch(version):
        return None
    for directory in (FLUID_VENDOR_DIR, FLUID_PREVIEW_DIR):
        candidate = directory / f"fluid-schema-{version}.json"
        if candidate.is_file():
            return candidate
    return None


def _vendored_versions(directory: Path) -> list[str]:
    return sorted(p.stem.replace("fluid-schema-", "") for p in directory.glob("fluid-schema-*.json"))

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
# them are user data, not references. "extensions" (RFC-02) is envelope-level
# and namespace-owned — its contents are never core refs.
FREE_FORM_KEYS = {"payloadTemplate", "config", "demographics", "attributes", "annotations", "labels", "extensions"}

SUM_TOLERANCE = 1e-9

#: The most values one YAML document may write out once its aliases and merge
#: keys are written out. PyYAML builds an alias as a shared reference, so a
#: document of a kilobyte can stand for billions of values, and whatever walks
#: the document or spells a value out pays for every one of them. This is the
#: bound the FLUX engine's read holds a document to, so the validator refuses
#: what the engine refuses. It bounds what a document stands for, not how long
#: its text is: no example document writes out as many as 200.
MAX_YAML_VALUES = 1_000_000

#: The most levels one YAML document may nest, counted through its aliases and
#: merge keys, the document itself being level 1. The engine's bound as well.
MAX_YAML_DEPTH = 64

#: The most characters one YAML document may write out, its aliases and merge keys
#: written out, in the keys and values it holds. A string is one value however
#: long it is, so the bound on values leaves a long string written out through
#: many aliases to cost its length each time: a document of 58 KB held 2,000
#: aliases of one 50,000 character string, and the schema message it raised
#: spelled all of it out. A document that uses no alias writes out no more than
#: its text holds, so only one of this size is refused; no example document
#: writes out as many as 3,000. The size, 64 MiB, is about 64 characters for
#: each of the 1,000,000 values a document may write out. Spelled out in a
#: message a string can take several times its length (a repr escapes what it
#: cannot print), so this bounds what is built to hundreds of MB, and the cap
#: on messages bounds what is kept and printed. The engine's read does not
#: count characters.
MAX_YAML_CHARS = 64 * 1024 * 1024

#: The most mappings the merge keys of one YAML document may name, each counted
#: for every mapping that holds the key. A merge key adds what the mappings it
#: names write out, and naming an empty one adds nothing, yet PyYAML visits each
#: one every time: a thousand mappings that each merge a list of a thousand
#: empty mappings write out about two thousand values and cost a million
#: visits. A mapping that names a non-empty one adds at least two values, so a
#: document within MAX_YAML_VALUES reaches this only by naming empty mappings.
MAX_YAML_MERGED = 1_000_000

#: The most characters one validator message keeps, and the most of the name of
#: the document it is about. A schema message spells out the value it refuses,
#: which can be large even inside the bounds above.
MAX_MESSAGE = 1_000
MAX_NAME = 200

#: The most characters of one line of validator or verify output, past its indent:
#: a name and a message, or what verify says about an archive, whose own names and
#: manifest values it spells out as they come.
MAX_LINE = 2_000

_NOTE = " [... {} characters not shown ...] "


def bounded(text: str, limit: int | None = None) -> str:
    """*text* when it fits in *limit* characters (MAX_MESSAGE), else its start and its end.

    jsonschema writes the value it refuses first and its verdict last
    ("{...} is not of type 'string'"), so keeping only the start would drop the
    part that says what is wrong. Both ends are kept, around a count of the
    characters left out, so the first line still reads. The result is never
    longer than *limit*, and the cost of making it is the limit, however long
    *text* is.
    """
    limit = MAX_MESSAGE if limit is None else limit
    if len(text) <= limit:
        return text
    kept = limit - len(_NOTE.format("")) - len(str(len(text)))   # the note's count has at most as many digits as len(text)
    if kept < 1:
        return text[:limit]
    tail = kept // 4
    head = kept - tail
    return f"{text[:head]}{_NOTE.format(len(text) - kept)}{text[len(text) - tail:]}"


def bounded_line(text: str) -> str:
    """*text* as one line of output: at most MAX_LINE characters, the cap read when this is called."""
    return bounded(text, MAX_LINE)


def canonical_digest(doc) -> str:
    """Content digest for RFC-03 lockfiles and RFC-06 seam provenance.

    sha256 over the RFC 8785 (JCS) canonicalisation. JCS — not merely sorted
    keys — because a digest that two implementations compute differently is
    not a digest: JCS also fixes number spelling (1000.0 and 1000 serialise
    identically) and emits raw UTF-8 rather than backslash-u escapes, which
    `json.dumps` does not.
    """
    import hashlib
    return hashlib.sha256(rfc8785.dumps(doc)).hexdigest()


def semver_satisfies(version: str, rng: str) -> bool:
    """Minimal semver-range check for RFC-03: exact 'x.y.z', caret '^x.y[.z]'
    (same major, >= floor), tilde '~x.y[.z]' (same major.minor, >= floor)."""
    def parse(v):
        parts = v.split(".")
        if len(parts) < 3:
            parts += ["0"] * (3 - len(parts))
        return tuple(int(p) for p in parts[:3])

    try:
        got = parse(version)
        if rng.startswith("^"):
            floor = parse(rng[1:])
            return got[0] == floor[0] and got >= floor
        if rng.startswith("~"):
            floor = parse(rng[1:])
            return got[:2] == floor[:2] and got >= floor
        return got == parse(rng)
    except ValueError:
        return False


_MERGE_TAG = "tag:yaml.org,2002:merge"
_COLLECTIONS = (yaml.MappingNode, yaml.SequenceNode)


class _OutOfBounds(yaml.YAMLError):
    """A document that writes out, or nests, more than a read may build."""


def _where(node) -> str:
    mark = node.start_mark
    return f"(line {mark.line + 1}, column {mark.column + 1})"


def _merged_parts(value_node) -> list:
    """The mappings a merge key's value names: itself, or those of a sequence.

    Anything else is left to the constructor, which refuses it as YAML.
    """
    if isinstance(value_node, yaml.MappingNode):
        return [value_node]
    if isinstance(value_node, yaml.SequenceNode):
        return [part for part in value_node.value if isinstance(part, yaml.MappingNode)]
    return []


class _Measure:
    """What a composed document writes out and how deep it goes, each node measured once.

    PyYAML composes an alias as the node it names, so a composed document is a
    graph that costs what its text costs. Building it is what costs what it
    writes out: a scalar is one value and as many characters as it holds, a
    collection is one value plus what its items (a mapping's keys and values)
    write out, and an alias stands for all of its node wherever it is written.
    A merge key (`<<`) copies the pairs of the mappings it names into the
    mapping that holds it, at that mapping's level, so it adds what those
    mappings write out, less the mappings themselves. The levels are counted
    the same way, the document being level 1. What a merge key's value adds is
    worked out once however many mappings hold the key, so the measure costs
    what the text costs too.

    The measure walks the document with a stack of generators, as PyYAML's own
    constructor does, so how deep a document is, which its text sets, does not
    use the interpreter's stack: every document PyYAML can compose is measured.

    Measuring the composed document before it is constructed is the pattern of
    the FLUX engine's read and of OmegaConf 2.4's loader (a `construct_document`
    hook that counts expanded nodes and refuses an alias that holds itself);
    go-yaml likewise refuses "excessive aliasing" while it decodes.
    """

    def __init__(self) -> None:
        self.values, self.depth, self.merged, self.chars = MAX_YAML_VALUES, MAX_YAML_DEPTH, MAX_YAML_MERGED, MAX_YAML_CHARS
        self.measured: dict[int, tuple[int, int, int]] = {}      # id(node) -> (values, levels, characters)
        self.merges: dict[int, tuple[int, int, int, int]] = {}   # id(a merge key's value) -> (values, levels, characters, mappings)
        self.named = 0                                           # mappings named by the merge keys met so far
        self.on_path: set[int] = set()

    def node(self, root, level: int = 1) -> tuple[int, int, int]:
        """The values, levels and characters *root* writes out, met at *level*; refused past a bound."""
        stack = [self._visit(root, level)]
        result = None
        while stack:
            try:
                call = stack[-1].send(result)
            except StopIteration as done:
                stack.pop()
                result = done.value
            else:
                stack.append(self._visit(*call))
                result = None
        return result

    def _scalar(self, node, level: int) -> tuple[int, int, int]:
        if level > self.depth:
            raise _OutOfBounds(f"a document nests deeper than {self.depth} levels {_where(node)}")
        return 1, 1, len(node.value)

    def _visit(self, node, level: int):
        """Measure *node* met at *level*. A generator: it yields (child, level) for a collection it needs
        measured and is sent that child's (values, levels, characters); it returns its own."""
        if not isinstance(node, _COLLECTIONS):
            return self._scalar(node, level)
        if level > self.depth:
            raise _OutOfBounds(f"a document nests deeper than {self.depth} levels {_where(node)}")
        key = id(node)
        known = self.measured.get(key)
        if known is not None:
            if level + known[1] - 1 > self.depth:
                raise _OutOfBounds(f"a document nests deeper than {self.depth} levels {_where(node)}")
            return known
        if key in self.on_path:
            raise _OutOfBounds(f"a document holds itself through an alias {_where(node)}")
        self.on_path.add(key)
        values, levels, chars = 1, 1, 0
        if isinstance(node, yaml.MappingNode):
            for key_node, value_node in node.value:
                if key_node.tag == _MERGE_TAG:
                    added, merged_levels, added_chars = yield from self._merge(node, value_node, level)
                    values, levels, chars = values + added, max(levels, merged_levels), chars + added_chars
                    continue
                for part in (key_node, value_node):
                    if isinstance(part, _COLLECTIONS):
                        part_values, part_levels, part_chars = yield part, level + 1
                    else:
                        part_values, part_levels, part_chars = self._scalar(part, level + 1)
                    values, levels, chars = values + part_values, max(levels, part_levels + 1), chars + part_chars
        else:
            for item in node.value:
                if isinstance(item, _COLLECTIONS):
                    item_values, item_levels, item_chars = yield item, level + 1
                else:
                    item_values, item_levels, item_chars = self._scalar(item, level + 1)
                values, levels, chars = values + item_values, max(levels, item_levels + 1), chars + item_chars
        self.on_path.discard(key)
        if values > self.values:
            raise _OutOfBounds(
                f"a document writes out more than {self.values} values once its aliases "
                f"and merge keys are written out {_where(node)}")
        if chars > self.chars:
            raise _OutOfBounds(
                f"a document writes out more than {self.chars} characters once its aliases "
                f"and merge keys are written out {_where(node)}")
        self.measured[key] = (values, levels, chars)
        return values, levels, chars

    def _merge(self, host, value_node, level: int):
        """What the mappings named by *value_node*, a merge key's value in *host*, add to *host* at *level*
        (a generator, as `_visit` is): its values, levels and characters."""
        key = id(value_node)
        known = self.merges.get(key)
        if known is None or level + known[1] - 1 > self.depth:
            # The first time, or a mapping too deep from here: measuring them one by one refuses it.
            parts = _merged_parts(value_node)
            added, levels, chars = 0, 0, 0
            for merged in parts:
                merged_values, merged_levels, merged_chars = yield merged, level
                added, levels, chars = added + merged_values - 1, max(levels, merged_levels), chars + merged_chars
            known = self.merges[key] = (added, levels, chars, len(parts))
        self.named += known[3]
        if self.named > self.merged:
            raise _OutOfBounds(
                f"a document names more than {self.merged} mappings in its merge keys {_where(host)}")
        return known[0], known[1], known[2]


class _StringTimestampLoader(yaml.SafeLoader):
    """SafeLoader that keeps unquoted timestamps as plain strings, within bounds.

    PyYAML would otherwise coerce `start: 2026-07-01T00:00:00Z` to a
    datetime object, which the schema (correctly) rejects as "not a string"
    with a confusing Python-typed error message.

    Each document is measured once it is composed and before anything is built
    from it (`_Measure`), since building it is what costs what it writes out.
    """

    def construct_document(self, node):
        _Measure().node(node, 1)
        return super().construct_document(node)


_StringTimestampLoader.add_constructor(
    "tag:yaml.org,2002:timestamp",
    lambda loader, node: loader.construct_scalar(node),
)


def load_yaml_docs(path: Path):
    """Load YAML documents; returns (docs, error_message_or_None).

    The file is read as UTF-8 whatever the host's locale, so every host checks
    the text the FLUX engine reads as UTF-8 and takes its digests over. Read in
    the locale's encoding instead, one file could be two documents: a byte that
    UTF-8 reads inside a comment can end the comment in another encoding, and
    the rest of its line becomes a key the engine never reads. A file that is
    not UTF-8 is reported as unreadable rather than raised, and none of its
    documents is returned, however many decoded before the bad byte.

    A document is held to the bounds the engine's read holds it to, counted as
    its aliases and merge keys are written out: at most MAX_YAML_VALUES values,
    at most MAX_YAML_DEPTH levels, and no alias that holds itself. Its merge
    keys may name at most MAX_YAML_MERGED mappings in all, and it may write out
    at most MAX_YAML_CHARS characters. Past one it is reported as unreadable,
    with its line and column, before anything is built from it, and none of the
    file's documents is returned either.
    """
    try:
        with path.open(encoding="utf-8") as fh:
            docs = list(yaml.load_all(fh, Loader=_StringTimestampLoader))
    except UnicodeDecodeError:
        return [], "unreadable YAML: not UTF-8 text"
    except RecursionError:
        # PyYAML composes a nested collection by recursion, so text nested
        # deeper than the interpreter's recursion limit raises this.
        return [], "unreadable YAML: nested too deeply to read"
    except (yaml.YAMLError, OSError) as exc:
        return [], f"unreadable YAML: {str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__}"
    return [d for d in docs if d is not None], None


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
        self.flux_docs: dict[str, dict] = {}   # schema-VALID flux docs only
        self.fluid_docs: dict[str, tuple[Path, dict]] = {}
        self._fluid_validators: dict[str, Draft202012Validator | None] = {}

    def err(self, source, message):
        self.errors.append(f"{bounded(str(source), MAX_NAME)}: {bounded(message)}")

    # ---- loading ---------------------------------------------------------

    def load(self):
        for path in sorted(self.dir.glob("*.flux.yml")) + sorted(self.dir.glob("*.flux.yaml")):
            docs, load_error = load_yaml_docs(path)
            if load_error:
                self.err(path.name, load_error)
                continue
            for doc in docs:
                if not isinstance(doc, dict):
                    self.err(path.name, f"document is not a mapping (got {type(doc).__name__})")
                    continue
                schema_errors = sorted(self.flux_validator.iter_errors(doc), key=lambda e: e.json_path)
                for e in schema_errors:
                    self.err(path.name, f"schema: {e.json_path}: {e.message}")
                if schema_errors:
                    continue  # cross-checks assume schema-valid shapes
                doc_id = doc["id"]
                if doc_id in self.flux_docs:
                    self.err(path.name, f"duplicate document id '{doc_id}'")
                else:
                    self.flux_docs[doc_id] = doc
        for path in sorted(self.dir.glob("*.fluid.yml")) + sorted(self.dir.glob("*.fluid.yaml")):
            docs, load_error = load_yaml_docs(path)
            if load_error:
                self.err(path.name, load_error)
                continue
            for doc in docs:
                if not isinstance(doc, dict):
                    self.err(path.name, f"document is not a mapping (got {type(doc).__name__})")
                    continue
                doc_id = doc.get("id")
                if not isinstance(doc_id, str):
                    self.err(path.name, "FLUID document has no string 'id'")
                    continue
                if doc_id in self.fluid_docs:
                    self.err(path.name, f"duplicate FLUID document id '{doc_id}'")
                elif doc_id in self.flux_docs:
                    self.err(path.name, f"FLUID document id '{doc_id}' collides with a FLUX document id")
                else:
                    self.fluid_docs[doc_id] = (path, doc)

    def _fluid_validator(self, version):
        if version not in self._fluid_validators:
            schema_file = fluid_schema_file(version)
            self._fluid_validators[version] = (
                Draft202012Validator(json.loads(schema_file.read_text(encoding="utf-8")), format_checker=FormatChecker())
                if schema_file is not None
                else None
            )
        return self._fluid_validators[version]

    # ---- cross-document checks -------------------------------------------

    def check_refs(self):
        for doc_id, doc in self.flux_docs.items():
            refs: list[tuple[str, str, str]] = []
            walk_refs(doc.get("spec", {}), "spec", refs)
            for field, value, path in refs:
                expected_kind = REF_KINDS[field]
                name = value.split("@", 1)[0]  # RFC-03: strip a semver range
                target = self.flux_docs.get(name)
                if target is None:
                    self.err(doc_id, f"dangling reference {path} -> '{name}' (no such document in bundle)")
                elif expected_kind and target.get("kind") != expected_kind:
                    self.err(doc_id, f"{path} -> '{name}' resolves to kind {target.get('kind')}, expected {expected_kind}")

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

    def check_traits(self):
        """RFC-01: categorical levels sum to 1; bounded normal has min < max."""
        for doc_id, doc in self.flux_docs.items():
            if doc.get("kind") != "Persona":
                continue
            for name, trait in (doc.get("spec", {}).get("traits", {}) or {}).items():
                if not isinstance(trait, dict):
                    continue
                if trait.get("dist") == "categorical":
                    total = sum(v for v in trait.get("levels", {}).values() if isinstance(v, (int, float)))
                    if abs(total - 1.0) > SUM_TOLERANCE:
                        self.err(doc_id, f"traits.{name}.levels sums to {total}, expected 1.0")
                elif trait.get("dist") == "normal":
                    lo, hi = trait.get("min"), trait.get("max")
                    if lo is not None and hi is not None and lo >= hi:
                        self.err(doc_id, f"traits.{name}: min {lo} must be below max {hi}")

    def _versioned_refs(self):
        """Yield (doc_id, path, name, range) for every RFC-03 versioned ref."""
        for doc_id, doc in self.flux_docs.items():
            spec = doc.get("spec", {})
            for field in ("moduleRefs", "modules"):
                for i, value in enumerate(spec.get(field, []) or []):
                    if isinstance(value, str) and "@" in value:
                        name, rng = value.split("@", 1)
                        yield doc_id, f"spec.{field}[{i}]", name, rng

    def check_supply_chain(self):
        """RFC-03: every versioned ref resolves through flux.lock to an exact
        version and a content digest of the in-bundle document."""
        versioned = list(self._versioned_refs())
        lock_path = self.dir / "flux.lock"
        if not versioned:
            return
        if not lock_path.exists():
            self.err("flux.lock", "versioned refs are used but the bundle has no flux.lock")
            return
        lock_docs, load_error = load_yaml_docs(lock_path)
        lock = lock_docs[0] if lock_docs and isinstance(lock_docs[0], dict) else None
        if load_error or lock is None:
            self.err("flux.lock", load_error or "lockfile is not a mapping")
            return
        entries = lock.get("modules", {}) if isinstance(lock.get("modules"), dict) else {}
        # Each target is digested once, however many refs name it: a digest costs
        # the target's whole size, and a bundle may hold many short refs to one
        # large document.
        digests: dict[str, str] = {}
        for doc_id, path, name, rng in versioned:
            entry = entries.get(name)
            if not isinstance(entry, dict):
                self.err(doc_id, f"{path}: '{name}@{rng}' has no flux.lock entry")
                continue
            pinned = entry.get("version")
            if not isinstance(pinned, str) or not semver_satisfies(pinned, rng):
                self.err(doc_id, f"{path}: locked version {pinned} does not satisfy range '{rng}'")
            target = self.flux_docs.get(name)
            if target is None:
                continue  # dangling ref already reported by check_refs
            declared = target.get("version")
            if declared != pinned:
                self.err(doc_id, f"{path}: {name} declares version {declared} but flux.lock pins {pinned}")
            digest = entry.get("digest")
            if name not in digests:
                digests[name] = "sha256:" + canonical_digest(target)
            actual = digests[name]
            if digest != actual:
                self.err(doc_id, f"{path}: {name} content digest mismatch — flux.lock has {digest}, bundle has {actual}")

    def check_semantics(self):
        """RFC-07: every semanticRef resolves to a measure declared by a
        Module binding the ossie-model port."""
        measures = set()
        bound = False
        for doc in self.flux_docs.values():
            if doc.get("kind") != "Module":
                continue
            for bind in doc.get("spec", {}).get("binds", []) or []:
                if bind.get("port") == "ossie-model":
                    bound = True
                    for m in (bind.get("config", {}) or {}).get("measures", []) or []:
                        if isinstance(m, str):
                            measures.add(m)
                        elif isinstance(m, dict) and isinstance(m.get("name"), str):
                            measures.add(m["name"])
        for doc_id, doc in self.flux_docs.items():
            if doc.get("kind") != "Experiment":
                continue
            for i, metric in enumerate(doc.get("spec", {}).get("metrics", []) or []):
                sref = metric.get("semanticRef")
                if not sref:
                    continue
                measure = sref.split("/", 1)[1]
                if not bound:
                    self.err(doc_id, f"spec.metrics[{i}].semanticRef '{sref}' used but no Module binds the ossie-model port")
                elif measure not in measures:
                    self.err(doc_id, f"spec.metrics[{i}].semanticRef '{sref}': measure '{measure}' is not declared by the bound semantic model (has: {sorted(measures)})")

    def check_agent_policy(self):
        for doc_id, doc in self.flux_docs.items():
            policy, skills = doc.get("agentPolicy"), doc.get("skills")
            if not skills or not isinstance(policy, dict):
                continue  # schema already enforces skills => agentPolicy
            allowed = set(policy.get("allowedModels", []))
            budget = policy.get("tokenBudget", 0)
            for i, skill in enumerate(skills):
                model = skill.get("model")
                if model and model not in allowed:
                    self.err(doc_id, f"skills[{i}].model '{model}' is not in agentPolicy.allowedModels")
                sb = skill.get("tokenBudget")
                if sb and sb > budget:
                    self.err(doc_id, f"skills[{i}].tokenBudget {sb} exceeds agentPolicy.tokenBudget {budget}")

    def check_fluid_documents(self):
        """Every .fluid.yml in the bundle must be valid FLUID — referenced or not."""
        previews = set(self._preview_fluid_versions())
        for doc_id, (path, doc) in self.fluid_docs.items():
            declared = doc.get("fluidVersion")
            validator = self._fluid_validator(declared) if isinstance(declared, str) else None
            if validator is None:
                self.err(path.name, f"declared fluidVersion '{declared}' has no vendored schema in vendor/fluid/ or vendor/fluid-preview/")
                continue
            label = f"{declared} (preview)" if declared in previews else declared
            for e in sorted(validator.iter_errors(doc), key=lambda e: e.json_path)[:10]:
                self.err(path.name, f"fails FLUID {label}: {e.json_path}: {e.message}")

    def _vendored_fluid_versions(self):
        """The vendored FLUID releases: the set a semver range resolves against."""
        return _vendored_versions(FLUID_VENDOR_DIR)

    def _preview_fluid_versions(self):
        """The vendored FLUID previews: only an exact pin selects one. A version
        vendored as a release too is a release, as in fluid_schema_file."""
        releases = set(self._vendored_fluid_versions())
        return [v for v in _vendored_versions(FLUID_PREVIEW_DIR) if v not in releases]

    def check_fluid_seam(self):
        for doc_id, doc in self.flux_docs.items():
            if doc.get("kind") != "Simulation":
                continue
            gating_profiles = self._gating_consent_profiles(doc)
            for i, emit in enumerate(doc.get("spec", {}).get("emits", [])):
                where = f"spec.emits[{i}]"
                product_ref, expose_id = emit.get("productRef"), emit.get("exposeId")
                fluid_version = emit.get("fluidVersion")
                entry = self.fluid_docs.get(product_ref)
                if entry is None:
                    self.err(doc_id, f"{where}.productRef '{product_ref}' does not resolve to a .fluid.yml document in the bundle")
                    continue
                fluid_path, fluid_doc = entry
                declared = fluid_doc.get("fluidVersion")
                if isinstance(fluid_version, str) and fluid_version[:1] in "^~":
                    # RFC-06: a semver range, resolved against the vendored
                    # releases. A preview is not one of them: as with a
                    # prerelease under node-semver, only an exact pin selects it.
                    rng = fluid_version
                    if not any(semver_satisfies(v, rng) for v in self._vendored_fluid_versions()):
                        self.err(doc_id, f"{where}: no vendored FLUID version satisfies range '{rng}' (vendored: {self._vendored_fluid_versions()})")
                    if declared in self._preview_fluid_versions():
                        self.err(doc_id, f"{where}: {fluid_path.name} declares FLUID {declared}, a preview, and a range never selects a preview: pin fluidVersion \"{declared}\" exactly to opt in")
                    elif not (isinstance(declared, str) and semver_satisfies(declared, rng)):
                        self.err(doc_id, f"{where}: {fluid_path.name} declares fluidVersion {declared}, which does not satisfy the pinned range '{rng}'")
                elif declared != fluid_version:
                    self.err(doc_id, f"{where}: pinned fluidVersion {fluid_version} but {fluid_path.name} declares {declared}")
                # RFC-06: provenance — the proven contract bytes are the shipped bytes
                provenance = emit.get("provenance") or {}
                contract_digest = provenance.get("contractDigest")
                if contract_digest:
                    actual = "sha256:" + canonical_digest(fluid_doc)
                    if contract_digest != actual:
                        self.err(doc_id, f"{where}: provenance.contractDigest mismatch — declared {contract_digest}, bundle contract is {actual}")
                # RFC-05: seam gate on the twin's own credibility
                min_credibility = emit.get("minCredibility")
                if min_credibility is not None:
                    self._check_seam_credibility(doc_id, where, doc, min_credibility)
                exposes = [e for e in fluid_doc.get("exposes", []) if isinstance(e, dict)]
                expose = next((e for e in exposes if e.get("exposeId") == expose_id), None)
                if expose is None:
                    self.err(doc_id, f"{where}.exposeId '{expose_id}' is not an expose of {product_ref} (has: {[e.get('exposeId') for e in exposes]})")
                    continue
                self._check_consent_strictness(doc_id, where, expose, gating_profiles)

    def _check_seam_credibility(self, doc_id, where, sim_doc, min_credibility):
        """RFC-05: a Playback scorecard calibrating this Simulation's world must
        report at least the required credibility."""
        world_ref = sim_doc.get("spec", {}).get("worldRef", "").split("@", 1)[0]
        scores = [
            p.get("spec", {}).get("scorecard", {}).get("credibility")
            for p in self.flux_docs.values()
            if p.get("kind") == "Playback"
            and p.get("spec", {}).get("worldRef") == world_ref
            and isinstance(p.get("spec", {}).get("scorecard"), dict)
        ]
        scores = [c for c in scores if isinstance(c, (int, float))]
        if not scores:
            self.err(doc_id, f"{where}: minCredibility {min_credibility} set but no Playback scorecard calibrates world '{world_ref}'")
        elif max(scores) < min_credibility:
            self.err(doc_id, f"{where}: twin credibility {max(scores)} is below the required minCredibility {min_credibility}")

    def _gating_consent_profiles(self, sim_doc):
        """ConsentProfiles gating this Simulation via campaignRefs -> Campaign.consentRef."""
        profiles = []
        for campaign_ref in sim_doc.get("spec", {}).get("campaignRefs", []) or []:
            campaign = self.flux_docs.get(campaign_ref)
            if not campaign or campaign.get("kind") != "Campaign":
                continue
            profile = self.flux_docs.get(campaign.get("spec", {}).get("consentRef", ""))
            if profile and profile.get("kind") == "ConsentProfile":
                profiles.append(profile)
        return profiles

    def _check_consent_strictness(self, doc_id, where, expose, profiles):
        """The emitted contract must be at least as strict as every gating ConsentProfile."""
        policy = expose.get("policy", {}).get("agentPolicy", {}) if isinstance(expose.get("policy"), dict) else {}
        contract_allowed = set(policy.get("allowedUseCases", []) or [])
        for profile in profiles:
            pid, pspec = profile.get("id"), profile.get("spec", {})
            denied = set(pspec.get("deniedUseCases", []) or [])
            violation = contract_allowed & denied
            if violation:
                self.err(doc_id, f"{where}: contract allows use cases denied by ConsentProfile {pid}: {sorted(violation)}")
            profile_allowed = set(pspec.get("allowedUseCases", []) or [])
            if profile_allowed and contract_allowed and not contract_allowed <= profile_allowed:
                extra = contract_allowed - profile_allowed
                self.err(doc_id, f"{where}: contract allows use cases outside ConsentProfile {pid}'s allow-list: {sorted(extra)}")

    def run(self) -> list[str]:
        if not self.dir.is_dir():
            self.err(str(self.dir), "bundle directory does not exist or is not a directory")
            return self.errors
        self.load()
        if not self.flux_docs and not self.errors:
            self.err(str(self.dir), "bundle contains no .flux.yml documents")
        self.check_refs()
        self.check_sums_and_sets()
        self.check_traits()
        self.check_supply_chain()
        self.check_semantics()
        self.check_agent_policy()
        self.check_fluid_documents()
        self.check_fluid_seam()
        return self.errors


def main(argv: list[str]) -> int:
    flux_schema = json.loads(FLUX_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(flux_schema)
    flux_validator = Draft202012Validator(flux_schema, format_checker=FormatChecker())

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
            print(f"       {bounded_line(e)}")
        failed = failed or bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
