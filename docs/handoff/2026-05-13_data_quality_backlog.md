# Data-quality handoff — 2026-05-13

**Status:** Release-safety architecture is complete and shipped (ADR-0001, P1+P2+P3+P4). Catalog v`2026.05.13.162119` is live on Supabase and bundled into Flutter `main` HEAD `555515a`. The release pipeline produces **0 blocking errors** and **0 authoring warnings** on every clean build.

This document hands off **four real but non-blocking data-quality issues** that were tracked during the release-safety sprint but deferred to dedicated investigations. Each is a meaningful bug — not a cosmetic concern — and each likely affects more products than the current count suggests once the root cause is found.

---

## 2026-05-14 status update — backlog has shrunk substantially

Re-checked against the current build (`scripts/dist/export_manifest.json`,
generated `2026-05-14T09:29:08Z`, catalog `product_count=8414`,
`errors=0`, `warnings=0`):

| Bucket                                  | 2026-05-13 baseline | 2026-05-14 current | Status                  |
| --------------------------------------- | ------------------- | ------------------ | ----------------------- |
| **1. NOT_SCORED products**              | 128                 | **42**             | Still active (67% drop) |
| **2. Filter regression (inactives)**    | 19                  | **2**              | Still active (89% drop) |
| **3. Cleaner classifier (actives→inactive)** | 17             | **0**              | ✅ **CLOSED**           |
| **4. Duplicate-warnings test**          | failing             | **passing**        | ✅ **CLOSED**           |

`excluded_by_gate` total: 164 → 44 (73% reduction).

### What's still open

**Bucket 1 — 42 NOT_SCORED:** all 42 share the identical error signature
(`Batch 3 data integrity gate — mapping/dosage gate failed upstream`).
Identical signature suggests a single root cause likely covers most/all
of them; first action remains "sample one representative dsld_id and
trace through the scoring pipeline to find where it bails."

**Bucket 2 — 2 inactives-dropped:** affected dsld_ids are `327403` and
`329092`, both single-inactive drops. Same
`enhanced_normalizer._process_other_ingredients_enhanced` filter-too-
aggressive root cause as the original 19 — investigation playbook in
Bucket 2 below is still valid.

### What's closed

**Bucket 3 — cleaner classifier:** `excluded_by_gate` shows 0
`DROPPED_AS_INACTIVE` errors and 0 `all raw actives reclassified` errors
against the current 8,414-product build. Fish-oil and single-active
products are now scoring correctly.

**Bucket 4 — duplicate-warnings test:** `test_no_duplicate_warnings`
now passes locally. The test/build dedup key asymmetry was resolved
(either the test was updated or the build's dedup logic tightened —
either way the contract is consistent now).

### Recommended next move

When picking this back up: focus on Bucket 1 (42 entries with identical
signature — highest-yield investigation) followed by Bucket 2's 2
residuals. Buckets 3 and 4 can be closed in the doc with a brief
"closed in commit X" notation when the next pipeline release ships.
The original investigation principles below (no fast patches, trace
ALL representatives, etc.) all still apply.

---

## Engineering principles for this handoff

Before opening any bucket below, please internalize these. They are the same principles that produced the release-safety stack and the banned-substance preflight fix:

1. **No fast patches.** Every fix must address the root cause. Patching symptoms hides the next regression.
2. **No patch-on-patch.** If you find yourself adding an exception to an exception, stop. Refactor the predicate.
3. **No bloat.** Add fields, modules, or flags only when the existing surface genuinely cannot carry the new semantic.
4. **No assumptions.** Verify against the live data before changing logic. The 26-banned-substance bug looked like missing source data; it was actually a thread-through gap. The 22 kidney-disease warnings looked like 22 product issues; they all collapsed to a single data-file rewrite. Always trace ALL representatives before deciding scope.
5. **Best practice, accuracy only.** This is a medical-grade product. A wrong warning is worse than no warning. A missing warning is worse than a confusing one.
6. **Scope discipline.** Each bucket below likely deserves its own commit (or sequence of atomic commits). Don't bundle fixes across buckets.
7. **Document the gap as well as the fix.** Future engineers should understand *why* the bug existed and what invariant the fix restores.
8. **Tests prove invariants, not anecdotes.** Write the test for the medical / architectural rule, then write a regression test for the specific failing product as a canary.

---

## Current state of the deferred work

