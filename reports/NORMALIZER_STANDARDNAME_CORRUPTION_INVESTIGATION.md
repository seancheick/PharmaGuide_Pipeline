# Normalizer `standardName` Corruption — Investigation Report

**Date:** 2026-05-28
**Investigator:** Claude (Opus 4.6)
**Severity:** HIGH — affects user-facing safety warnings on production products
**Status:** Bandaid applied in `build_final_db.py`; root cause in normalizer unresolved

---

## The Bug

The product "Prenatal Multi Organic Berry" (Garden of Life, DSLD ID `235583`) displays a **"High-risk ingredient: Chromium"** warning in the Flutter app. This is wrong — the product contains Chromium(III) (the safe, beneficial supplemental form), not Chromium(VI) (hexavalent, a Group 1 carcinogen).

The label simply says **"Chromium"** — which in supplement context is always Cr(III). No supplement legally contains Cr(VI).

### What the user sees

```
Review before use
  High-risk ingredient: Chromium
  Chromium(VI) is an IARC Group 1 human carcinogen...
```

This is a **false positive** that could cause users to avoid a safe prenatal vitamin.

---

## Root Cause Chain

The corruption flows through **4 systems** before reaching the user:

```
1. Normalizer (enrich_supplements_v3.py)
   Sets standardName = "Chromium (VI) — Hexavalent Chromium" for bare "Chromium"
       |
       v
2. Enricher (_check_banned_substances)
   Has explicit hexavalent guard — CORRECTLY blocks contaminant_data match
   Result: contaminant_data.banned_substances.substances = [] (empty, correct)
       |
       v
3. Build (build_final_db.py :: _resolver_status_in)
   Walks ingredient standardName through banned_recalled alias index
   Finds corrupted standardName matches HM_CHROMIUM_HEXAVALENT (status: high_risk)
   Sets blocking_reason = "high_risk_ingredient"
       |
       v
4. Flutter app (ReviewBeforeUse section)
   Reads blocking_reason + banned_substance_detail → shows warning
```

**The critical failure:** The normalizer corrupts `standardName` at step 1. The enricher's guard at step 2 correctly prevents a contaminant match. But the build's `_resolver_status_in` at step 3 **re-discovers the corrupted standardName** via a different code path and flags it anyway.

---

## The Investigation — How We Got Here

This was not a straightforward debugging session. The bug led through multiple dead ends and false leads across a ~15K-line normalizer, a ~5K-line build script, and the Flutter warning pipeline. Here's the full trace:

### Attempt 1: Is the detail blob failing to load?

Initial hypothesis: the Supabase 402 (storage quota exceeded) was blocking blob fetches, making `blobError = true` and hiding all deep-dive cards. This was **partially correct** — it explained why many cards were missing — but the Chromium warning persisted after the 402 was resolved and blobs loaded successfully.

### Attempt 2: Is it in `harmful_additives.json`?

Searched `harmful_additives.json` for chromium entries. Found none. Dead end — the match isn't coming from the harmful additives system.

### Attempt 3: Found `HM_CHROMIUM_HEXAVALENT` in `banned_recalled_ingredients.json`

The entry exists with:
- `status: "high_risk"`
- `aliases`: "hexavalent chromium", "chromium 6", "Cr(VI)", etc. — all explicitly hexavalent
- `negative_match_terms`: "chromium picolinate", "chromium iii", "trivalent chromium", etc.
- But **bare "chromium" is NOT in the aliases** — so how is it matching?

### Attempt 4: The enricher's `_check_banned_substances` (line 8423)

Read through the 300-line matching function. Found **two guards** that should prevent this:

1. **`negative_match_terms` check (line 8600-8606):** Vetoes matches when the ingredient text contains any negative term. But bare "Chromium" doesn't contain "chromium picolinate" or "chromium iii", so this doesn't fire.

2. **`_has_explicit_hexavalent_chromium_evidence` (line 8657-8663):** Hard-coded guard specifically for `HM_CHROMIUM_HEXAVALENT` — only allows the match if the ingredient text explicitly mentions "hexavalent", "VI", "6+", "chromate", or "dichromate".

