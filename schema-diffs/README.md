# Schema diffs

One document per released version pair, generated alongside each release.
The diff is part of the release deliverable: a version bump without a diff
document does not ship.

- [0.5.4 → 0.5.5](diff-0.5.4-to-0.5.5.md): the FLUX window widens; the FLUID 0.7.7 preview moves to forge-cli `471c2602`, which accepts a versioned table's validity window (`openEnd`, `chain`, `lifecycle`, `asOf`) and refuses Airflow ids past 250 characters or ending with a line break, and an EMR on EKS label that names no image
- [0.5.3 → 0.5.4](diff-0.5.3-to-0.5.4.md): the FLUX window widens and no constraint of the schema changes; the validator, `pack`, `verify` and the enforcement gate refuse input outside the JSON data model or past an implementation limit, which 0.5.3 read or raised on (VERSIONING.md, Input bounds)
- [0.5.2 → 0.5.3](diff-0.5.2-to-0.5.3.md): the FLUX window widens; the FLUID 0.7.7 preview moves to forge-cli `e88301f7`, which refuses enum lists that are not comma-separated levels
- [0.5.1 → 0.5.2](diff-0.5.1-to-0.5.2.md): additive; the FLUID 0.7.7 preview joins the seam, selected only by an exact pin
- [0.5.0 → 0.5.1](diff-0.5.0-to-0.5.1.md) — additive; the FLUID seam window widens to 0.7.6
- [0.4.1 → 0.5.0](diff-0.4.1-to-0.5.0.md) — additive; RFC-04 enforcement contract + RFC-09 signed bundles (all nine RFCs shipped)
- [0.4.0 → 0.4.1](diff-0.4.0-to-0.4.1.md) — additive; RFC-05 credibility scorecard + RFC-06 seam ranges & provenance
- [0.3.0 → 0.4.0](diff-0.3.0-to-0.4.0.md) — additive; RFC-01/02/03/07/08 (distributions, extension port, supply chain, semantic port, UI hints)
- [0.2.0 → 0.3.0](diff-0.2.0-to-0.3.0.md) — breaking; first open-source release