| Bucket | Type | Count affected (current build) | Blocking? | File / function suspect |
|---|---|---|---|---|
| **NOT_SCORED** | scoring gate | 128 products | No — `excluded_by_gate` | Batch 3 mapping/dosage gate; see `scripts/score_supplements.py` (or equivalent scoring pipeline) |
| **Filter regression: inactives dropped** | cleaner / normalizer | 19 products | No — `excluded_by_gate` | `scripts/enhanced_normalizer.py:_process_other_ingredients_enhanced` |
| **Cleaner classifier: actives → inactive** | cleaner / normalizer | 17 products | No — `excluded_by_gate` | `scripts/enhanced_normalizer.py:_is_nutrition_fact` |
| **Duplicate-warnings test failure** | UX / build emission | ~10 products in test sample | No — test fails but production blob is correct per current dedup | `scripts/tests/test_safety_copy_contract.py:test_no_duplicate_warnings` vs build's `_warning_dedup_key` |

**Important framing:** the "count affected" numbers are what the *current build* surfaces. The root cause may affect a much larger latent population. Examples from the recent sprint:
- The 26 banned-substance errors all turned out to be ONE bug in the resolver→emitter thread, but it could have been masking 100s more if the source data grew.
- The 22 kidney-disease warnings collapsed to ONE entry in `harmful_additives.json`. ALL products containing SHMP (sodium hexametaphosphate) were affected.

Investigate first for breadth, not just for the immediate count.

---

## Bucket 1: 128 NOT_SCORED products

### What this is

Products that the scoring pipeline (Batch 3 data integrity gate) refused to score. Sample error:
> `review_queue: NOT_SCORED verdict — mapping/dosage gate failed upstream; product cannot ship without a coherent score (Batch 3 data integrity gate).`

The gate is correctly refusing to ship products without a coherent score. The question is **WHY** each one failed:

- Real data issue (label has undisclosed dosage, unmappable ingredient name)?
- Pipeline mapping gap (the ingredient SHOULD map but the resolver misses it)?
- Scoring engine bug (mapping succeeded but scorer crashed)?
- Authoring backlog (canonical_id never assigned to a real ingredient)?

128 is ~1.5% of catalog. If it's a pipeline bug, the real fix could be one PR. If it's 128 separate data issues, it's an authoring sprint.

### Where to start

1. **Sample 20 representative dsld_ids** from `scripts/dist/export_manifest.json` → `excluded_by_gate[]` where `error` contains `NOT_SCORED`. Don't pick the first 20 — pick 20 across different brands so you sample the failure space, not one brand's quirks.
2. **For each, trace through the scoring pipeline.** Where exactly does it bail? Capture the scorer's verdict reason. Group by signature.
3. **Bucket the 128 by failure signature.** If 100 share a single signature, focus there first. If they're spread across 50 signatures, you're looking at authoring debt.
4. **Test fixture strategy:** create one synthetic product per signature. Test that the fix produces the expected scored output. THEN re-run the full build and verify the 128 → N drop matches your expectation.

### Files to read first

- `scripts/score_supplements.py` (or whatever the current scoring entry point is)
- `scripts/build_final_db.py:derive_blocking_reason()` — where the NOT_SCORED verdict lands
- `scripts/build_final_db.py:_EXPORT_ERROR_TAXONOMY` — line ~1755, where the `review_queue:` pattern is classified as `excluded_by_gate`
- The scoring config / engine that produces `verdict='NOT_SCORED'`

### What "done" looks like

- Every NOT_SCORED product either ships with a coherent score OR has a documented reason why it cannot ship (insufficient label data, intentional exclusion).
- The `excluded_by_gate` count drops to something defensible (likely <20 products that are genuinely unshippable).
- No fix that simply downgrades the gate severity. The gate exists for a reason: incoherent scores are worse than no score.

---

## Bucket 2: 19 filter regression — inactives silently dropped

### What this is

Products where the raw DSLD label disclosed N inactive ingredients but the blob emits fewer. Sample error:
> `[16202] raw DSLD disclosed 1 real inactive(s) but blob emits 0. Filter regression — inspect enhanced_normalizer._process_other_ingredients_enhanced (Sprint E1.2.4).`

The error message already names the suspected code site: `enhanced_normalizer._process_other_ingredients_enhanced`. Affected dsld_ids include 16202, 178677, 242312, 246330, 268245.

### Why this matters

If an inactive ingredient is silently dropped:
- The product blob is missing a real label-disclosed inactive
- Allergen / harmful_additive / banned_recalled detection on that inactive never runs
- The user might receive a "all-green" safety verdict for a product that contains a flagged inactive

This is a **silent under-protection** failure mode — exactly the class of bug the release-safety system was designed to prevent in storage. We need the same discipline at the cleaner layer.

### Where to start

