# Phase-3 Clinical Sign-off — Engineering Fix Handoff

**Date:** 2026-09-20 · **Branch:** `remediation/quarantine-clearing-20260919` · **Head:** `77cbb38c`
**Production:** untouched (no rebuild, no merge to main, no lane output modified)

---

## 1. Commits

| SHA | Content |
|---|---|
| `77cbb38c` | Cleaner fixes (omega owner, context-driven spec limits, standardization markers, %DV guard) + IQM marker entries + vocab category + tests + replay harnesses |
| `124982a0` | (earlier) Clinical sign-off packet + response-sheet generator |
| `77037d9f` | (earlier) Frozen quarantine baseline + Phase-3 triage tables |

## 2. Files changed in `77cbb38c` (10)

- `scripts/enhanced_normalizer.py` — 4 hunks, all tagged `2026-09-19 clinical-signoff fix`
- `scripts/data/form_keywords_vocab.json` — new `omega3_constituent_forms` category (EPA/DHA/DPA/ALA)
- `scripts/data/ingredient_quality_map.json` — HEAD + `miroestrol` + `withaferin_a` schema-complete entries, statistics exactly reconciled
- `scripts/preflight.py` — B/R collision allowlist += the two marker identities
- `scripts/tests/test_clinical_signoff_engineering_fixes_20260919.py` — **new**, 20 tests
- `scripts/tests/test_silent_active_drop_recovery.py` — 2 tests re-baselined (dated notes)
- `scripts/tests/test_cleaner_active_evidence_preservation.py` — 1 test re-baselined (dated note)
- `scripts/audits/quarantine_triage_20260919/add_standardization_marker_identities.py` — idempotent IQM generator
- `scripts/audits/quarantine_triage_20260919/compare_bulk1340_live.py` — live-vs-snapshot comparator
- `scripts/audits/quarantine_triage_20260919/shadow_replay_ab.py` — HEAD-vs-fixed shadow replay

## 3. Verification

- **At-commit clean-worktree run:** 233 passed (IQM schema, all 20 new tests, omega/rollup suites, vocab contracts, Nickel/Tin, citation verifier).
- **Shared-worktree fast tier:** 15,899 passed; the 30 failures decompose as: 12 = peer session's uncommitted per-enzyme IQM entries (in-flight), 2 = peer's uncommitted `scoring_v4/modules` edits, 2 = peer's rework of `digestive_enzymes` routing (blend-anchor + static audit), 2 = re-baselined by this work. **Zero failures attributable to the committed state.**
- **Negative controls proven:** colloidal silver stays score-eligible in BOTH its real shape (Silver 20 mcg/1 mL, live 241744) and the hypothetical top-level `Silver 20 ppm` shape; independently-dosed EPA/DHA children survive; non-standardized botanical children (silymarin) are not forced into marker roles.

## 4. Shadow replay (blast radius, live DSLD basis)

10 records replayed twice (HEAD cleaner vs fixed cleaner), 0 crashes:

| Result | Products |
|---|---|
| Changed, exactly as intended (5) | 75188, 243713 (omega owner), 216948 (markers), 328464 (spec limit), 13041 (%DV guard) |
| Unchanged (5) | 232718 (output already correct; IQM resolves the conflict), 241744 (silver control), 223563, 231334, 328644 (E2: no heuristic conversion — correct) |

Report: `reports/quarantine_triage_2026_09_19/shadow_replay_ab.json`.

## 5. Before → after for the Phase-3 families

