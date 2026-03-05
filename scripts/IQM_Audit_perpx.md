# IQM & Scoring Pipeline — Master Audit Prompt

> **Purpose:** Run this master prompt with Claude Code quarterly (or monthly) to ensure the supplement scoring engine remains the most accurate, clinically rigorous, and schema-complete system in existence.

You are an expert Data Engineer and Clinical Supplement Formulator auditing a supplement scoring pipeline that powers a consumer health app. This is our most critical data quality job—accuracy directly affects health decisions for real users. You must be thorough, evidence-based, and never rush.

## CODEBASE ORIENTATION & PRE-FLIGHT CHECK

**Before you propose any changes, execute this Pre-Flight Codebase Check:**

1. Search the codebase for our normalizer/matching scripts (`scripts/enrich_supplements_v3.py`) to see how ingredient text is matched against `aliases`.
2. Understand that we CANNOT mass-delete aliases just because they have the word "supplement" or look like typos (e.g., "vitamnis a"). These exist to catch bad OCR and poorly formatted labels. Never delete an alias unless it is chemically mapping to the wrong form.
3. Review the test suite (`python -m pytest scripts/tests/`). Understand that ALL 1828+ tests must pass after every single JSON edit.

**Key Files & Constraints:**

- **IQM file:** `scripts/data/ingredient_quality_map.json` — the master ingredient database.
- **Scoring Engine:** `scripts/score_supplements.py` — reads IQM scores to produce final product grades.
- **Scoring Range:** `bio_score` is 0-15. If `natural=True`, `score` = `bio_score` + 3 (max score = 18). If `natural=False`, `score` = `bio_score` (max score = 15). **`bio_score` MUST NOT exceed 15.**
- **UI Notes:** The `notes` field is read directly by the consumer on their phone screen. It must be scientifically accurate but easy to understand.

---

## TASK 1: IQM 5-POINT AUDIT (PRIMARY — ~70% of effort)

Audit EVERY parent in `ingredient_quality_map.json` in batches of 3-4 parents at a time. For each batch, execute the following 5-Point Audit using real-world clinical knowledge and web/medical searches for validation:

### 1. DUPLICATION, ARCHITECTURE & CONSOLIDATION

- **Duplicate/Scattered Parents:** Scan the ENTIRE IQM file for parents that cover the same ingredient but are scattered (e.g., `prebiotics` vs `inulin`). The rule: one ingredient = one parent.
- **Merge Identical Molecules:** Merge forms that are the exact same molecule (e.g., "magnesium glycinate" and "magnesium bisglycinate").
- **Consolidate Formats:** A molecule's bioavailability doesn't change because it's a "powder" vs "tablet". Merge these into the base chemical form. (Exception: Keep liposomal, micellized, or enteric-coated separate).
- **Umbrella vs Specific:** If strain-specific forms exist under an umbrella parent (e.g., `probiotics`) AND under species-level parents (e.g., `lactobacillus_rhamnosus`), merge down to the species-specific parent using the higher `bio_score`.
- **One Unspecified:** Ensure there is only ONE "unspecified" form per parent.

### 2. ALIAS HYGIENE & CONFLICTS

- Ensure no alias overlaps between different forms within the parent.
- Move vague aliases (e.g., "whole bark", "plant extract") to the "unspecified" form.
- Add missing, highly common market aliases, patented brand names (e.g., "BetaTOR", "MagnaPower", "Sharp-PS Gold"), and common misspellings.
- Remove suffix aliases ending in " supplement" ONLY IF you have verified the normalizer safely ignores them. Do not delete OCR typo aliases.

### 3. CLINICAL SCORING & BIOAVAILABILITY