1. **Pick one product** — e.g. DSLD 16202. Locate its `raw_source_text` for the missing inactive by reading from `/Users/seancheick/Documents/DataSetDsld/...` (raw DSLD JSON) or from the cleaner's input.
2. **Trace `_process_other_ingredients_enhanced`** with that exact input. Find the branch that drops it. Capture the filter predicate.
3. **Determine: should this predicate fire?** Compare with the inactive resolver's behavior in `scripts/inactive_ingredient_resolver.py` — the resolver successfully matches many inactives the normalizer drops. The normalizer's filter is probably too aggressive.
4. **Write a regression test** for each represented dropped ingredient. Use real label text. Assert the cleaner produces the inactive entry.

### Files to read first

- `scripts/enhanced_normalizer.py:_process_other_ingredients_enhanced` (~line 4758, see grep)
- `scripts/inactive_ingredient_resolver.py` (the resolver that successfully matches these later — implicit oracle)
- The raw DSLD JSON for one affected product

### What "done" looks like

- The 19 products' previously-dropped inactives appear in their final blobs.
- A new test pinned in `scripts/tests/` covering at least 3 of the 19 cases as regression guards.
- Probably also a broader audit comparing `len(raw_inactives) vs len(blob_inactives)` across the full catalog — there may be more silent drops not currently flagged.

---

## Bucket 3: 17 cleaner classifier — actives demoted to inactive

### What this is

Products where ALL the raw label's active ingredients were reclassified as inactive by the cleaner. Sample error:
> `[1056] all raw actives reclassified as inactive — likely cleaner classifier bug. raw_actives=5, blob_actives=0, drop_reasons=['DROPPED_AS_INACTIVE']. Investigate enhanced_normalizer._is_nutrition_fact for this product's category/group combo.`

Affected: 1056, 11587, 16040, 20529, 2248, etc.

### Why this matters

A product with `blob_actives=0` cannot be scored, cannot have its actives audited against banned_recalled, cannot show dosage info on its active ingredients. The product effectively becomes inert from the user's perspective — but it might contain real safety-relevant actives that just got mis-classified.

Sample: DSLD 1056 is **GNC Fish Oil**. The raw label had 5 actives. The cleaner classified ALL 5 as inactive. The product ships as if it has no active ingredients — which for a fish oil is medically wrong.

### Where to start

1. **Read `_is_nutrition_fact` in `scripts/enhanced_normalizer.py`** — note the line numbers from `grep`: 1640, 3453, 3522, 4326, 4451, 4557, 4657 (callers) and the def itself.
2. **For DSLD 1056 specifically:** locate the raw label, find the 5 actives, trace `_is_nutrition_fact` on each. The function should NOT match Fish Body Oil / Vitamin E / etc. as "nutrition fact" — those are real label-disclosed actives.
3. **Likely root cause:** the classifier matches on name patterns that overlap with nutrition-panel labels (e.g. "Vitamin E" appears in both ingredient lists and nutrition facts). For fish-oil category products specifically, the classifier needs category-awareness.
4. **Design path:** rather than a name-only classifier, route through ingredient category + product category. A "Vitamin E" entry in a multivitamin's active list ≠ "Vitamin E" in a soft-gel's emulsifier list. The product's `productCategoryName` / `productGroupName` should inform classification.

### Files to read first

- `scripts/enhanced_normalizer.py:_is_nutrition_fact` and all 7 call sites
- DSLD 1056's raw source data (Documents/DataSetDsld/staging/brands/GNC/1056.json or similar)
- The `cleaned` output at `scripts/products/output_GNC/cleaned/cleaned_batch_1.json` — see what made it through

### What "done" looks like

- Real actives are no longer reclassified as inactives in fish-oil / single-active-supplement product categories.
- Regression tests covering at least 3 categories (fish oil, single-ingredient prohormone, single-ingredient herbal extract) that previously failed.
- Audit comparing `raw_actives_count vs blob_actives_count` across the catalog — like Bucket 2, there may be silent demotions not currently caught.

---

## Bucket 4: Duplicate-warnings test (`test_no_duplicate_warnings`)

### What this is

The test `scripts/tests/test_safety_copy_contract.py::test_no_duplicate_warnings` is currently FAILING but **the failure does NOT reflect a literal duplicate in the build output**. The build's `_warning_dedup_key` correctly distinguishes warnings by `matched_rule_id` / `ingredient_name`; the test's `_warning_key` does not.

**Example: DSLD 1005 (GNC Fish Oil with GLA), "4 pregnancy/no_data duplicates" decomposes as:**
- EPA / pregnancy / no_data
- DHA / pregnancy / no_data
- Fish Body Oil / pregnancy / no_data
- Borage Oil / pregnancy / no_data

These are 4 *distinct* per-ingredient warnings. They share severity, condition, and source_rule, but differ by ingredient. The build keeps them — correctly under its current key. The test flags them — also correctly under its narrower key.

### Why this is non-trivial

There are TWO real concerns hiding here:

