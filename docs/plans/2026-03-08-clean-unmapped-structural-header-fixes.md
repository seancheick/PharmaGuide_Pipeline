# Clean Unmapped Structural Header Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix clean-stage false unmapped records caused by structural inactive headers, punctuation/modifier normalization gaps, and verified same-ingredient alias/form misses without stripping real ingredient identities.

**Architecture:** Keep the solution narrow and evidence-based. First add regression tests for the raw-validated cases. Then extend clean-stage structural-header extraction for container rows with child forms, add conservative normalization helpers for apostrophes/comma-modifier variants/known typo headers, and only then add true alias/form mappings for verified same-ingredient cases.

**Tech Stack:** Python, pytest, JSON reference DBs, DSLD cleaner/enricher pipeline.

---

### Task 1: Add failing regression tests for structural inactive headers

**Files:**
- Modify: `scripts/tests/test_pipeline_regressions.py`
- Modify: `scripts/tests/test_clean_unmapped_alias_regressions.py`
- Reference: `scripts/enhanced_normalizer.py`

**Step 1: Write failing tests for structural header detection**
- Add tests for `_is_label_header()` or a new structural-header helper covering:
  - `Soft Gel Shell`
  - `Shell Ingredients`
  - `Fish Gelatin Caplique Capsule`
  - `Gelatin softgel`
  - `May also contain`
  - `Mineral Enzyme Acivators` must not be treated as a real ingredient container if it has nested children

**Step 2: Write failing tests for header unwrapping**
- Add tests that `otheringredients` rows with `forms[]` unwrap child forms and do not emit the parent label as an unmapped ingredient.
- Cover raw-like shapes for:
  - `Soft Gel Shell -> [Annatto, Beef Gelatin, Glycerin, Titanium Dioxide, Water]`
  - `Shell Ingredients -> [Gelatin, purified Water, Vegetable Glycerin]`
  - `May also contain -> [Cellulose, Silica]`

**Step 3: Run targeted tests to see failures**
Run:
```bash
python3 -m pytest scripts/tests/test_pipeline_regressions.py -q
```
Expected: failures for new structural-header cases.

### Task 2: Add failing regression tests for normalization gaps

**Files:**
- Modify: `scripts/tests/test_clean_unmapped_alias_regressions.py`
- Reference: `scripts/enhanced_normalizer.py`
- Reference: `scripts/tests/test_scorable_classification.py`

**Step 1: Write failing tests for punctuation/variant normalization**
- Add tests showing clean-stage mapping succeeds for:
  - `Cat’s Claw (Uncaria tomentosa) extract`
  - `Deep Sea Fish Oil, Purified`
  - `Pumpkin Seed Oil, Cold-Pressed`
  - `St. John’s Bread`
  - `Brewer’s Yeast`

**Step 2: Write failing tests for form alias handling**
- Add tests showing:
  - `L-Methylfolate Calcium Salt` maps under folate/5-MTHF form logic
  - `Deep Sea Fish Oil, Purified` maps as fish oil inactive identity
  - `DL-Malic Acid` maps as a real inactive ingredient, not skipped

**Step 3: Run targeted tests to see failures**
Run:
```bash
python3 -m pytest scripts/tests/test_clean_unmapped_alias_regressions.py -q
```
Expected: failures for newly added cases.

### Task 3: Implement structural-header extraction fixes in the cleaner

**Files:**
- Modify: `scripts/enhanced_normalizer.py`
- Modify: `scripts/constants.py` only if new constant-based labels are needed

**Step 1: Add a narrow structural-header helper**
- Introduce a helper that identifies inactive container/header rows that are not ingredients themselves but may contain useful `forms[]` children.
- Include exact or conservative pattern-based support for verified raw labels only.

**Step 2: Route structural headers through the existing form-unwrapping path**
- Update `_process_ingredients_parallel()` and `_process_ingredients_sequential()` to treat those headers like existing label headers.
- Preserve children.
- Do not emit the parent container row.

**Step 3: Preserve real shell materials**
- Ensure child forms such as `Gelatin`, `Beef Gelatin`, `Glycerin`, `Water`, `Cellulose`, `Silica`, `Titanium Dioxide` still survive as inactive ingredients.

**Step 4: Verify no accidental skip of real ingredients**
- Keep logic restricted to the verified structural labels and child-bearing rows.

### Task 4: Implement conservative normalization improvements

**Files:**
- Modify: `scripts/enhanced_normalizer.py`
- Possibly modify the matcher/helper used by the cleaner if normalization belongs there

**Step 1: Normalize curly apostrophes and similar punctuation safely**
- Ensure curly apostrophes normalize consistently to straight apostrophes for matching.
- Do not drop important tokens.

**Step 2: Handle comma-modifier inactive variants conservatively**
- Support cases like:
  - `Deep Sea Fish Oil, Purified`
  - `Pumpkin Seed Oil, Cold-Pressed`
- Reuse existing matching behavior where possible instead of broad fuzzy expansion.

**Step 3: Add typo-tolerant matching only for verified structural labels**
- Handle `Mineral Enzyme Acivators` as the known typo of `Activators`.
- Do not introduce broad edit-distance behavior globally.

### Task 5: Add verified alias/form mappings for true ingredient gaps

**Files:**
- Modify: `scripts/data/ingredient_quality_map.json`
- Modify: `scripts/data/other_ingredients.json`
- Use Python JSON round-trip, not hand-editing.

**Step 1: IQM alias/form additions**
- Add only the verified same-ingredient mappings from raw/clean investigation, such as:
  - `L-Methylfolate Calcium Salt`
  - `Cat’s Claw (Uncaria tomentosa) extract`
  - any remaining verified fish-oil modifier variants not solved purely by normalization

**Step 2: OI additions**
- Add true inactive ingredients like `DL-Malic Acid` if not already represented.
- Do not add structural headers as OI parents.

### Task 6: Verify safety routing remains correct

**Files:**
- Reference: `scripts/enhanced_normalizer.py`
- Reference: safety DBs

**Step 1: Confirm `Delta-8` remains a safety-route case**
- Ensure the cleaner does not accidentally downgrade it into OI handling.

### Task 7: Run verification

**Files:**
- No file changes

**Step 1: Run targeted tests**
```bash
python3 -m pytest scripts/tests/test_pipeline_regressions.py scripts/tests/test_clean_unmapped_alias_regressions.py scripts/tests/test_scorable_classification.py -q
```

**Step 2: Run integrity checks**
```bash
python3 scripts/db_integrity_sanity_check.py --strict
```

**Step 3: Spot-check cleaner behavior**
- Re-run small direct checks in Python for the validated cases.
- Confirm parent headers no longer appear unmapped while child forms remain present.

**Step 4: Summarize residual items**
- Separate any remaining unmapped records into:
  - true DB additions still needed
  - safety routes
  - residual parser bugs
