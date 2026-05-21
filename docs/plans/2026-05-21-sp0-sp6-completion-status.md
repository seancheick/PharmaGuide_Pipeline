# SP-0 → SP-6 Completion Status

Date: 2026-05-21

This document captures the final state of the vocab/stability sub-projects
that started 2026-05-20 with the SP-0 design doc
(`2026-05-20-pipeline-stability-vocab-expansion-design.md`).

## TL;DR

All seven sub-projects (SP-0 through SP-6) are shipped to `main` on both
the pipeline repo and the Flutter repo. Pipeline is ready for fresh DSLD
batch runs.

Final verification (lean targeted bundle + full regression sweep):

| Suite | Count | Time |
|---|---|---|
| SP-0..SP-6 audit + readiness (22 test files) | 334 | 0.9 s |
| Full v4 + cert + b5 + build_final_db + score + evidence ecosystem | 1,269 | 5.4 s |
| **Total** | **1,603 pass, 0 fail, 90 skipped** (real-catalog canaries awaiting fresh batches) | |

## Sub-project status

### SP-0 — Source-of-truth contract
Status: ✅ Shipped (b5d0a249).
- Design doc: `docs/plans/2026-05-20-pipeline-stability-vocab-expansion-design.md`
- Locks the rule: `enrich` computes normalized vocab IDs once; downstream
  stages consume them; legacy fields only fallback for old batches.

### SP-1 — supplement_taxonomy (product class)
Status: ✅ Shipped (5996e720, e43507ea, 3cc0f7b6, 544ec50a).
- Vocab: `scripts/data/product_type_vocab.json` (20 IDs)
- Classifier: `scripts/supplement_taxonomy.py`
- Flutter: `product_type_vocab.dart` + VocabRegistry getter `productType(id)`
- 27 contract tests + 11 bug-regression tests
- Enricher writes `primary_type` + `supplement_taxonomy` per product

### SP-2 — v4 taxonomy adoption
Status: ✅ Shipped (033cdb68, c8a453b2, 897a6c3e).
- Inventory: `scripts/audits/sp2_adoption/INVENTORY.md`
- Audit script: `scripts/audits/sp2_adoption_audit.py`
- Killed the v4 parallel B5 classifier — `_b5_class_for_product` now
  delegates to `scoring_v4.router.class_for_product`
- v3 scorer migrated: `_b5_class_for_product` + `_resolve_percentile_category`
  read taxonomy first
- Adoption regression test locks the inventory baseline (22 real code reads)

### SP-3 — form_factor canonical vocab
Status: ✅ Shipped (586b98d3, d155d348, 4a2b6e75, a56493aa, d94d7b1f).
- Vocab: `scripts/data/form_factor_vocab.json` (18 canonical IDs)
- Normalizer: `scripts/form_factor_normalizer.py`
- Enricher writes `form_factor_canonical` per product (softgel finally
  distinct from capsule)
- Consumers (completeness gate, multi/prenatal formulation, build_final_db)
  read canonical-first with legacy fallback
- Flutter: `form_factor_vocab.dart` + VocabRegistry getter `formFactor(id)`

### SP-4 — ingredient_category canonical vocab
Status: ✅ Shipped (0b380700, 03a38d57, 7249713b, bcdb265).
- Vocab: `scripts/data/ingredient_category_vocab.json` (17 canonical singular IDs)
- Normalizer: `scripts/ingredient_category_normalizer.py`
- `supplement_type_utils.canonical_category()` is now a thin wrapper —
  the hardcoded CATEGORY_ALIASES map is no longer the source of truth
- Cross-stage canary locks that plural/singular/mixed-case all collapse
  to the same canonical id
- Flutter: `ingredient_category_vocab.dart` + VocabRegistry getter
  `ingredientCategory(id)`

### SP-5 — functional_roles canonical vocab (LOCKED v1.0.0)
Status: ✅ Shipped (12a969ec, 2a42d69).
- Vocab: `scripts/data/functional_roles_vocab.json` (32 LOCKED clinician-signed roles)
- Already used by `harmful_additives.json`, `other_ingredients.json`,
  `botanical_ingredients.json`
- SP-5 added: Flutter Dart loader + VocabRegistry getter `functionalRole(id)`
- Canonical-ID enforcement test locks that data files reference only
  vocab IDs (no enricher / scorer can invent off-vocab roles)

