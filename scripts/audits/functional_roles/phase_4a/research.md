# Phase 4a — flag-based suppression of retire + move-to-actives entries

**Date:** 2026-04-30 | **Schema bump:** other_ingredients.json 5.1.0 → 5.2.0

## What changed

Added two boolean flags to `other_ingredients.json` entries:

| Flag | Count | Purpose |
|---|---|---|
| `is_label_descriptor: true` | **89** | Label-noise entries (marketing copy, source descriptors, phytochemical markers, generic descriptors). Not real ingredients — should never render as chips. |
| `is_active_only: true` | **117** | Entries that will physically relocate to the active-ingredient pipeline in V1.1 (botanical_extract, glandular_tissue, branded complexes, amino_acid_derivative, phytocannabinoids, marine extracts). Suppress from inactive section meanwhile. |

Both flag classes are derived deterministically from `categorize.py` action types (`retire` / `move_to_actives`). Mutually exclusive — no entry has both.

## Pipeline plumbing

`scripts/build_final_db.py:2272` — added a single guard at the top of the `inactive_ingredients[]` build loop:

```python
if other_ref.get("is_label_descriptor") or other_ref.get("is_active_only"):
    continue
```

Net effect: when a product's `inactiveIngredients[]` contains a flagged entry, the Flutter blob's `inactive_ingredients[]` array silently skips that row. The user never sees "AGELOSS_FACTOR_DESCRIPTOR" or "BioCell Collagen Complex" rendered as a chip in the inactive section.

## Why flag-based, not deletion?

- **Ingredient resolution still needs these entries** — the cleaner/enricher uses them to identify label phrases like "Standardized to 50% Curcuminoids" and route them away from active scoring. Physical deletion would break that.
- **Flags are reversible** — if the V1.1 attribute layer changes how a category is treated, we just unset the flag. Deletion is one-way.
- **Schema still consistent** — entries keep their `id`, `aliases`, `category`, `notes`, etc. Only the visual surfacing in the Flutter blob is suppressed.

## Why not just check `category` directly in build_final_db?

We could, but:
- Categories are about to be canonicalized in Phase 4b (collapse 241 → ~30). Flags are a stable contract that survives the rename.
- Flags read better in the data file (semantic intent) than category-string matching (incidental classification).
- Future entries added with new categories don't need code changes — `categorize.py` is the single source of truth.

## Coverage post-Phase 4a

| Outcome | Count |
|---|---|
| Populated functional_roles[] (will render chips) | 466 |
| `is_label_descriptor: true` (suppressed) | 89 |
| `is_active_only: true` (suppressed) | 117 |
| Manual review (NHA_GLYCOLIPIDS — neither flag) | 1 |
| **Total entries** | **673** |

Flutter user-visible inactive entries: max **466 / 673 = 69%** (down from "every excipient row potentially shown" before — Phase 4a removes 31% of label noise from the user UI).

## What's deferred

- **Phase 4b (next):** category canonicalization (rename 241 → ~30 values per clinician table 2B). Cosmetic, no scoring impact.
- **Phase 4c (V1.1, deferred):** physical removal of `additive_type` field. Requires migrating internal `ADDITIVE_TYPES_SKIP_SCORING` set in `enrich_supplements_v3.py` to `FUNCTIONAL_ROLES_SKIP_SCORING`. Touches scoring logic — needs full regression battery and is out of scope for V1.

## Verification

- [x] 89 + 117 = 206 entries flagged (matches categorize.py output)
- [x] No entry has both flags (mutually exclusive invariant)
- [x] Flagged entries all have `functional_roles=[]` (Phase 3 backfill consistency)
- [x] Unflagged entries (excluding NHA_GLYCOLIPIDS) all have populated roles
- [x] `resolve_other_ingredient_reference` surfaces both flags to build_final_db
- [x] Integrity gate: 0 findings
- [x] 36 tests pass (7 Phase 4a + 22 Phase 3 batch tests + contract tests)