- **Verify with PubMed/NIH:** Is the bioavailability claim backed by human PK data? Find the SYSTEMIC absorption number, not just the intestinal uptake number.
- **Score Formula:** Verify `score = bio_score + (3 if natural else 0)`.
- **Natural Flag:** Verify `natural` is chemically correct. Probiotics/Botanicals = True. Synthetic vitamins and petrochemical-derived amino acids (e.g., generic taurine) = False.
- **Phantom Forms:** Delete "X from food" forms that cannot actually appear on a supplement label, as they inflate scores with false natural bonuses.

### 4. NOTES & OVERCLAIMS (Consumer UI Focus)

- **Rewrite for the Phone UI:** Clean up the `notes` field. Rewrite marketing fluff into objective clinical facts. Example: Instead of "10x better," write "Absorbed via HCP-1 receptors, bypassing standard competitive mineral channels."
- Every non-unspecified form needs an 80+ character note with specific RCT citations, manufacturer/brand identification, and a clear mechanism description.
- **OCR Parsing Fixes:** Look out for and delete string errors in the notes/absorption fields (e.g., weird numbers like "109615" or "759690" which were supposed to be percentages).

### 5. SCHEMA ENFORCEMENT

- Ensure `absorption_structured` strictly contains `value`, `range_low`, `range_high`, `quality`, and `notes` keys. If data is missing, set to `null` rather than omitting the key. Values must be 0-1 (proportion, not percentage).
- `dosage_importance` must be present (Primary=1.5, Secondary=1.0, Trace=0.5).

---

## TASK 2: SUPPORTING DATA FILES AUDIT (~15% of effort)

- **Banned & Recalled:** Search FDA MedWatch/EU RASFF for NEW recalls since the last audit. Update `banned_recalled_ingredients.json`. Verify `legal_status` and `clinical_risk` enums.
- **Harmful Additives:** Read `harmful_additives.json`. Cross-reference with EFSA/FDA updates. Verify severity levels (critical 3.0, high 2.0, moderate 1.0, low 0.5). Ensure consumer UI notes are clean.
- **Top Manufacturers:** Read `top_manufacturers_data.json`. Search for new GMP violations or FDA warning letters. Remove/flag violators.
- **Clinical Studies:** Read `backed_clinical_studies.json`. Search PubMed for new systematic reviews.
- **Absorption Enhancers:** Read `absorption_enhancers.json`. Verify pairings are clinically supported (e.g., piperine + curcumin).
- **Proprietary Blends:** Review `proprietary_blends.json` to ensure the scoring engine accurately detects and maps proprietary blend patterns based on label visibility.

---

## TASK 3: ENRICHMENT & SCHEMA INTEGRITY (~15% of effort)

- **Unmapped Ingredients:** Check for unmapped active ingredients. Determine if they belong to an existing IQM parent (missing alias) or need a new parent.
- **Cross-Parent Alias Collisions:** Run `test_no_cross_ingredient_duplicate_aliases`. Fix unintentional collisions. Intentional cross-parent aliases MUST be added to `ALLOWED_CROSS_ALIASES`.
- **Test Suite Health:** Run `python -m pytest scripts/tests/ -v -x`. ALL tests must pass after every batch edit.

---

## AUDIT WORKFLOW RULES (MANDATORY)

1. **Work in batches of 3-4 IQM parents.**
2. **Launch PubMed research BEFORE making changes.** Never guess a `bio_score`.
3. **Never hand-edit JSON.** Always use Python scripts: `json.load() → modify → json.dump(indent=2, ensure_ascii=False)`.
4. **Run the Test Suite after every batch.** (`python -m pytest scripts/tests/ -x -q`). Do not move to the next batch until tests pass.
5. **Output a Batch Summary** detailing: Form, Old Bio/Score, New Bio/Score, Alias additions, and Clinical Reasoning (with citations).
6. **Wait for my approval ("go ahead")** before moving to the next batch.

Are you ready? Please run the Pre-Flight Codebase Check, scan the IQM JSON to find where we left off (working top-to-bottom), and present your first Proposed Action Plan for the next 3 to 4 parents.
