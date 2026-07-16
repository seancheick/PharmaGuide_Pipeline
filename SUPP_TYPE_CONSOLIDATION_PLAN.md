# Supplement-Type Consolidation — Implementation Plan

**Status (2026-07-16):** mandatory review checkpoint after Phase 1. Phases -1,
0a, 0b, 0c, 0d-R1/R2/R3/R4/R7a, and Phase 1 are complete. Phase 2 has **not**
started. RC1 and the separate R5 evidence, R6 panel-policy, and R7b vocabulary
decisions remain open and must be resolved before the destructive
legacy-classifier retirement.
**Branch:** `supp-type-consolidation`, cut from main `e2583594`. Resolve the live branch tip with `git rev-parse --short HEAD`; do not trust a copied commit hash in this document.
**Plan baseline:** catalog `v2026.07.15.200540`. The branch was independently
reviewed through local commit `4ed09667`; resolve the live tip rather than
assuming that hash is still current. The temporary audit harness is now
fail-closed and score-path capable, at schema 3. Its checked-in default baseline
may still be an obsolete pre-schema artifact, so every run must validate the
baseline schema/content hash and refuse an incompatible file.

> Reviewed across multiple investigation and architecture-review rounds. Symbol names are authoritative; line numbers are navigation hints tied to the baseline and will drift as implementation proceeds. Resolve every symbol against live code before editing. Where a claim was later disproven, the correction is recorded rather than deleted — read the **TRAPS** section before touching anything.

---

## 0. Fresh-session start checklist

The next agent can execute this plan end to end, subject to the two explicit user-approval checkpoints. Start here:

1. Read the repository `AGENTS.md` and this entire plan before editing.
2. Confirm `git branch --show-current` is `supp-type-consolidation`, inspect `git log --oneline -5`, and compare the live branch against main. Do not recreate the branch or reset it to a copied hash.
3. Inspect `git status --short`. At the documented baseline, `scripts/PIPELINE_OPERATIONS_README.md` has an unrelated user-owned modification. Preserve it, do not stage it, and do not overwrite it. Re-evaluate live status because the user may have changed it since this plan was written.
4. Confirm no pipeline or release process is running before changing operational entrypoints. The shipped baseline is already green; do **not** rerun the full pipeline during development. The user owns the full-corpus pipeline execution and production release/promotion unless they explicitly authorize the agent to run them in the active session.
5. Add this plan to the working plan and execute one atomic RED-first slice at a time. Use only `scripts/test.sh` for tests.
6. Do **not** restart completed phases. Read the as-built notes and
   `scripts/CLASSIFIER_PRECEDENCE_SPEC.md`, then execute the remaining work in
   this order:
   1. RC1 definition/inventory pass (no classifier edit until the included and
      excluded row populations are specified and tested);
   2. record separate dispositions for R5 (pre-workout/hydration evidence), R6
      (B-complex panel policy), and R7b (multi-identity family vocabulary);
   3. regenerate a schema-3 harness baseline from the exact comparison commit,
      then review the complete classifier/score ledger;
   4. Phase 2 reader migration and legacy-classifier retirement;
   5. stop at the formal Phase-2 checkpoint before any Phase-3 work.

   The percentile third brain is already retired, every current classifier
   branch emits a machine reason code, and the formulation scorer already reads
   the canonical `is_single_scorable_active` fact. Do not recreate any of those
   decisions in a compatibility adapter.

   ⚠️ **Verification traps that cost real time — read before writing any enrich A/B:**
   - The enricher's database paths are **config-relative**. Run it with `cwd=repo-root` and it silently loads **22 databases instead of 29**, then fails products with `unknown target_id 'acerola_cherry'`. Always run enrichment probes from `scripts/`.
   - Cleaned products key on **`id` / `fullName`**, not `dsld_id` / `product_name` (`validate_product` accepts both). Feed `enrich_product` the wrong shape and it returns an `EMPTY_ENRICHMENT_SCHEMA` placeholder that never reaches the taxonomy — a **vacuous A/B that looks like a clean pass**. Always assert the probe reached `supplement_taxonomy`.
   - `enriched_date`, `enrichment_metadata.generated_at` and `match_ledger.generated_at` are volatile. A blob digest must strip them recursively or **every** product looks changed.
   - Never `git stash pop` bare in this repo — there are 5 pre-existing user/codex stashes and a failed `stash push` will let `pop` restore the wrong one over your tree. Use file copies for before/after probes.
7. Stop for user review after Phase 2 and again before Phase 3. A request to execute the plan does not waive those safety checkpoints.
8. The sole full-corpus rebuild belongs to Phase 5 and is launched by the user under the standing operating agreement. The agent prepares the command, waits for completion, and verifies the resulting artifacts. Targeted temporary artifact generation and read-only corpus audits are allowed earlier; promotion is not.

---

## 1. Goal

**One brain.** Today the pipeline runs **two independent supplement-type classifiers** with different vocabularies and different row iterators. They disagree, and different subsystems route on different ones — so the same product can be scored as single-ingredient by one engine and multi-ingredient by another.

End state:

- **One** type classifier: `classify_supplement()` (the canonical taxonomy).
- **One** scoring producer: v4 (`quality_score_v4_100` is already the shipped score).
- `supplement_type` survives **only as a mechanically-derived compatibility mirror** with **zero independent logic**.
- No duplicated clinical decisions anywhere.

---

## 2. Current state (verified)

### Shipped
Catalog `v2026.07.15.200540` is **ACTIVE** on Supabase (13,272 products). All release gates green, scoring snapshot `32 passed`. Main is `e2583594`.

### Denominator — reconciled exactly (independently confirmed by Codex)
```
14,193  enriched products on disk  ← what the CLASSIFIER sees
   -13  export_contract_quarantined (verdict_not_scored)
─────
14,180  total_exported
  -908  upc_dedup duplicates_removed (750 UPC groups)
─────
13,272  SHIPPED
```
⚠️ The original investigation's **`11,979` was a stale pre-run corpus**. Its **"~375 misrouted products" figure is HISTORICAL and must be re-measured** on the 14,193 baseline before being cited or used as a success metric.

### Baseline `primary_type` distribution (current main, 14,193 products, via harness)
```
 4264   30.0%  general_supplement     <-- the catch-all
 2143   15.1%  herbal_botanical
 1463   10.3%  multivitamin
 1285    9.1%  amino_acid
 1200    8.5%  single_vitamin
  835    5.9%  single_mineral
  668    4.7%  omega_3
  369    2.6%  protein_powder
  353    2.5%  probiotic
  324    2.3%  sleep_support
  306    2.2%  vitamin_mineral_combo
  288    2.0%  joint_support
  205    1.4%  fiber_digestive
  153    1.1%  b_complex
  153    1.1%  immune_support
   91    0.6%  beauty_hair_skin_nails
   67    0.5%  collagen        <-- investigation target
   12    0.1%  pre_workout     <-- investigation target
    9    0.1%  greens_powder   <-- investigation target
    5    0.0%  electrolyte     <-- investigation target (Thorne Catalyte is in our fixture set)
```
Those low counts are an **investigation signal**, not a quota or proof by themselves. Reproduced fixtures show that generic vitamin/mineral and protein branches can preempt more specific branches, but each proposed reclassification still requires positive evidence and a near-miss negative test. Do not increase a category merely to make its distribution look more plausible.

