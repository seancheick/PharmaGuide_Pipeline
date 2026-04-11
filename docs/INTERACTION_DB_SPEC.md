# PharmaGuide — Interaction DB & Nutrient Safety Engineering Plan

**Document version:** 2.0.0
**Last updated:** 2026-04-11
**Status:** Planning complete, ready for implementation
**Supersedes:** v1.0.0 (written without knowledge of existing Flutter infrastructure)

---

## 🎯 Next Agent — Start Here

**If you are a fresh agent reading this cold, here is the exact state of the world:**

1. **What's already done:**
   - v3.4.x scoring recalibration shipped (A1 15→18, A2 3→5, Ω3 2→3, B1 cap 8→15) across 5,231 products.
   - Catalog v2026.04.11.040818 bundled into Flutter (`assets/db/pharmaguide_core.db`, 11.75 MB, LFS).
   - Supabase OTA round-trip verified.
   - This spec.

2. **What to build next (in order):**
   - **M1: Stack Nutrient Accumulator** — Flutter only, 2–3 days, ships independently of any interaction DB work. This closes the biggest medical-grade gap: UL checks currently run per-product, not per-stack. See §5.
   - **M2: Pipeline Interaction DB builder + verifier** — new Python scripts that normalize the user's draft JSON + supp.ai export, validate CUI/RXCUI against UMLS and RxNorm APIs, and emit a bundled SQLite. See §6.
   - **M3: Flutter Interaction DB binding** — Drift wrapper around the bundled SQLite. See §7.
   - **M4: Stack interaction engine** — extend the existing `StackInteractionChecker`, add RxNorm-backed medication entry UI. See §8.
   - **M5: Product-scan interaction warnings** — banner on product detail when a scanned item interacts with existing stack or meds. See §9.

3. **Critical existing infrastructure you must reuse, not rebuild (§4):**
   - `lib/core/constants/severity.dart` — `Severity` enum (5 tiers, colors, stack penalties)
   - `lib/core/models/interaction_result.dart` — `InteractionResult` model maps 1:1 to the draft JSON format
   - `lib/services/stack/stack_interaction_checker.dart` — 119-line category-level check engine, already wired into stack add flow
   - `lib/data/database/tables/user_stacks_table.dart` — `UserStacksLocal` already supports `type='medication'` with `rxcui` + `drug_classes` columns. **Do not create a separate `user_medications` table.**
   - `lib/services/fit_score/e1_dosage_calculator.dart` — already has per-product UL check logic. Reuse the RDA/UL parsing.

4. **Data the user has ready:**
   - A draft JSON of ~150 curated interactions (unverified) — format documented in §10.1. User will paste into `scripts/data/curated_interactions/interactions_drafts_v0.json` when ready.
   - supp.ai full database export — **commercial use cleared by the user**. Drop at `scripts/data/suppai_import/suppai_raw.json`.
   - RxNorm API: free NLM endpoint at https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html — no auth, 20 req/sec cap.
   - UMLS API for CUI validation (already used by `scripts/api_audit/verify_cui.py`).

5. **Key architectural commitments (non-negotiable):**
   - Bundled SQLite, not in-memory JSON.
   - Interaction DB ships as a **separate** asset from `pharmaguide_core.db` so they have independent release cycles.
   - Medications are PHI and **never** sync to Supabase (enforced at build time via a grep assertion).
   - Interactions are **user-scoped** and never enter the arithmetic quality score.
   - Nutrient accumulation is a **pure function**, not a new table.
   - Food interactions become one-line **flags on the product**, not a food tracker.
   - Data quality pipeline (CUI/RXCUI verification) is **mandatory** before any entry is shipped. Major+ severity without a source blocks the build.

---

## 1. Purpose & Scope

### What this system does

1. **Stack nutrient accumulation (M1).** Sum every active ingredient across all items in the user's stack and warn when totals exceed RDA/UL thresholds.
2. **Drug ↔ supplement interactions (M2–M5).** When the user scans a supplement, check it against medications they've entered and supplements already in their stack.
3. **Supplement ↔ supplement interactions (M4).** Pairwise antagonism/synergy checks across the stack.
4. **Drug class lookups (M2).** Handle the common case where the user knows "I'm on a statin" but not the specific molecule.

### What this system does NOT do (v1)

- **No food tracker.** Food-interaction data becomes a static flag on the product (`take_with_food`, `avoid_grapefruit`), never a logged-consumption feature.
- **No pharmacogenomic gene-variant modeling.** CYP2D6 etc. is out of scope.
- **No dose-dependent interaction modeling beyond a simple threshold.** A single `dose_threshold_text` field is shipped; full pharmacokinetic simulation is deferred.
- **No clinical decision support for providers.** PharmaGuide is a consumer app.
- **No real-time drug approval updates.** The interaction DB ships as versioned bundled data, updated on pipeline release cycles.

---

## 2. Build Order & Milestones

| M | Deliverable | Days | Blockers | Repo(s) |
|---|---|---|---|---|
| **M1** | Stack nutrient accumulator + UL progress-bar panel | 2–3 | None | Flutter only |
| **M2** | `build_interaction_db.py` + `verify_interactions.py` | 3–5 | User's draft JSON, supp.ai dump, UMLS+RxNorm API keys | Pipeline only |
| **M3** | Flutter Drift wrapper + bundled asset + import script update | 2–3 | M2 produces dist/interaction_db.sqlite | Flutter only |
| **M4** | Extend `StackInteractionChecker` with DB lookups + RxNorm medication entry screen | 3–5 | M3 done | Flutter only |
| **M5** | `interaction_warning_card` on product scan | 2–3 | M4 done | Flutter only |

**Total: ~3 weeks end-to-end. M1 alone is shippable in 2–3 days.**

---

