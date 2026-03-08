# Pipeline Audit Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the confirmed audit defects in the DSLD pipeline without regressing current enrichment or scoring behavior.

**Architecture:** Apply the confirmed fixes in small batches, starting with safety-critical matching and scoring correctness, and protect each change with targeted regression tests. Keep data-only corrections separate from code-path changes so validation failures are easy to localize.

**Tech Stack:** Python, pytest, JSON reference databases

---

### Task 1: Add failing regressions for Batch 1 issues

**Files:**
- Modify: `scripts/tests/test_banned_recall_precision.py`
- Modify: `scripts/tests/test_score_supplements.py`
- Modify: `scripts/tests/test_dosage_golden_fixtures.py`

**Step 1: Write the failing tests**

Add regressions for:
- Ephedra matching on `Mormon Tea`
- `1,3-Butylene Glycol` false-positive suppression
- B0 moderate penalty using max behavior instead of last-write-wins
- B2 allergen penalty deduplication by allergen type
- Folate UL in DFE terms

**Step 2: Run tests to verify they fail**

Run:
`pytest scripts/tests/test_banned_recall_precision.py scripts/tests/test_score_supplements.py scripts/tests/test_dosage_golden_fixtures.py -q`

Expected: new tests fail on current code/data.

### Task 2: Implement Batch 1 code and data fixes

**Files:**
- Modify: `scripts/data/banned_recalled_ingredients.json`
- Modify: `scripts/data/rda_optimal_uls.json`
- Modify: `scripts/score_supplements.py`
- Modify: `scripts/enrich_supplements_v3.py`

**Step 1: Apply minimal fixes**

Implement:
- Remove the `Mormon Tea` self-suppression collision
- Add `1,3-Butylene Glycol` exclusions
- Change B0 moderate penalty logic to order-independent max behavior
- Deduplicate B2 allergen penalties by allergen identity/type
- Add safe regex error handling for denylist patterns
- Preserve diagnostic logging for the snippet extraction fallback
- Correct folate UL values to DFE terms

**Step 2: Run targeted tests**

Run:
`pytest scripts/tests/test_banned_recall_precision.py scripts/tests/test_score_supplements.py scripts/tests/test_dosage_golden_fixtures.py -q`

Expected: all targeted tests pass.

### Task 3: Apply confirmed data-consistency fixes

**Files:**
- Modify: `scripts/data/backed_clinical_studies.json`
- Modify: `scripts/data/clinical_risk_taxonomy.json`
- Modify: `scripts/data/ingredient_quality_map.json`

**Step 1: Correct confirmed inconsistent entries**

Update:
- Longvida, Apigenin, Luteolin, ZyloFresh, Spermidine, BioPerine, Iodine
- `clinical_risk_taxonomy.json` metadata count
- Curcumin enhanced-form `natural` flags

**Step 2: Run data integrity and evidence-related tests**

Run:
`pytest scripts/tests/test_db_integrity.py scripts/tests/test_clinical_schema_compat.py -q`

Expected: pass.

### Task 4: Verify full remediation set

**Files:**
- No additional edits required

**Step 1: Run broader verification**

Run:
`pytest scripts/tests/test_banned_recall_precision.py scripts/tests/test_manufacturer_violation_matching.py scripts/tests/test_score_supplements.py scripts/tests/test_dosage_golden_fixtures.py scripts/tests/test_db_integrity.py scripts/tests/test_clinical_schema_compat.py -q`

Expected: pass.

**Step 2: Summarize deferred items**

Document any still-open policy questions separately:
- DMSA dedupe semantics
- Magnesium UL scoring policy
- Missing banned-substance additions
- user_goal cluster annotation cleanup