Both guards work correctly. The enricher produces **zero contaminant matches** for this product. This was confusing — if the enricher blocks it, where does the warning come from?

### Attempt 5: Check the detail blob

The blob for product 235583 has:
- `banned_substance_detail`: empty
- `top_warnings`: empty (0 entries)
- `contaminant_data`: no chromium match

But the ingredient entry has:
```json
{
  "raw_source_text": "Chromium",
  "name": "Chromium",
  "standardName": "Chromium (VI) — Hexavalent Chromium",
  "standard_name": "Chromium"
}
```

**Two different names!** `standard_name` (from IQM) is correct: "Chromium". But `standardName` (from the normalizer) is wrong: "Chromium (VI) — Hexavalent Chromium".

### Attempt 6: Check the SQLite product row

```sql
SELECT top_warnings, verdict, blocking_reason FROM products_core WHERE dsld_id = 235583
```

Result:
- `verdict: "CAUTION"`
- `blocking_reason: "high_risk_ingredient"` -- THIS IS THE PROBLEM

### Attempt 7: Trace `blocking_reason` in `build_final_db.py`

`derive_blocking_reason()` (line 2713) calls:
1. `has_banned_substance()` → checks `contaminant_matches()` → 0 results → checks `_resolver_status_in()` for "banned" status
2. Falls through to `contaminant_matches()` loop for "high_risk" → 0 results
3. Should return `None` since verdict is "CAUTION"

But somehow `blocking_reason` is set. Re-reading more carefully: `_resolver_status_in` doesn't just check `contaminant_data` — it walks the **ingredient arrays** and checks their `name`, `raw_source_text`, and **`standardName`** against the banned_recalled alias index.

### Attempt 8: The smoking gun

```python
index.get(normalize_text("Chromium"))  # → None (no match)
index.get(normalize_text("Chromium (VI) — Hexavalent Chromium"))  # → HM_CHROMIUM_HEXAVALENT!
```

The corrupted `standardName` matches the index. The `_resolver_status_in` function at line 542 reads `ing.get("standardName")` — which is the hexavalent name set by the normalizer — and finds the banned entry.

### Attempt 9: Try to fix via `negative_match_terms`

First fix attempt: add bare `"chromium"` to `negative_match_terms` in `banned_recalled_ingredients.json`. This broke the test `test_explicit_hexavalent_chromium_still_matches_contaminant_gate` because `_has_negative_match_term` uses **substring matching** — "chromium" is a substring of "hexavalent chromium", so it would veto legitimate matches too. Reverted.

### Attempt 10: Surgical guard in `_resolver_status_in`

Added the same `_has_explicit_hexavalent_chromium_evidence` pattern used by the enricher to the build-side resolver. This checks the **raw label text** (not the corrupted `standardName`) for explicit hexavalent mentions before allowing the match. All 91 tests pass.

---

## Where the Normalizer Goes Wrong

The normalizer (`enrich_supplements_v3.py`, ~15,000 lines) has multiple resolution paths for mapping label text to standard names:

1. **IQM (ingredient_quality_map) lookup** — correct, maps "Chromium" → "Chromium"
2. **Non-scorable index** — built from `banned_recalled_ingredients`, `harmful_additives`, `other_ingredients`, `standardized_botanicals`
3. **ingredientGroup fallback** — uses DSLD's `ingredientGroup` field to resolve when the label text misses
4. **UNII-anchored index** — matches by FDA substance identifier
5. **Token-bounded fuzzy matching** — partial name matching
6. **Product name fallback** — extracts ingredients from product names

The `standardName` is set by whichever path resolves first or last (unclear — multiple paths can overwrite). The non-scorable index (path 2) includes `HM_CHROMIUM_HEXAVALENT`'s `standard_name` as a key. When the normalizer processes bare "Chromium":

- IQM correctly resolves it → `standard_name: "Chromium"`
- But somewhere in the enrichment pipeline, `standardName` gets overwritten to the banned_recalled entry's `standard_name`: "Chromium (VI) — Hexavalent Chromium"