### Current reviewed branch preview (not a shipped artifact)

After the completed classifier slices plus the independent review corrections,
the read-only harness reports 14,193 products with this leading distribution:
`general_supplement=3924`, `herbal_botanical=2381`, `multivitamin=1455`,
`amino_acid=1291`, `single_vitamin=1279`, `single_mineral=882`,
`omega_3=668`, `probiotic=351`, and `collagen=96`.

Relative to Claude's pre-review branch tip (`33ca27ca`), the review corrections
change 114 primary types. The score preview changes only four products and has
**zero** verdict, safety-verdict, suppression, blocking, status, or
`mapped_coverage` flips. One quality-tier change requires explicit review:
DSLD `29032` (Raw Candida Cleanse), `Acceptable` 70.0 → `Weak` 67.5 after
`fiber_digestive` → conservative `general_supplement`. Do not accept or freeze
that delta by aggregate; inspect its row evidence during the expected-change
review.

---

## 3. The two brains

| | **Legacy** | **Canonical** |
|---|---|---|
| Field | `supplement_type.type` | `supplement_taxonomy.primary_type` (+ top-level `primary_type`) |
| Producer | `infer_supplement_type()` — `supplement_type_utils.py:233` | `classify_supplement()` — `supplement_taxonomy.py:502` |
| Row iterator | `_iter_classification_rows` — reads **full** `ingredient_quality_data.ingredients` | `_iter_classification_rows_v2` (`:1323`) — reads **only** `ingredients_scorable` |
| Vocabulary | 7 types (`single_nutrient`, `herbal_blend`, `targeted`, `specialty`, …) | ~20 types (`single_vitamin`, `single_mineral`, `collagen`, `electrolyte`, …) |
| Reader helper | `supp_type_of()` — `generic_helpers.py:196` (marked **LEGACY**) | `primary_type_of()` — `generic_helpers.py:211` |

### Root causes of drift

- **RC1 (scope unresolved; old ~1.0% estimate disproven)** —
  `_iter_classification_rows_v2` reads only `ingredients_scorable`
  (`mapped=True`). A broad detector found dropped dose-bearing rows in 3,662
  products (25.80%), but that pool mixes genuine unmapped actives with correctly
  excluded excipients/structural rows. The next pass must define
  `quantified_label_active_rows` from explicit cleaner roles and exclusion
  reasons, not include every dosed row. Named positive canaries remain
  Nattokinase `294772` and Horsetail `294422`; EDTA chelators/fillers are named
  negatives.
- **RC2 (~1.9%; 21 cross single/multi)** — `classify_supplement` **never calls `mark_compound_duplicate_rows`**, so elemental + compound salt counts as two actives. *e.g. Magnesium Glycinate `315678`, Choline L-Bitartrate `252532`.* (Same family as the tracked elemental/compound bug.)
- **RC3 (~0.26%, reverse — taxonomy is RIGHT)** — the legacy iterator lacks `nested_display_only`/`composition_leaf` exclusion and double-counts EPA+DHA sub-rows. *e.g. Fish Oil `13801`.*
- **7 branch-ordering / coverage bugs** in `classify_supplement` (details §7).

### The routing split (the actual bug)
Most current v4 routing prefers the taxonomy, but legacy decision/fallback readers remain throughout the inventory in §6. The proven direct scoring split is `generic_formulation.py:421/452/494/608`, which gates the **A6 focus bonus, premium-single floor, standard-single floor, and enzyme bonus** on legacy `supp_type_of()` + `SINGLE_INGREDIENT_SUPP_TYPES = {"single","single_nutrient"}` (`:163`; `"single"` is a **dead literal** production never emits). Empirically proven: a magnesium product with one decorative zero-dose row → legacy `targeted` (counts 2) vs taxonomy `single_mineral` (counts 1) → single floor denied → **~5–22 point under-score**. Existing tests do not guard the real disagreement because they hard-code the legacy type.

---

## 4. ⚠️ TRAPS — read before touching anything

Each of these was a real, verified near-miss. They exist because someone (Claude) asserted them wrongly first.

1. **`probiotic_data` MUST precede the taxonomy.** `classify_supplement` consumes `probiotic_data` (`supplement_taxonomy.py:666-674`: `is_probiotic_product`, `total_cfu`, `total_strain_count`). `enrich_supplements_v3.py:17585-17589` carries an explicit comment: *"MUST run AFTER probiotic_data so the NP exemption gate for probiotic strains can fire correctly."*
   ⛔ **Never move taxonomy ahead of `probiotic_data`.** It is safe to move both operations earlier together in the dependency order. Moving taxonomy alone starves the CFU gate and breaks the verified Paradise-style guard (Zinc + 5 NP strains with `total_cfu=0` correctly → `single_mineral`, NOT probiotic).

2. **The SoT audit will block the release the moment RC1 lands.** `audit_source_of_truth_contract.py:839+` hard-requires the exact string
   `taxonomy["classification_input_source"] == "ingredient_quality_data.ingredients_scorable"`
   and **greps prose reasons** (`" ".join(reasons).lower()` for `"omega-3:"`). RC1 changes that row population → literal stops matching → **clinical-drift gate fails → release blocked**. That gate runs *first* in `release_full.sh`. **Migrate the gate before changing the row population** (Phase 0a).

3. **Do not force fake confidence.** Zero confidence is *truthful* when there is no quantified evidence. Rule: reasons never empty; zero confidence allowed **only** with an explicit reason code (`no_quantified_active_evidence`); such products must not silently become scoring-eligible; **never** bump confidence to satisfy a gate.

4. **The 30% catch-all reduction is a MEASURED OUTCOME, not a quota.** Treating it as a target pressures the classifier into overconfident categories — Goodhart's law. Report the number; never optimize toward it.

5. **Import analysis is NOT sufficient.** `run_pipeline.py:173/497` invokes v3 **by subprocess**, not import. This caused a materially wrong "v3 is dead" conclusion. Use **source search + runtime entrypoints + subprocess calls**.

6. **Line numbers are NOT execution order.** `14782` is a method *definition*, reached via `_collect_percentile_context` → `_infer_percentile_category` → `enrich_product:17567`. Trace call chains.

7. **v3 is NOT dead code.** It is the live Stage-3 producer; `build_final_db.py` → `overlay_v4_scored(enriched, scored_v3)` (`export_adapter.py:230/255`) starts from a **copy of the v3 dict** and inherits ~13 v3-native fields including the safety-critical **`mapped_coverage`** (`build_final_db.py:8105`), which drives *"never show safe when `mapped_coverage < 0.3`"*. Removing v3 is a **migration**, not a deletion.

---

## 5. Verified execution order (`enrich_product`, def `17428`)

