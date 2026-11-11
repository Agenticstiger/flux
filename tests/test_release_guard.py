#!/usr/bin/env python3
"""The release guard in .github/workflows/release.yml, run against small fake trees.

Nothing else exercises that guard before a tag is pushed, so a mistake in it would
show up on release day. This pulls the python heredoc out of the workflow and runs it
in a scratch tree, once per case: the tags it must accept (a specification release
`vX.Y.Z`, and a post-release `vX.Y.Z.postN` that republishes the same specification)
and the ones it must refuse.

Run: python3 tests/test_release_guard.py   (exit 0 = green)
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "release.yml"
STEP = "- name: The tag, pyproject.toml, the package constants and the schema file agree"


def guard_source() -> str:
    step = WORKFLOW.read_text(encoding="utf-8").split(STEP, 1)[1]
    heredoc = re.search(r"python3 - <<'PY'\n(.*?)\n\s+PY\n", step, re.DOTALL)
    assert heredoc, "the guard step no longer runs a python heredoc"
    return textwrap.dedent(heredoc.group(1))


def run_guard(tag: str, pyproject: str, package: str, schema_constant: str, schemas=("0.5.0",)):
    """Run the guard for *tag* in a tree whose files carry the given versions."""
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        (root / "pyproject.toml").write_text(
            f'[project]\nname = "flux-spec"\nversion = "{pyproject}"\n', encoding="utf-8"
        )
        (root / "flux_spec").mkdir()
        (root / "flux_spec" / "__init__.py").write_text(
            f'__version__ = "{package}"\nSCHEMA_VERSION = "{schema_constant}"\n', encoding="utf-8"
        )
        (root / "schema").mkdir()
        for version in schemas:
            (root / "schema" / f"flux-schema-{version}.json").write_text("{}", encoding="utf-8")
        output = root / "github-output"
        env = {**os.environ, "GITHUB_REF_NAME": tag, "GITHUB_OUTPUT": str(output)}
        done = subprocess.run(
            [sys.executable, "-c", guard_source()],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        published = output.read_text(encoding="utf-8").strip() if output.exists() else ""
        return done.returncode, published, (done.stdout + done.stderr).strip()


# (name, tag, pyproject version, __version__, SCHEMA_VERSION, schema files, expected output)
# An expected output of None means the guard must refuse.
CASES = [
    ("a specification release", "v0.5.0", "0.5.0", "0.5.0", "0.5.0", ("0.5.0",), "version=0.5.0"),
    (
        "a post-release of the same specification",
        "v0.5.0.post1",
        "0.5.0.post1",
        "0.5.0.post1",
        "0.5.0",
        ("0.5.0",),
        "version=0.5.0.post1",
    ),
    (
        "a second post-release",
        "v0.5.0.post2",
        "0.5.0.post2",
        "0.5.0.post2",
        "0.5.0",
        ("0.5.0",),
        "version=0.5.0.post2",
    ),
    (
        "a post-release whose SCHEMA_VERSION was moved with the package",
        "v0.5.0.post1",
        "0.5.0.post1",
        "0.5.0.post1",
        "0.5.0.post1",
        ("0.5.0",),
        None,
    ),
    (
        "a post-release whose pyproject.toml still says 0.5.0",
        "v0.5.0.post1",
        "0.5.0",
        "0.5.0.post1",
        "0.5.0",
        ("0.5.0",),
        None,
    ),
    (
        "a post-release whose __version__ was not moved",
        "v0.5.0.post1",
        "0.5.0.post1",
        "0.5.0",
        "0.5.0",
        ("0.5.0",),
        None,
    ),
    (
        "a plain tag while the package says post1",
        "v0.5.0",
        "0.5.0.post1",
        "0.5.0.post1",
        "0.5.0",
        ("0.5.0",),
        None,
    ),
    (
        "a package patch with no schema file of that version",
        "v0.5.1",
        "0.5.1",
        "0.5.1",
        "0.5.1",
        ("0.5.0",),
        None,
    ),
    (
        "a post-release of a version that has no schema file",
        "v0.6.0.post1",
        "0.6.0.post1",
        "0.6.0.post1",
        "0.6.0",
        ("0.5.0",),
        None,
    ),
    ("a development tag", "v0.5.0.dev1", "0.5.0.dev1", "0.5.0.dev1", "0.5.0", ("0.5.0",), None),
    ("a release candidate tag", "v0.5.0rc1", "0.5.0rc1", "0.5.0rc1", "0.5.0", ("0.5.0",), None),
    ("a tag without the v", "0.5.0", "0.5.0", "0.5.0", "0.5.0", ("0.5.0",), None),
    ("post0, which PEP 440 spells without the suffix", "v0.5.0.post0", "0.5.0.post0", "0.5.0.post0", "0.5.0", ("0.5.0",), None),
    ("a post number with a leading zero", "v0.5.0.post01", "0.5.0.post01", "0.5.0.post01", "0.5.0", ("0.5.0",), None),
    ("a bare post suffix", "v0.5.0.post", "0.5.0.post", "0.5.0.post", "0.5.0", ("0.5.0",), None),
]


def main() -> int:
    failures = []
    for name, tag, pyproject, package, schema_constant, schemas, expected in CASES:
        code, published, message = run_guard(tag, pyproject, package, schema_constant, schemas)
        if expected is None:
            ok = code != 0 and published == "" and "REFUSED" in message
        else:
            ok = code == 0 and published == expected
        print(f"[{'ok' if ok else 'FAIL'}] {name}: {tag}")
        if not ok:
            failures.append((name, code, published, message))
    for name, code, published, message in failures:
        print(f"\n{name}: exit {code}, output {published!r}\n{message}", file=sys.stderr)
    print(f"\n{len(CASES) - len(failures)}/{len(CASES)} release guard cases behave")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
