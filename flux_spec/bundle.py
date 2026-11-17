#!/usr/bin/env python3
"""FLUX evidence bundles (RFC-09).

Turns a validated bundle directory into a portable, verifiable artifact:

    python3 scripts/bundle.py pack   examples/telco-payment-recovery -o dist/
    python3 scripts/bundle.py verify dist/telco-payment-recovery.flux.tgz

`pack` validates the bundle offline, writes `flux-manifest.json` (per-file
sha256, an RFC 6962 Merkle root, and an attestation of what the toolchain
could prove), emits a **deterministic** gzip archive, and writes an in-toto
Statement v1 for supply-chain tooling.

Determinism follows the reproducible-builds.org recipe: entries sorted by
name, mtime zeroed in both the tar entries and the gzip header, ownership
normalised to 0/0 with empty names, fixed mode, GNU format (PAX extended
headers can smuggle atime/ctime). Same inputs, same bytes — so two parties
can compare bundles by digest alone.

`verify` re-derives every digest and the Merkle root, re-validates the
documents against the schema the manifest names, and checks the attestation
against reality. That schema must be inside this toolchain's compatibility
window, so a pack made by an earlier release in the window still verifies
after an upgrade. It needs nothing from the author: no engine, no network, no
trust in the packer.

Signing is deliberately transport-agnostic and detached: sign the manifest
bytes with whatever your organisation already uses —

    ssh-keygen -Y sign -f ~/.ssh/id_ed25519 -n flux flux-manifest.json
    cosign sign-blob --key cosign.key flux-manifest.json
    openssl dgst -sha256 -sign key.pem -out flux-manifest.sig flux-manifest.json

— and ship the signature alongside. Because the manifest commits to the
Merkle root, a signature over the manifest covers every byte of the bundle.

Profiles: an offline bundler may attest `core` (validator green) or
`enterprise` (validator green plus a Playback scorecard). It never attests
`runtime` — Level 3 requires a live engine, so claiming it from a packer
would be a lie.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

from .validate import Bundle, load_yaml_docs
from ._paths import REPO, schema_dir

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


class _Rejected(Exception):
    """Internal: stop verifying, the problem list already says why."""

SCHEMA_PATH = schema_dir() / "flux-schema-latest.json"
MANIFEST_SCHEMA_PATH = schema_dir() / "flux-manifest-0.5.0.json"
MANIFEST_NAME = "flux-manifest.json"
STATEMENT_SUFFIX = ".attestation.json"
PREDICATE_TYPE = "https://agenticstiger.github.io/flux/attestation/v1"
GENERATOR = "flux bundle 0.5.0"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def accepted_schemas() -> dict[str, tuple[str, Path]]:
    """The schemas `verify` re-validates a pack against: `$id` -> (version, file).

    One per version in this toolchain's compatibility window, the `fluxVersion`
    enum of the current schema (VERSIONING.md). The window is read from that
    file rather than restated here, so a release that widens or resets it moves
    what `verify` accepts with no edit to this module. Every released schema
    ships with the package, immutable, so each version resolves to the file its
    packs were validated against.

    The lookup is keyed on the exact `$id` a manifest declares, the way
    sigstore-python's `Bundle` accepts a closed set of bundle media types: an
    id outside the set is refused, never mapped to the newest schema.
    """
    window = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["properties"]["fluxVersion"]["enum"]
    accepted = {}
    for version in window:
        path = schema_dir() / f"flux-schema-{version}.json"
        schema_id = json.loads(path.read_text(encoding="utf-8")).get("$id") if path.is_file() else None
        if schema_id:
            accepted[schema_id] = (version, path)
    return accepted


def _schema_named(schema_id: str) -> tuple[Path | None, str]:
    """The schema file a manifest's *schema_id* names, or None and the refusal."""
    accepted = accepted_schemas()
    if schema_id in accepted:
        return accepted[schema_id][1], ""
    window = ", ".join(version for version, _ in accepted.values())
    return None, (f"schemaId {schema_id} is not a FLUX schema inside this toolchain's compatibility "
                  f"window (FLUX {window}); verify the pack with a flux-spec release whose window includes it")


