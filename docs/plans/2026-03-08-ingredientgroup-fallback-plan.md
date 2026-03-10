# IngredientGroup Fallback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a guarded `ingredientGroup` fallback to cleaner mapping so unmapped labels can resolve to DSLD's own canonical ingredient group when the raw label text misses.

**Architecture:** Keep the fallback late in the cleaner mapping chain so direct name matches still win. Use exact normalized `ingredientGroup` matching only, scoped to the cleaner path, and cover it with regression tests on current unmapped labels and representative no-regression cases.

**Tech Stack:** Python, pytest, JSON reference databases

---

### Task 1: Add guarded cleaner fallback

**Files:**
- Modify: `scripts/enhanced_normalizer.py`
- Modify: `scripts/tests/test_clean_unmapped_alias_regressions.py`
- Modify: `scripts/tests/test_pipeline_regressions.py`

**Step 1: Write the failing test**

Add regression cases showing that cleaner mapping resolves via `ingredientGroup` only after direct name lookup misses:

```python
def test_ingredient_group_fallback_maps_current_unmapped_labels(normalizer):
    cases = [
        ("D-Limonene Oil", "Limonene"),
        ("Lime Oil", "Lime"),
        ("Titanium Dioxide color", "Titanium Dioxide"),
    ]
    for name, ingredient_group in cases:
        standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
            name, [], ingredient_group=ingredient_group
        )
        assert mapped is True
        assert standard_name != name
```

Also add no-regression coverage showing a direct name match still wins and the fallback does not override it.

**Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest scripts/tests/test_clean_unmapped_alias_regressions.py scripts/tests/test_pipeline_regressions.py -q -k 'ingredient_group_fallback'
```

Expected: FAIL because `_enhanced_ingredient_mapping()` does not yet accept or use `ingredientGroup` for fallback.

**Step 3: Write minimal implementation**

Update `scripts/enhanced_normalizer.py` so:
- `_enhanced_ingredient_mapping()` accepts an optional `ingredient_group`
- it first tries existing direct name logic unchanged
- on miss, it tries one exact normalized lookup using `ingredient_group`
- inactive/active behavior continues through existing classification logic
- the fallback does not use fuzzy matching and does not replace successful direct matches

**Step 4: Run test to verify it passes**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest scripts/tests/test_clean_unmapped_alias_regressions.py scripts/tests/test_pipeline_regressions.py -q -k 'ingredient_group_fallback'
```

Expected: PASS

**Step 5: Run broader verification**

Run:

```bash
python3 scripts/db_integrity_sanity_check.py --strict
PYTHONPATH=scripts python3 -m pytest scripts/tests/test_clean_unmapped_alias_regressions.py scripts/tests/test_pipeline_regressions.py scripts/tests/test_db_integrity.py -q -k 'not cerevisiae'
```

Expected: integrity clean, targeted suite passes.

**Step 6: Shadow-run the affected slice**

Run:

```bash
python3 scripts/clean_dsld_data.py --input-dir /tmp/ingredientgroup_shadow_raw --output-dir /tmp/ingredientgroup_shadow_out --config scripts/config/cleaning_config.json
```

Compare before/after on:
- `D-Limonene Oil`
- `Lime Oil`
- `Titanium Dioxide color`
- one direct-match control case

**Step 7: Commit**

```bash
git add scripts/enhanced_normalizer.py scripts/tests/test_clean_unmapped_alias_regressions.py scripts/tests/test_pipeline_regressions.py docs/plans/2026-03-08-ingredientgroup-fallback-plan.md
git commit -m "fix: add guarded ingredient group fallback"
```