```
17509  enriched["supplement_type"] = _classify_supplement_type(product)    ← legacy WRITE
17524  enriched["supplement_type"] = _classify_supplement_type(enriched)   ← legacy WRITE (re-classify)
17567  enriched.update(_infer_percentile_category(product, enriched))      ← legacy READ fires here
17585  enriched["probiotic_data"] = _collect_probiotic_data(product)
17590  taxonomy = classify_supplement(enriched)                            ← taxonomy WRITE
17591  enriched["supplement_taxonomy"] = taxonomy
17592  enriched["primary_type"] = taxonomy["primary_type"]
```

**Required target order:**

1. ingredient-quality data
2. **probiotic data**
3. canonical taxonomy
4. emit `primary_type` / `secondary_type` + `supplement_type` **compatibility mirror**
5. emit percentile compatibility fields **from the taxonomy**
6. downstream scoring-evidence classification

---

## 6. Consumer inventory (source + runtime, not imports)

**Writers — all in one file (good news):** `enrich_supplements_v3.py` only — `17509`/`17524` (legacy), `17590`–`17592` (taxonomy + top-level `primary_type`).

**Legacy readers (production):**

| Location | Count | Notes |
|---|---|---|
| `score_supplements.py` | **7** — 566, 2045, 2097, 3156, 3246, 4683, 5284 | more than first mapped |
| `scoring_v4/modules/generic_formulation.py` | 4 — 421/452/494/608 | **the scoring bug** |
| `build_final_db.py` | 3 — 823, 858, 4563 | |
| `enrich_supplements_v3.py` | 3 — 14782, 14845, 17724 | 14782 = the ordering one |
| `scoring_input_contract.py:2920` | 1 | legacy multivitamin fallback |
| `scoring_v4/router.py:896` | 1 | broad-panel-guarded |
| `scoring_v4/confidence.py:456` | 1 | |
| `scoring_v4/modules/sports_formulation.py:109` | 1 | legacy fallback |
| `api_audit/cert_audit_report.py` | 2 | 243, 382 |
| **`dashboard/`** | ~20 | **NOT a migration cost — see below** |

**✅ Dashboard needs zero migration (verified).** Its call sites read the exported **DB column** `supplement_type` (`row["supplement_type"]` from the dataframe), fed by taxonomy-first `resolve_export_supplement_type` (`build_final_db.py:846`). The compatibility mirror covers them entirely.

**⚠️ `supplement_taxonomy` is declared in the source-of-truth matrix** (`audit_source_of_truth_contract.py:63`; read at 622/666/799/839) — **shape changes have contract-gate consequences.**

**Third decision system:** `_infer_percentile_category()` (def `enrich:14802`; context `_collect_percentile_context` def `:14752`, legacy read `:14782`) **independently decides** percentile category. One-brain fails unless it is **retired or reduced to decorating the canonical taxonomy result** — not merely handed the taxonomy as one more input.

---

## 7. `classify_supplement` accuracy bugs (all empirically reproduced)

Dominant defect is **branch ordering**: generic vitamin/mineral combo branches (`:926`, `:966`) and the panel/protein branches (`:1006`) fire *before* the specific `collagen` (`:1030`), amino-dominant (`:1024`), `herbal_botanical` (`:1018`), and electrolyte branches — and lack the vocabulary to emit those types.

1. **Collagen multi-SKUs never reach `collagen`** — Collagen+VitC → `general_supplement`; Collagen+MCT+strain → `protein_powder`. Only a strict single-active collagen routes correctly. *(HIGH)*
2. **`active_count==2` is a black hole** — herb/collagen-dominant with one named → `general_supplement` @0.85 (turmeric+bioperine, ashwagandha+bioperine → should be `herbal_botanical`); with neither named and no vitamin/mineral id → **no assignment at all**, leaving `general_supplement` @ **0.00 confidence, empty reasons**. Adding a 3rd active fixes it — proving the 2-active band is the anomaly. *(HIGH)*
3. **Pure mineral panels → `multivitamin`** — the `multi_panel_signal` gate (`:653-661` → `:781-790`) needs only `len(vitamin_ids)+len(mineral_ids) >= 6`; **zero vitamins required**. *(HIGH)*
4. **Electrolyte panels without a name token → `single_mineral`** — gate (`:966-974`) requires an electrolyte/hydration *name* token. *(MED-HIGH)*
5. **Homogeneous 2–5 combos collapse to a SINGLE type** (`:952-959`, `:978-985`) — 3-mineral blend → `single_mineral` → `is_single=True` on a multi-ingredient product. *(MED)*
6. **B-vitamins + ≥3 minerals → `multivitamin`** (bound `non_b_minerals<=2` at `:749`) instead of `b_complex`/`vitamin_mineral_combo`. *(MED)*
7. **Confident fallback cannot self-correct** — `general_supplement` asserted at 0.85 (`:946`); the DSLD disagreement check only logs when `confidence < 0.7` (`:1076`) and `_check_dsld_agreement` (`:1271`) is bool-only, so a confidently-wrong type silently ignores a contradicting DSLD `productType`. *(MED)*

**Verified CORRECT — do not "fix":** Paradise-style decorative probiotics (`total_cfu=0` → `single_mineral`, not probiotic); empty/all-NP/0-active → `general_supplement` @0.0 (fail-safe); named-amino-with-cofactors (`:852`); omega carrier-oil exception (`:805-812`); `sole_active_is_strain` (`:692`); fiber-primary-with-accessory-probiotics guard (`:357-398`).

---

## 8. The harness (temporary; harden before trusting)

`scripts/audits/supptype_drift_preview.py` is **TEMPORARY, read-only, and deleted at cutover**. It never selects a shipped result. Its classification distribution is useful, but the baseline implementation at `aee50d10` has four known defects that make its score-impact claims unsafe:

1. `classify_row()` recomputes taxonomy, but `score_products()` scores the original enriched product without injecting that recomputed taxonomy. After classifier edits, classification sees new code while scoring can still read the stale embedded taxonomy.
2. `score_products()` invokes only legacy `SupplementScorer`; it does not measure the shipped v4 score contract.
3. The affected-product set includes only `primary_type` changes. It misses score-driving changes such as `is_single_scorable_active` changing while `primary_type` remains stable.
4. Input handling fails open: unreadable JSON is skipped, duplicate DSLD IDs overwrite silently, and added/missing product IDs are not blocking.

The static `SINGLE_FAMILY` set is also duplicate classification logic: an `amino_acid` product can contain multiple scorable actives. Remove it and consume the canonical single-active fact.

### Mandatory Phase -1 harness contract

Before using the harness as evidence, make it satisfy all of the following with focused tests:

