# Pipeline Triage & Fix — Fresh-Agent Handoff

> **How to use:** Start a fresh agent in this repo (`/Users/seancheick/Downloads/dsld_clean`) and give it this file as its task: *"Read `PIPELINE_TRIAGE_HANDOFF.md` in full and execute it. End in plan mode."* Everything it needs is below — it does not have the context of the session that produced this.

---

## 0. Mission

Two documents on `main` at repo root — **`CODE_REVIEW_FINDINGS.md`** (~40 findings, P0–P3) and **`FIX_PLAN.md`** (4-phase fix plan) — are a **point-in-time review dated 2026-07-05**. The code has moved since. Your job, in order:

1. **Triage** — for every finding, determine its status *against current code* (FIXED / PARTIAL / OPEN) with reproduced evidence.
2. **Validate** the fix plan against reality — correct anything obsolete, wrong, or risky.
3. **Plan** — produce a phased, safety-first implementation plan and **STOP in plan mode for approval**. Write **no** fix code until the plan is approved.

This is a **medical-grade supplement-safety pipeline**. A wrong score or a suppressed allergen can mislead a real health decision. Engineer accordingly.

## 1. First actions

- Load these skills before doing anything: `superpowers:systematic-debugging`, `superpowers:test-driven-development`, `superpowers:verification-before-completion`, and `superpowers:writing-plans` (for the plan-mode deliverable). Follow them literally.
- Read `CLAUDE.md` in this repo and obey it. Highlights: **never assume, always verify**; **accuracy over speed**; **NO batch fixes on data files** (one entry at a time, verify, test — batch ops skip entries silently); **test every change**.
- This is the **pipeline** repo only. The Flutter app is a separate repo — out of scope.

## 2. Non-negotiable engineering rules