def _validator_for(schema_path: Path, given) -> Draft202012Validator:
    """A validator for the schema in *schema_path*: *given* when it was built
    from that schema (same `$id`), else a new one with format checking."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    given_schema = getattr(given, "schema", None)
    if isinstance(given_schema, dict) and given_schema.get("$id") == schema.get("$id"):
        return given
    return Draft202012Validator(schema, format_checker=FormatChecker())


def merkle_root(files: dict[str, str]) -> str:
    """Root over sorted (path, digest) pairs.

    Domain separation follows RFC 6962 (Certificate Transparency): leaves are
    hashed with a 0x00 prefix and interior nodes with 0x01, so an interior
    hash can never be replayed as a leaf (the Merkle second-preimage attack).
    An odd node is promoted unchanged.

    One deliberate divergence from RFC 6962: the leaf commits to
    `path\\0digest`, not to the file bytes alone. A manifest must bind *which*
    file has which digest — without the path in the leaf, swapping the
    contents of two manifested files would leave the root unchanged.

    Paths are sorted by Unicode code point (Python's default), which is
    locale-independent — unlike shell `sort`, a known reproducibility trap.
    """
    LEAF, NODE = b"\x00", b"\x01"
    level = [
        hashlib.sha256(LEAF + path.encode() + b"\x00" + bytes.fromhex(digest.split(":", 1)[1])).digest()
        for path, digest in sorted(files.items())
    ]
    if not level:
        return "sha256:" + hashlib.sha256(LEAF).hexdigest()
    while len(level) > 1:
        level = [
            hashlib.sha256(NODE + level[i] + level[i + 1]).digest() if i + 1 < len(level) else level[i]
            for i in range(0, len(level), 2)
        ]
    return "sha256:" + level[0].hex()


def intoto_statement(archive: Path, manifest: dict) -> dict:
    """The attestation as an in-toto Statement v1 (in-toto.io/Statement/v1).

    The manifest is the bundle's *internal* integrity structure; this is the
    *interop* artifact. Shaping it as an in-toto Statement means existing
    supply-chain tooling — cosign, in-toto-verify, anything that speaks DSSE —
    can carry, sign and verify FLUX evidence without knowing what FLUX is:

        cosign attest-blob --predicate flux-attestation.json \\
          --type https://agenticstiger.github.io/flux/attestation/v1 <archive>

    Note in-toto digests are bare hex keyed by algorithm, not the `sha256:`
    prefixed form used inside the FLUX manifest.
    """
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": archive.name, "digest": {"sha256": sha256_file(archive)}}],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "schemaId": manifest["schemaId"],
            "fluxVersions": manifest["fluxVersions"],
            "merkleRoot": manifest["merkleRoot"],
            "fileCount": len(manifest["files"]),
            **manifest["attestation"],
        },
    }


def bundle_files(directory: Path, skip_signatures: bool = True) -> dict[str, str]:
    """Digest every file in the bundle.

    The manifest is always excluded — it cannot contain its own digest.
    Detached signatures are excluded while *packing* (they belong beside the
    archive, not inside it), but never while *verifying*: an unmanifested
    file must be reported no matter what it is called, or `evil.sig` becomes
    a place to smuggle content past the digest check.
    """
    out = {}
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        rel = path.relative_to(directory).as_posix()
        if rel == MANIFEST_NAME or (skip_signatures and rel.endswith(".sig")):
            continue
        out[rel] = "sha256:" + sha256_file(path)
    return out


def _symlink_entries(directory: Path) -> list[str]:
    """Every symlink in the bundle tree, as refusal messages. Empty means clean.

    `bundle_files` reads through a link (`is_file()` follows it), so packing
    one would archive its target's bytes: anything the packing process can
    read, an ssh key or a .env, becomes content of a signed, distributed
    artifact. `verify` refuses links inside an archive (`_extract_safely`),
    and flux-engine refuses them before it packs; this is the same guard on
    `pack`'s way in, with the message shape of both. `rglob` lists a linked
    directory without descending into it.
    """
    return [
        f"unsupported bundle entry (symlink): {path.relative_to(directory).as_posix()}"
        for path in sorted(directory.rglob("*")) if path.is_symlink()
    ]


def collect_attestation(directory: Path, validator) -> tuple[dict, list[str]]:
    """Validate the bundle and describe what can honestly be attested."""
    b = Bundle(directory, validator)
    errors = b.run()
    if errors:
        return {}, errors

    scorecards, seam, versions = [], [], set()
    for doc_id, doc in b.flux_docs.items():
        versions.add(doc.get("fluxVersion"))
        spec = doc.get("spec", {})
        if doc.get("kind") == "Playback" and isinstance(spec.get("scorecard"), dict):
            sc = spec["scorecard"]
            scorecards.append({"playbackId": doc_id, "grade": sc["grade"], "credibility": sc["credibility"]})
        if doc.get("kind") == "Simulation":
            for emit in spec.get("emits", []):
                entry = {
                    "simulationId": doc_id,
                    "productRef": emit["productRef"],
                    "exposeId": emit["exposeId"],
                    "fluidVersion": emit["fluidVersion"],
                }
                digest = (emit.get("provenance") or {}).get("contractDigest")
                if digest:
                    entry["contractDigest"] = digest
                seam.append(entry)

    attestation = {
        "profile": "enterprise" if scorecards else "core",
        "validator": {"status": "green", "documents": len(b.flux_docs)},
    }
    if scorecards:
        attestation["scorecards"] = sorted(scorecards, key=lambda s: s["playbackId"])
    if seam:
        attestation["seam"] = seam
    return {"attestation": attestation, "fluxVersions": sorted(v for v in versions if v)}, []


def build_manifest(directory: Path, validator) -> tuple[dict, list[str]]:
    extra, errors = collect_attestation(directory, validator)
    if errors:
        return {}, errors
    files = bundle_files(directory)
    schema_id = json.loads(SCHEMA_PATH.read_text())["$id"]
    manifest = {
        "manifestVersion": 1,
        "generator": GENERATOR,
        "schemaId": schema_id,
        "fluxVersions": extra["fluxVersions"],
        "files": files,
        "merkleRoot": merkle_root(files),
        "attestation": extra["attestation"],
    }
    return manifest, []


def _write_manifest(path: Path, manifest: dict) -> None:
    """Write *manifest* to *path*, never through a link planted there: with
    O_NOFOLLOW the open fails on a symlink instead of truncating its target.
    `pack` refuses links before this point; this holds if one appears later.
    A new manifest is owner-only: the packing user signs it, and its entry in
    the archive carries the archive's own fixed mode."""
    nofollow = getattr(os, "O_NOFOLLOW", 0)    # POSIX; elsewhere the pack-time refusal stands alone
    with open(path, "w", encoding="utf-8", opener=lambda p, flags: os.open(p, flags | nofollow, 0o600)) as fh:
        fh.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def _deterministic_info(name: str, size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mtime = 0            # zeroed: same inputs -> same bytes
    info.mode = 0o644
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    return info


def pack(directory: Path, out_dir: Path, validator) -> int:
    directory = directory.resolve()          # `pack .` must not become a nameless archive
    if not directory.name:
        print(f"[FAIL] {directory}: cannot determine a bundle name")
        return 1
    links = _symlink_entries(directory)        # before anything reads through one
    if links:
        print(f"[FAIL] {directory}: a pack holds regular files only; replace each link with a copy of its file")
        for link in links[:10]:
            print(f"       {link}")
        return 1
    manifest, errors = build_manifest(directory, validator)
    if errors:
        print(f"[FAIL] {directory}: bundle does not validate — refusing to pack")
        for e in errors[:10]:
            print(f"       {e}")
        return 1
    Draft202012Validator(json.loads(MANIFEST_SCHEMA_PATH.read_text())).validate(manifest)

    try:
        _write_manifest(directory / MANIFEST_NAME, manifest)
    except OSError as exc:
        print(f"[FAIL] {directory}: cannot write {MANIFEST_NAME}: {exc.strerror or exc}")
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"{directory.name}.flux.tgz"

    payload = dict(manifest["files"])
    payload[MANIFEST_NAME] = "sha256:" + sha256_file(directory / MANIFEST_NAME)
    raw = io.BytesIO()
    # GNU format, not PAX: reproducible-builds.org warns PAX extended headers
    # can carry atime/ctime (and PIDs under POSIXLY_CORRECT).
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.GNU_FORMAT) as tar:
        for rel in sorted(payload):
            data = (directory / rel).read_bytes()
            tar.addfile(_deterministic_info(f"{directory.name}/{rel}", len(data)), io.BytesIO(data))
    # gzip separately with mtime=0 — the gzip header carries its own timestamp,
    # which would otherwise make every repack a different file.
    with open(archive, "wb") as fh:
        with gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=fh, mtime=0) as gz:
            gz.write(raw.getvalue())

    statement = intoto_statement(archive, manifest)
    statement_path = out_dir / f"{directory.name}{STATEMENT_SUFFIX}"
    statement_path.write_text(json.dumps(statement, indent=2, sort_keys=True) + "\n")

    print(f"[ok] packed {archive}")
    print(f"     profile={manifest['attestation']['profile']} "
          f"documents={manifest['attestation']['validator']['documents']} "
          f"files={len(manifest['files'])}")
    print(f"     merkleRoot={manifest['merkleRoot']}")
    print(f"     archive sha256:{sha256_file(archive)}")
    print(f"     in-toto statement: {statement_path}")
    print(f"     sign it: ssh-keygen -Y sign -f <key> -n flux {directory / MANIFEST_NAME}")
    print(f"          or: cosign attest-blob --predicate {statement_path} --type {PREDICATE_TYPE} {archive}")
    return 0


