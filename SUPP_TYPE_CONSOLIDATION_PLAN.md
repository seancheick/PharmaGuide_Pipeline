# Supplement-Type Consolidation — Implementation Plan

**Status:** approved, scoped, ready for RED-first implementation.
**Branch:** `supp-type-consolidation` @ `aee50d10`, cut from main `e2583594`.
**No production classifier code has been modified yet.** Only a read-only audit harness was added.

> Reviewed across three rounds (Claude 5-agent investigation → Codex round 1 (7 amendments) → Codex round 2/3 (3 prerequisites)). Every fact below with a `file:line` was **verified against live code**, not assumed. Where a claim was later disproven, the correction is recorded rather than deleted — read the **TRAPS** section before touching anything.

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
   67    0.5%  collagen        <-- not credible
   12    0.1%  pre_workout     <-- not credible
    9    0.1%  greens_powder   <-- not credible
    5    0.0%  electrolyte     <-- not credible (Thorne Catalyte is in our own fixture set)
```
Those floor values are the **branch-ordering fingerprint**: `collagen` / `electrolyte` / `greens_powder` / `pre_workout` are effectively unreachable because generic vitamin/mineral and protein branches fire first and cannot emit those types. The products are sitting in the 30% `general_supplement` bucket.

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
- **RC1 (~1.0%)** — `_iter_classification_rows_v2` reads only `ingredients_scorable` (requires `mapped=True`), silently dropping **unmapped-but-dosed** rows that carry `cleaner_row_role="active_scorable"` / `score_eligible_by_cleaner=True`. Clear single-ingredient products become `general_supplement` / 0 actives. *e.g. Nattokinase dsld `294772`, Horsetail `294422`.*
- **RC2 (~1.9%; 21 cross single/multi)** — `classify_supplement` **never calls `mark_compound_duplicate_rows`**, so elemental + compound salt counts as two actives. *e.g. Magnesium Glycinate `315678`, Choline L-Bitartrate `252532`.* (Same family as the tracked elemental/compound bug.)
- **RC3 (~0.26%, reverse — taxonomy is RIGHT)** — the legacy iterator lacks `nested_display_only`/`composition_leaf` exclusion and double-counts EPA+DHA sub-rows. *e.g. Fish Oil `13801`.*
- **7 branch-ordering / coverage bugs** in `classify_supplement` (details §7).

### The routing split (the actual bug)
Everything routes on the **taxonomy** *except* `generic_formulation.py:421/452/494/608`, which gates the **A6 focus bonus, premium-single floor, standard-single floor, and enzyme bonus** on legacy `supp_type_of()` + `SINGLE_INGREDIENT_SUPP_TYPES = {"single","single_nutrient"}` (`:163`; `"single"` is a **dead literal** production never emits). Empirically proven: a magnesium product with one decorative zero-dose row → legacy `targeted` (counts 2) vs taxonomy `single_mineral` (counts 1) → single floor denied → **~5–22 point under-score**. No test guards it (the existing test hard-codes `supp_type="single_nutrient"`).

---

## 4. ⚠️ TRAPS — read before touching anything

Each of these was a real, verified near-miss. They exist because someone (Claude) asserted them wrongly first.

1. **`probiotic_data` MUST precede the taxonomy.** `classify_supplement` consumes `probiotic_data` (`supplement_taxonomy.py:666-674`: `is_probiotic_product`, `total_cfu`, `total_strain_count`). `enrich_supplements_v3.py:17585-17589` carries an explicit comment: *"MUST run AFTER probiotic_data so the NP exemption gate for probiotic strains can fire correctly."*
   ⛔ **Do not move the taxonomy build earlier to solve the percentile-ordering problem.** It starves the CFU gate and breaks the verified Paradise-style guard (Zinc + 5 NP strains with `total_cfu=0` correctly → `single_mineral`, NOT probiotic).

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

## 8. The harness (already built — use it, don't rebuild it)

`scripts/audits/supptype_drift_preview.py` — **TEMPORARY, read-only, DELETE at Phase 5 cutover.** Never selects a shipped result.

```bash
source scripts/python_env.sh
$PG_PYTHON scripts/audits/supptype_drift_preview.py baseline --score   # snapshot BEFORE edits
# ... make classifier changes ...
$PG_PYTHON scripts/audits/supptype_drift_preview.py compare --score
```

Classifies all **14,193** products in **~33 s** (vs ~1 hr pipeline) and reports:
- old → new **confusion matrix**
- **single-vs-multi flips** (these drive the formulation floors / A6)
- which **frozen snapshot fixtures** will drift
- with `--score`: in-process re-score of **only type-changed products** → **grade and VERDICT flips** (the only ones that matter for safety)

`baseline` recomputes with current code before storing, so diffs are **code-vs-code**, never code-vs-stale-blob. Baseline artifact lands in gitignored `scripts/products/reports/`.

**Iterate against the harness. Run the full pipeline exactly once, at the end.**

---

## 9. Phases

Every phase is **RED-first TDD**. Use the harness between iterations.

### Phase 0 — prerequisites, then the classifier

- **0a. Migrate the SoT audit** (`audit_source_of_truth_contract.py:839+`) from the hard-coded `classification_input_source` literal + **prose grepping** to **structured reason codes + canonical row evidence**. **With tests.**
  🔒 *Release-blocking prerequisite — RC1 breaks this gate otherwise.*
- **0b. Retire / reduce `_infer_percentile_category()`** to a **decorator** over the canonical taxonomy result (not an independent decider).
- **0c. Enforce the dependency order** from §5 (ingredient-quality → probiotic → taxonomy → mirror → percentile-from-taxonomy). Respect the `MUST run AFTER probiotic_data` invariant.
- **0d. Classifier fixes** — RC1 (two row populations), RC2 (compound-dup), and the 7 branch-ordering bugs (§7).

**Two row populations (mandatory design).** Classification must see unmapped-but-genuine label-active rows; scoring must reject unresolved identities. **Do not** let the taxonomy consume `get_scoring_ingredients(strict=True)`. Define one shared row contract with two explicit subsets:
- `quantified_label_active_rows` — classification input, **includes unmapped dose-bearing actives**
- `score_eligible_rows` — validated mapped subset used for scoring

The taxonomy must emit at least:
- `quantified_label_active_count`
- `scorable_active_count`
- `is_single_scorable_active`
- `classification_reason_codes` (structured — the SoT gate consumes these)
- stable source paths / row identifiers used in the decision

> **`is_single_scorable_active = true` only when there is exactly one score-eligible active AND no second unresolved quantified active.** Otherwise a product with one mapped + one unmapped active would incorrectly receive single-ingredient bonuses.

### Phase 1 — migrate the last legacy scoring consumer
Replace `supp_type_of()` + `SINGLE_INGREDIENT_SUPP_TYPES` in `generic_formulation.py:421/452/494/608` with the taxonomy-emitted **`is_single_scorable_active`** fact. Modules **consume** the fact; they never rebuild it.

### Phase 2 — retire the legacy classifier ✅ one brain
- Delete `infer_supplement_type()` + its iterator + `supp_type_of()`.
- **Keep the `supplement_type` field/DB column** (`build_final_db.py:1920` — final-DB + dashboard contract) as a **pure mechanical mirror of the taxonomy with no independent logic**. Include canonical counts/reasons in the mirror if compatibility requires.
- **Remove the mirror from enriched artifacts only after every enriched-artifact consumer has migrated.**
- Collapse `resolve_export_supplement_type` (`build_final_db.py:846`) to taxonomy-only; simplify the cosmetic `build_supplement_type_audit` (`:822`).
- **KEEP `mark_compound_duplicate_rows`** (enrich's UL path uses it) and the shared helpers `supplement_taxonomy.py:28` imports from `supplement_type_utils` (`canonical_category`, `PROBIOTIC_TERMS`, `CATEGORY_ALIASES`) — **do not delete that whole file.**
- Delete `shadow_score_comparison.py` (dev tool, zero release references).

🛑 **CHECKPOINT — formal, non-shipping.** Commit and review the **classifier-only audit** (harness output; not a pipeline rebuild). **Never ship or merge a code+artifact combination known to be out of sync.** Proceed only after approval.

### Phase 3 — one scored-artifact assembler (safety-critical)
Build **one deep interface**:
```
build_scored_artifact(enriched_product) -> complete scored artifact
```
It owns: v4 scoring; shared coverage + strict-contract diagnostics; safety/verdict precedence; compatibility projections; the inventoried v3-native fields.

- The Stage-3 **CLI handles only** batch I/O, manifests, atomic writes, failure reporting. **Do not assemble compatibility fields in the CLI** — that just builds a second assembler while removing the first.
- `build_final_db.py` **consumes the artifact directly** instead of overlaying v4 onto a v3 dict (`export_adapter.py:255`).
- **`mapped_coverage`: expose the EXISTING shared result — never re-implement.** Authoritative calc lives in `scoring_input_contract.py`; v4's `gate_completeness.py:192` already consumes it; ownership declared in `contracts/source_of_truth_matrix.json:308`.
- **Inventory all 13 inherited fields BEFORE coding** — table per field: current producer | canonical future owner | downstream consumers | required vs optional | missing/malformed behavior | parity test | retirement condition. Safety verdicts, diagnostics, `score_basis`, strict-contract results, unmapped counts and coverage must **not** hide under "carry 13 fields."

🛑 **CHECKPOINT before Phase 3 begins** — do not touch the `mapped_coverage` producer without approval.

### Phase 4 — verify, then delete v3 (never in one commit)
Order is mandatory:
1. Add the v4 producer.
2. **Verify it on frozen inputs.**
3. Repoint Stage 3 (`run_pipeline.py:173`) + `preflight.py:93`.
4. Fresh release **dry run** + artifact audits.
5. **Only then** delete v3 (`score_supplements.py` drops as a unit — no production module imports it; the §13 AST lock is asserted by tests).
6. Re-freeze **only explicitly approved** deltas.

Also repoint the canary (`reports/canary_rebuild.py:48`).

**Classify the ~45 v3 tests — do not bulk port/delete:**
- production-contract tests → **must be ported**
- safety/verdict/export tests → **must pass before v3 deletion**
- obsolete v3 arithmetic tests → may be deleted
- characterization tests → **retain until migration is proven**

A **temporary read-only parity harness** is allowed during migration. It must never choose the shipped result and must be deleted at cutover.

### Phase 5 — cleanup + the single rebuild
Dead-code sweep; **delete `scripts/audits/supptype_drift_preview.py`**; **one** full rebuild + `release_full.sh` strict gates + snapshot re-freeze with per-drift review.

---

## 10. Hard gates

**After Phase 2:**
- Every production decision consumer uses the canonical taxonomy.
- Every changed product ID has a **named classification reason code**.
- Ingredient-order changes and decorative rows **cannot** alter classification.
- Compound sibling rows **cannot** turn one active into multiple.
- `general_supplement` reasons are **never empty**. Zero confidence **is** allowed when truthful, but only with an explicit reason code (`no_quantified_active_evidence`), and such products must not silently become scoring-eligible. **No arbitrary confidence increase to satisfy a gate.**

**Before deleting v3:**
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

---

## 11. Expected drift (set expectations)

This consolidation re-routes a large slice of the catalog. **All 32 frozen fixtures will likely drift.** Review in **aggregate** (confusion matrix, verdict-flip and grade-flip counts) rather than line-by-line, and **expand the fixture set** to cover newly-reachable types (`collagen`, `electrolyte`, `amino_acid`) — there is currently no frozen baseline for types that were unreachable, i.e. exactly the products being fixed.

The only drift lines that are **safety-relevant** are **verdict flips** and **grade flips**. The harness reports both.

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
| `mapped_coverage` true owner | `scoring_input_contract.py`; consumed `gate_completeness.py:192`; declared `contracts/source_of_truth_matrix.json:308` |
| Export type resolver | `build_final_db.py:846` |
| DB column contract | `build_final_db.py:1920` |
| Snapshot gate | `release_full.sh:503` → `tests/test_scoring_snapshot_v1.py` |
| Freezer | `tests/freeze_contract_snapshots.py <dsld_id>` (one id at a time) |
| Harness | `scripts/audits/supptype_drift_preview.py` |

**Test runner:** `bash scripts/test.sh fast` (never raw `pytest` — it picks Xcode's Python 3.9 and the ~1 hr heavy suite). Pinned interpreter: `source scripts/python_env.sh` → `$PG_PYTHON`.

**Note (zsh):** unquoted `$VAR` does **not** word-split, and `--include=*.py` gets glob-expanded. Quote globs; use explicit lists in `for` loops.

---

## 13. Working agreement

- **Verify live; never assert from memory.** The repo mutates (parallel Codex sessions).
- **RED first.** Watch the test fail for the *right* reason before implementing.
- **Root cause, never the symptom.** Never weaken a gate to make it pass.
- **Evidence-only vocabulary.** Add a term only when the corpus shows it (a speculative `piece`/`bear`/`worm` addition silently deleted an existing contract assertion).
- **Under-warn is the unacceptable direction.** Over-warn is merely annoying.
- Iterate against the **harness** (~33 s), not the pipeline (~1 hr).
