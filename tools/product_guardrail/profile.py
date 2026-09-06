"""Product Guardrail profile — FLUX.

Hand-written and deliberately NOT synced: this is where the repo-specific
facts live so that canon_payload.py and check.py can stay byte-identical
across every repo.

This repo is public and it is a SPEC: its prose is read by implementers who
have no other source for what these things are called.
"""

# The product ships American spelling; the canon is British. Symmetric, so
# "Command Centre" is a finding here too — the rule keeps working rather than
# becoming a no-op in one direction.
LOCALE = "en-US"

SURFACE_TIER = (
    "README.md",
    "docs/",
    # A JSON Schema `title`/`description` is product-facing: it renders into
    # the docs site and into the UI hints, so it is copy that happens to live
    # in a data file.
    "schema/",
    "GOVERNANCE.md",
    "CONTRIBUTING.md",
    "VERSIONING.md",
    "SECURITY.md",
    "LICENSE",
    "NOTICE",
    # NOT "examples/": every file there is .yml, and there is no YAML
    # extractor, so listing it would read as coverage while scanning nothing.
    # Add the entry when an extractor exists, not before.
)

EXCLUDED = (
    # A changelog records what was said at the time. Rewriting it to a name
    # adopted after that release is falsification, not compliance.
    "CHANGELOG.md",
    "node_modules",
    "vendor/",
    "dist",
    ".cache",
    ".temp",
    "vendor",
    "schema-diffs/",
    # GENERATED. `docs/schema/kinds.md` comes from scripts/generate-kinds-doc.py
    # and `flux-ui-hints-*.json` from generate-ui-hints.py, both drift-checked
    # in CI with `git diff --exit-code`. A finding here belongs to the
    # generator, and telling someone to edit the output would put them in a
    # fight with that drift check.
    "docs/schema/kinds.md",
    "flux-ui-hints-*",
    # The guardrail quotes every term it forbids.
    "tools/product_guardrail/",
)

SCAN_ENTITY_FILES = True
PY_ALL_STRINGS = ()

# Floors: a scan that collapses must fail loudly rather than pass vacuously.
# Set below today's real numbers so ordinary growth does not trip them.
# Set as a fraction of what the repo actually produces today (66 files,
# ~1.06 MB, ~1040 spans), not at a token value. Floors far below the real
# numbers cannot detect the collapse they exist for: at the previous settings
# most of the corpus could disappear and the gate would still print
# "canon holds".
MIN_FILES_SCANNED = 43
MIN_BYTES_READ = 700_000
MIN_SPANS_EXTRACTED = 686
MIN_TEXT_EXTRACTED = 112_000

GRACE = []