The exact overwrite location is unclear because `standardName` is set in **dozens of places** across the normalizer and enricher (30+ references in `enrich_supplements_v3.py` alone). The `ingredientGroup` fallback path (line 3341-3399) is the most likely culprit — it does an `_exact_ingredient_group_lookup` against the non-scorable index and has `negative_match_terms` support, but the negative terms are substring-based and don't catch bare "chromium" (same issue as Attempt 9).

---

## Scope of Impact — Likely NOT Just Chromium

This bug pattern can affect **any ingredient whose bare name normalizes to match a banned_recalled entry's standard_name or alias**. Candidates to audit:

| Ingredient | Banned Entry | Risk |
|-----------|-------------|------|
| Chromium | HM_CHROMIUM_HEXAVALENT | **CONFIRMED** — active bug |
| Iron | Any iron-related banned entry? | Check if bare "Iron" maps to a toxic iron form |
| Copper | Cupric Sulfate (ADD_CUPRIC_SULFATE)? | Check if bare "Copper" gets corrupted |
| Selenium | Sodium Selenite? | Check organic vs inorganic selenium forms |
| Any mineral with toxic/safe valence states | | General pattern |

**Recommended audit query:**
```python
# Find all products where ingredient.standardName != ingredient.standard_name
# and standardName matches a banned_recalled entry
for product in all_enriched:
    for ing in product['activeIngredients'] + product['inactiveIngredients']:
        std_name = ing.get('standardName', '')
        safe_name = ing.get('standard_name', '')
        if std_name != safe_name and std_name in banned_recalled_standard_names:
            print(f"CORRUPTION: {product['dsld_id']} — {ing['name']}: "
                  f"standardName={std_name}, standard_name={safe_name}")
```

---

## Current State of the Fix

### Applied (bandaid):
**File:** `build_final_db.py`, function `_resolver_status_in` (line 544)

Added a guard that mirrors the enricher's `_has_explicit_hexavalent_chromium_evidence`:
- When the matched entry is `HM_CHROMIUM_HEXAVALENT`, check the **raw label text** (`ing.name` + `ing.raw_source_text`) for explicit hexavalent mentions
- If absent, skip the match
- This prevents the corrupted `standardName` from triggering a false `blocking_reason`

**This is a bandaid, not a fix.** The corrupted `standardName` still propagates into the detail blob. Any downstream consumer that reads `standardName` instead of `standard_name` will see the wrong value.

### NOT fixed:
1. **The normalizer overwrite** — `standardName` is still set to "Chromium (VI) — Hexavalent Chromium" for bare "Chromium" in the enriched data
2. **Other ingredients** — unknown how many other ingredients have the same `standardName` corruption pattern
3. **`standardName` vs `standard_name` duality** — the blob has BOTH fields with DIFFERENT values, which is a data contract violation

---

## Recommendations for the Proper Fix

### 1. Audit all `standardName` corruptions

Run the audit query above against the full enriched dataset. Produce a list of every product/ingredient where `standardName` diverges from `standard_name` and the divergent value matches a banned_recalled entry. This tells you the scope.

### 2. Fix the normalizer's resolution priority

The IQM should be the **authoritative** source for active ingredients. If the IQM maps "Chromium" → "Chromium", no other resolution path should overwrite `standardName` to a banned_recalled entry's name. The fix:

```python
# Pseudocode: in the normalizer's resolution chain
if iqm_result and iqm_result.mapped:
    standardName = iqm_result.standard_name
    # LOCK — do not allow banned_recalled or non-scorable paths to overwrite
elif banned_recalled_result:
    # Only set standardName if no IQM match exists
    standardName = banned_recalled_result.standard_name
```

The current code has no clear priority hierarchy — whichever path runs last wins.

### 3. Unify `standardName` and `standard_name`

The blob should not have two fields with the same semantic purpose and different values. Either:
- **Option A:** Drop `standardName` from the blob entirely, use only `standard_name` (from IQM)
- **Option B:** Make `standardName` always equal `standard_name` at blob-build time
- **Option C:** Rename to make the semantic difference explicit if they truly serve different purposes