### SP-6 — evidence_grade (three locked vocabs)
Status: ✅ Shipped (6fe5747e, 800a446).
- `evidence_level_vocab` (5 study-design tiers)
- `evidence_strength_vocab` (6 qualitative tiers)
- `study_type_vocab` (7 study types)
- All three LOCKED, clinician-signed, with per-vocab contract tests
  pre-dating SP-6.
- SP-6 added: canonical-ID enforcement across data files, PMID/NCT
  provenance audit, Flutter Dart loader parity check, v4
  anti-redefinition guard.

## Layer separation (the SP-0 rule)

Each axis is answered by exactly one canonical vocab:

| Axis | Vocab | What it answers |
|---|---|---|
| Product class | `supplement_taxonomy` (SP-1) | WHICH class of product |
| Physical state | `form_factor_vocab` (SP-3) | HOW it's delivered |
| Ingredient identity | `canonical_id` / IQM parent | WHO it is |
| Ingredient category | `ingredient_category_vocab` (SP-4) | WHAT it is |
| Functional role | `functional_roles_vocab` (SP-5) | WHY it's in the product |
| Safety role | `banned_status` / `clinical_risk` | Is it safe |
| Evidence (study design) | `evidence_level_vocab` (SP-6) | How strong is the study |
| Evidence (qualitative) | `evidence_strength_vocab` (SP-6) | How established is the rule |
| Evidence (study type) | `study_type_vocab` (SP-6) | What kind of study |
| IQM parent UI label | `iqm_category_vocab` | Display only |

No vocab does two jobs. No layer has two competing canonical forms.

## Pipeline readiness for fresh DSLD batches

Verified end-to-end via `scripts/tests/test_pipeline_readiness_e2e.py`
(9/9 pass in 0.14 s) and import smoke test of every pipeline module:

```
✅ clean_dsld_data
✅ enrich_supplements_v3      (writes primary_type + form_factor_canonical)
✅ score_supplements           (reads taxonomy.primary_type, percentile_category)
✅ build_final_db              (reads form_factor_canonical, supplement_taxonomy)
✅ supplement_taxonomy
✅ form_factor_normalizer
✅ ingredient_category_normalizer
✅ supplement_type_utils       (canonical_category() vocab-driven)
✅ scoring_v4.router           (taxonomy-first)
✅ score_supplements_v4_shadow (delegates to router)
```

Verified raw-DSLD-shape handling: every DSLD `physicalState.langualCode`
(uppercase or lowercase) maps to the correct `form_factor_canonical`; every
plural / singular / mixed-case category string canonicalizes deterministically.

When the fresh batches arrive at `/Users/seancheick/Documents/DataSetDsld/`
and you run:

```bash
python3 scripts/run_pipeline.py --raw-dir <fresh_dir>
```

…the pipeline will:

1. **Clean** preserves DSLD physicalState/productType/ingredientRows shape
2. **Enrich** writes `primary_type`, `supplement_taxonomy`, `form_factor_canonical`,
   canonicalized per-row `category` (via vocab-driven `canonical_category`)
3. **Score (v3)** reads taxonomy `primary_type` for B5 + percentile cohorts
4. **v4 shadow scorer** routes by taxonomy, scores against the 4 v4 modules
5. **build_final_db** exports canonical form_factor + primary_type into
   products_core columns
6. **Flutter** reads everything via VocabRegistry — no second source of truth

If any stage fails, the readiness test gives a near-instant smoke check
and the per-vocab sync tests catch silent drift.

## Test discipline change (Sean's directive 2026-05-21)

Switched from "run full v4 sweep after every commit" to "run targeted
per-task tests during development, full sweep ONCE at end of arc."
Per-task tests are ~0.1–0.3 s; the full sweep is ~5 s. Saves ~30 min
per multi-commit sub-project.

## What's NOT done (intentional non-scope)

Per the SP-0 design doc, the following are deferred to future sprints:

- **brandName → brand_name** canonical rename (3 parallel copies across stages)
- **serving_basis vs servingSizes** dual-path reconciliation
- **scorer supp_type unification** — v3 scoring math still uses some legacy
  type values; the taxonomy primary_type is read at the routing boundary,
  not in the scoring math. Future sprint can map primary_type values to
  scoring behavior.

These are documented as v1.1 follow-ups.
