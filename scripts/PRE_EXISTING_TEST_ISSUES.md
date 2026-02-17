# Pre-Existing Test Issues Report

This document details the 33 test failures that existed **before** the Pipeline Hardening implementation. These are unrelated to the hardening work and represent database coverage gaps and file path issues.

---

## Executive Summary

| Category | Failed Tests | Root Cause |
|----------|--------------|------------|
| Harmful Schema v2 | 7 | Wrong file path (relative vs absolute) |
| ID Redirects | 1 | Missing file `data/id_redirects.json` |
| Ingredient Matching | 25 | Database coverage gaps (missing aliases) |
| **Total** | **33** | |

---

## Issue 1: Harmful Schema v2 Tests (7 failures)

### Symptoms
```
FileNotFoundError: [Errno 2] No such file or directory: 'scripts/data/harmful_additives.json'
```

### Affected Tests
- `test_match_rules_populated`
- `test_references_structured_exists`
- `test_review_metadata`
- `test_jurisdiction_status_codes`
- `test_cui_uniqueness`
- `test_entity_relationships_present`
- `test_missing_match_tokens_report_empty`

### Root Cause
The test file uses a relative path that assumes the current working directory is the repository root:

```python
# tests/test_harmful_schema_v2.py:4
DATA_PATH = Path("scripts/data/harmful_additives.json")  # WRONG
```

But tests are run from `scripts/` directory, so the path should be:
```python
DATA_PATH = Path("data/harmful_additives.json")  # CORRECT
# OR
DATA_PATH = Path(__file__).parent.parent / "data" / "harmful_additives.json"  # ROBUST
```

### Evidence
```bash
$ ls data/harmful_additives.json
data/harmful_additives.json  # File EXISTS at correct location

$ ls scripts/data/harmful_additives.json
ls: scripts/data/harmful_additives.json: No such file or directory
```

### Fix Required
Update `tests/test_harmful_schema_v2.py` line 4:
```python
DATA_PATH = Path(__file__).parent.parent / "data" / "harmful_additives.json"
```

---

## Issue 2: ID Redirects Test (1 failure)

### Symptoms
```
FileNotFoundError: [Errno 2] No such file or directory:
'/Users/.../scripts/tests/../data/id_redirects.json'
```

### Affected Tests
- `test_banned_collision_corpus.py::TestIdRedirects::test_load_id_redirects`

### Root Cause
The test expects a file `data/id_redirects.json` that doesn't exist:

```python
# tests/test_banned_collision_corpus.py:282-286
def test_load_id_redirects(self):
    redirects_path = os.path.join(
        os.path.dirname(__file__),
        '..', 'data', 'id_redirects.json'
    )
    with open(redirects_path, 'r') as f:  # FileNotFoundError
```

### Evidence
```bash
$ ls data/*.json | grep redirect
# (no output - file doesn't exist)
```

### Fix Required
Either:
1. Create `data/id_redirects.json` with the expected schema
2. Mark the test as `@pytest.mark.skip` until the file is created
3. Remove the test if no longer needed

---

## Issue 3: Ingredient Matching Regression (25 failures)

### Symptoms
```
AssertionError: Expected 'nicotinamide_riboside' to match label 'Nicotinamide Riboside 300mg'
Got matches: []
```

### Affected Tests (25 total)
| Label Text | Expected Key | Reason |
|------------|--------------|--------|
| Nicotinamide Riboside 300mg | nicotinamide_riboside | No aliases |
| NMN (Nicotinamide Mononucleotide) 500mg | nmn | No aliases |
| Curcumin Phytosome (Meriva) | curcumin | No aliases |
| Liposomal Curcumin 500mg | curcumin | No aliases |
| Turmeric Root Powder 1000mg | turmeric | No aliases |
| Organic Turmeric Extract | turmeric | No aliases |
| Flaxseed Oil 1000mg | flaxseed | No aliases |
| Organic Flax Oil | flaxseed | No aliases |
| Cold-Pressed Linseed Oil | flaxseed | No aliases |
| Lactobacillus acidophilus 10 Billion CFU | lactobacillus_acidophilus | No aliases |
| Silymarin 80% (Milk Thistle Extract) | silymarin | No aliases |
| Milk Thistle Seed Extract | milk_thistle | No aliases |
| Boswellic Acids 65% | boswellic_acids | No aliases |
| Allicin (from Garlic) | allicin | No aliases |
| 5-HTP (from Griffonia simplicifolia) | 5_htp | No aliases |
| L-Tryptophan 500mg | l_tryptophan | No aliases |
| Acetyl-L-Carnitine HCl | acetyl_l_carnitine | No aliases |
| Quercetin Dihydrate 500mg | quercetin | No aliases |
| Creatine Monohydrate 5g | creatine_monohydrate | No aliases |
| Creatine HCl (Con-Cret) | creatine | No aliases |
| Honokiol 98% | honokiol | No aliases |
| Vitamin K1 (Phylloquinone) | vitamin_k1 | No aliases |
| Methylcobalamin (Vitamin B12) | vitamin_b12_cobalamin | No aliases |
| Inulin (from Chicory Root) | inulin | No aliases |
| Beta-Glucan 250mg | beta_glucan | No aliases |