MAX_BUNDLE_BYTES = 256 * 1024 * 1024   # declared, uncompressed, across all members
MAX_MEMBERS = 10_000
COPY_CHUNK = 1 << 20


def _extract_safely(tar: tarfile.TarFile, root: Path, problems: list[str]) -> Path | None:
    """Materialise a verified-safe subset of the archive under `root`.

    Everything hostile is rejected *before* anything is written: attacker-declared
    sizes are budgeted first (gzip compresses zeros ~1000:1, so a 500 KB archive
    can otherwise claim gigabytes), only regular files are extracted, and every
    member must live under one shared top-level directory — a member outside it
    would be extracted but never digested, which is exactly how undeclared
    content sneaks past a manifest.
    """
    members = tar.getmembers()
    if len(members) > MAX_MEMBERS:
        problems.append(f"archive declares {len(members)} members, above the {MAX_MEMBERS} cap")
        return None
    declared = sum(m.size for m in members if m.isfile())
    if declared > MAX_BUNDLE_BYTES:
        problems.append(f"archive declares {declared} uncompressed bytes, above the {MAX_BUNDLE_BYTES} cap")
        return None

    tops = set()
    for m in members:
        name = Path(m.name)
        if name.is_absolute() or ".." in name.parts or not name.parts:
            problems.append(f"unsafe archive path: {m.name}")
            return None
        tops.add(name.parts[0])
    if len(tops) != 1:
        problems.append(f"expected exactly one bundle directory, found {sorted(tops) or 'none'}")
        return None

    for m in members:
        if m.isdir():
            continue
        if not m.isfile():
            problems.append(f"unsupported archive entry ({'symlink' if m.issym() or m.islnk() else 'special'}): {m.name}")
            return None
        if len(Path(m.name).parts) < 2:
            problems.append(f"entry outside the bundle directory: {m.name}")
            return None
        target = root / m.name
        if target.exists():
            problems.append(f"duplicate archive entry: {m.name}")
            return None
        target.parent.mkdir(parents=True, exist_ok=True)
        source = tar.extractfile(m)
        if source is None:
            problems.append(f"unreadable archive entry: {m.name}")
            return None
        with open(target, "wb") as fh:
            shutil.copyfileobj(source, fh, COPY_CHUNK)
    return root / tops.pop()