**(A) UX warning fatigue.** A user opening a fish-oil product seeing 4 separate "insufficient pregnancy data" banners (one per omega-3 ingredient) gets less, not more, useful safety information. They'd prefer ONE consolidated message: "Insufficient pregnancy data for the omega-3 ingredients in this product (EPA, DHA, Fish Body Oil, Borage Oil)."

**(B) Test/build alignment.** Either the test's dedup key is wrong (the build's stricter key is correct, drop the test) OR the build's dedup is too lax (a consolidation step needs to happen post-dedup).

The right answer is probably **a new consolidation primitive** that groups same-rule-different-ingredient warnings under one entry with a `affected_ingredients[]` array. This requires:
- Schema change (warnings get an `affected_ingredients` field)
- Flutter rendering update (banner shows ingredient list)
- Build-side consolidation code path

That's a small sprint, not a 30-minute fix. Until then, the test should be updated to align with the build (and the UX concern documented as separate work).

### Where to start

1. **Confirm the framing.** Read `_warning_dedup_key` (build, line ~1940) and `_warning_key` (test, line ~321 of test_safety_copy_contract.py). The test's key is a strict subset of the build's — that asymmetry is the root cause of the false-positive failure.
2. **Decision:** is "EPA/pregnancy + DHA/pregnancy" a duplicate from the user's perspective, or two distinct warnings? Brainstorm with design before coding.
3. **If duplicate (consolidate):** design the consolidation primitive. Schema field, build code, Flutter render. Test ALL the cases — banned_substance and harmful_additive warnings have similar shape but shouldn't consolidate the same way.
4. **If distinct (separate):** update the test's `_warning_key` to include `matched_rule_id` / `ingredient_name`. Re-run and confirm green.

### Files to read first

- `scripts/build_final_db.py:_warning_dedup_key` (~line 1940)
- `scripts/build_final_db.py:_dedup_warnings` (~line 1995)
- `scripts/tests/test_safety_copy_contract.py:_warning_key` (~line 321)
- `scripts/tests/test_safety_copy_contract.py:test_no_duplicate_warnings` (~line 342)

### What "done" looks like

- Either the test is updated to match the build's correct semantics (10 min fix), OR the build gains a consolidation primitive and the test passes against the consolidated output (sprint-sized).
- Documentation of WHICH path was taken and WHY in this repo's ADRs.
- If consolidation path: Flutter UI design that handles `affected_ingredients[]`.

---

## What NOT to do

- **Don't bypass the gates** by demoting any of these issues to `warnings` or excluding them silently. The gates exist for a reason.
- **Don't add per-product allowlists.** If a fix requires 17 separate exceptions, the predicate is wrong, not the data.
- **Don't refactor adjacent code** while in here. Each bucket above touches a focused code path. Keep changes scoped — separate PRs for separate buckets.
- **Don't trust the affected-count.** A fix that drops 19 to 12 is a partial fix. Investigate why 12 remain.
- **Don't weaken `_validate_banned_preflight_propagation` or `_validate_warning_display_mode_consistency`.** These are the medical-grade gates that catch real safety contract violations. They are correctly strict.

---

## What "fully resolved" looks like (whole-handoff DoD)

When all four buckets are addressed:
- `scripts/dist/export_manifest.json` shows `errors=0`, `excluded_by_gate < 20`, `warnings=0`.
- `pytest scripts/tests/` is fully green against `scripts/dist/` (excluding intentional `pytest.skip` for not-yet-landed sprints).
- The fixes are documented in ADRs and the cleaner / scoring / dedup logic carries inline references to the invariants each function upholds.
- Catalog `product_count` is higher than 8,350 (we'd expect to recover most of the 164 currently excluded products).
- A new audit step (similar to `audit_active_banned_recalled_parity`) exists for: "raw label inactives vs blob inactives", "raw label actives vs blob actives". These should run in CI.

---

## Reference: recent successful fixes (use as templates)

Both completed during the release-safety sprint. Same principles, different scopes:

- **Sprint E1.1.4 banned-substance preflight** (commit `5b43384`) — single thread-through gap in resolver→emitter→blob. 26 products affected, ONE fix at the source, 19 tests.
- **Sprint E1.1.2 kidney-disease warning** (commit `9ebccc1`) — single bad phrase in one harmful_additive entry. 22 products affected, ONE data rewrite + ONE build priority flip, 3 regression tests.

Both fixes used the same investigation pattern:
1. Find ONE representative.
2. Trace from observable failure backwards through the pipeline.
3. Find the layer where the bug *actually* lives (not where the symptom shows).
4. Fix at that layer, not at the symptom layer.
5. Test the invariant, not the anecdote.

Apply the same to each of the four buckets above.
