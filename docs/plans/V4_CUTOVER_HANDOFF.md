# V4 Cutover — Handoff for the Next Agent

**Date:** 2026-06-08. **Status: v4 is validated + cutover-ready; cutover NOT yet executed.**
**Mission:** Make v4 the single production scoring path. Wire it into the export, flip the
release to v4, then remove ALL shadow scaffolding + dead v3/experimental code so the codebase
has ONE clean path — no `shadow_*`, no dead calibration, no parallel v3 scorer. Best practice:
do it in reversible stages with a rollback branch, not a big-bang rewrite.

Read these first (truth order per CLAUDE.md): the Python source in `scripts/` is the truth;
then `docs/plans/SCORING_V4_PROPOSAL.md` (§19 P5 = cutover-as-config), `.planning/v4-finalization/PLAN.md`
(Step 11 Cutover Prep / Step 12 Release), and the audit reports under `reports/`.

---

## 0. Codex review (2026-06-08) — plan APPROVED with 3 cautions + a concrete sequence

A second-opinion review (codex) approved this plan as "directionally right and much more accurate
than 'just flip a flag'" and confirmed the core finding: **v4 is not production-wired; the export
still ships v3 fields, so cutover is a plumbing/export migration + validation, not a scorer rewrite.**
Three cautions to honor (they refine §3-§4):

1. **The consumer score is `quality_score_v4_100` (the six-pillar public score) — NOT the raw.**
   Keep `raw_score_v4_100` as audit/debug only. Do not make the raw the main shipped score unless
   you intentionally abandon the six-pillar public model (you should not).
2. **Map into existing Flutter fields, but stamp the model version LOUDLY.** Add `score_model_version
   = "v4"` to the export, plus `quality_score_status`, `quality_pillars_v4`, `raw_score_v4_100`,
   `clean_label_flags_v4`. Otherwise Flutter may render a v4 score as if it were old v3 math.
3. **Do not delete v3 immediately.** Keep v3 as rollback for ≥1 release/canary cycle. ORDER:
   remove dead display-calibration code FIRST → rename shadow fields LATER → retire v3 ONLY after
   the production export + Flutter + Supabase are all proven green.

**Codex's concrete cutover sequence (use this as the Phase-A/B checklist):**
1. Commit the handoff. ✅ (done — `051641ba`)
2. Commit/park the dirty depletion changes. ✅ (done — medication_depletions `b7b4594f`)
3. Add an export flag `--score-model v3|v4`, **default v3**.
4. Wire v4 into `build_final_db.py` behind that flag.
5. Export BOTH the audit fields and the public fields (incl. the §3/caution-2 stamp + extras).
6. Build a GHOST v4 final DB (full release candidate, not touching production).
7. Run: contract sync, raw-to-final, inactive safety, Step 10 cohort, **Flutter bundle parity**.
8. ONLY THEN switch the release scripts / Supabase sync to v4.

User decides; this is an approved recommendation, not a directive.

---

## 1. Current architecture (VERIFIED 2026-06-08, do not assume — re-verify before editing)

There are TWO parallel paths and they DO NOT currently connect:

**Production path (v3, ships today):**
```
run_pipeline.py  →  clean_dsld_data.py  →  enrich_supplements_v3.py  →  score_supplements.py (V3)
   →  build_final_db.py  →  scripts/final_db_output/pharmaguide_core.db + detail_blobs
   →  sync_to_supabase.py  →  Supabase (the Flutter app reads this)
```
- `build_final_db.py` reads V3 fields off the scored blob: `score_80`, `score_100_equivalent`,
  `verdict`, `safety_verdict`, and writes the FROZEN export columns `score_quality_80`,
  `score_display_100_equivalent`, `score_100_equivalent`, `verdict`, `safety_verdict`.
- `build_final_db.py` has **ZERO** references to v4 (`grep -c shadow_score_v4 build_final_db.py` → 0).

**V4 shadow path (audit-only, NOT in run_pipeline or the export):**
```
score_supplements_v4_shadow.py  (entry: score_product_v4_shadow(enriched_product))
   ├─ scoring_v4/router.py, gate_safety.py, gate_completeness.py, modules/*  (the rubric)
   ├─ scoring_v4/quality_score.py  (assemble_quality_score → the public six-pillar score)
   └─ scoring_v4/display_calibration.py  (DEAD — see §5)
emits:  shadow_score_v4_100 (raw), shadow_score_v4_verdict, shadow_score_v4_module,
        shadow_score_v4_confidence, shadow_score_v4_breakdown, shadow_score_v4_display_100,
        quality_score_v4_100 (public /100), quality_pillars_v4 (6 pillars), quality_tier,
        quality_score_status, raw_score_v4_100, clean_label_flags_v4
consumed by:  audit_scoring_contract_leaks.py + the api_audit/* tools ONLY.
```
- v3's `score_supplements.py` is UNTOUCHED through the whole v4 build (per SCORING_V4_PROPOSAL §847).
- The keystone (commit `0cca38a1`): **the v4 production score IS the rubric raw — the affine was
  deleted.** So there is NO calibration step in v4; `display_calibration.py` is superseded.

