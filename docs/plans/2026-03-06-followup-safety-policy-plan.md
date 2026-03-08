# Follow-Up Safety Policy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the approved follow-up safety-policy changes without breaking current pipeline behavior.

**Architecture:** Apply compatibility-first changes in small batches. Keep data migrations backward-compatible, protect each batch with failing tests first, and verify affected suites after every change.

**Tech Stack:** Python, pytest, JSON reference databases

---

### Task 1: Write failing regressions for follow-up policy changes

**Files:**
- Modify: `scripts/tests/test_banned_recall_precision.py`
- Modify: `scripts/tests/test_dosage_golden_fixtures.py`
- Modify: `scripts/tests/test_clinical_schema_compat.py`
- Modify: `scripts/tests/test_db_integrity.py` or add focused test file as needed

**Step 1: Add failing tests**

Add regressions for:
- DMSA dedupes to a single banned hit
- Magnesium remains `over_ul` but emits a softer user-facing/scoring path
- Newly added banned substances are present and match correctly
- Iodine evidence fields are internally aligned
- Goal mappings resolve stable IDs and legacy labels

**Step 2: Verify red**

Run:
`pytest scripts/tests/test_banned_recall_precision.py scripts/tests/test_dosage_golden_fixtures.py scripts/tests/test_clinical_schema_compat.py -q`

Expected: the new tests fail on current code/data.

### Task 2: Implement DMSA and banned-substance data updates

**Files:**
- Modify: `scripts/data/banned_recalled_ingredients.json`
- Modify: `scripts/enrich_supplements_v3.py`

**Step 1: Apply minimal implementation**

- Canonicalize DMSA to one row
- Add canonical dedupe for banned hits
- Add new banned substances with conservative aliases and notes

**Step 2: Verify**

Run:
`pytest scripts/tests/test_banned_recall_precision.py scripts/tests/test_banned_matching.py -q`

### Task 3: Implement magnesium caution policy

**Files:**
- Modify: `scripts/rda_ul_calculator.py`
- Modify: `scripts/score_supplements.py` only if needed

**Step 1: Apply minimal implementation**

- Preserve real UL and `over_ul`
- Add magnesium-specific explanatory note
- Use a softer scoring/adequacy path than the generic excessive branch

**Step 2: Verify**

Run:
`pytest scripts/tests/test_dosage_golden_fixtures.py scripts/tests/test_score_supplements.py -q`

### Task 4: Implement iodine and goal-mapping consistency updates

**Files:**
- Modify: `scripts/data/backed_clinical_studies.json`
- Modify: `scripts/data/user_goals_to_clusters.json`
- Modify: any consumer/validator tests required for compatibility

**Step 1: Apply minimal implementation**

- Align iodine evidence fields
- Migrate goal mappings to cluster IDs
- Preserve display labels / legacy compatibility

**Step 2: Verify**

Run:
`pytest scripts/tests/test_clinical_schema_compat.py scripts/tests/test_db_integrity.py -q`

### Task 5: Run broader verification

**Files:**
- No additional edits required

**Step 1: Full targeted verification**

Run:
`pytest scripts/tests/test_banned_recall_precision.py scripts/tests/test_banned_matching.py scripts/tests/test_manufacturer_violation_matching.py scripts/tests/test_score_supplements.py scripts/tests/test_dosage_golden_fixtures.py scripts/tests/test_clinical_schema_compat.py scripts/tests/test_db_integrity.py -q`

Expected: pass.
