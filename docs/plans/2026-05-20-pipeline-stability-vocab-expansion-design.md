# Pipeline Stability Vocab Expansion Design

Date: 2026-05-20

## Goal

Make product classification and shared vocabularies sturdy enough that each
pipeline stage consumes the same normalized IDs instead of re-inferring the
same concept from label text, legacy `supplement_type`, or ad hoc category
counts.

The immediate clinical-risk driver is routing accuracy. A product routed to
the wrong scoring module can get the wrong dose rubric, wrong confidence
drivers, and wrong final score. The taxonomy layer is now the intended source
of truth for product class; this plan expands that pattern to other repeated
concepts.

## Source-of-Truth Contract

1. `clean` preserves raw label and DSLD source fields.
2. `enrich` computes normalized taxonomy/vocab IDs once and stores them in
   explicit fields.
3. `score`, v4 shadow scoring, and `build_final_db` consume normalized IDs.
4. Downstream stages may use legacy fields only when the normalized taxonomy is
   absent in old batches.
5. Name-keyword fallbacks must be local, documented, and guarded by canary
   tests because they are less reliable than normalized IDs.

## Current Product Taxonomy Status

Implemented:

- `scripts/supplement_taxonomy.py` emits `primary_type`, `secondary_type`,
  `percentile_category`, confidence, reasons, active counts, and category
  breakdown.
- `scripts/data/product_type_vocab.json` is the shared product-type vocab.
- `enrich_supplements_v3.py` writes `supplement_taxonomy`.
- `score_supplements.py`, v4 router, and `build_final_db.py` prefer taxonomy
  when present.

Recent hardening:

- `e43507ea` fixed taxonomy/router boundaries for prenatal DHA, targeted
  products mis-tagged as multivitamins, sleep, probiotic, amino acid, protein,
  greens, electrolyte, and related classes.
- `3cc0f7b6` keeps ALA-only and omega 3-6-9 products out of the EPA/DHA omega
  module unless EPA/DHA is actually disclosed.

## Required Guardrails

Every new shared vocab must ship with:

- A vocab JSON file with stable IDs and metadata.
- A single pipeline stage that owns normalization.
- Raw-to-final propagation tests for at least one real product.
- Unknown/fallback-rate audit thresholds.
- False-positive canaries for the highest-risk lookalikes.
- Documentation of allowed downstream fallbacks for old batches.

## Subprojects

### SP-0: Source-of-Truth Contract

Status: started.

Scope:

- Document this contract.
- Audit every downstream consumer that still uses legacy `supplement_type`,
  `primary_category`, `category_breakdown`, or name-derived categories.
- For each consumer, either migrate to taxonomy or document why it needs a
  lower-level signal.

Exit criteria:

- v4 router uses taxonomy first and only falls back for old batches.
- `build_final_db` exposes taxonomy-driven `primary_category`.
- scoring output preserves taxonomy metadata.
- tests cover taxonomy-vs-legacy disagreement cases.

### SP-1: Product Taxonomy Bugs

Status: mostly complete for current known bugs.

Scope:

- Keep `scripts/tests/test_supplement_taxonomy_bugs.py` as permanent regression
  coverage.
- Add real-catalog canary coverage as new misroutes are discovered.
- Do not weaken taxonomy to make old legacy fields pass.

Remaining recommended additions:

- Positive canaries for collagen, fiber/digestive, and immune-support classes.
- Unknown-rate audit for `general_supplement`.

### SP-2: v4 Adoption Audit

Scope:

- Audit v4 routing, gates, confidence, and module-specific logic for duplicate
  class inference.
- Keep physical-fact overrides only where clinically necessary. Example:
  disclosed EPA/DHA canonical can route omega even if taxonomy is generic.
- Avoid using `category_breakdown.fatty_acid` as a module route. It caused
  false positives for ALA, CLA, GLA, MCT, and lecithin.

### SP-3: Form Factor Vocab

Scope:

- Normalize product form once in enrich.
- Preserve raw form text and normalized `form_factor_id`.
- Score and export consume `form_factor_id`.

High-risk lookalikes:

- gummy vs chewable tablet
- powder vs drink mix
- softgel vs capsule
- liquid oral vs topical/liquid carrier

### SP-4: Ingredient Category Vocab

Scope:

- Normalize ingredient category into stable IDs.
- Keep category separate from functional role, safety role, evidence class, and
  ingredient identity.

Rule:

- `ingredient_category` answers what the ingredient is.
- `functional_role` answers why it is in the product.
- `safety_role` answers whether it affects safety/scoring gates.

### SP-5: Functional Role Vocab

Scope:

- Allow multiple roles per ingredient.
- Include provenance for role assignment.
- Avoid using functional role as ingredient identity.

Examples:

- magnesium: `mineral`, roles may include `electrolyte_support` or
  `sleep_support`
- inulin: `fiber`, role may include `prebiotic_support`

### SP-6: Evidence Grade Vocab

Scope:

- Normalize evidence provenance and confidence separately from product claims.
- Map evidence grade to clinical-study data and audited identifiers.
- Do not infer evidence grade from marketing copy.

## Verification Standard

The minimum verification bundle for each subproject:

```bash
python3 -m pytest scripts/tests/test_supplement_taxonomy.py scripts/tests/test_supplement_taxonomy_bugs.py -q
python3 -m pytest scripts/tests/test_v4_*.py scripts/tests/test_cert_*.py -q
python3 -m pytest scripts/tests/test_build_final_db.py scripts/tests/test_score_supplements.py -q
```

Large full-suite runs are useful but not the only gate. If a full run is slow
or inconclusive, report that honestly and rely on focused suites mapped to the
changed surface.

## Non-Goals

- Do not move implementation truth into `docs/superpowers`.
- Do not create duplicate taxonomy systems in Flutter.
- Do not let downstream modules silently override taxonomy with weaker name
  heuristics.
- Do not collapse ingredient identity, category, function, safety, and evidence
  into one field.
