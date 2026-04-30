# Phase 4b — `harmful_additives.json` category canonicalization

**Date:** 2026-04-30 | **Schema bump:** 5.2.0 → 5.3.0
**Source:** CLINICIAN_REVIEW.md Section 2A

## What changed

Collapsed 21 distinct `category` values to **12 canonical safety-taxonomy values + 3 transitional V1 holdouts** (Phase 4c migration targets).

## Renames applied (24 entries total)

| Renamed from | → | To | Count | Why |
|---|---|---|---|---|
| `artificial_color` | → | `colorant_artificial` | 1 | Spelling duplicate collapse |
| `fat_oil` | → | `excipient` | 5 | Functional role `carrier_oil` lives in `functional_roles[]`; safety category is the catch-all |
| `flavor` | → | `excipient` | 4 | `flavor_natural`/`flavor_artificial`/`flavor_enhancer` in `functional_roles[]`; safety category catch-all |
| `preservative_antioxidant` | → | `preservative` | 4 | `antioxidant` role lives in `functional_roles[]`; primary safety bucket |
| `sweetener` (bare) | → | `sweetener_natural` | 8 | All bare-`sweetener` entries are natural-source per per-entry analysis |

Plus per-id overrides for the 2 `colorant` entries (clinician 2A: "no category-level defaulting"):

| ID | Old | New | Why |
|---|---|---|---|
| `ADD_IRON_OXIDE` | colorant | `colorant_natural` | Mineral source; FDA 21 CFR 73.200 |
| `ADD_CANDURIN_SILVER` | colorant | `excipient` | Brand covers multiple formulations; per-product verification deferred to V1.1 |

## Canonical V1 set (12 + 3 transitional)

**Stable (clinician 2A canonical 12):** `excipient`, `preservative`, `emulsifier`, `colorant_artificial`, `colorant_natural`, `sweetener_artificial`, `sweetener_natural`, `sweetener_sugar_alcohol`, `filler`, `contaminant`, `processing_aid`, `phosphate`

**Transitional — Phase 4c migration targets** (entries in this group physically relocate to actives in V1.1, so the safety taxonomy bucket is moot once they leave):
- `mineral_compound` (1 — Cupric Sulfate)
- `nutrient_synthetic` (2 — Synthetic B Vitamins, Synthetic Vitamins)
- `stimulant_laxative` (1 — Senna)

## Why this is safe

- **No scoring impact**: `category` was always informational; the structural dimension is now `functional_roles[]`.
- **Integrity gate uses the multi-valued vocab** (32 IDs), not the safety category, so canonicalization doesn't break validation.
- **No external consumers** of specific category strings — Flutter renders chips from `functional_roles[]`, not `category`.
- **Granular info preserved**: every renamed entry still carries its precise role(s) in `functional_roles[]` (Phase 3 batches 1-3). E.g., BHA → `category: "preservative"` AND `functional_roles: ["preservative", "antioxidant"]`. No information loss.

## Coverage

| Distinct category values | Before | After |
|---|---|---|
| harmful_additives.json | **21** | **15** (12 canonical + 3 transitional) |

Phase 4c (V1.1, deferred) reduces to **12 canonical** by relocating the 4 transitional entries to the active-ingredient pipeline.

## What's NOT done in 4b

- `other_ingredients.json` category canonicalization (241 → 30) is **deferred**. Reason: Flutter doesn't read `category` from `other_ingredients` (it reads `functional_roles[]` for chips), so the rename is purely internal hygiene with low V1 value. Phase 4c+ work.
- `additive_type` field drop is **deferred to V1.1** — requires migrating internal `ADDITIVE_TYPES_SKIP_SCORING` set in `enrich_supplements_v3.py` to `FUNCTIONAL_ROLES_SKIP_SCORING`. Touches scoring logic.

## Verification

- [x] All 24 renames applied
- [x] No retired category values remain in data file
- [x] Specific high-visibility renames spot-checked (BHA/BHT/TBHQ → preservative; cane sugar → sweetener_natural; Iron Oxide → colorant_natural)
- [x] Distinct category count: 15 (target met)
- [x] Integrity gate: 0 findings
- [x] 27 prior tests pass + 4 new Phase 4b tests pass