**Net:** "cutover" = (a) wire v4 into the export, (b) map v4 fields → the frozen production fields,
(c) flip the release to v4 with rollback, (d) delete the shadow scaffolding + dead v3/affine code.

---

## 2. The six-pillar public contract (what ships to the app)

`assemble_quality_score(shadow)` is the consumer score. `quality_score_v4_100` = sum of six
pillars: formulation/20 + dose/20 + evidence/20 + transparency/15 + verification/15 +
safety_hygiene/10. Tiers: Elite 95-100 / Excellent 90-94 / Strong 80-89 / Acceptable 70-79 /
Weak 55-69 / Poor <55. Config: `scripts/scoring_v4/config/quality_score.json`. Every pillar
carries a one-line human reason (white-box). `raw_score_v4_100` (audit) is NEVER mutated by the
public layer. Verdict precedence (gate_safety owns BLOCKED/UNSAFE/CAUTION; score-band owns
POOR/SAFE): `BLOCKED > UNSAFE > CAUTION > POOR(<40 raw) > SAFE`.

---

## 3. THE key design decision — field mapping + the /80-vs-/100 question

The export schema (FROZEN names per CLAUDE.md) is built around an 80-point model:
`score_quality_80` (REAL), `score_display_100_equivalent` (TEXT), `score_100_equivalent` (REAL),
`verdict`, `safety_verdict`. v4 is natively /100 (`quality_score_v4_100`, `raw_score_v4_100`).

Decide ONE mapping and write it down (this is the heart of Step 11):
- **Recommended (minimal Flutter impact):** keep the FROZEN field NAMES, flip only the SOURCE:
  - `verdict` ← `shadow_score_v4_verdict`
  - `score_display_100_equivalent` ← `quality_score_v4_100` (the public six-pillar /100)
  - `score_100_equivalent` ← `quality_score_v4_100`
  - `score_quality_80` ← `round(quality_score_v4_100 * 0.8, 1)` (scale /100→/80 for the legacy field)
    OR migrate the column to /100 and drop the /80 legacy IF Flutter is updated in lockstep.
  - `safety_verdict` ← the v4 gate's safety verdict (gate_safety result).
  - Suppression: BLOCKED/UNSAFE/NOT_SCORED already null the public score in `quality_score.py`
    (`quality_score_status` ∈ scored/suppressed_safety/not_scored) — honor it in the export's
    review-queue logic (build_final_db lines ~1146-1180 currently key off v3 verdict/score).
- **Coordinate with Flutter** (`/Users/seancheick/PharmaGuide ai`, see memory `reference_flutter_repo`):
  the app reads `score_quality_80`, `score_display_100_equivalent`, `verdict`. Either keep names
  (recommended) or do a coordinated nullable-column migration (precedent:
  `reference_flutter_food_advisory_consumption_pattern`). Do NOT silently change the contract.
- **The shipped consumer score MUST be `quality_score_v4_100` (six-pillar public), never
  `raw_score_v4_100`** (raw is audit/debug only — codex caution 1).
- **Stamp the model version loudly (codex caution 2):** export `score_model_version = "v4"` so
  Flutter can never render a v4 score as v3 math. Also export these v4-only fields (additive,
  nullable): `quality_score_status`, `quality_pillars_v4` (the explainable breakdown),
  `quality_tier`, `raw_score_v4_100` (audit), `clean_label_flags_v4`. New nullable columns/blob
  fields — do NOT overload existing ones.

---

## 4. Best-practice staged cutover plan

**Phase 0 — Pre-flight (no code changes):**
- Create a rollback branch from the current main (`git branch v3-production-rollback`).
- Re-run the release-readiness gates against a FRESH build (all must be green — they were on
  2026-06-08): `db_integrity_sanity_check.py`; `audit_contract_sync.py --build-dir <dir> --out ...`;
  `audit_inactive_safety.py`; `audit_raw_to_final.py --build-dir <dir> --products-root scripts/products --out ... --canary`;
  `coverage_gate.py`. Run the full suite (`python3 -m pytest scripts/tests/`).
- Lock the field-mapping decision (§3) in writing.

