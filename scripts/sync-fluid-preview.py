#!/usr/bin/env python3
"""Re-create the vendored FLUID preview schemas from their pins.

FLUX vendors FLUID releases under vendor/fluid/, verbatim from FLUID's
published schemas, and a FLUID version that is still a preview under
vendor/fluid-preview/ (VERSIONING.md, "FLUID previews"). A preview is not
published as a release yet, so it is copied from the repository where FLUID's
schema is written, at one pinned commit. vendor/fluid-preview/pins.json records,
for each preview file, that repository, the path in it, the full commit and the
sha256 of the bytes.

This script fetches each file at its pinned commit, checks the bytes against the
pinned sha256, and writes them. CI runs it and then `git diff --exit-code
vendor/fluid-preview`, so a copy that differs from its pin fails the build. Same
pattern as scripts/sync-engine-docs.sh: a full 40-character commit, never a
branch, because a moving pin is no pin. The digest names the bytes as well as
where they come from, as Bazel's http_file sha256 does.

Usage:
    python3 scripts/sync-fluid-preview.py
        re-create every preview from its pin
    python3 scripts/sync-fluid-preview.py --repin VERSION COMMIT
        move the pin of the preview of FLUID VERSION to COMMIT (a full commit of
        the same repository), then re-create it; commit the result in a
        flux-spec PR with a schema-diff note

FLUID_PREVIEW_SOURCE=/path/to/clone reads the file from a local clone of the
pinned repository (`git show COMMIT:PATH`) instead of downloading it.

Stdlib only. After a change, run scripts/sync-package-data.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PREVIEW_DIR = REPO / "vendor" / "fluid-preview"
PINS_PATH = PREVIEW_DIR / "pins.json"

#: The keys of one pin, in the order pins.json writes them.
PIN_FIELDS = ("file", "fluidVersion", "repository", "path", "commit", "sha256")

_FILE = re.compile(r"^fluid-schema-(\d+\.\d+\.\d+)\.json$")
_REPOSITORY = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")
_PATH = re.compile(r"^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

#: A FLUID schema is a few hundred kilobytes; anything far larger is not one.
MAX_BYTES = 16 * 1024 * 1024
TIMEOUT_SECONDS = 60


class PinError(ValueError):
    """A pin that does not name one immutable file."""


class FetchError(RuntimeError):
    """The pinned file could not be read at its pinned commit."""


def check_pin(pin: object) -> dict:
    """Return *pin* when it names exactly one immutable file, else raise PinError."""
    if not isinstance(pin, dict):
        raise PinError(f"a pin is an object with the keys {list(PIN_FIELDS)}, not {type(pin).__name__}")
    keys = set(pin)
    if keys != set(PIN_FIELDS):
        missing, extra = sorted(set(PIN_FIELDS) - keys), sorted(keys - set(PIN_FIELDS))
        raise PinError(f"pin keys must be exactly {list(PIN_FIELDS)} (missing {missing}, unknown {extra})")
    for key in PIN_FIELDS:
        if not isinstance(pin[key], str):
            raise PinError(f"pin {key!r} must be a string")
    name = pin["file"]
    match = _FILE.match(name)
    if not match:
        raise PinError(f"pin file {name!r} is not named fluid-schema-X.Y.Z.json")
    if match.group(1) != pin["fluidVersion"]:
        raise PinError(f"pin file {name!r} does not hold FLUID {pin['fluidVersion']}")
    if not _REPOSITORY.match(pin["repository"]):
        raise PinError(f"pin repository {pin['repository']!r} is not https://github.com/OWNER/REPO")
    path = pin["path"]
    if not _PATH.match(path) or any(part in (".", "..") for part in path.split("/")):
        raise PinError(f"pin path {path!r} is not a plain relative path inside the repository")
    if path.rsplit("/", 1)[-1] != name:
        raise PinError(f"pin path {path!r} does not end in the vendored file name {name!r}")
    if not _COMMIT.match(pin["commit"]):
        raise PinError(
            f"pin commit {pin['commit']!r} is not a full 40-character commit: "
            "a branch, a tag or a short commit can move, and a moving pin is no pin"
        )
    if not _SHA256.match(pin["sha256"]):
        raise PinError(f"pin sha256 {pin['sha256']!r} is not 64 lowercase hex digits")
    return pin


def load_pins(path: Path = PINS_PATH) -> list[dict]:
    """Every pin in *path*, checked: one per file and one per FLUID version."""
    document = json.loads(path.read_text(encoding="utf-8"))
    previews = document.get("previews") if isinstance(document, dict) else None
    if not isinstance(previews, list):
        raise PinError(f"{path.name} has no 'previews' list")
    pins = [check_pin(pin) for pin in previews]
    for field in ("file", "fluidVersion"):
        values = [pin[field] for pin in pins]
        if len(values) != len(set(values)):
            raise PinError(f"{path.name} pins one {field} more than once")
    return pins


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(pin: dict) -> bytes:
    """The bytes of the pinned file at the pinned commit."""
    source = os.environ.get("FLUID_PREVIEW_SOURCE")
    if source:
        result = subprocess.run(
            ["git", "-C", source, "show", f"{pin['commit']}:{pin['path']}"],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            message = result.stderr.decode("utf-8", "replace").strip()
            raise FetchError(f"{source} cannot show {pin['commit']}:{pin['path']}: {message}")
        return result.stdout
    owner, name = _REPOSITORY.match(pin["repository"]).groups()
    url = f"https://raw.githubusercontent.com/{owner}/{name}/{pin['commit']}/{pin['path']}"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310 (https only)
            data = response.read(MAX_BYTES + 1)
    except (urllib.error.URLError, OSError) as exc:
        raise FetchError(f"cannot fetch {url}: {exc}") from exc
    if len(data) > MAX_BYTES:
        raise FetchError(f"{url} is larger than {MAX_BYTES} bytes, which no FLUID schema is")
    return data


def _unpinned_files(pins: list[dict]) -> list[str]:
    pinned = {pin["file"] for pin in pins}
    return sorted(p.name for p in PREVIEW_DIR.glob("fluid-schema-*.json") if p.name not in pinned)


def sync(pins: list[dict]) -> int:
    status = 0
    for pin in pins:
        data = fetch(pin)
        digest = sha256_hex(data)
        where = f"{pin['repository']} {pin['path']} at {pin['commit']}"
        if digest != pin["sha256"]:
            print(
                f"REFUSED: {where} has sha256 {digest}, but pins.json pins {pin['sha256']}. "
                "The pin does not name these bytes: re-pin with --repin, or correct the digest.",
                file=sys.stderr,
            )
            status = 1
            continue
        (PREVIEW_DIR / pin["file"]).write_bytes(data)
        print(f"[sync-fluid-preview] vendor/fluid-preview/{pin['file']} <- {where} (sha256 {digest})")
    for name in _unpinned_files(pins):
        print(f"REFUSED: vendor/fluid-preview/{name} has no pin in pins.json: pin it or remove it", file=sys.stderr)
        status = 1
    return status


def repin(pins: list[dict], version: str, commit: str) -> int:
    matches = [pin for pin in pins if pin["fluidVersion"] == version]
    if not matches:
        print(f"REFUSED: no preview of FLUID {version} is pinned in pins.json", file=sys.stderr)
        return 2
    candidate = check_pin({**matches[0], "commit": commit})
    data = fetch(candidate)
    candidate["sha256"] = sha256_hex(data)
    (PREVIEW_DIR / candidate["file"]).write_bytes(data)
    updated = [candidate if pin is matches[0] else pin for pin in pins]
    document = json.loads(PINS_PATH.read_text(encoding="utf-8"))
    document["previews"] = [{key: pin[key] for key in PIN_FIELDS} for pin in updated]
    PINS_PATH.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(
        f"[sync-fluid-preview] FLUID {version} re-pinned to {commit} (sha256 {candidate['sha256']}). "
        "Next: python3 scripts/sync-package-data.py, and a schema-diff note in the flux-spec PR."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Re-create the vendored FLUID previews from their pins.")
    parser.add_argument("--repin", nargs=2, metavar=("VERSION", "COMMIT"), help="move one preview's pin to COMMIT")
    args = parser.parse_args(argv)
    try:
        pins = load_pins()
        if args.repin:
            return repin(pins, *args.repin)
        return sync(pins)
    except (PinError, FetchError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