| Family | Before | After | Disposition path |
|---|---|---|---|
| GNC fish oil 75188/243713 | Dose-less DHA/EPA orphans → `no eligible row` quarantine | Dosed `Total Omega-3 300 mg` owner; children as provenance | Exits quarantine at rebuild; normal gates |
| PM Phytogen 216948 | Miroestrol/Isoflavonoids standalone → identity conflict → quarantine | `standardization_marker` role under dosed 80 mg Pueraria parent; IQM-resolved | Exits quarantine; conservative evidence; estrogenic caution retained by safety layer |
| Longevity A.I. 232718 | Withaferin A 12 mg unresolved vs watchlist → quarantine | IQM marker identity + `from Ashwagandha extract` provenance; 12 mg preserved | **Not auto-cleared** (per instruction #4): normal Safety/Evidence gates re-run; WATCH_WITHAFERIN_A stays active |
| Ginkgo 328464 | `Ginkgolic Acid 1 ppm` as scoreable active | `specification_limit` display-only (nested-under-extract context) | Score the 120 mg extract normally; medication cautions unchanged. Note: live DSLD re-acquired the row — upstream vintages fluctuate; the structural fix is the durable answer |
| Gummy 13041 | Zero-dose rows with %DV were `scoreable` | `daily_value_no_amount`, never scoreable; **no %DV back-calculation** | Needs reviewed label correction or upstream quantity fix to score |
| E2 six (223563/223572/231334/231335/263865/328644) | mg-implausible units passed through | **Unchanged by design** — no plausibility conversion | `product_label_corrections.json` receipts only, gated on live-vs-snapshot + label-image evidence |
| Bulk 1340 ×5 | Clinically mis-filed as `dose_rows_absent` | **Reclassified:** `DOSE_OVER_UL_CRITICAL` + completeness gate | Safety-gate result retained (see §6) |

## 6. Changed conclusion (recorded for the Phase-3 ledger)

**Bulk 1340 is NOT a missing-dose case.** Frozen enriched records carry 39–41 quantified rows. Exact per-nutrient gate report (exposure = label dose × **the label's own `maxDailyServings: 2`** — live DSLD `servingSizes`, "Consume 1-2 servings per day"):

| Product | Penalized flags | Non-penalized |
|---|---|---|
| 228823 | Niacin 285.7% UL (2×50 mg vs 35 mg) | Magnesium 125.7%; folate deduped |
| 243799 | Niacin 285.7% | folate deduped |
| 243808 | Niacin 285.7%; **Folate 257.3% (snapshot triplication artifact: live DSLD has ONE row, snapshot has three)** | Calcium 134.0%; Magnesium 125.7% |
| 243812 | Niacin 289.1%; Magnesium 171.4% | Calcium 128.4%; folate deduped |
| 243815 | — (1 serving/day) | Niacin 144.6% |

Secondary block: completeness gate on `ingredientRows[5]` = **Vitamin A 3000 mcg, DV 334%** (arithmetically coherent; form encoding in the frozen snapshot lacks the disclosed form — likely the known Vitamin-A form-detection gap). 243808/243812's snapshot rows are **stale vs live DSLD** (labels re-issued). No disposition change made; safety result stands.

## 7. Remaining work

1. **Peer session's uncommitted work** (NOT in this handoff): per-enzyme IQM entries (currently fail 12 schema tests), `enrich_supplements_v3.py` enzyme set, `scoring_v4/modules` edits (fail static audit), `supplement_taxonomy.py`, related test reworks. Integrator must coordinate before the next rebuild.
2. **Full-corpus replay** requires the raw DSLD snapshot (not present on this machine). Run `shadow_replay_ab.py --ids <all 259>` (or a batch replay) where `raw_data/` exists; generalize `compare_bulk1340_live.py` for the stale-source report across all Phase-3 products (`unchanged / changed / resolves / re-review`).
3. **needs_info ×4:** 12300, 75291, 254396, 254413 — label retrieval before disposition.
4. **E2 ×6:** live-vs-snapshot comparison, then reviewed correction receipts (mechanism exists; no heuristic path).
5. **18 rejected proposals:** 16 EDTA → `safety_policy_review_required` (safety-policy classification), PM/Longevity handled by this commit, ginkgolic handled by this commit.
6. **Vitamin-A form-detection** gap (228823's completeness row is an instance).

## 8. Fix classification (team taxonomy)

| Fix | Classification |
|---|---|
| Omega aggregate owner | Normalization (cleaner row-role) |
| Spec-limit ppm/ppb guard | Normalization (context-driven, not unit-only) |
| Standardization markers | Identity modeling (IQM entries + cleaner role) |
| %DV-no-amount guard | Normalization (transcription-defect recognition) |
| Bulk 1340 folate triplication / stale Vitamin-A row | Data refresh (upstream re-issue) — rebuild will inherit |
| Bulk 1340 niacin/magnesium UL | Safety-policy working as intended (label max-servings exposure) |
| E2 units | Data refresh via reviewed receipts (pending) |