### 4. Add `negative_match_terms` support with exact-match mode

The current `_has_negative_match_term` uses substring matching, which makes it impossible to add bare mineral names as negative terms without blocking legitimate matches. Add support for:

```json
"negative_match_terms": [
  "chromium picolinate",
  {"term": "chromium", "match_mode": "exact"}
]
```

Where `exact` means the entire ingredient name must equal the term (not just contain it as a substring).

### 5. Add regression test for the specific bug

```python
def test_bare_chromium_not_flagged_as_hexavalent():
    """Bare 'Chromium' on a supplement label is Cr(III), never Cr(VI)."""
    enriched = build_enriched_product(ingredients=[{"name": "Chromium"}])
    assert enriched['activeIngredients'][0]['standardName'] != "Chromium (VI) — Hexavalent Chromium"
    assert derive_blocking_reason(enriched, scored) != "high_risk_ingredient"
```

### 6. Centralize the resolution chain

The normalizer has **6+ resolution paths** that can each set `standardName`. There's no single function that determines the final value — it's set and potentially overwritten across hundreds of lines. This is the architectural root cause.

Proposed refactor: create a single `resolve_standard_name()` function with an explicit priority chain:

```python
def resolve_standard_name(raw_name, ingredient_group, iqm, banned_recalled, ...):
    """Single entry point for standardName resolution.
    
    Priority (highest to lowest):
    1. IQM exact match
    2. IQM alias match
    3. Standardized botanicals
    4. Other ingredients DB
    5. ingredientGroup fallback (with negative_match_terms)
    6. banned_recalled (ONLY if raw text explicitly matches)
    
    Once resolved at a given priority, lower priorities cannot overwrite.
    """
```

This would eliminate the spaghetti overwrite pattern and make the resolution deterministic and auditable.

---

## Files to Investigate

| File | Lines | What to look at |
|------|-------|-----------------|
| `scripts/enrich_supplements_v3.py` | ~15,000 | `standardName` assignment (30+ locations). Non-scorable index build (line 1223). ingredientGroup fallback (line 3341). `_check_banned_substances` hexavalent guard (line 8657). |
| `scripts/enhanced_normalizer.py` | ~3,400 | `negative_match_terms` usage (line 3350). ingredientGroup lookup. |
| `scripts/build_final_db.py` | ~5,200 | `_resolver_status_in` (line 514) — where the bandaid was applied. `derive_blocking_reason` (line 2713). `contaminant_matches` (line 492). |
| `scripts/data/banned_recalled_ingredients.json` | N/A | `HM_CHROMIUM_HEXAVALENT` entry (line 17386). |
| `scripts/data/ingredient_quality_map.json` | N/A | `chromium` entry — correctly maps to "Chromium". |

---

## How to Verify the Fix Worked

After fixing the normalizer:

```bash
# 1. Re-enrich Garden of Life
python3 scripts/enrich_supplements_v3.py --brand Garden_of_life

# 2. Check the enriched output
python3 -c "
import json, glob
for f in glob.glob('scripts/products/output_Garden_of_life_enriched/enriched/*.json'):
    with open(f) as fh:
        data = json.load(fh)
    for p in (data if isinstance(data, list) else [data]):
        if str(p.get('dsld_id','')) == '235583':
            for ing in p.get('activeIngredients',[]):
                if 'chrom' in ing.get('name','').lower():
                    assert ing['standardName'] == 'Chromium', f'STILL CORRUPTED: {ing[\"standardName\"]}'
                    print('PASS: standardName is correct')
            break
"

# 3. Rebuild and verify the DB
python3 scripts/build_all_final_dbs.py
python3 -c "
import sqlite3
db = sqlite3.connect('scripts/dist/pharmaguide_core.db')
row = db.execute('SELECT blocking_reason FROM products_core WHERE dsld_id = 235583').fetchone()
assert row[0] is None, f'STILL FLAGGED: blocking_reason={row[0]}'
print('PASS: blocking_reason is None')
"

# 4. Run full test suite
python3 -m pytest scripts/tests/ -k "chromium or banned_match or hexavalent" -x
```