- **Current taxonomy projection:** score a defensive copy containing the taxonomy recomputed by current code, including `primary_type`, `secondary_type`, the taxonomy-derived compatibility mirror, and every score-driving classification fact. Use one production projection seam shared by enrichment and the harness; do not maintain a harness-only mirror algorithm.
- **Baseline parity:** before storing the initial baseline, assert that recomputed current taxonomy matches the embedded fresh-run taxonomy for every product, or emit an explicit baseline-drift ledger and stop. Never silently mix fresh code with stale enriched taxonomy.
- **Production v4 preview:** run the existing production v3+v4 assembly path (`SupplementScorer` scaffolding followed by the v4 export adapter) until `build_scored_artifact()` replaces it. Capture at least `quality_score_v4_100`/its authoritative adapter key, `quality_score_status`, final verdict, safety verdict/status, quality tier/grade, six pillars, `mapped_coverage`, blocking reason, and strict-contract status.
- **Exact-path canary:** prove the preview equals the real final-build projection on the frozen fixture set. Any export-only hard block or suppression not represented in the preview must be called out and validated through a targeted final-build canary before a checkpoint.
- **Complete impact selection:** compare all score-driving taxonomy fields and facts, not only `primary_type`. During Phase 1, either rescore the full corpus or prove that the selected affected-product set includes every product whose scoring behavior can change.
- **No independent single inference:** remove `SINGLE_FAMILY`; compare `is_single_scorable_active`, `quantified_label_active_count`, and `scorable_active_count` directly.
- **Fail closed:** unreadable/corrupt files, malformed batch shapes, duplicate product IDs, missing baseline products, new unacknowledged products, count mismatch, score errors, and baseline-schema mismatch return non-zero.
- **Deterministic baseline:** include schema version, baseline commit, corpus count, sorted product IDs, and a timestamp-excluded content hash. Reject a baseline created from a different schema or corpus unless explicitly regenerated.
- **Expected-change ledger:** JSON output contains every changed product, old/new structured classification evidence, score/status/verdict/pillar deltas, and named reason codes. Do not truncate the machine-readable ledger even when console output is summarized.

Required RED-first harness tests:

1. A recomputed taxonomy change alters the v4 preview even when the enriched blob contains stale taxonomy.
2. A change only to `is_single_scorable_active` is included and rescored even when `primary_type` is unchanged.
3. A multi-active amino-acid product is not reported as single from its type name.
4. Duplicate IDs, unreadable JSON, missing IDs, added IDs, and scoring errors each produce a non-zero exit.
5. Frozen fixtures match the production final-build projection for every captured field.

After Phase -1 is green, the intended loop is:

```bash
source scripts/python_env.sh
$PG_PYTHON scripts/audits/supptype_drift_preview.py baseline --score
# ... one RED-first implementation slice ...
$PG_PYTHON scripts/audits/supptype_drift_preview.py compare --score --json-out <ledger-path>
```

> **PHASE -1 IS COMPLETE AND GREEN** (2026-07-15). Measured, not estimated:
> `baseline --score` = **222.6s**, `compare --score` = **~36s** (8 workers), classification-only ≈ 28s.
> Two consecutive no-op compares report **0/14,193 — a zero noise floor**, so any drift the harness reports now is a real consequence of your change.
>
> - The harness **re-execs under `PYTHONHASHSEED=0`**; do not remove that without reading `_pin_hash_seed`'s docstring (an unrelated production non-determinism in `scoring_input_contract._botanical_child_identity` flips 2/14,193 products at random — tracked separately, do **not** fix it here: it lives in the checkpoint-protected `mapped_coverage` owner).
> - `baseline` **refuses to freeze** when the artifact's embedded taxonomy differs from what current code recomputes, and names the drifting FIELDS. Today: 13,631/14,193 identical + 562 cosmetic (`classification_reasons` only, from the determinism fix) → `--allow-baseline-drift` is currently justified for exactly that reason. If a **DECISION FIELD** ever appears in that list, stop: the artifacts were written by a different classifier.
> - Selection is fact-level, not `primary_type`-level. Phase 0a proved this matters: it changed 14,193/14,193 products with **0** `primary_type` changes — a type-only diff would have reported nothing at all.
> - Exact-path canary (`test_supptype_preview_exact_path_canary.py`, **slow** profile) proves the preview reproduces the **shipped** `products_core` rows for all 30 frozen fixtures. Run it after any scoring-path change; if it fails, the harness is no longer evidence.
> - Contract tests: `test_supptype_drift_preview_harness.py` (fast). Both files are deleted with the harness at cutover.

The harness is a fast preflight, not a release gate. Iterate against it and use targeted artifact canaries at checkpoints. At cutover, the user runs the full 14,193-product pipeline exactly once; the agent verifies its output.

---

## 9. Phases

Every phase is **RED-first TDD**. Use the harness between iterations.

### Phase -1 — make the migration harness trustworthy

Implement and test the complete harness contract in §8 before changing classifier behavior. This phase may extract a small behavior-preserving production seam for applying current taxonomy fields to a defensive product copy, but it must not change classification results or production routing.

**Exit gate:** all Phase -1 failure-mode tests pass; current embedded-vs-recomputed taxonomy parity is accounted for across exactly 14,193 product IDs; frozen preview fields match the production final-build projection; a score-driving single-fact-only change is demonstrably detected.

### Phase 0 — prerequisites, then the classifier

- **0a. Define and emit the structured taxonomy evidence contract without changing classification behavior, then migrate the SoT audit** (`audit_source_of_truth_contract.py:839+`) from the hard-coded `classification_input_source` literal + **prose grepping** to that contract. **With tests.** The producer and consumer change together; the audit must never require fields no current producer emits.
  🔒 *Release-blocking prerequisite — RC1 breaks this gate otherwise.*