## 3. High-Level Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  PIPELINE REPO (peaceful-ritchie)                              │
│                                                                │
│  INPUTS                                                        │
│  ├── scripts/data/curated_interactions/                        │
│  │   └── interactions_drafts_v*.json   (user's hand-curated)   │
│  ├── scripts/data/suppai_import/                               │
│  │   └── suppai_raw.json               (supp.ai export)        │
│  └── scripts/data/curated_overrides/                           │
│      └── interaction_overrides.json    (manual conflict fixes) │
│                                                                │
│  NORMALIZATION (scripts/build_interaction_db.py)               │
│  ├── JSON schema validation                                    │
│  ├── CUI / RXCUI lookup via                                    │
│  │     scripts/api_audit/verify_interactions.py                │
│  │       - RxNorm API for drug RXCUI                           │
│  │       - UMLS API for supplement CUI                         │
│  │       - ingredient_quality_map.json for canonical_id        │
│  ├── Direction normalization (Med-Sup / Sup-Med symmetry)      │
│  ├── Dedup by (agent1_id, agent2_id, severity)                 │
│  ├── Conflict resolution (more cautious severity wins)         │
│  └── Major+ severity must have ≥1 source or build FAILS        │
│                                                                │
│  OUTPUT (scripts/dist/)                                        │
│  ├── interaction_db.sqlite             (bundled SQLite)        │
│  ├── interaction_db_manifest.json      (version + checksum)    │
│  └── interaction_audit_report.json     (drift + quality gates) │
└────────────────────────────────────────────────────────────────┘
                           │
                           │  LFS bundled via import_catalog_artifact.sh
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  FLUTTER REPO (PharmaGuide ai / main)                          │
│                                                                │
│  BUNDLED ASSETS                                                │
│  ├── assets/db/pharmaguide_core.db       (existing, LFS)       │
│  ├── assets/db/interaction_db.sqlite     (NEW, LFS)            │
│  └── assets/db/interaction_db_manifest.json                    │
│                                                                │
│  DATA LAYER                                                    │
│  ├── lib/data/database/interaction_database.dart     (NEW)     │
│  ├── lib/data/database/interaction_database.g.dart   (gen)     │
│  └── lib/data/database/tables/interactions_table.dart (NEW)    │
│                                                                │
│  SERVICE LAYER                                                 │
│  ├── lib/services/stack/                                       │
│  │   ├── stack_nutrient_aggregator.dart    (NEW - M1)          │
│  │   ├── stack_ul_checker.dart             (NEW - M1)          │
│  │   ├── stack_interaction_checker.dart    (EXTEND - M4)       │
│  │   └── stack_safety_report.dart          (NEW - M4)          │
│  └── lib/services/medications/                                 │
│      └── rxnorm_api_service.dart           (NEW - M4)          │
│                                                                │
│  UI LAYER                                                      │
│  ├── lib/features/stack/widgets/                               │
│  │   ├── nutrient_accumulation_panel.dart  (NEW - M1)          │
│  │   ├── nutrient_progress_bar.dart        (NEW - M1)          │
│  │   └── stack_safety_banner.dart          (NEW - M4)          │
│  ├── lib/features/medications/                                 │
│  │   └── medication_entry_screen.dart      (NEW - M4)          │
│  └── lib/features/product_detail/widgets/                      │
│      └── interaction_warning_card.dart     (NEW - M5)          │
└────────────────────────────────────────────────────────────────┘
```

---

## 4. Existing Flutter Infrastructure (reuse, do not rebuild)

Before touching any code, the next agent must read and understand these files. They shape everything below.

### 4.1 `lib/core/constants/severity.dart`

```dart
enum Severity {
  contraindicated(weight: 5, e2cPenalty: -8, label: 'BLOCK — Do Not Use', color: Color(0xFFDC2626)),
  avoid          (weight: 4, e2cPenalty: -5, label: 'AVOID',              color: Color(0xFFDC2626)),
  caution        (weight: 3, e2cPenalty: -3, label: 'CAUTION',            color: Color(0xFFF97316)),
  monitor        (weight: 2, e2cPenalty: -1, label: 'MONITOR',            color: Color(0xFFEAB308)),
  safe           (weight: 0, e2cPenalty:  0, label: 'SAFE',               color: Color(0xFF22C55E));
}

enum EvidenceLevel {
  established(label: 'Strong Evidence'),
  probable   (label: 'Good Evidence'),
  theoretical(label: 'Theoretical');
}
```

Five tiers with stack-score penalties already baked in. Every interaction result in the app uses this enum.

### 4.2 `lib/core/models/interaction_result.dart`

```dart
enum InteractionType { drugSupplement, supplementSupplement, drugDrug, conditionSupplement }
enum InteractionSource { pipeline, stackEngine, aiChat }

class InteractionResult {
  final String id;
  final InteractionType type;
  final Severity severity;
  final EvidenceLevel evidenceLevel;
  final String agent1Name;
  final String agent2Name;
  final String mechanism;
  final String management;
  final bool doseDependant;
  final String? doseThreshold;
  final List<String> sourceUrls;
  final InteractionSource source;
}
```

Draft JSON fields map 1:1 to this model. The only addition needed is an optional `effectType` (inhibitor/enhancer/additive/neutral) field. See §10.3.

### 4.3 `lib/services/stack/stack_interaction_checker.dart`

119 lines. Already runs these category-level checks on stack add:
- Stimulant ↔ sedative antagonism
- Stimulant ↔ stimulant stacking warning
- Blood-thinner ↔ blood-thinner stacking warning

Returns `List<InteractionResult>`. **Extend this file in M4** with new DB-backed methods — do not create a parallel service.

### 4.4 `lib/data/database/tables/user_stacks_table.dart`

```dart
class UserStacksLocal extends Table {
  TextColumn get id => text()();
  TextColumn get type => text().withDefault(const Constant('supplement'))(); // supplement | medication
  TextColumn get name => text()();
  TextColumn get dsldId => text().nullable()();
  TextColumn get rxcui => text().nullable()();                          // for medications
  TextColumn get ingredientKeys => text().nullable()();                 // JSON array for supplements
  TextColumn get drugClassesCol => text().named('drug_classes').nullable()();
  TextColumn get dosage => text().nullable()();
  TextColumn get frequency => text().nullable()();
}
```

Medications already live in the same table as supplements via `type='medication'`. The `rxcui` and `drug_classes` columns already exist. **Do not add a second table.**

### 4.5 `lib/services/fit_score/e1_dosage_calculator.dart`

Already parses RDA and UL from `rda_ul_data` reference entries:

```dart
final rdaEntry = _findNutrientEntry(recommendations, name);
final ul  = _getUl(rdaEntry, ageBracket, sex);
final rda = _getRda(rdaEntry, ageBracket, sex);

if (ul != null && ul > 0 && amount > ul) {
  ulExceeded = true;
}
```

**Reuse `_findNutrientEntry`, `_getUl`, `_getRda` in `stack_ul_checker.dart`.** Do not reimplement the parsing.

---

## 5. M1: Stack Nutrient Accumulator (ship first)

### 5.1 Rationale

Currently the app checks UL per product. A user taking three multivitamins each at 80% of zinc UL would see no warning — the stack-level total (240% of UL) is silently lost. This is the biggest medical-grade miss in the app today. M1 fixes it with zero new tables and zero new data files. Ship this independently of any interaction DB work.

### 5.2 New files

```
lib/services/stack/
├── stack_nutrient_aggregator.dart     (~100 LOC)
└── stack_ul_checker.dart              (~150 LOC)

lib/features/stack/widgets/
├── nutrient_accumulation_panel.dart   (~200 LOC)
└── nutrient_progress_bar.dart         (~80 LOC)

test/services/stack/
├── stack_nutrient_aggregator_test.dart
└── stack_ul_checker_test.dart

test/features/stack/widgets/
├── nutrient_accumulation_panel_test.dart
└── nutrient_progress_bar_test.dart
```

### 5.3 `stack_nutrient_aggregator.dart`

Pure function. No state. No persistence. Input: list of stack items with their `detail_blob.ingredients[]`. Output: `Map<String canonicalId, NutrientTotal>`.

```dart
class NutrientTotal {
  final String canonicalId;
  final String displayName;
  final double totalAmount;
  final String unit;               // always normalized to the canonical unit
  final List<NutrientContribution> contributions;
}

class NutrientContribution {
  final String productName;
  final String stackEntryId;
  final double amount;
  final String unit;
}

class StackNutrientAggregator {
  /// Sum every active ingredient across a stack.
  /// Merges by canonical_id. Normalizes units before summing.
  /// Skips ingredients without usable per-serving amounts.
  Map<String, NutrientTotal> aggregate(List<StackItemWithBlob> stack);
}
```

Implementation notes:
- Iterate each stack item's `detail_blob.ingredients[]`
- For each ingredient with `canonical_id` and `normalized_amount`, add to the running total keyed by `canonical_id`
- Unit normalization: use the `normalized_unit` the pipeline already emits (mg for most, mcg for trace, IU for fat-solubles). No conversion logic on the Flutter side.
- If two products report the same nutrient in different units, log a warning and skip the non-canonical one (should not happen if the pipeline is correct)
- Cache the result per-stack-hash; recompute only when a stack item is added/removed/edited

### 5.4 `stack_ul_checker.dart`

```dart
enum NutrientTier {
  noRda,          // no RDA data available — display without tier color
  underFifty,     // < 50% RDA (not flagged, just informational)
  adequate,       // 50-100% RDA                → green
  abundant,       // 100-200% RDA               → gold
  aboveTypical,   // > 200% RDA, < 80% UL       → yellow
  approachingUl,  // 80-100% UL                 → orange
  exceedsUl,      // > 100% UL                  → red (warning)
}

class NutrientStatus {
  final NutrientTotal total;
  final double? rda;
  final double? ul;
  final double? pctOfRda;
  final double? pctOfUl;
  final NutrientTier tier;
  final String? warning;  // human-readable when tier >= approachingUl
}

class StackUlChecker {
  /// Classify each aggregated nutrient against RDA/UL from reference data.
  /// Reuses _findNutrientEntry/_getUl/_getRda from E1DosageCalculator.
  List<NutrientStatus> check(
    Map<String, NutrientTotal> aggregated, {
    required AgeBracket? ageBracket,
    required Sex? sex,
  });
}
```

Warning strings are nutrient-specific and live in a small map:
- Zinc > UL → "Exceeds Upper Limit — risk of copper depletion"
- Iron > UL → "Exceeds Upper Limit — risk of GI toxicity"
- Vitamin A > UL → "Exceeds Upper Limit — risk of hepatotoxicity and teratogenicity"
- Vitamin D > UL → "Exceeds Upper Limit — risk of hypercalcemia"
- Generic fallback → "Exceeds Upper Limit — review with healthcare provider"

### 5.5 `nutrient_accumulation_panel.dart` UX

```
┌────────────────────────────────────────────────────────────┐
│ Your Stack — 5 products, 38 nutrients tracked              │
├────────────────────────────────────────────────────────────┤
│                                                            │
│ Vitamin D3                                    4,000 IU/day │
│ ████████████████████░░░░░░░░░░░░░   200% RDA │ 67% UL     │
│   • Thorne D/K2 Liquid    2,000 IU                         │
│   • Pure Encaps D3 2k     2,000 IU                         │
│                                                            │
│ Magnesium                                       600 mg/day │
│ ████████████░░░░░░░░░░░░░░░░░░░░░   150% RDA │ 60% UL     │
│   • Natural Vit. Cal/Mag   400 mg                          │
│   • Thorne Mag Glycinate   200 mg                          │
│                                                            │
│ Zinc                                             52 mg/day │
│ ██████████████████████████░░░░░░░   473% RDA │ 130% UL ⚠️ │
│ ⚠️  Exceeds Upper Limit — risk of copper depletion         │
│   • Multi A                15 mg                           │
│   • Immune Support         22 mg                           │
│   • Zinc Picolinate        15 mg                           │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

- Sort order: `exceedsUl` first, then `approachingUl`, then by RDA% descending
- Collapsible rows: tap to reveal contribution list
- Warning chip uses `Severity.caution.color` for `approachingUl` and `Severity.avoid.color` for `exceedsUl`
- Panel slots into `stack_screen.dart` above the product list

### 5.6 M1 Done Gate

| Gate | Check |
|---|---|
| Aggregator tests | ≥ 10 tests covering unit normalization, dedup, empty stack, missing canonical_id |
| UL checker tests | ≥ 8 tests covering all 7 tiers, null RDA, null UL, age/sex brackets |
| Widget tests | Panel renders with 0/1/many nutrients, progress-bar color matches tier |
| Dart analyze | Zero new warnings |
| Build passes | `flutter build apk --debug` succeeds |
| Manual QA | Add 3 products to a stack, verify zinc accumulates, verify exceedsUl warning fires |

**Ship M1 as a single PR before starting M2.**

---

## 6. M2: Pipeline Interaction DB Builder

### 6.1 Files to create

```
scripts/
├── build_interaction_db.py                      (~400 LOC)
├── data/
│   ├── curated_interactions/
│   │   └── interactions_drafts_v0.json          (user will paste here)
│   ├── suppai_import/
│   │   └── suppai_raw.json                      (user will drop here)
│   ├── curated_overrides/
│   │   └── interaction_overrides.json           (manual conflict fixes)
│   └── drug_classes.json                        (NEW reference file)
├── api_audit/
│   └── verify_interactions.py                   (~300 LOC)
└── tests/
    ├── test_build_interaction_db.py
    └── test_verify_interactions.py
```

### 6.2 `verify_interactions.py` responsibilities

Runs before `build_interaction_db.py` and blocks the build on any serious issue.

Checks, in order:

1. **JSON schema validation.** Every entry must have the required fields (§10.1). Malformed JSON fails fast.
2. **Duplicate ID detection.** Entries sharing an `id` fail.
3. **RXCUI verification (drugs).** Call the RxNorm API `/rxcui/{rxcui}/properties`. Confirm the RXCUI is real and currently valid. Compare the returned drug name to `agent_name` — mismatch raises a warning.
4. **CUI verification (supplements).** Call UMLS `/search/current` with the claimed `agent_name`, confirm the returned CUI matches `agent_id`. Mismatch raises a warning and auto-corrects the CUI in the output.
5. **canonical_id mapping.** For every supplement agent, look up the CUI in `scripts/data/ingredient_quality_map.json`. If present, attach the `canonical_id` for Flutter-side lookup. If not present, log an unmapped-supplement warning (not blocking).
6. **Drug class expansion.** For `class:statins` etc., expand against `scripts/data/drug_classes.json`. Missing class → blocks build.
7. **Direction normalization.** Both `Med-Sup` and `Sup-Med` should produce the same entry. Normalize so `agent1_type='drug'` is always drug-side when one side is a drug. Store the original `type` as `type_authored` for audit.
8. **Severity normalization.** Map the draft's 4-tier vocab into the Flutter 5-tier `Severity` enum:
   - `Contraindicated` → `contraindicated`
   - `Major` → `avoid`
   - `Moderate` → `caution`
   - `Minor` → `monitor`
9. **Major+ evidence gate.** Entries with `severity in ('contraindicated', 'avoid')` must have at least one non-empty `source_urls` entry OR a PMID in `source_pmids`. Empty-source Major+ entries **block the build**.
10. **Source URL quality.** Extract PMIDs from PubMed URLs into a parallel `source_pmids` field for fast attribution.

The script returns a structured report:

```json
{
  "total_entries": 152,
  "valid": 138,
  "warnings": 11,
  "errors": 3,
  "blocked_by": [
    {
      "id": "DDI_WAR_TURMERIC",
      "reason": "Major severity requires at least 1 source URL or PMID"
    }
  ],
  "cui_corrections": [
    {
      "id": "DDI_WAR_VITK",
      "claimed": "C0042810",
      "claimed_resolves_to": "Vitamin D",
      "correct_cui_for_vitamin_k": "C0042839",
      "action": "corrected in output"
    }
  ]
}
```

Exit code 0 only if `errors == 0`.

### 6.3 `build_interaction_db.py` responsibilities

Runs after `verify_interactions.py` passes. Produces `scripts/dist/interaction_db.sqlite`.

1. Load verified drafts + supp.ai import + overrides.
2. Dedup by `(agent1_id, agent2_id)` — prefer verified draft over supp.ai over raw imports.
3. Conflict resolution on severity mismatch: **more cautious always wins** (contraindicated > avoid > caution > monitor). Log every resolved conflict to the audit report.
4. Apply `interaction_overrides.json` last — manual fixes override everything.
5. Create SQLite with schema from §6.4.
6. Create all indexes (see §6.4).
7. Populate `drug_class_map` table from `scripts/data/drug_classes.json`.
8. Populate `interaction_db_metadata` table with:
   - `schema_version: 1.0.0`
   - `built_at: <iso>`
   - `source_drafts_count`
   - `source_suppai_count`
   - `total_interactions`
   - `sha256_checksum`
9. Write `interaction_db_manifest.json` next to the SQLite with the same metadata + a release-stage timestamp.
10. Write `interaction_audit_report.json` with conflict resolutions, dropped entries, and CUI corrections.

### 6.4 SQLite schema

```sql
CREATE TABLE interactions (
  id                    TEXT PRIMARY KEY,
  agent1_type           TEXT NOT NULL,        -- drug | supplement | food | drug_class
  agent1_name           TEXT NOT NULL,
  agent1_id             TEXT NOT NULL,        -- RXCUI | CUI | canonical_id | class:name
  agent1_canonical_id   TEXT,                 -- maps to ingredient_quality_map, null if drug/food
  agent1_drug_class     TEXT,                 -- if drug, the canonical class id
  agent2_type           TEXT NOT NULL,
  agent2_name           TEXT NOT NULL,
  agent2_id             TEXT NOT NULL,
  agent2_canonical_id   TEXT,
  agent2_drug_class     TEXT,
  severity              TEXT NOT NULL,        -- contraindicated|avoid|caution|monitor
  effect_type           TEXT,                 -- inhibitor|enhancer|additive|neutral
  mechanism             TEXT NOT NULL,
  management            TEXT NOT NULL,
  evidence_level        TEXT,                 -- established|probable|theoretical
  source_urls_json      TEXT NOT NULL,        -- JSON array, possibly empty []
  source_pmids_json     TEXT NOT NULL,        -- JSON array, possibly empty []
  bidirectional         INTEGER DEFAULT 1,
  dose_dependent        INTEGER DEFAULT 0,
  dose_threshold_text   TEXT,
  type_authored         TEXT NOT NULL,        -- original 'Med-Sup' etc, for audit
  source                TEXT NOT NULL,        -- 'curated'|'suppai'|'override'
  last_updated          TEXT NOT NULL
);

CREATE INDEX idx_int_a1_canon ON interactions(agent1_canonical_id)
  WHERE agent1_canonical_id IS NOT NULL;
CREATE INDEX idx_int_a2_canon ON interactions(agent2_canonical_id)
  WHERE agent2_canonical_id IS NOT NULL;
CREATE INDEX idx_int_a1_id    ON interactions(agent1_type, agent1_id);
CREATE INDEX idx_int_a2_id    ON interactions(agent2_type, agent2_id);
CREATE INDEX idx_int_a1_class ON interactions(agent1_drug_class)
  WHERE agent1_drug_class IS NOT NULL;
CREATE INDEX idx_int_a2_class ON interactions(agent2_drug_class)
  WHERE agent2_drug_class IS NOT NULL;

CREATE TABLE drug_class_map (
  class_id         TEXT PRIMARY KEY,      -- 'class:statins'
  class_name       TEXT NOT NULL,         -- 'Statins'
  drug_rxcuis_json TEXT NOT NULL,         -- JSON array of member RXCUIs
  source           TEXT NOT NULL,
  last_updated     TEXT NOT NULL
);

CREATE TABLE interaction_db_metadata (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
```

**Lookup-speed target: <1ms for any realistic query.** Every lookup the app will issue corresponds to one of the six indexes above.

### 6.5 M2 Done Gate

| Gate | Check |
|---|---|
| `verify_interactions.py` | ≥ 20 unit tests covering every failure mode |
| `build_interaction_db.py` | ≥ 15 tests including dedup, conflict resolution, override precedence |
| RxNorm integration test | Real API call for 5 common drugs, expects live responses |
| UMLS integration test | Real API call for 5 common supplements |
| Blocked-build demo | A deliberately broken draft (empty source_urls at Major) must fail the build with a clear error |
| SQLite integrity | `PRAGMA integrity_check` returns `ok`, all 6 indexes present |
| Output size | `interaction_db.sqlite` < 10 MB (expect 2–5 MB for M2 scope) |

---

## 7. M3: Flutter Interaction DB Binding

### 7.1 New files

```
lib/data/database/
├── interaction_database.dart        (~150 LOC, Drift)
├── interaction_database.g.dart      (generated)
└── tables/
    └── interactions_table.dart      (~60 LOC)
```

### 7.2 Drift schema (`interactions_table.dart`)

Mirrors §6.4 exactly. Read-only. Loaded from `assets/db/interaction_db.sqlite`.

### 7.3 `interaction_database.dart` public API

```dart
class InteractionDatabase extends _$InteractionDatabase {
  InteractionDatabase.fromAsset()
    : super(_openBundled('assets/db/interaction_db.sqlite'));

  /// Find all interactions involving a specific supplement.
  Future<List<InteractionRow>> lookupByCanonicalId(String canonicalId);

  /// Find all interactions involving a specific drug RXCUI.
  Future<List<InteractionRow>> lookupByRxcui(String rxcui);

  /// Find all interactions involving a drug class.
  Future<List<InteractionRow>> lookupByDrugClass(String classId);

  /// Find interactions between two specific agents (symmetric — checks both directions).
  Future<List<InteractionRow>> lookupPair(
    String a1Id, String a1Type, String a2Id, String a2Type,
  );

  /// Resolve a drug class to its member RXCUIs (for medication entry UI).
  Future<List<String>> rxcuisForDrugClass(String classId);

  /// Get DB metadata — version, build date, counts.
  Future<InteractionDbMetadata> getMetadata();
}
```

### 7.4 `import_catalog_artifact.sh` update

Extend the existing bridge script to copy `interaction_db.sqlite` and `interaction_db_manifest.json` alongside the catalog files. Add validation gates:
- Checksum verify against manifest
- SQLite integrity_check
- Row count > 0
- All required tables present

### 7.5 M3 Done Gate

| Gate | Check |
|---|---|
| Drift build_runner | Regenerates `interaction_database.g.dart` cleanly |
| All 5 public lookup methods | Unit-tested against a fixture DB |
| Import script | 5 new validation gates pass on real artifact |
| App startup | Loads bundled DB in <200ms on device |
| Analyze | Zero new warnings |

---

## 8. M4: Stack Interaction Engine

### 8.1 Files

```
lib/services/stack/
├── stack_interaction_checker.dart     (EXTEND with ~200 new LOC)
└── stack_safety_report.dart           (NEW ~150 LOC)

lib/services/medications/
└── rxnorm_api_service.dart            (NEW ~120 LOC)

lib/features/medications/
└── medication_entry_screen.dart       (NEW ~250 LOC)

lib/features/stack/widgets/
└── stack_safety_banner.dart           (NEW ~100 LOC)
```

### 8.2 `stack_interaction_checker.dart` — new methods

Keep the existing 119 lines. Add:

```dart
/// Check a new product's ingredients against every medication in the user's stack.
Future<List<InteractionResult>> checkMedicationInteractions({
  required List<String> newProductCanonicalIds,
  required List<UserStackEntry> stackMedications,
  required InteractionDatabase db,
});

/// Check a new product's ingredients against every OTHER supplement in the stack.
Future<List<InteractionResult>> checkSupplementPairInteractions({
  required List<String> newProductCanonicalIds,
  required List<UserStackEntry> stackSupplements,
  required InteractionDatabase db,
});
```

Both return the existing `InteractionResult` model. Use the `InteractionSource.pipeline` enum variant.

### 8.3 `stack_safety_report.dart`

Aggregates every safety signal into a single object for the UI:

```dart
class StackSafetyReport {
  final List<NutrientStatus> nutrientStatuses;           // from M1
  final List<InteractionResult> stackInteractions;       // from M4 pair checks
  final List<InteractionResult> medicationInteractions;  // from M4 drug checks
  final List<InteractionResult> categoryWarnings;        // existing stim/sed/bt checks

  Severity get overallSeverity;                // highest severity across all signals
  Map<Severity, int> get severityCounts;       // counts for summary badge
  List<dynamic> get orderedWarnings;           // ordered for render, most severe first
}
```

### 8.4 `rxnorm_api_service.dart`

Thin wrapper around the NLM RxNorm REST API. No auth. Rate-limited to 20 req/sec client-side.

```dart
class RxNormApiService {
  Future<List<RxNormSuggestion>> search(String query);         // /approximateTerm
  Future<String?> getRxcui(String drugName);                   // /rxcui
  Future<List<String>> getClasses(String rxcui);               // /rxclass/class/byRxcui
  Future<RxNormDrugInfo?> getDrugInfo(String rxcui);           // /rxcui/{rxcui}/properties
}

class RxNormSuggestion {
  final String name;
  final String rxcui;
  final int score;
}
```

- **In-memory LRU cache** (50 entries). No SQLite cache needed; search volume is low.
- **Offline fallback:** If the API is unreachable, fall back to a bundled `drug_classes.json` dropdown so users can pick a class-level entry without network.

### 8.5 `medication_entry_screen.dart` flow

1. Autocomplete text field → `RxNormApiService.search()` on 300ms debounce
2. User picks a suggestion → fetches RXCUI + classes
3. Optional fields: started date, dose, frequency
4. Save → inserts into `user_stacks_local` with `type='medication'`, `rxcui`, `drug_classes`
5. Immediately runs `StackInteractionChecker.checkMedicationInteractions` across the user's existing supplement stack and surfaces any hits

**Privacy assertion at build time:** Add a test that grep-fails the build if any Supabase sync code path touches rows where `type='medication'`. Medications are PHI, never leave the device.

### 8.6 M4 Done Gate

| Gate | Check |
|---|---|
| New checker methods | ≥15 tests each, including edge cases (empty stack, unmapped ingredients, class-level matches) |
| Safety report | Golden-path test: stack with 3 sups + 2 meds produces expected ordered warnings |
| RxNorm service | Integration test hits live API, unit tests with mock |
| Medication entry UI | Widget tests for autocomplete, save, offline fallback |
| PHI assertion | Build-time grep test blocks merge if `type='medication'` reaches any sync service |

---

## 9. M5: Product Scan Interaction Warnings

### 9.1 Files

```
lib/features/product_detail/widgets/
└── interaction_warning_card.dart      (NEW ~180 LOC)

test/features/product_detail/widgets/
└── interaction_warning_card_test.dart
```

### 9.2 Flow

1. User scans / opens a product detail
2. Product's `detail_blob.ingredients[]` → list of canonical_ids
3. Query:
   - `db.lookupByCanonicalId()` for each ingredient → interactions involving this supplement
   - Cross-reference against the user's current stack medications (from `user_stacks_local`)
   - Cross-reference against the rest of the user's stack supplements
4. Dedup and order by severity
5. Render `InteractionWarningCard` at the top of the detail screen, above scoring sections
6. Each warning renders with:
   - Severity chip (reusing `Severity.color` and `Severity.label`)
   - "Because you're taking X" or "Because X is in your stack"
   - Mechanism (condensed one-liner)
   - Management text (the actionable advice)
   - "Learn more" expand to show source URLs

### 9.3 M5 Done Gate

| Gate | Check |
|---|---|
| Widget tests | Renders 0 / 1 / N warnings correctly |
| Integration test | Real bundled DB, scan a fixture product, verify warnings fire |
| E2E test (manual) | Scan a fish oil while Warfarin is in stack → "AVOID" banner fires |

---

## 10. Schemas & Data Formats

### 10.1 User draft JSON format (unverified input to pipeline)

Everything below is the user's existing convention. Do not change it. `verify_interactions.py` normalizes and validates.

```json
{
  "id": "DDI_WAR_VITK",
  "type": "Med-Sup",
  "agent1_name": "Warfarin",
  "agent1_id": "1161204",
  "agent2_name": "Vitamin K",
  "agent2_id": "C0042839",
  "severity": "Major",
  "interaction_effect_type": "Inhibitor",
  "mechanism": "Affects INR/clotting time",
  "management": "Monitor INR closely. Maintain consistent vitamin K intake.",
  "source_urls": ["https://www.ncbi.nlm.nih.gov/books/NBK501808/"]
}
```

**Allowed `type` values:**
`Med-Sup` · `Sup-Med` · `Sup-Sup` · `Med-Med` · `Med-Food` · `Sup-Food` · `Food-Med`

**Allowed `severity` values (draft vocabulary):**
`Contraindicated` · `Major` · `Moderate` · `Minor`

**Allowed `interaction_effect_type` values:**
`Inhibitor` · `Enhancer` · `Additive` · `Neutral`

**Allowed agent_id formats:**
- `[0-9]+` → RXCUI (drug)
- `C[0-9]{7}` → UMLS CUI (supplement or drug)
- `class:[a-z_]+` → drug class (e.g. `class:statins`, `class:ssris`)

### 10.2 Drug classes reference file

`scripts/data/drug_classes.json` — the source of truth for `class:X` expansion.

```json
{
  "_metadata": {
    "schema_version": "1.0.0",
    "last_updated": "2026-04-11",
    "total_classes": 24,
    "source": "NLM RxClass + manual curation"
  },
  "classes": {
    "class:statins": {
      "display_name": "Statins",
      "description": "HMG-CoA reductase inhibitors for cholesterol management",
      "member_rxcuis": ["83367", "36567", "42463", "301542", "42470"],
      "member_names": ["atorvastatin", "simvastatin", "rosuvastatin", "pravastatin", "lovastatin"],
      "rxclass_id": "N0000175461"
    },
    "class:ssris": { },
    "class:beta_blockers": { },
    "class:ace_inhibitors": { },
    "class:maois": { },
    "class:benzodiazepines": { },
    "class:nsaids": { },
    "class:anticonvulsants": { },
    "class:diabetes_meds": { },
    "class:insulins": { },
    "class:corticosteroids": { },
    "class:immunosuppressants": { },
    "class:hiv_protease_inhibitors": { },
    "class:antipsychotics": { },
    "class:triptans": { },
    "class:antacids": { },
    "class:calcium_channel_blockers": { },
    "class:diuretics": { },
    "class:oral_contraceptives": { },
    "class:sedatives": { },
    "class:stimulants": { },
    "class:antihypertensives": { },
    "class:b_vitamins": { }
  }
}
```

Build seed data by calling RxClass `getClassByRxNormDrugId` for each class — automated, one-time run during M2.

### 10.3 Dart `InteractionResult` extension

Add ONE new field to the existing model:

```dart
enum EffectType { inhibitor, enhancer, additive, neutral }

class InteractionResult {
  // ... all existing fields ...
  final EffectType? effectType;  // NEW
}
```

Update `fromRow()` and any constructors. Existing callers pass `null`, no breakage.

---

## 11. Data Sources

| Source | Type | Status | License |
|---|---|---|---|
| User's draft JSON | Curated hand-drafted interactions | ~150 entries, unverified | Internal |
| supp.ai database | Academic supplement-drug interactions | Dump downloaded | **Commercial use cleared by user** |
| RxNorm (NLM) | Drug identifier + class lookup | Free public API | Public domain |
| UMLS (NLM) | CUI verification | Existing script `verify_cui.py` | Requires license (already have) |
| ChEMBL | Mechanism of action (future) | Deferred | Open |
| DrugBank | Drug↔drug interactions | Deferred to post-v1 | Commercial — requires license |

**M1 through M5 require only the first four.** DrugBank integration is post-v1.

---

## 12. File Layout Summary

### Pipeline repo (peaceful-ritchie)

```
docs/
├── INTERACTION_DB_SPEC.md            (this file)
└── ...

scripts/
├── build_interaction_db.py           (M2, NEW)
├── api_audit/
│   └── verify_interactions.py        (M2, NEW)
├── data/
│   ├── curated_interactions/
│   │   └── interactions_drafts_v0.json  (user pastes here)
│   ├── suppai_import/
│   │   └── suppai_raw.json              (user drops export here)
│   ├── curated_overrides/
│   │   └── interaction_overrides.json   (manual fixes)
│   └── drug_classes.json                (M2, NEW)
├── dist/
│   ├── pharmaguide_core.db           (existing)
│   ├── pharmaguide_core_manifest.json
│   ├── interaction_db.sqlite         (M2, NEW)
│   └── interaction_db_manifest.json  (M2, NEW)
└── tests/
    ├── test_build_interaction_db.py  (M2, NEW)
    └── test_verify_interactions.py   (M2, NEW)
```

### Flutter repo (PharmaGuide ai)

```
assets/db/
├── pharmaguide_core.db               (existing, LFS)
├── pharmaguide_core.db.previous      (backup)
├── interaction_db.sqlite             (M3, NEW, LFS)
└── interaction_db_manifest.json      (M3, NEW)

lib/
├── core/
│   ├── constants/severity.dart       (REUSE)
│   └── models/interaction_result.dart (EXTEND — add effectType)
├── data/database/
│   ├── core_database.dart            (REUSE)
│   ├── interaction_database.dart     (M3, NEW)
│   ├── interaction_database.g.dart   (M3, GENERATED)
│   └── tables/
│       ├── user_stacks_table.dart    (REUSE — already supports meds)
│       └── interactions_table.dart   (M3, NEW)
├── services/
│   ├── fit_score/
│   │   └── e1_dosage_calculator.dart (REUSE — RDA/UL parsing)
│   ├── stack/
│   │   ├── stack_nutrient_aggregator.dart   (M1, NEW)
│   │   ├── stack_ul_checker.dart            (M1, NEW)
│   │   ├── stack_interaction_checker.dart   (M4, EXTEND)
│   │   └── stack_safety_report.dart         (M4, NEW)
│   └── medications/
│       └── rxnorm_api_service.dart          (M4, NEW)
└── features/
    ├── stack/
    │   ├── stack_screen.dart                (M1, EXTEND to slot panel)
    │   └── widgets/
    │       ├── nutrient_accumulation_panel.dart  (M1, NEW)
    │       ├── nutrient_progress_bar.dart        (M1, NEW)
    │       └── stack_safety_banner.dart          (M4, NEW)
    ├── medications/
    │   └── medication_entry_screen.dart     (M4, NEW)
    └── product_detail/
        └── widgets/
            └── interaction_warning_card.dart (M5, NEW)

scripts/
└── import_catalog_artifact.sh        (M3, EXTEND — bundle interaction_db too)
```

---

## 13. Testing Strategy

### Pipeline (M2)

- **Unit tests** for every normalization function in `verify_interactions.py`
- **Fixture tests** for every failure mode: broken JSON, bad CUI, empty sources at Major, duplicate IDs, drug class expansion misses
- **Integration tests** that hit real RxNorm + UMLS APIs, gated on a `--live` flag so CI can run offline
- **Golden dataset:** a small `test_fixtures/curated_interactions_golden.json` with 20 hand-verified entries; the pipeline must produce a byte-identical `interaction_db.sqlite` from this fixture on every run

### Flutter (M1, M3, M4, M5)

- **M1 pure-function tests** for `StackNutrientAggregator` and `StackUlChecker` — no widget dependency, fast
- **Widget tests** for every new widget using mock data
- **Golden-image tests** for the nutrient accumulation panel in all 7 tier colors
- **Integration test** (M4) that loads the real bundled `interaction_db.sqlite` fixture, adds a warfarin medication + a fish oil supplement to the stack, and asserts the expected InteractionResult appears
- **PHI assertion** (M4): a dedicated test that greps the sync_service source for any read of `user_stacks_local` rows where `type='medication'` and fails if found

### Full-suite gates

- Pipeline: `pytest scripts/tests/` must stay green (currently 3,259 passed / 4 skipped)
- Flutter: `flutter test` must stay green (count TBD — baseline before M1)
- Build: both repos must compile on every PR

---

## 14. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Draft JSON has wrong CUIs | High | High | `verify_interactions.py` auto-corrects via UMLS lookup and logs every correction |
| Major+ entries without PMIDs survive to production | Medium | Very high (liability) | Build fails on empty `source_urls` at Major+ |
| supp.ai import has conflicting severity with curated drafts | Medium | Medium | More cautious severity wins, logged to audit report |
| Drug class expansion misses a real drug | Medium | High | RxClass API is authoritative; maintenance is quarterly |
| User enters a misspelled medication | High | Low | RxNorm `approximateTerm` endpoint handles fuzzy input |
| RxNorm API unavailable | Low | Medium | Bundled `drug_classes.json` fallback lets users pick class-level without network |
| Interaction DB bloats past 10 MB | Low | Low | Monitor in M2, add an index-only build mode if needed |
| PHI (medications) leaks to Supabase | Very low | Very high | Build-time grep assertion; explicit test |
| Severity tier drift between pipeline and Flutter | Low | Medium | Single source of truth: `severity.dart` enum, pipeline mapper references the same values |

---

## 15. Out of Scope (v1)

Do not build these unless explicitly reopened:

- Food logging / diet tracking
- Gene-variant pharmacogenomics
- Full pharmacokinetic dose modeling
- Provider / clinical decision support UI
- Real-time drug approval feeds
- Interaction DB editing UI inside the app
- DrugBank integration (post-v1, pending license decision)

---

## 16. Operational Notes

### Release cadence

- `pharmaguide_core.db` and `interaction_db.sqlite` have **independent** release cycles.
- Pipeline builds both in the same CI run but stages them as separate artifacts in `scripts/dist/`.
- Flutter's `import_catalog_artifact.sh` can accept either one or both; it validates manifests independently.
- Version bump policy: patch version on `interaction_db.sqlite` for data-only updates, minor version for schema changes.

### Monitoring

- Add a dashboard card to `scripts/dashboard/views/quality.py` showing:
  - Total interactions shipped
  - Source breakdown (curated / suppai / overrides)
  - Count blocked by evidence gate per release
  - Top 10 most-referenced canonical_ids and RXCUIs

### Support

- Users who hit false positives can report from within the app. Reports append to a local log; user can share via email. No automatic telemetry (privacy).

---

## 17. Session State for Handoff

- **Spec version:** 2.0.0
- **Previous spec:** v1.0.0 (978 lines, written 2026-04-10 without Flutter infrastructure knowledge). This document replaces it.
- **Last architectural decision:** Ship M1 (stack nutrient accumulator) before any interaction DB work. M1 is Flutter-only, 2–3 days, closes the biggest medical gap independently.
- **Last user request:** "Turn everything you just told me in a detailed plan and update the previous interaction db you did also, so at the end of this session if i create another agent he know exactly what to do"
- **Artifacts waiting for next agent:**
  - User's draft JSON (~150 entries) — will be pasted into `scripts/data/curated_interactions/interactions_drafts_v0.json`
  - supp.ai full export — will be dropped at `scripts/data/suppai_import/suppai_raw.json`
  - UMLS + RxNorm API access already available via existing `env_loader.py`
- **What to do first in the next session:**
  1. Read this spec in full.
  2. Read the five "Existing Flutter Infrastructure" files in §4.
  3. Confirm the user is ready to start M1.
  4. Start M1 with TDD: write `stack_nutrient_aggregator_test.dart` first.
  5. Never touch M2+ until M1 is merged and green.