**Phase A — Wire v4 into the export (the actual cutover; reversible):**
- Add an export flag **`--score-model v3|v4` (default v3)** to `build_final_db.py` (codex sequence
  step 3). Behind it, for each product compute `assemble_quality_score(score_product_v4_shadow(
  enriched))` and write the mapped fields (§3) into the export columns. Default-v3 means the flag
  is a no-op until you opt in — fully reversible, single switch back.
- **Export BOTH audit + public fields** (codex step 5): the public score (`quality_score_v4_100`
  → display fields), the version stamp `score_model_version`, and the v4-only audit/explainability
  fields from §3. Keep v3 reachable until Phase C.
- Build a **ghost v4 final DB** (codex step 6) — a full release candidate that does NOT touch
  production Supabase.
- Confirm `run_pipeline.py` produces an enriched corpus the v4 scorer consumes (today it runs v3
  scoring; the v4 scorer takes the SAME enriched input contract — you may drop the v3 score stage
  or run v4 in its place).
- Build ONE release candidate and produce a v3-vs-v4 side-by-side delta (reuse
  `audit_raw_to_final.py` + the Step-10 cohort harness). Gate: shipped_safety_downgrades = 0,
  no banned→SAFE, no unexplained NOT_SCORED, Flutter imports clean, Supabase upload size controlled.

**Phase B — Release-candidate validation (gate before flipping production):**
- Re-run the Step-10 cohort review (7 reviewers, `reports/v4_cohort_synthesis.md` is the prior
  baseline) on the v4-as-production build.
- Named-flagship spot check lands in expected bands (Thorne/Pure prenatal, Nordic/Thorne omega,
  creatine, KSM-66, named-strain probiotics).
- `sync_to_supabase.py --dry-run` against the RC; verify size + schema. DO NOT touch production
  Supabase until explicit go (memory `reference_supabase_project`).

**Phase C — Remove the shadow scaffolding + dead code (the "single clean path"):**
> **ORDER MATTERS (codex caution 3):** (1) delete dead display-calibration code FIRST →
> (2) rename shadow fields LATER → (3) retire v3 ONLY after the production export + Flutter +
> Supabase are all proven green across ≥1 release/canary cycle. Do not collapse these into one step.
- Rename the v4 surface from `shadow_*`/`*_v4_shadow` to production semantics. Suggested:
  `score_supplements_v4_shadow.py` → `score_supplements_v4.py`; `shadow_score_v4_*` columns →
  the production field names; drop the `SCORING_MODE='shadow'` provenance.
- DELETE dead code: `scoring_v4/display_calibration.py` + every `calibrate_display` /
  `shadow_score_v4_display_100` reference (superseded by the rubric-is-score keystone; verify
  no remaining consumer first with grep).
- RETIRE v3: once v4 ships green and stable, remove `score_supplements.py` (v3) + its
  `run_pipeline.py` stage + v3-only helpers, AFTER confirming nothing else imports them
  (`grep -rl "score_supplements\b"`). Keep the rollback branch; don't delete history.
- Collapse any v3/v4 dual-path branches in `build_final_db.py` to the single v4 path.

**Phase D — Docs, schema, hygiene:**
- Update `FINAL_EXPORT_SCHEMA_V1.md`, `SCORING_ENGINE_SPEC.md`, `PIPELINE_ARCHITECTURE.md`,
  `DATABASE_SCHEMA.md`, CLAUDE.md to describe the single v4 path. Bump the export schema version.
- Re-run `/graphify` after the refactor (the call graph drifts).
- Remove superseded plans from `docs/archive/*` references if they mislead.

---

## 5. Dead / shadow / old code inventory (verify each with grep before deleting)

| Item | Why | Action |
|---|---|---|
| `scoring_v4/display_calibration.py` + `calibrate_display` + `shadow_score_v4_display_100` | Affine deleted (keystone `0cca38a1`); raw IS the score | DELETE |
| `shadow_score_v4_*` naming / `SCORING_MODE='shadow'` | Becomes production after cutover | RENAME to production |
| `score_supplements.py` (v3) + its run_pipeline stage | Replaced by v4 once stable | RETIRE after Phase B green (keep rollback branch) |
| Any `*_v4_profile_cutover_*` / affine remnants in reports | Superseded experiments | Archive, don't treat as truth |
| v3-only helpers no longer imported | Dead after v3 retires | grep-confirm then remove |

---

## 6. Hard rules (medical-grade — do not violate)

- **Never modify production Supabase until explicit cutover sign-off.** v3 ships until then.
- **Commits require explicit user approval** (AskUserQuestion), one atomic change at a time.
- **`raw_score_v4_100` is never mutated by display/quality layers** — the audit score is sacred.
- **No hallucinated identifiers** — any PMID/CUI/UNII/CAS/RXCUI must be content-verified via the
  live API (`scripts/api_audit/verify_*.py`); mark UNVERIFIED otherwise. (No identifiers change
  in a pure cutover, but the staged P1 evidence work below DOES touch them.)