- **0b. Retire / reduce `_infer_percentile_category()`** to a **decorator** over the canonical taxonomy result (not an independent decider).

  > **Measured 2026-07-15 (corpus evidence, gathered before any 0b code).** The two percentile brains disagree on **7,975/14,193 products (56.2%)**, and the disagreement is almost entirely one-way: taxonomy says `herbal_botanical` (2,139), `amino_acid` (1,251), `single_vitamin` (1,189), `single_mineral` (778)… while the enricher's top-level `percentile_category` says `general_supplement`.
  >
  > **This does NOT currently ship, and that is the key de-risking fact.** `build_final_db.py:8144` resolves the export's `percentile_category` from `supplement_taxonomy.percentile_category` first, falling back to the percentile context's `category_key`. Verified against the shipped catalog: `products_core.percentile_category` matches the taxonomy (herbal_botanical 2,033 / amino_acid 1,200 / fish_oil 607 via `_PERCENTILE_CATEGORY_MAP["omega_3"] = "fish_oil"`), not the enricher's collapsed value. So the third brain's output is already **dead for the catalog** while remaining live in the enriched artifact.
  >
  > Consequence for 0b: making `_infer_percentile_category` decorate the taxonomy **aligns the artifact with what already ships** rather than changing the shipped cohort — a far smaller blast radius than the 56% number suggests. Confirm before coding: (1) nothing between the current call site (`:17567`) and the taxonomy write consumes the top-level `percentile_category`; (2) `score_supplements._attach_category_percentiles` reads the top-level value, but v3 percentiles are recomputed by `build_final_db` (`:8798-8806`) and do not ship — verify, do not assume. 0b requires the §5 order change (0c) first, since a decorator cannot run before the thing it decorates.

  > **✅ 0b DONE 2026-07-16** (commit `refactor(enrich): project percentile category from the taxonomy (Phase 0b)`).
  >
  > **Root cause was vocabulary, not weights.** `data/percentile_categories.json` defines **9** categories; the taxonomy's `_PERCENTILE_CATEGORY_MAP` has **20**. Everything the config could not express (`herbal_botanical`, `amino_acid`, `single_vitamin`, `single_mineral`, `sleep_support`, …) had no id to land on and fell into the `general_supplement` fallback — that is the entire one-way 56.2% collapse. It also used different ids for the same concept (`collagen_powder` vs taxonomy `collagen`, `electrolyte_powder` vs `electrolyte`).
  >
  > **Both checks from the note above resolved, and (2) corrected:** v3's percentile output *does* partially ship — `build_final_db:8145` takes `percentile_label` from `cp["category_label"]`. But that value already comes from `score_supplements._resolve_percentile_category`, which since SP-2.8 prefers `supplement_taxonomy.percentile_category` and title-cases it ("Herbal Botanical"). So the decorator pattern already existed downstream; the enricher was the last independent decider, and two consumers had already learned to ignore it.
  >
  > **As built:** `_infer_percentile_category` → `_decorate_percentile_category(enriched)`; **237 lines** of decision machinery deleted (`_canonical_token`, `_word_token_match`, `_percentile_category_fallback_id`, `_collect_percentile_context`, the inferer), replaced by a ~50-line projection reading only `supplement_taxonomy`. Label derivation now has a single owner, `supplement_taxonomy.percentile_label_for()`, matching the shipped title-case exactly. Missing taxonomy → reason-coded `taxonomy_unavailable` @ confidence 0.0, never an invented cohort (TRAP 3).
  >
  > **The explicit-override branch was dropped, deliberately.** `product.percentile_category` was honoured at confidence 1.0 — a second brain "handed the taxonomy as one more input", which §6 forbids. It is dead on the corpus (**0/14,193** cleaned products carry it). Curation that needs to move a product's class must move the *taxonomy*, not a downstream mirror.
  >
  > **Verified:** 219 products / 28 brands, seed pinned. `primary_type` changed **0**; `percentile_category` changed **104** (97 of them `general_supplement` → a real cohort). All 104 now match `products_core` — i.e. the artifact was corrected to agree with the catalog; **the shipped cohort did not move**. New `percentile_category_source` is `taxonomy_v2` for 219/219.
  >
  > **Test disposition (§9 rule applied):** `TestPercentileCategoryInference`'s 4 tests covered the retired engine → deleted as obsolete legacy behaviour. Their clinical intent was **ported, not dropped**, as end-to-end taxonomy assertions in `test_percentile_category_decorator.py` (green tea capsule ≠ greens powder; whey → protein_powder; greens superfood → greens_powder). `TestPercentileCategorySchema` kept — the data file is still loaded and still checked by `db_integrity_sanity_check`.
  >
  > **Phase 5 dead-data note:** `percentile_categories.json`'s `classification_rules` and its 9 curated labels are now unread by production. Retire the file (and its enricher `database_paths` entry + `db_integrity_sanity_check` hook) in the dead-code sweep — it is the config that caused this defect, so leaving it loaded invites the decider to grow back.
- **0c. Enforce the dependency order** from §5 (ingredient-quality → probiotic → taxonomy → mirror → percentile-from-taxonomy). Respect the `MUST run AFTER probiotic_data` invariant.

  > **✅ 0c DONE 2026-07-16** (commit `refactor(enrich): run percentile inference AFTER the taxonomy (Phase 0c)`). Live order is now IQD → probiotic → `apply_taxonomy_projection` → percentile. Pure reordering, **0 behaviour change** proven on real products, not argued: 219 products across all 28 brands enriched end-to-end before/after with the seed pinned and stamps stripped → primary_type 0 changed, percentile_* 0 changed, enriched blob **0/219** changed. Guarded behaviourally (spies on what `enriched` held at call time, not source order) by `tests/test_enrich_taxonomy_dependency_order.py`, which also pins TRAP 1 end to end via the Paradise-style NP-exemption case. **0b is now unblocked.**
- **0d. Classifier fixes** — RC1 (two row populations), RC2 (compound-dup), and the 7 branch-ordering bugs (§7).

  > **NAMED CANARIES for 0d, surfaced by the 0b A/B (2026-07-16).** Real products from a 219-product / 28-brand sample where the retired percentile decider disagreed with the taxonomy *and was arguably right*. Each is currently **shipping with the taxonomy's answer**, so these are live defects, not hypotheticals — and they corroborate §7 with names instead of counts. Use them as 0d fixtures:
  >
  > | dsld | product | taxonomy says (ships) | §7 bug |
  > |---|---|---|---|
  > | `174772` | **Omega-3 EPA/DHA** | `single_vitamin` | an omega-3 product not reaching `omega_3`/fish_oil — check RC1 + the omega branch |
  > | `309959` | Preseries Lean **Pre-Workout** Tropical Punch | `multivitamin` | §7 #3: the `multi_panel_signal` gate needs only `len(vitamin_ids)+len(mineral_ids) >= 6` and **zero vitamins required**, so a pre-workout's vitamin panel hijacks it |
  > | `295773` | Bulk Strawberry Kiwi | `multivitamin` | same panel hijack |
  > | `248656` | Atlas Dutch Chocolate | `multivitamin` | protein-ish product → multivitamin; panel hijack vs §7 #5 |
  > | `309960`, `329215` | Preseries **Stim-Free** Blue Raspberry | `general_supplement` | pre-workout falling to the catch-all |
  > | `268231` | Keto +Plus Fruit Punch | `general_supplement` | §7 #4: electrolyte/hydration panel without a name token |
  >
  > This is direct evidence for §2's "investigation targets": `pre_workout` (12) and `electrolyte` (5) are low **because real pre-workouts and hydration products are being absorbed by `multivitamin` and `general_supplement`** — not because the catalog lacks them. Still requires positive evidence + a near-miss negative per §0d before any reclassification; do not raise a count to make a distribution look plausible (TRAP 4).

**Structured taxonomy evidence contract (0a).** Give it an explicit schema/version and stable semantics. At minimum it includes:

- a stable contract-level input identifier (not a physical JSON-path literal used as policy);
- the physical source fields used, for diagnostics only;
- enumerated `classification_reason_codes`;
- structured row evidence containing stable source path/row ID, canonical ID when known, normalized category, quantified status, score-eligibility status, and inclusion/exclusion role;
- explicit representation for unresolved-but-quantified label actives;
- no audit logic that parses human-readable `classification_reasons` prose.

Strict release mode accepts only the current structured contract version. If temporary old-artifact inspection is necessary, expose it through an explicit non-release compatibility option; never silently dual-read prose in the strict gate.