### Root Cause
**The ingredient database entries lack aliases**, so the matching algorithm can't find them.

**Database entries (current):**
```json
{
  "curcumin": {
    "standard_name": "Curcumin",
    "aliases": []  // EMPTY - no way to match variations
  },
  "nicotinamide_riboside": {
    "standard_name": "Nicotinamide Riboside",
    "aliases": []  // EMPTY
  }
}
```

**Database entries (needed):**
```json
{
  "curcumin": {
    "standard_name": "Curcumin",
    "aliases": [
      "curcumin phytosome",
      "meriva curcumin",
      "liposomal curcumin",
      "curcumin c3 complex"
    ]
  },
  "nicotinamide_riboside": {
    "standard_name": "Nicotinamide Riboside",
    "aliases": [
      "niagen",
      "nr",
      "nicotinamide riboside chloride"
    ]
  }
}
```

### Evidence - Matching Fails

```python
# Test what enricher produces
enricher = SupplementEnricherV3()
product = {
    'id': 'TEST_001',
    'activeIngredients': [{'name': 'Curcumin Phytosome (Meriva)', 'quantity': 500, 'unit': 'mg'}]
}
enriched, issues = enricher.enrich_product(product)

# Result:
# ingredients_scorable: [{'canonical_id': None, 'name': 'Curcumin Phytosome (Meriva)'}]
# The ingredient exists in DB but matching fails because:
# 1. "Curcumin Phytosome (Meriva)" normalized ≠ "curcumin"
# 2. No aliases to match variations
```

### Evidence - Database Has Entries But No Aliases
```bash
$ python3 -c "
import json
with open('data/ingredient_quality_map.json') as f:
    data = json.load(f)
print('curcumin aliases:', data['curcumin'].get('aliases', []))
print('nicotinamide_riboside aliases:', data['nicotinamide_riboside'].get('aliases', []))
"

# Output:
# curcumin aliases: []
# nicotinamide_riboside aliases: []
```

### Fix Required
Populate aliases in `data/ingredient_quality_map.json` for all 25 failing ingredients:

```json
{
  "curcumin": {
    "standard_name": "Curcumin",
    "aliases": [
      "curcumin phytosome", "meriva", "liposomal curcumin",
      "curcumin c3", "curcumin extract", "turmeric curcumin"
    ]
  },
  "turmeric": {
    "standard_name": "Turmeric",
    "aliases": [
      "turmeric root", "turmeric powder", "turmeric extract",
      "organic turmeric", "curcuma longa"
    ]
  },
  "flaxseed": {
    "standard_name": "Flaxseed",
    "aliases": [
      "flaxseed oil", "flax oil", "linseed oil", "linseed",
      "organic flax", "cold-pressed flax"
    ]
  }
  // ... etc for all 25 ingredients
}
```

---

## Summary of Fixes Needed

### Priority 1: Quick Fixes (File Paths)
1. **Fix `test_harmful_schema_v2.py`** - Change line 4 to use absolute path
2. **Create `data/id_redirects.json`** - Or skip the test

### Priority 2: Database Work (Ingredient Coverage)
3. **Add aliases to `ingredient_quality_map.json`** for these categories:

| Category | Ingredients Needing Aliases |
|----------|----------------------------|
| NAD+ Precursors | nicotinamide_riboside, nmn |
| Curcuminoids | curcumin, turmeric |
| Omega-3 Sources | flaxseed |
| Probiotics | lactobacillus_acidophilus |
| Botanical Extracts | silymarin, milk_thistle, boswellic_acids, allicin |
| Amino Acids | 5_htp, l_tryptophan, acetyl_l_carnitine |
| Other | quercetin, creatine_monohydrate, creatine, honokiol, vitamin_k1, vitamin_b12_cobalamin, inulin, beta_glucan |

### Estimated Effort
| Fix | Effort |
|-----|--------|
| File path fixes | 5 minutes |
| id_redirects.json creation | 15 minutes |
| Alias population (25 ingredients) | 2-3 hours |

---

## Verification After Fixes

```bash
# After applying fixes, verify:
python -m pytest tests/test_harmful_schema_v2.py -v
python -m pytest tests/test_banned_collision_corpus.py::TestIdRedirects -v
python -m pytest tests/test_ingredient_matching_regression.py::TestRealLabelCorpus -v

# Expected: All 33 previously failing tests should pass
```

---

## Conclusion

These 33 failures are **pre-existing data quality issues** unrelated to the Pipeline Hardening work:

- **8 failures** are file path/missing file issues (quick fix)
- **25 failures** are database coverage gaps requiring alias population

The Pipeline Hardening implementation is complete and all 58 new tests pass. The pre-existing failures should be addressed as a separate database maintenance task.