- **NO batch fixes on data files** — fix one entry at a time, test, verify.
- **Keep a rollback branch.** No force-push, no history rewrite.
- **Field names are FROZEN** (`score_quality_80`, `score_display_100_equivalent`); change the
  source, not the contract, unless Flutter is migrated in lockstep.

---

## 7. Verification gates (run at every phase; all were GREEN on 2026-06-08)

`db_integrity_sanity_check.py` (0 findings) · `audit_contract_sync.py` (all GREEN) ·
`audit_inactive_safety.py` (0 violations) · `audit_raw_to_final.py --canary` (0 BLOCKER/HIGH) ·
`coverage_gate.py` · `test_v4_safety_parity_release.py` (v3-BLOCKED stays v4-BLOCKED; note the
documented `RED3_RECLASSIFIED_TO_CAUTION` allowlist) · full `pytest scripts/tests/` ·
the Step-10 cohort (`reports/v4_cohort_synthesis.md`). Hard gates: shipped_safety_downgrades=0,
0 banned→SAFE, 0 unexplained NOT_SCORED, no top-band inflation.

---

## 8. State carried in from the 2026-06-08 session (context)

v4 was validated cutover-ready: Step-10 trust gate passed (7 reviewers, ~10,144 products,
0 errors; 93/104 balanced-sample correct; top band earned; safety gates sound). Shipped this
session (all on `origin/main`): six-pillar PR1-6 + PR2.1 brand-cert; clean-label flag layer
(titanium dioxide informs + small penalty, verdict SAFE); cert registry (8 programs); harmful-
additive severity recalibration (Green 3↑, Blue 1/2 + BHT↓); Red 3 banned→high_risk (CAUTION);
**watchlist contract fix** (is_safety_concern=True, non-blocking concern); POOR-verdict canary
re-baseline; cross-DB overlap allowlist; P0 opaque-stimulant-blend CAUTION; P1 collagen evidence
aliases; brand-alias substring-bug hygiene; medication_depletions v5.3.0; EU-additive safety-copy.

**Staged (NOT done) — pick up alongside or after cutover:**
- **P1 evidence matcher (`reports/v4_evidence_matcher_audit.md`):** Defect A = broaden the brand
  guard (`_brand_mentioned`) to read ingredient-name fields + `labelText.searchText` (recovers
  ~50 legit branded products like KSM-66). It is COUPLED to a per-compound bare-alias quarantine
  (measured: broadening alone over-credits ~1,000 generic products) that needs clinical-evidence-
  validity review (commodity compounds like MSM/piperine share generic evidence; standardized
  extracts like Meriva/LJ100/AstaReal do NOT). Defect B = curate evidence-reviewed GENERIC ginkgo
  + pine-bark studies (verified PMIDs); never alias generic into a brand study.
- Harmful-additive Batch 1 slice 3 (clean_label tiers on dyes — `_from_harmful` resolver wiring,
  inform-only/penalty_base=0 to avoid B1 double-count) + Batch 2 (aspartame IARC 2B, etc.).
- POOR-verdict-vs-six-pillar-tier semantics (is the <40 POOR verdict redundant with tier=Poor<55?).
- Six-pillar lock + contract doc.

**Parallel agent (codex)** also commits to this `main` (e.g. medication_depletions, Shatavari
UNII, watchlist export posture). Check `git status` / recent log before editing shared files;
don't collide on `enrich_supplements_v3.py` (13K-line mega-file) / `score_supplements.py`.

---

## 9. Key files + commands

- Pipeline: `scripts/run_pipeline.py` · clean/enrich/score scripts · `scripts/build_final_db.py`
  (the cutover edit site) · `scripts/sync_to_supabase.py` (`--dry-run` first).
- v4: `scripts/score_supplements_v4_shadow.py`, `scripts/scoring_v4/` (router, gates, modules,
  `quality_score.py`, config), the dead `display_calibration.py`.
- Plan/state: `.planning/v4-finalization/PLAN.md` + `STATE.json` (currently phase 9), this file.
- Build a release: `python3 scripts/run_pipeline.py <dataset>` → `python3 scripts/build_final_db.py
  <scored> <out>` → audits → `sync_to_supabase.py <out> --dry-run`.
- Treat the mega-files (`enrich_supplements_v3.py` 13K, `score_supplements.py` 4K,
  `enhanced_normalizer.py` 7K) as gray boxes: lock the interface, verify at the boundary with tests.

**First move for the next agent:** confirm §1 is still accurate (grep, don't trust this doc),
get the user to lock the §3 field mapping, cut the rollback branch, then do Phase A behind a flag.