> **0a AS BUILT** (2026-07-15; commit `feat(taxonomy): structured evidence contract; migrate SoT gate off prose (0a)` — resolve the live hash with `git log --oneline`, per §4). The contract began at `1.0.0` and is now **`1.1.0`** after the independent review corrected identity-vs-row category semantics. It emits `classification_input_contract` (stable ids `score_eligible_rows` / `iqd_all_rows_fallback` / `raw_label_actives`), `classification_row_evidence` (source_path, row_id, canonical_id, category, quantified, score_eligible, role), `classification_reason_codes`, identity and row counts, and `unresolved_quantified_active_count`. `classification_input_source` is retained but demoted to a diagnostic. Strict release mode rejects a missing taxonomy and any malformed current-version evidence contract; it never falls back to prose or path literals.
>
> **DEFERRED to 0d, deliberately:** `classification_reason_codes`. The vocabulary must name the *decisive branch*, and there are 45 `primary_type` assignment sites that **0d itself reorders and rewrites** (§7). Authoring codes against the pre-0d branch structure would mean writing them twice and reviewing them against a tree that is about to change. The release-blocking half of 0a — getting the strict gate off the path literal and off prose — is complete and independent of the codes. The §10 gate "every changed product ID has a named classification reason code" is an *after-Phase-2* gate, so the codes must land with the 0d rewrite that gives them meaning. Do not open 0d without them.
>
> ⚠️ **Operational consequence, by design:** once this branch merges, `release_full.sh` blocks at the clinical gate (`CLINICAL_TAXONOMY_CONTRACT_VERSION`, one aggregated finding per file) until the corpus is re-enriched, because current artifacts predate the contract. That is the plan's Phase 5 sequencing — "never ship a code+artifact combination known to be out of sync" — not a regression. Main is unaffected while this branch is unmerged.

**Two row populations (mandatory design).** Classification must see unmapped-but-genuine label-active rows; scoring must reject unresolved identities. **Do not** make taxonomy's classification population equal to `get_scoring_ingredients(strict=True)`. Define one classification-input contract that composes the existing scoring-input owner rather than copying its eligibility rules:

- `quantified_label_active_rows` — classification input, **includes unmapped dose-bearing actives**
- `score_eligible_rows` — validated mapped subset obtained from the authoritative `get_scoring_ingredients(strict=True)` result, not reimplemented in taxonomy

The taxonomy must emit at least:

- `quantified_label_active_count`
- `scorable_active_count`
- `is_single_scorable_active`
- `classification_reason_codes` (structured — the SoT gate consumes these)
- stable source paths / row identifiers used in the decision

> **`is_single_scorable_active = true` only when there is exactly one score-eligible active AND no second unresolved quantified active.** Otherwise a product with one mapped + one unmapped active would incorrectly receive single-ingredient bonuses.

> **✅ SPEC AUTHORED 2026-07-16 — `scripts/CLASSIFIER_PRECEDENCE_SPEC.md`.** Read it before writing any 0d code; it carries the corpus measurements, the rules (R1–R7), fixtures, and the implementation order. Headlines that change this plan:
> - **§7's severity ratings do not match the corpus.** #3 (rated HIGH) is **8 products**; #4 (rated MED-HIGH) has **~0 real defects**; the worst defect is the #2 2-active band at **749**, and **503 products violate §10's "reasons are never empty" gate today** (1,776 sit at 0.0 confidence).
> - **RC2 *causes* #2.** Products named "Vitamin B3", "Choline L-Bitartrate 600 mg" (the plan's own cited case), "Pure Collagen Types 1 and 3" have `actives=2, distinct_ids=1` → `general_supplement` @ **0.0 with `reasons=[]`**. `classify_supplement` references `mark_compound_duplicate_rows` **zero** times. Fix RC2 first, then re-measure — it likely collapses a large share of the 503.
> - **#4 electrolyte: DO NOT FIX.** Only 17 candidates exist and they are correctly classified (BCAA/protein/botanical products with adjunct electrolytes). §2's "`electrolyte`=5 is an investigation target" is **not supported** — promoting them would be TRAP 4. `pre_workout` (12) *is* supported: real pre-workouts are absorbed by `multivitamin` via the panel gate.
> - **#5 is not RC2.** 0/346 `single_*`-with-≥2-actives are duplicate rows; all 346 are genuinely multi-identity. This is the Phase 1 driver for `is_single_scorable_active`.
> - **Vocabulary decision: add no new term.** Mineral-only panels affect 8 products; §13's evidence-only rule says do not mint `mineral_complex` for 8. No GLOSSARY change needed.

**Classifier precedence specification (required before 0d code).** Branch reordering alone is not an implementation specification. Add a checked-in decision table/ADR for every affected category with:

- required canonical identity evidence;
- title and DSLD intent evidence, including whether either is required or only corroborating;
- dominance/materiality threshold where an adjunct must not own the product;
- exclusions and higher-priority categories;
- exact output type and reason code;
- at least one positive fixture and one near-miss negative fixture;
- ingredient-order and decorative-row invariance cases.

In particular, an incidental collagen row must not hijack a multivitamin, and three arbitrary minerals must not automatically become an electrolyte. Pure multi-mineral, pure multi-vitamin, and B-vitamin-plus-mineral panels require an explicit vocabulary decision backed by corpus evidence. If a new term is required, add it to `scripts/GLOSSARY.md` first; if evidence is insufficient, retain a reason-coded conservative residual instead of inventing certainty.

### Phase 1 — migrate the formulation scoring split
Replace `supp_type_of()` + `SINGLE_INGREDIENT_SUPP_TYPES` in `generic_formulation.py:421/452/494/608` with the taxonomy-emitted **`is_single_scorable_active`** fact. Modules **consume** the fact; they never rebuild it.

> **✅ COMPLETE 2026-07-16.** All four gates now consume the canonical fact.
> Corpus measurement found 550 legacy-name/fact disagreements: 470 products
> were denied a single floor and 80 were over-credited. Shared fixtures were
> ported to inject the taxonomy fact and exercise real scoring behavior.

### Phase 2 — retire the legacy classifier ✅ one brain

**Entry gate:** RC1 must either be completed under its reviewed row-population
contract or explicitly deferred with a blocking rationale. R5, R6, and R7b must
each have a recorded disposition; they are not one vocabulary decision. Do not
delete the rollback brain while the canonical brain's intended input population
is still undefined.

