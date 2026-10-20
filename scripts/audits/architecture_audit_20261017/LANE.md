# Lane — architecture and code-quality audit (audit-only), October 17–18, 2026

Goal: repository-wide, evidence-based architecture audit with a risk-ranked refactoring roadmap.
Spec: Sean's brief plus eight refinements (two-tier review, concrete decomposition designs,
value-based ranking, equivalence beyond scores, defects vs. intentional choices, revision pinning
with a source-verifying reviewer, conservative output, five first-wave improvements). Plan:
`~/.claude/plans/here-s-how-i-would-delegated-nebula.md`.

Pinned revision: `5fb2be1ca` (main; latest green `pipeline-tests` run 39070168203).

Files this lane writes (all inside this directory, untracked, no commit):
`LANE.md`, `census.py`, `census.json`, `census.md`, `family_maps/*.md`, `AUDIT.md`,
`EVIDENCE_LEDGER.md`.

Will NOT touch: any production module, data file, rule, skill, `.claude/state/CURRENT_HANDOFF.md`
(belongs to the dose-V4.1 lane), the other lane's uncommitted docs, or the 5 untracked submission
JSONs. No pipeline run, no profiling, no broad test suite.

Owner Check: no owner created; dated audit under `scripts/audits/` (convention: `dead_code_20261001`,
`doc_census_20260928`). Equivalence tooling owners to extend, never duplicate:
`scripts/audits/quality_redesign/replay.py`, `release_safety/catalog_diff.py`,
`reports/canary_rebuild.py`, `audit_raw_to_final.py`.

Status: complete. Census frozen (byte-identical across two runs); probes persist closure members and the
collector peer group; family maps saved; AUDIT.md and EVIDENCE_LEDGER.md final after a self-refutation pass
and a fresh-context reviewer whose 23 corrections were each reproduced and applied (ledger §Review). No file
outside this directory was changed; nothing committed. Next step belongs to Sean: review AUDIT.md §H and
decide which first-wave items, the equivalence harness (R11) and the two behavioral/ownership items (R9, R7)
to start; register the audit in the pending-items LEDGER if wanted (that file belongs to another lane).
