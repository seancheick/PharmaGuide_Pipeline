# Migration: `category_error_type` Enum (Dr Pham D7 Sign-Off)

> **For Dr Pham:** Status update on the Supabase / export migration for the new `category_error_type` enum.

## TL;DR

**The IQM is consumed via local SQLite cache (offline-first), not Supabase tables.** So there's no Supabase ALTER TABLE migration needed — the enum addition is a JSON schema additive change that flows through the export pipeline. The new field is **already populated** in `ingredient_quality_map.json` (Batch 37, applied 2026-04-25). The remaining work is wiring it through the export pipeline + Flutter parser.

---

## Where the Enum Lives Across the Stack

```
┌─────────────────────────────────────────────────────────────────────────┐
│  scripts/data/ingredient_quality_map.json   (SOURCE OF TRUTH)           │
│  forms[*].absorption_structured.category_error_type  ← added 2026-04-25 │
│  forms[*].absorption_structured.category_error_label ← UI-friendly text │
└─────────────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  scripts/build_final_db.py  (EXPORT — needs update)                     │
│  Pass through both fields to the SQLite export                          │
└─────────────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  Flutter app (PharmaGuide) — local SQLite (offline-first)               │
│  Read category_error_label → render in UI when struct.value=null        │
│  Replace "N/A" / "missing data" with explanatory text                   │
└─────────────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────────┐
│  Supabase pending_products table — no schema change needed              │
│  (Pending products use the SAME local IQM lookup; no separate enum     │
│  storage required)                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Enum Values + Counts (from current IQM)

```sql
-- Conceptual SQL (doesn't run; IQM is in JSON not Postgres)
-- Provided here as a reference for what would be the constraint
-- if anyone migrates this to a relational store

CREATE TYPE category_error_type AS ENUM (
    'local_action',                -- 9 forms: manuka, slippery elm
    'composite_food',              -- 9 forms: organ extracts, spirulina
    'colonic_fermentation',        -- 5 forms: inulin, larch AG, pectin, alpha-GOS
    'viscous_fiber_luminal',       -- 4 forms: psyllium, konjac glucomannan
    'protein_digestion_barrier',   -- 2 forms: SOD
    'live_organism',               -- (probiotics — strain-specific scoring pending)
    'framework_mismatch',          -- 14 forms: digestive enzymes, HA, butterbur, kelp/I2, mixed probiotics
    'oral_tolerance',              -- 1 form: UC-II (8th category-error pattern)
    'bbb_blocked'                  -- (GABA — applied as bio downgrade in B36, not enum yet)
);
```

**Total tagged: 41 forms across the 8 category-error patterns** (from B37 application).

---

## UI Labels (Front-End-Ready)

| Enum value | UI Label |
|---|---|
| `local_action` | "Works locally; not systemically absorbed" |
| `composite_food` | "Multi-nutrient food; score per-nutrient" |
| `colonic_fermentation` | "Fermented in colon to SCFAs (microbiome)" |
| `viscous_fiber_luminal` | "Forms a gel in the gut (luminal action)" |
| `protein_digestion_barrier` | "Protein/enzyme digested before absorption" |
| `live_organism` | "Live organism; survival/colonization is the metric" |
| `framework_mismatch` | "Bioavailability framework does not apply" |
| `oral_tolerance` | "Immune signaling via Peyer's patches (oral tolerance)" |
| `bbb_blocked` | "Does not cross blood-brain barrier (BBB)" |

---

## Migration Steps

### ✅ Step 1: IQM JSON (DONE — Batch 37)
Added `category_error_type` + `category_error_label` to `forms[*].absorption_structured` for 41 affected forms.

### 🟡 Step 2: Export pipeline pass-through (NEXT)
Update `scripts/build_final_db.py` to pass these fields through to the final SQLite export. The fields are additive, so Flutter parsers that don't read them will continue to work.

```python
# In build_final_db.py — add to the per-form export logic:
form_export = {
    "value": struct.get("value"),
    "quality": struct.get("quality"),
    "range_low": struct.get("range_low"),
    "range_high": struct.get("range_high"),
    "notes": struct.get("notes"),
    "category_error_type": struct.get("category_error_type"),   # NEW
    "category_error_label": struct.get("category_error_label"), # NEW
}
```

### 🟡 Step 3: Flutter parser (PharmaGuide app)
When `value` is null in IQM, instead of rendering "N/A" or "missing data", check for `category_error_label` and display it as the absorption explanation.

```dart
// Pseudocode for Flutter UI
String absorptionDisplay(IngredientForm form) {
  if (form.value != null) {
    return '${(form.value * 100).toStringAsFixed(0)}% bioavailability';
  }
  if (form.categoryErrorLabel != null) {
    return form.categoryErrorLabel;  // e.g. "Works locally in the gut"
  }
  return 'Bioavailability not measured';
}
```

### 🟢 Step 4: Schema docs
Update `scripts/DATABASE_SCHEMA.md` to document the new fields under the IQM section.

### 🟢 Step 5: Supabase
**No SQL migration needed.** Supabase stores user-facing data (stacks, pending products), not the IQM master. The enum lives in the JSON master + flows through the export.

---

## Why This Architecture (Offline-First)

The IQM has 1,379 forms — too large to query on every scan. So:
- **IQM master** (JSON) → built into the bundled SQLite the Flutter app ships with
- **Per-scan lookups** are local (sub-millisecond)
- **Supabase** only stores user-specific data (stacks, scans-per-day, pending product submissions)
- **Updates to IQM** ship via app updates (pipeline → export_manifest → bundled SQLite)

So Dr Pham's enum approval translates to **an additive JSON field + Flutter UI logic**, no relational DB migration. ✓

---

## Sample User-Facing Improvements

**Before Batch 37:**
> Manuka Honey UMF 15+ — Bioavailability: ❌ Not measured

**After Batch 37 (with Flutter wiring):**
> Manuka Honey UMF 15+ — Works locally in the gut/throat (not systemically absorbed)
> ℹ️ This product's mechanism is local antibacterial action, not absorption.

**Before:**
> UC-II Undenatured Collagen — Bioavailability: ❌ Not measured

**After:**
> UC-II Undenatured Collagen — Immune signaling via Peyer's patches (oral tolerance)
> ℹ️ Works at low doses (40 mg) by training the gut immune system, not by absorption.

This is exactly the front-end win Dr Pham flagged in her D7 sign-off.

---

## Timeline

| Step | Owner | ETA |
|---|---|---|
| Step 1: IQM JSON | ✅ Pipeline (B37) | DONE |
| Step 2: build_final_db.py | Pipeline | This sprint |
| Step 3: Flutter parser | App team | Next Flutter sprint |
| Step 4: Schema docs | Pipeline | This sprint |
| Step 5: Supabase | n/a | No migration needed |