- Delete `infer_supplement_type()` + its iterator + `supp_type_of()`.
- **Keep the `supplement_type` field/DB column** (`build_final_db.py:1920` — final-DB + dashboard contract) as a **pure mechanical mirror of the taxonomy with no independent logic**. Include canonical counts/reasons in the mirror if compatibility requires.
- **Remove the mirror from enriched artifacts only after every enriched-artifact consumer has migrated.**
- Collapse `resolve_export_supplement_type` (`build_final_db.py:846`) to taxonomy-only; simplify the cosmetic `build_supplement_type_audit` (`:822`).
- **KEEP `mark_compound_duplicate_rows`** (enrich's UL path uses it) and the shared helpers `supplement_taxonomy.py:28` imports from `supplement_type_utils` (`canonical_category`, `PROBIOTIC_TERMS`, `CATEGORY_ALIASES`) — **do not delete that whole file.**
- Delete `shadow_score_comparison.py` (dev tool, zero release references).

**Reader-disposition gate.** Before deleting any legacy helper, record and complete the disposition of every reader found in §6:

| Reader family | Required disposition |
|---|---|
| Seven `score_supplements.py` reads | Migrate each decision/diagnostic to taxonomy fields, structured facts, or the mechanical mirror while v3 remains the live rollback producer. No independent fallback classification. |
| `generic_formulation.py` | Completed in Phase 1: consume `is_single_scorable_active`; remove type-name inference and redundant single-count decisions. |
| `scoring_input_contract.py` and `scoring_v4/router.py` legacy multivitamin fallbacks | Replace with canonical taxonomy plus panel-evidence rules; preserve themed-multivitamin behavior with positive and near-miss tests, then delete the fallback readers. |
| `scoring_v4/confidence.py` | Use structured taxonomy confidence/reason codes. Any old-blob compatibility belongs in an explicit adapter, not the production decision path. |
| `sports_formulation.py` | Remove the legacy type fallback; use canonical taxonomy/profile evidence only. |
| `enrich_supplements_v3.py` | Replace early legacy writes/reads, percentile inference, and completeness checks with taxonomy projection/decorator fields in the dependency order from §5. |
| `build_final_db.py` | Taxonomy-only resolution plus mechanical DB compatibility mirror; no legacy preference/fallback. |
| API audit reports and dashboard | Continue reading the exported DB compatibility column where appropriate; verify they do not make independent classification decisions. |
| Tests/fixtures | Classify as production contract, explicit old-artifact adapter, or obsolete legacy behavior. Port or delete intentionally; never mass-rewrite fixture fields without semantic review. |

The Phase 2 gate is source search + runtime entrypoint/subprocess inventory + focused tests. A zero import count alone is not proof.

🛑 **CHECKPOINT — formal, non-shipping.** Commit and review the **classifier-only audit** (harness output; not a pipeline rebuild). **Never ship or merge a code+artifact combination known to be out of sync.** Proceed only after approval.

### Phase 3 — one scored-artifact assembler (safety-critical)
Build **one deep interface**:
```
build_scored_artifact(enriched_product) -> complete scored artifact
```
It owns: v4 scoring; shared coverage + strict-contract diagnostics; safety/verdict precedence; compatibility projections; the inventoried v3-native fields.

- The Stage-3 **CLI handles only** batch I/O, manifests, atomic writes, failure reporting. **Do not assemble compatibility fields in the CLI** — that just builds a second assembler while removing the first.
- `build_final_db.py` **consumes the artifact directly** instead of overlaying v4 onto a v3 dict (`export_adapter.py:255`).
- **`mapped_coverage`: expose the EXISTING shared result — never re-implement.** Authoritative calc lives in `scoring_input_contract.py`; v4's `gate_completeness.py:192` already consumes it; ownership declared in `scripts/contracts/source_of_truth_matrix.json` (`mapping_coverage_contract`).
- **Inventory all 13 inherited fields BEFORE coding** — table per field: current producer | canonical future owner | downstream consumers | required vs optional | missing/malformed behavior | parity test | retirement condition. Safety verdicts, diagnostics, `score_basis`, strict-contract results, unmapped counts and coverage must **not** hide under "carry 13 fields."
- Add targeted Stage-3 artifact generation over frozen fixtures and representative canaries for every route module, hard safety state, malformed/missing coverage state, and changed classification family. This exercises CLI I/O/manifests and the assembler without a full-corpus rebuild.
- Prove missing/corrupt input, partial output, duplicate IDs, and failed atomic writes return non-zero and cannot leave a promotable manifest.

🛑 **CHECKPOINT before Phase 3 begins** — do not touch the `mapped_coverage` producer without approval.

### Phase 4 — add and repoint the v4 producer; retain v3 for rollback
Order is mandatory:

1. Add the v4 producer.
2. **Verify it on frozen and targeted artifacts**, including exact final-build parity.
3. Repoint Stage 3 (`run_pipeline.py:173`) + `preflight.py:93`.
4. Run a targeted release-path dry run + artifact audits against v4-produced temporary artifacts.
5. Keep `score_supplements.py` present but inactive as a rollback artifact until the single full-corpus v4 rebuild and delta review pass in Phase 5. The production entrypoint and preflight must already point to v4.

The historical `reports/canary_rebuild.py` reference is stale; that file does not exist at the documented baseline. Search live runtime/tool references before cutover and repoint only canaries that actually exist. Do not create a replacement solely to satisfy this old path.

**Classify the ~45 v3 tests — do not bulk port/delete:**

- production-contract tests → **must be ported**
- safety/verdict/export tests → **must pass before v3 deletion**
- obsolete v3 arithmetic tests → may be deleted
- characterization tests → **retain until migration is proven**

A **temporary read-only parity harness** is allowed during migration. It must never choose the shipped result and must be deleted at cutover.

### Phase 5 — single rebuild, approval, v3 deletion, and cleanup

Order is mandatory and preserves the one-rebuild rule:

1. With Stage 3 repointed to v4 **and v3 still present but inactive**, stop and give the user the exact canonical full-rebuild command. The user launches the single 14,193-product rebuild. Do not run it as the agent unless the user explicitly changes this instruction. Wait for the user's completion output, then verify the resulting manifests and artifacts before continuing.
2. Run the complete artifact audits and the hardened drift harness. Require exact product-ID/count parity and generate the complete expected-change ledger.
3. Review safety/status/verdict changes individually. Review score/tier/pillar changes by reason-coded bucket plus named canaries, with every changed product still represented in the machine-readable ledger.
4. Re-freeze only explicitly approved fixture deltas.
5. Delete v3 (`score_supplements.py` drops as a unit), repoint any remaining canary/tool reference, and delete obsolete v3 tests according to their Phase 4 classification. The full rebuild has already proven the v4 producer across the corpus, so deleting the now-inactive file does not require another rebuild.
6. Run `scripts/test.sh fast`, `scripts/test.sh release`, and strict read-only artifact audits against the approved fresh artifacts. Prepare the canonical `release_full.sh` command and its expected gates for the user. Production release/promotion remains user-owned unless explicitly authorized; any code-path or schema failure blocks promotion.
7. Delete `scripts/audits/supptype_drift_preview.py` and any other temporary parity tooling only after cutover acceptance. Complete the dead-code sweep and documentation update in separate cleanup commits.

---

## 10. Hard gates

**Before Phase 0 classifier work:**

- Hardened harness is fail-closed and green on its focused tests.
- Exactly 14,193 unique baseline product IDs are accounted for; no unreadable files, duplicate IDs, or silent omissions.
- Recomputed taxonomy is either identical to the embedded baseline taxonomy or every mismatch is recorded and resolved before baseline freeze.
- The v4 preview matches the production final-build projection on frozen fixtures for every captured field.
- Single-fact-only changes are detected even when `primary_type` is unchanged.
- Structured taxonomy evidence schema/version and reason-code vocabulary are defined before the strict SoT audit consumes them.

**After Phase 2:**

- Every production decision consumer uses the canonical taxonomy.
- Every changed product ID has a **named classification reason code**.
- Ingredient-order changes and decorative rows **cannot** alter classification.
- Compound sibling rows **cannot** turn one active into multiple.
- `general_supplement` reasons are **never empty**. Zero confidence **is** allowed when truthful, but only with an explicit reason code (`no_quantified_active_evidence`), and such products must not silently become scoring-eligible. **No arbitrary confidence increase to satisfy a gate.**

**Before deleting v3:**

- The v4 producer has completed the full 14,193-product rebuild while v3 remained available but inactive.
- Exact product-ID and count parity.
- `mapped_coverage` present, numeric, bounded `[0,1]`.
- The `<0.3` protection remains **fail-closed**.
- Missing or malformed coverage **cannot** produce `SAFE`.
- Safety status / verdict precedence parity.
- Required-field and artifact-schema parity.
- Compatibility-field parity.
- No missing products or silent partial outputs.
- No deprecated `/80` export fields.
- **Per-product expected-change ledger reviewed.**

### Independent review gates already added (2026-07-16)

- The classification contract is now `1.1.0`. The bump is intentional: category
  counts and category-derived decisions now use distinct identities, while raw
  label-row counts are emitted separately as `category_row_breakdown`.
- Strict SoT mode fails closed for missing taxonomy, an unknown input contract,
  missing row evidence, empty/missing reason codes, or a stale contract version.
  It aggregates artifact-wide defects instead of emitting 14,193 duplicates.
- Every decision branch must set a machine reason code. A branch that omits one
  raises `RuntimeError` in development/tests rather than publishing an
  unexplained classification.
- Reversing all ingredient rows across all 14,193 products produces **0** drift
  in primary/secondary type, percentile category, confidence, reasons, reason
  codes, counts, category maps, or row evidence.
- The schema-3 harness captures both identity counts and raw row counts. A
  schema-2 baseline is incompatible by design and must not be coerced or
  silently re-frozen.
- A clean `scripts/test.sh fast` run completed with **10,835 passed, 42 skipped,
  1 strict xfail**. The xfail is the explicitly deferred R7b vocabulary issue,
  not an untriaged failure. A later post-documentation run, immediately after
  two full-corpus score previews, completed 10,834 tests but two unrelated tests
  hit their 120-second timeout; both passed in isolation in 2.29 seconds.
  Focused contract/review suite: 48 passed. Treat the latter as measured host
  resource contention, not as a license to ignore future repeated timeouts.

---

## 11. Expected drift (set expectations)

This consolidation may reroute a material slice of the catalog, but do not assume that all 32 frozen fixtures will drift. The harness must report the observed fixture changes. Expand the fixture set before implementation to cover currently underrepresented/reproduced paths such as collagen, electrolyte, amino-acid blends, multi-mineral panels, and general-supplement residuals.

Review policy:

- **Safety-critical, review individually:** safety status, score suppression, BLOCKED/UNSAFE/CAUTION/SAFE verdict transitions, safety flags, blocking reasons, coverage failures, and any missing/malformed contract result.
- **Quality-critical, review by reason-coded bucket plus named canaries:** score, tier/grade, pillar, module-route, confidence, and transparency/evidence changes.
- **Always machine-complete:** every changed product remains in the per-product ledger even when human review is aggregated. No offsetting aggregate is allowed to hide a missing or unexpected product-level change.

---

## 12. Reference — key file:line anchors

| What | Where |
|---|---|
| Canonical classifier | `supplement_taxonomy.py:502` (`classify_supplement`) |
| Canonical iterator | `supplement_taxonomy.py:1323` (`_iter_classification_rows_v2`) |
| Taxonomy consumes probiotic_data | `supplement_taxonomy.py:666-674` |
| Legacy classifier | `supplement_type_utils.py:233` (`infer_supplement_type`) |
| Legacy reader helper | `generic_helpers.py:196` (`supp_type_of`) |
| Taxonomy reader helper | `generic_helpers.py:211` (`primary_type_of`) |
| The scoring bug | `generic_formulation.py:163, 421, 452, 494, 608` |
| Enrich writers | `enrich_supplements_v3.py:17509, 17524, 17590-17592` |
| Probiotic build (ordering invariant) | `enrich_supplements_v3.py:17585-17589` |
| Percentile inference (3rd brain) | `enrich_supplements_v3.py:14752, 14782, 14802`; called at `17567` |
| SoT audit trap | `audit_source_of_truth_contract.py:63, 839+` |
| v3 invoked by subprocess | `run_pipeline.py:173, 497`; required by `preflight.py:93` |
| v4 overlays the v3 dict | `export_adapter.py:230, 255`; `build_final_db.py:8493, 8503` |
| `mapped_coverage` inherited | `build_final_db.py:8105` |
| `mapped_coverage` true owner | `scoring_input_contract.py`; consumed `gate_completeness.py:192`; declared by `mapping_coverage_contract` in `scripts/contracts/source_of_truth_matrix.json` |
| Export type resolver | `build_final_db.py:846` |
| DB column contract | `build_final_db.py:1920` |
| Snapshot gate | Locate `test_scoring_snapshot_v1.py` invocation in `release_full.sh` and `rebuild_dashboard_snapshot.sh`; symbol/path is authoritative, line numbers drift |
| Freezer | `tests/freeze_contract_snapshots.py <dsld_id>` (one id at a time) |
| Temporary harness (must be hardened in Phase -1) | `scripts/audits/supptype_drift_preview.py` |

**Test runner:** `bash scripts/test.sh fast` (never raw `pytest` — it picks Xcode's Python 3.9 and the ~1 hr heavy suite). Pinned interpreter: `source scripts/python_env.sh` → `$PG_PYTHON`.

**Note (zsh):** unquoted `$VAR` does **not** word-split, and `--include=*.py` gets glob-expanded. Quote globs; use explicit lists in `for` loops.

---

## 13. Working agreement

- **Verify live; never assert from memory.** The repo mutates (parallel Codex sessions).
- **RED first.** Watch the test fail for the *right* reason before implementing.
- **Root cause, never the symptom.** Never weaken a gate to make it pass.
- **Evidence-only vocabulary.** Add a term only when the corpus shows it (a speculative `piece`/`bear`/`worm` addition silently deleted an existing contract assertion).
- **Under-warning carries the highest clinical risk.** Systematic over-warning is still a defect because it reduces usefulness, trust, and signal-to-noise; tolerate it only as an explicit temporary fail-safe with measured scope and a removal condition.
- Iterate against the hardened harness instead of the full pipeline. The baseline classification-only pass was ~33 seconds; score preview may take longer and must report its measured duration rather than inheriting that estimate.