1. **Never trust the review's status field.** It is 9+ days stale. At least one headline (C7, unit reconciliation) is *already fixed*; others are partially addressed. Re-derive every status **live**, from current code + a real reproduction.
2. **Root cause before any fix** (systematic-debugging's Iron Law). No symptom patches. The review's own **5 cross-cutting root causes** (§ "Cross-cutting root causes") are the real targets — fixing one root often closes several findings. Prefer that over N band-aids.
3. **Failing test first** (TDD). Every fix ships with a regression test that *fails before, passes after*. Reproduce the bug as an automated test, not a manual check.
4. **Never weaken a test or relax a strict gate to go green.** A red gate is the signal, not the obstacle. If a test encodes wrong behavior, prove it's wrong before changing it — and change it to the *correct* expectation, not to whatever makes it pass.
5. **Verify broad, not focused-green.** The `fast` test profile *excludes* the heavy files that catch real regressions (`test_enrichment_regressions.py`, `test_scorable_classification.py`, the scoring snapshots). Run those explicitly. Focused-green is not proof.
6. **Substring-matching-without-word-boundaries is the #1 recurring root cause** in this codebase (colors, excipients, company names, units, salts…). When you fix one instance, `grep` for its siblings and fix the class.
7. **When you touch identity/matching:** understand *both sides* of any producer/consumer contract. The largest bug class here came from a re-verifier being *stricter* than the primary matcher — "inconclusive" is **not** "contradiction." Identity matching keys on unique `source_path`, never raw label text.

## 3. Environment & tooling (exact commands)

- **Python:** `source scripts/python_env.sh` then use `"$PG_PYTHON"` (pinned interpreter). Raw `python3` is wrong.
- **Tests:** `bash scripts/test.sh <profile> [targets]` — profiles: `fast` (local, excludes heavy/generated-artifact tests), `release` (release-critical slice + strict gates), `full` (everything), `slow` (heavy integration only). To exercise a slow-listed file, name it explicitly.
- **Strict release gates** (all must stay green — run after any change that could move catalog identity/scoring):
  - `"$PG_PYTHON" scripts/audit_source_of_truth_contract.py matrix --strict-release`
  - `"$PG_PYTHON" scripts/audit_identity_integrity.py --products-dir scripts/products`
  - Scoring snapshot contract: `bash scripts/test.sh fast scripts/tests/test_scoring_snapshot_v1.py`
- **The pipeline stages:** raw → **clean** (`clean_dsld_data.py` / `enhanced_normalizer.py`) → **enrich** (`enrich_supplements_v3.py`) → **coverage_gate** (`coverage_gate.py`) → **score** (`score_supplements.py`). Orchestration: `run_pipeline.py`, `batch_run_all_datasets.sh`. Release: `release_full.sh` (builds catalog → Supabase → Flutter bundle; it runs every strict gate).
- **Where identity lands:** `canonical_id` is assigned at **enrich** (the matcher) and stamped into `ingredient_quality_data.ingredients[]`. The raw `activeIngredients[].canonical_id` stays as the cleaner set it (often `None`) — that is not the resolved value; read the quality-data rows. To propagate an IQM/data fix, **re-enrich** (no re-clean needed): `"$PG_PYTHON" scripts/run_pipeline.py --output-prefix products/output_<Brand> --stages enrich,score`.

## 4. Hard-won lessons to apply (from the identity/scoring work that preceded this)

- **The full-corpus gate is the only proof for data-completeness bugs.** A *single* unmapped ingredient in *one* product (a real ALCAR-arginate salt missing from the alias map) blocked an entire release. Unit tests and brand samples will not surface this class — run the real identity/scoring audit on the real full output.
- **Scoring-snapshot drift: never blind-re-freeze.** After any scoring/identity change, `test_scoring_snapshot_v1.py` will drift. Each drifted line is *either* an intentional improvement (→ `freeze_contract_snapshots.py <id>` + a changelog entry in the fixtures manifest) *or* a regression (→ fix the code). Review **every** line; don't rubber-stamp.
- **Re-verify live before every claim.** The repo mutates under parallel agents and auto-rebuild hooks. Re-read source and re-pull generated output before asserting behavior.
- **Data-completeness gaps hide until the full run.** Budget for a full `batch_run_all_datasets.sh` + `release_full.sh` as the final proof of any fix that touches identity, matching, or scoring.

## 5. Phase 0 — Triage (READ-ONLY; produce a ledger)

For every finding (C1–C10, H1–H9, G1–G3, and the P3 batch):
1. Locate the cited code in **current** `main` (line numbers have shifted — find by symbol/content, not line).
2. Classify: **FIXED / PARTIAL / OPEN / CANNOT-REPRODUCE**.
3. For every **OPEN or PARTIAL P0/P1**, *reproduce it*: run the real function against real data via `"$PG_PYTHON"` and capture the wrong output. Evidence, not assertion. (The review gives repro inputs — e.g. C1 "Riboflavin → natural colors", C6 "Sodium 140 mg + Sodium Benzoate → sodium 0".)
4. Tag it with which of the 5 cross-cutting root causes it belongs to.
5. Respect the review's **"Verified clean (no action needed)"** section — don't re-litigate those.

**Deliverable — a findings ledger** (table): `id | severity | title | status | evidence (repro or file:line) | root-cause bucket | files to touch`.

## 6. Phase 1 — Validate & correct the fix plan

Read `FIX_PLAN.md`. For each proposed fix, decide:
- Still needed? (drop it if the finding is already FIXED.)
- Does it address the **root cause** or a symptom? Upgrade symptom-fixes to root-fixes where the root is shared.
- Will it collide with a strict gate or move the scoring snapshots? (It probably will — note the expected drift and how you'll adjudicate it.)
- Correct sequencing so no phase leaves a gate red.

**Deliverable — an annotated, corrected fix plan** keyed to the ledger.

## 7. Phase 2 — Implementation plan → STOP in plan mode

Group the **OPEN** findings into phases ordered by **safety/user impact** (P0 safety-inverting first: false allergen negatives, false UNSAFE, 1000× dose errors, benign-flagged-harmful). For each phase specify:
- The **root-cause fix(es)** and exact files.
- The **regression tests to add** — name each test and the exact behavior it locks (failing-first).
- **Verification:** which `test.sh` profile + which strict gates + a **full-pipeline score-diff review** (deltas are *expected*; review them per-product against the pre-fix baseline — do not fear or blind-accept them).
- **Blast radius / rollback** note.
- Make each phase **independently shippable** and gate-green on its own.

Present it with **ExitPlanMode** and wait for approval. **Do not write fix code before the plan is approved.**

## 8. Definition of done (for the whole effort, not one session)

Every OPEN finding fixed at the root with a failing→passing regression test; `bash scripts/test.sh full` green; all strict gates green on a **fresh full-corpus** `release_full.sh`; scoring-snapshot drift reviewed and reconciled (re-frozen intentional, code-fixed regressions); and a clean tree with each fix as a focused, tested commit. Nothing marked done without fresh verification evidence.