def verify(archive: Path, validator=None) -> int:
    """Verify an archive offline. Always reports; never raises.

    The documents are re-validated against the schema the manifest names, with
    *validator* when it was built from that schema, else from the schema's file.
    """
    problems: list[str] = []
    manifest = {}
    schema_file = None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with tarfile.open(archive, "r:gz") as tar:
                directory = _extract_safely(tar, root, problems)
            if directory is None:
                raise _Rejected()

            manifest_path = directory / MANIFEST_NAME
            if not manifest_path.exists():
                problems.append(f"no {MANIFEST_NAME}")
                raise _Rejected()
            manifest = json.loads(manifest_path.read_text())
            Draft202012Validator(json.loads(MANIFEST_SCHEMA_PATH.read_text())).validate(manifest)

            actual = bundle_files(directory, skip_signatures=False)
            for rel, digest in manifest["files"].items():
                if rel not in actual:
                    problems.append(f"missing file: {rel}")
                elif actual[rel] != digest:
                    problems.append(f"digest mismatch: {rel}")
            for rel in actual:
                if rel not in manifest["files"]:
                    problems.append(f"unmanifested file: {rel}")
            if merkle_root(manifest["files"]) != manifest["merkleRoot"]:
                problems.append("merkleRoot does not match the manifest file list")

            # Everything the manifest asserts is re-derived, never trusted. The
            # schemaId only picks the schema to re-validate against, inside the window.
            schema_file, refusal = _schema_named(manifest["schemaId"])
            if schema_file is None:
                problems.append(refusal)
                raise _Rejected()
            rebuilt, errors = collect_attestation(directory, _validator_for(schema_file, validator))
            if errors:
                problems.append(f"bundle no longer validates against {schema_file.name} ({len(errors)} errors, first: {errors[0]})")
            else:
                if rebuilt["attestation"] != manifest["attestation"]:
                    problems.append("attestation does not match a fresh validation of the bundle")
                if rebuilt["fluxVersions"] != manifest["fluxVersions"]:
                    problems.append(f"fluxVersions {manifest['fluxVersions']} does not match the documents ({rebuilt['fluxVersions']})")
    except _Rejected:
        pass
    except tarfile.ReadError as exc:
        problems.append(f"not a readable gzip archive: {exc}")
    except json.JSONDecodeError as exc:
        problems.append(f"{MANIFEST_NAME} is not valid JSON: {exc}")
    except ValidationError as exc:
        problems.append(f"{MANIFEST_NAME} violates the manifest schema: {exc.message}")
    except OSError as exc:
        problems.append(f"cannot read archive: {exc}")

    if problems:
        print(f"[FAIL] {archive}")
        for p in problems[:10]:
            print(f"       {p}")
        return 1
    print(f"[ok] {archive} — {len(manifest['files'])} files, merkle root verified, "
          f"attestation reproduced (profile={manifest['attestation']['profile']})")
    print(f"     re-validated against {schema_file.name}, the schema the manifest names")
    print(f"     verify the signature separately, e.g. ssh-keygen -Y verify ... < {MANIFEST_NAME}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="FLUX evidence bundles (RFC-09)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack", help="validate, manifest and archive a bundle")
    p.add_argument("directory", type=Path)
    p.add_argument("-o", "--out", type=Path, default=REPO / "dist")
    v = sub.add_parser("verify", help="verify an archive offline")
    v.add_argument("archive", type=Path)
    args = ap.parse_args(argv)

    validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text()), format_checker=FormatChecker())
    if args.cmd == "pack":
        return pack(args.directory, args.out, validator)
    return verify(args.archive, validator)


if __name__ == "__main__":
    raise SystemExit(main())
