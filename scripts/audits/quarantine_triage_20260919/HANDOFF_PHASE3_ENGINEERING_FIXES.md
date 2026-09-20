# Phase-3 Clinical Sign-off — Engineering Fix Handoff

**Date:** 2026-09-20 · **Branch:** `remediation/quarantine-clearing-20260919` · **Head:** `7ebf6c46`
**Production:** untouched (no rebuild, no merge to main, no lane output modified)

> **Status: `77cbb38c` is an INTEGRATION CANDIDATE, not a release approval** (team review 2026-09-20).
> Companion commit `7ebf6c46` (4 lines) completes its contract — see Verification Addendum §9.
> No feature scope was added after the team's handoff/verification-mode direction.

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

---

## 9. Verification Addendum (2026-09-20, handoff/verification mode)

Per team instruction #9/#10: `77cbb38c` reclassified from "release-ready" to
**integration candidate**; broad suite rerun from a clean detached worktree at
exactly the candidate commit, plus one completing fix.

### Commits

| SHA | Role |
|---|---|
| `124982a0` | base (the candidate's parent) |
| `77cbb38c` | **the integration candidate** (10 files, +1573/−42) |
| `c68cb7eb` | handoff doc (this file, v1) |
| `7ebf6c46` | completing fix: overlap-guard pin extension (1 file, +4) |

### Broad-suite results (clean detached worktrees, zero peer contamination)

| Commit | Result | Verdict on each failure |
|---|---|---|
| `124982a0` (base, targeted pair) | 1 failed / 1 passed | static-audit failure **pre-existing at base** |
| `77cbb38c` (candidate, `test.sh fast`) | **2 failed, 15,786 passed, 191 skipped** (5m50s) | see classification below |
| `7ebf6c46` (candidate + completing fix, `test.sh fast`) | **1 failed, 15,787 passed, 191 skipped** (5m35s) | only the pre-existing base failure remains |

Failure classification (verbatim test IDs, per instruction #10):

1. `test_scoring_source_of_truth_audit.py::test_static_audit_current_v4_modules_have_no_forbidden_fallbacks`
   — **PRE-EXISTING at base `124982a0`** (verified by running the pair at base in a
   clean worktree). Verbatim finding: `Finding(code='V4_IQD_INGREDIENTS_FALLBACK',
   message='scripts/scoring_v4/modules/generic_evidence.py:472 reads forbidden
   scoring fallback field')`. Owned by the peer/integrator queue
   (`generic_evidence.py` also carries the peer's uncommitted edits).
   NOT introduced by this branch; not suppressed — recorded verbatim.
2. `test_cross_db_overlap_guard.py::test_iqm_banned_overlap_set_is_only_intentional_high_risk_dual_classification`
   — **INTRODUCED by `77cbb38c`** (pin passed at base), root cause: the two new
   IQM marker identities legitimately carry `WATCH_WITHAFERIN_A` /
   `RISK_MIROESTROL` dual classifications, and the test pins the exact overlap
   set. Completed by `7ebf6c46`: the pin gains the two owner-decisioned entries
   (same documented pattern as vinpocetine 2026-09-11 and DHEA). The uncommitted
   4-line extension was already present in the shared worktree when this
   addendum was written; it was committed verbatim, not rewritten.

No `introduced-by-7ebf6c46` failures; no infrastructure failures.

### Peer-session isolation confirmation (instruction #9)

`git show 77cbb38c --name-only` ∩ peer-dirty files = **∅**. Verified explicitly:
no `enrich_supplements_v3.py`, `scoring_v4/modules/*`, `studied_formulas.py`,
`supplement_taxonomy.py`, `backed_clinical_studies.json`, or
`evidence_expansion_2026_09/*` content is in the candidate. The candidate was
never amended after creation. Shared worktree still holds the peer's 27 dirty
files, untouched.

### Bulk 1340 — label-version provenance guard (team caution, accepted)

The UL computations use **archived frozen-label values only** (220 mg Mg, 50 mg
niacin per serving). The current GNC page (190 mg Mg, same 1–2 servings/day
direction) confirms the max-serving exposure *semantics* but must never
overwrite per-DSLD-ID archived values. Every safety receipt must carry
`product ID + label version/date + source`. Current-vs-archived formula drift
(220→190 mg magnesium) is itself evidence for instruction #8's provenance model.

### Full-corpus replay: REQUIRED POST-CHERRY-PICK GATE (instruction #11)

The 10-record live-DSLD shadow A/B is an honest bounded result, **not** a
substitute for the 15k replay — the raw corpus is not present on this machine
(`raw_data/` absent; no local frozen ingest found). Required on an environment
holding the frozen corpus, before any production publish:

- total products replayed; crashes
- cleaned-representation changes; score changes
- quarantine exits; quarantine entries
- Safety-gate changes (every one)
- products changed OUTSIDE the expected families (75188/243713, 216948,
  232718, 328464, 13041 + ppm/ppb-nested rows)
- largest numerical score deltas
- before/after Phase-3 disposition per product

Harness: `shadow_replay_ab.py` (A/B on any ID list) + `compare_bulk1340_live.py`
(live-vs-snapshot classifier; generalize for the instruction #8 stale-source
report across all Phase-3 products).

### Cherry-pick recommendation (strictly on these results)

**Recommend `77cbb38c` + `7ebf6c46` together for cherry-pick** (integration
candidate pair), conditional on: (a) the frozen-corpus full replay gate above,
(b) integrator coordination with the peer session's in-flight enzyme work —
the pre-existing `V4_IQD_INGREDIENTS_FALLBACK` static-audit failure must be
resolved or explicitly accepted by its owner before release, since it predates
this branch. No merge, publish, or rebuild has been performed.
