# A. Executive release-readiness assessment — PharmaGuide main, audited 2026-09-28

| | |
|---|---|
| Pipeline main SHA | `391b87c5199527f3a3b157c0fed9d2003d7eb232` (local main; 2 commits ahead of pushed `origin/main` dde22dab) |
| Flutter main SHA | `d71e47f56d8221abfc8e38a1820c6ceddd66432b` (= origin/main) |
| Audit window | 2026-09-24 (Thursday) → 2026-09-28; last pre-window commit 7b031050 |
| Commits reviewed | 413 on main (153 Tier 1 code commits with forensic records, 129 data commits by batch, 131 docs/test/tooling/merge rows) |
| Products replayed | 143 real DSLD labels, clean→enrich→score at 7b031050 and at HEAD (0 errors both arms); 61 of them probed row by row; candidate 0d4d59a6 (13,530) and live catalog 2026.09.22 (15,310) joined for reference |
| Suite at HEAD | `scripts/test.sh fast`: 17,752 passed, 41 skipped, 0 failed |
| P0 | 0 |
| P1 | 2 — RR-07 (botanical profile zeroes a non-botanical product's Formulation), RR-11 (panel routes ship "review not finished" on scored Evidence; already in the candidate) |
| P2 | 6 — RR-01 (dynamic form ceiling vs C1), RR-02 (B12 form scores without approval receipt), RR-03 (two adequacy bases), RR-04 (phantom leucine anchor), RR-05 (coverage gap counts 0 in the total), RR-08 (dormant safety fail-open) |
| P3 | 3 — RR-06 (FiberSMART docs), RR-09 (Header rows), RR-10 (Chloride rows); plus the K-table docs/test hygiene rows |

## Can current main proceed toward release validation?
**CONDITIONALLY_READY.** Blockers before the release process starts (not authorization to deploy):
1. RR-11 — emit an Evidence result state on multi/prenatal and B-complex (one line per module + a contract test); the candidate already carries the wrong copy on ~1,553 products.
2. RR-07 — the botanical profile must not replace A1 with 0 − 4 when it recognizes no botanical (233404/233406 lose ~16 Formulation points and a tier).
3. RR-08 — wire `ingredient_assessment_complete` into the completeness gate so a resolver failure cannot ship SAFE (dormant today, one branch).
4. A full clean→enrich→score corpus pass at the fixed HEAD (no corpus exists at HEAD; af488ecf makes that mandatory anyway), then the release rung and the D19 delta review against the live catalog.
Should-fix before release (policy for Sean, measured with the candidate evaluator, no code until decided): RR-01, RR-03, RR-05, RR-02; then RR-04.

## The eight questions (§45)
- **Architecture** — one production pipeline and one public scorer: **yes** (`score_product_v4` → `scored_artifact`; the purpose-quality scorer is gone; export never re-scores). Two policies survive on one topic (adequacy basis, RR-03) and a second, unauthored layer sits on form quality (RR-01).
- **Data integrity** — every important fact traceable raw → export: **yes on the 61 probed labels**, with three explained exceptions: dosed Chloride rows and dosed Header rows become display-only with no disposition reason (RR-09/10), and one combined-name probiotic row is lost (297614). No silent loss of a scored ingredient was found; 12 sample products the candidate withheld are scored again at HEAD (form curation), 11 are held with a recorded reason.
- **Scoring** — reproducible from canonical inputs without hidden competing logic: **mostly**. Every magnitude is in `quality_score.json` (F); pillars are raw × weight ÷ per-route reference. Hidden layers found: the dynamic parent ceiling (RR-01), the botanical-profile override of A1 (RR-07), the phantom anchor row (RR-04).
- **Safety** — can missing data, exceptions or resolver failures create a safer-looking product? **One dormant path can** (RR-08). Banned/recalled products ship BLOCKED with their reason (33360); watchlist and high-risk rows penalize and warn (311187, 182627, 17192); interaction rules fail open on unknown parts and amounts; 0 safety-verdict changes on the sample across the window.
- **Schema** — pipeline and Flutter agree on fields, enums, nullability: **yes** for everything the app reads (row-twin retirements confirmed both sides; tiers, statuses, verdict enums match; no app recomputation). One contract regression: RR-11's null result state. Schema 3 (D14) is app-safe.
- **Recent work** — did the window's fixes survive together? **Yes** (M): no accidental reverts, two reverted pairs are net zero, the nettle/dandelion and registry sequences reconcile. Four conflicts are with *documents and gates*, not with each other: C1 and C9 in RECONCILIATION contradict runtime; three Dose/Evidence formula changes entered production without the recalibration gate the same document defines; ~33 commits carry no body.
- **Technical debt** likely to mislead: RECONCILIATION §C (C1 "not ported"), the register's FiberSMART/Q36 rows, SCORING_ENGINE_SPEC/PIPELINE_ARCHITECTURE stamps, `test_safety_only_rows_get_scored.py` docstring, the graphify graph, the `project_v4_score_is_rubric_raw` memory; curated vocabularies growing inside the enricher.
- **Release readiness** — CONDITIONALLY_READY as above.

## What the window got right (say so)
- Three real dual brains closed with byte-identical or fully measured proofs (form shares, unknown-form value, form matcher; EPA/DHA amount; quantity disclosure; unit selector; fiber set; B0/Safety-Hygiene policy). Row-twin retirements with a gate. Stage code fingerprints. Interaction coverage widened by twins, blend children and presence rules with measured, safety-positive deltas. Banned check reads what the gate reads. Citation gates wired into both release paths. The BCAA row-notes reading extends the matcher through IQM data, not a parser.

## Calibration (answer to the Codex status)
Codex's "correctness repaired" list holds on HEAD except that C1 *is* in production as a dynamic maximum and the B12 values are live without the approval C9 says they await; the adequacy basis is split by route. The fairest next step is one read-only evaluator packet (N: arms A1/A2, B, C, D) on the frozen sample plus a full frozen corpus, benchmark v7 ratified first, and only then config/data edits. The sample already shows where products "deserve better": a coverage gap costs up to 20 points (RR-05), a 200 mg vegetarian DHA is POOR (C-4), and a parent with only mediocre forms scores as if perfect (RR-01) — the same lever that makes riboflavin-5-phosphate 18/20 makes GABA powder 18.7/20.

Reports: B (commit index), C (wire), D (sample integrity + conservation), E (16 traces), F (score accounting + calibration observations), G (safety), H (contract), I (schema), J (dead/stale), K (docs/tests), L (One-Brain), M (regression), N (remediation), FINDINGS, VALIDATION_MATRIX, LEDGER. Not done in this pass: Supabase sync seam, a call-graph dead-code sweep of the enricher, PubMed re-verification of the citation batch, the 213472 label image (browser could not render the PDF).
