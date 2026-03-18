# Flutter Data Contract v1

> Version: 1.2.0 — 2026-03-18
> How the Flutter app reads data from the final DB at each screen level.
> Updated: interaction_summary, dose_threshold_evaluation, condition/drug_class mapping, 45 interaction rules (pregnancy+hypertension+diabetes), diabetes merged, high_cholesterol added

---

## Screen 1: Scan Card

Source: `products_core` (local SQLite, instant)

```dart
class ScanCardData {
  final String dsldId;
  final String productName;
  final String brandName;
  final String? imageUrl;         // May be PDF — use placeholder if not a real image
  final String? thumbnailKey;     // runtime cache key, not a device path

  // Status
  final String productStatus;     // active, discontinued, off_market
  final String? discontinuedDate;
  final String formFactor;
  final String supplementType;

  // Score
  final double? scoreQuality80;
  final String? scoreDisplay80;              // pre-formatted "71.1/80"
  final String? scoreDisplay100Equivalent;   // pre-formatted "88.8/100"
  final double? score100Equivalent;          // derived convenience
  final String? grade;            // Exceptional/Excellent/Good/Fair/...
  final String verdict;           // SAFE/CAUTION/POOR/UNSAFE/BLOCKED/NOT_SCORED
  final String safetyVerdict;

  // Percentile
  final double? percentileTopPct;
  final String? percentileLabel;

  // Display
  final List<Map> badges;         // from JSON column
  final List<String> topWarnings; // from JSON column, max 5
  final List<String> certPrograms;

  // Safety quick flags
  final bool hasBannedSubstance;
  final bool hasRecalledIngredient;  // ingredient-level, NOT product recall
  final bool hasHarmfulAdditives;
  final bool hasAllergenRisks;
  final String? blockingReason;      // e.g. high_risk_ingredient, recalled_ingredient
}
```

**SQL query:**
```sql
SELECT dsld_id, product_name, brand_name, image_url, thumbnail_key,
       product_status, discontinued_date, form_factor, supplement_type,
       score_quality_80, score_display_80, score_display_100_equivalent,
       score_100_equivalent, grade, verdict, safety_verdict,
       percentile_top_pct, percentile_label,
       badges, top_warnings, cert_programs,
       has_banned_substance, has_recalled_ingredient,
       has_harmful_additives, has_allergen_risks, blocking_reason
FROM products_core
WHERE upc_sku = ?
ORDER BY CASE product_status WHEN 'active' THEN 0 ELSE 1 END,
         score_quality_80 DESC,
         dsld_id
LIMIT 1
```

Note: UPCs are not unique in the export. The app should either use the deterministic
ordering above for the instant scan card, or fetch all matches and offer a chooser
when the barcode resolves to multiple products.

**What the user sees:**
- Product name + brand
- Score circle (score_quality_80 normalized to 100 if no profile, or combined with fit_20 if profile exists)
- Grade word
- Verdict badge (color-coded)
- Top 3-5 warnings
- Certification badges
- Status badge (if discontinued/off-market)

---

## Screen 2: Full Product Page

Source: `products_core` (instant) + `product_detail_cache` (cached or fetched)

### Top section (instant, from products_core):

```dart
class ProductPageHeader {
  // Everything from ScanCardData, plus:
  final double mappedCoverage;

  // Section scores (for radar/bar chart)
  final double scoreIngredientQuality;     // /25
  final double scoreIngredientQualityMax;
  final double scoreSafetyPurity;          // /30
  final double scoreSafetyPurityMax;
  final double scoreEvidenceResearch;      // /20
  final double scoreEvidenceResearchMax;
  final double scoreBrandTrust;            // /5
  final double scoreBrandTrustMax;

  // Percentile detail
  final double? percentileRank;
  final String? percentileCategory;
  final int? percentileCohort;

  // Compliance tags
  final bool isGlutenFree;
  final bool isDairyFree;
  final bool isSoyFree;
  final bool isVegan;
  final bool isVegetarian;
  final bool isOrganic;

  // Quick info
  final bool isProbiotic;
  final bool containsSugar;
  final bool containsSodium;
  final bool diabetesFriendly;       // false when data absent — cautious default
  final bool hypertensionFriendly;   // false when data absent — cautious default
  final bool isTrustedManufacturer;
  final bool hasThirdPartyTesting;
  final bool hasFullDisclosure;
}
```

### Detail section (from detail blob):

```dart
class ProductDetail {
  final List<IngredientDetail> ingredients;
  final List<InactiveIngredient> inactiveIngredients;
  final List<Warning> warnings;
  final SectionBreakdown sectionBreakdown;
  final ComplianceDetail complianceDetail;
  final CertificationDetail certificationDetail;
  final ProprietaryBlendDetail proprietaryBlendDetail;
  final DietarySensitivityDetail dietarySensitivityDetail;
  final ServingInfo servingInfo;
  final ManufacturerDetail manufacturerDetail;
  final EvidenceData? evidenceData;
  final RdaUlData? rdaUlData;     // may exist with collectionEnabled == false and a reason
}
```

**Loading flow:**
```
1. Show header instantly from products_core
2. Check product_detail_cache for dsld_id
3. If cached -> parse JSON -> render detail sections
4. If not cached + online -> fetch from Supabase -> save to cache -> render
5. If not cached + offline -> show header only, "Detail unavailable offline"
```

---

## Screen 3: Ingredient Detail (bottom sheet / detail card)

Source: `product_detail_cache` -> `ingredients[]` or `inactive_ingredients[]`

```dart
class IngredientDetail {
  final String rawSourceText;
  final String name;              // label-facing name
  final String standardName;      // cleaned label standardName
  final String normalizedKey;     // cleaned normalized_key
  final List<Map> forms;          // cleaned forms[] from label parsing
  final double? quantity;
  final String? unit;

  final String standard_name;     // IQM canonical name
  final String? form;             // IQM resolved form
  final String? matched_form;     // selected form match
  final List<Map> matched_forms;  // full multi-form evidence when present
  final List<Map> extracted_forms;// raw extracted form tokens when present
  final int? bio_score;           // 0-14
  final bool? natural;
  final double? score;            // real upstream field, do not rename
  final String notes;             // educational text from IQM form notes
  final String category;
  final bool mapped;
  final List<Map> safety_hits;    // exact upstream safety_hits plus export-derived entries
  final double? normalizedAmount;
  final String? normalizedUnit;

  // Computed fields
  final String role;              // always "active"
  final String parentKey;
  final double? dosage;
  final String? dosageUnit;
  final double? normalizedValue;
  final bool isMapped;

  // Safety flags
  final bool isHarmful;
  final String? harmfulSeverity;  // critical/high/moderate/low
  final String? harmfulNotes;     // mechanism or category
  final bool isBanned;            // exact/alias banned ingredient match
  final bool isAllergen;          // derived from allergen hit matching
}

class InactiveIngredient {
  final String rawSourceText;
  final String name;
  final String standardName;
  final String normalizedKey;
  final List<Map> forms;
  final String category;          // from enrichment or other_ingredients.json reference
  final bool isAdditive;
  final String? additiveType;     // from enrichment or other_ingredients.json reference

  // Reference data (from harmful_additives.json or other_ingredients.json)
  final String? standardName;     // canonical name from reference DB
  final String? severityLevel;    // harmful additive severity (empty if not harmful)
  final String? matchMethod;
  final String? matchedAlias;
  final String notes;             // educational text: harmful_additives notes or other_ingredients notes
  final String? mechanismOfHarm;  // harmful additive mechanism (empty if not harmful)
  final List<String> commonUses;  // from other_ingredients.json, e.g. ["emulsifier", "binder"]
  final List<String> populationWarnings; // at-risk groups from harmful_additives.json

  // Safety flags
  final bool isHarmful;
  final String? harmfulSeverity;
  final String? harmfulNotes;     // mechanism > notes > classification_evidence > category
}
```

**What the user sees when tapping an active ingredient:**
- Ingredient name + form
- Bio score + natural + score explanation
- Dosage with units
- Raw label text so the user sees exactly what was scanned
- Educational notes (the "why this form matters" text from IQM)
- Safety flags if harmful/banned/allergen
- Category tag

**What the user sees when tapping an inactive ingredient:**
- Ingredient name + category
- Additive type badge
- Common uses tags (e.g. "emulsifier", "coating")
- Educational notes (from other_ingredients.json or harmful_additives.json)
- If harmful: severity badge + mechanism of harm + population warnings
- If not harmful: neutral informational display

---

## Screen 4: Warning Detail (expandable / bottom sheet)

Source: `product_detail_cache` -> `warnings[]`

```dart
class Warning {
  final String type;              // banned_substance, recalled_ingredient, watchlist_substance,
                                  // high_risk_ingredient, harmful_additive, allergen,
                                  // interaction, drug_interaction, dietary, status
  final String severity;          // critical, high, moderate, low, info
  final String title;             // short display title
  final String detail;            // primary explanation text

  // Type-specific fields (nullable, present based on type):

  // banned/recalled/watchlist/high_risk:
  final String? date;                  // regulatory date
  final String? regulatoryDateLabel;   // "First FDA enforcement action"
  final String? clinicalRisk;          // "critical", "high", "moderate", "low"

  // harmful_additive:
  final String? notes;                 // educational context
  final String? mechanismOfHarm;       // biological mechanism
  final List<String>? populationWarnings; // at-risk groups
  final String? category;             // e.g. "colorant_artificial"

  // allergen:
  final String? notes;                 // cross-reactivity info, clinical severity
  final String? supplementContext;     // why this allergen appears in supplements
  final String? prevalence;            // "high", "moderate", "low"

  // interaction / drug_interaction:
  final String? action;                // actionable guidance ("Do not use...")
  final String? evidenceLevel;         // "established", "probable", "theoretical"
  final List<String>? sources;         // DOI/URL citations

  // all types:
  final String source;                 // provenance: "banned_recalled_ingredients",
                                       // "harmful_additives_db", "allergen_db",
                                       // "interaction_rules", "dietary_sensitivity_data", "dsld"
}
```

**What the user sees when expanding a warning:**
- Title + severity badge (color-coded)
- Detail text (reason for banned, mechanism for harmful, etc.)
- For interactions: actionable guidance + evidence level + citation links
- For allergens: supplement context + prevalence indicator
- For harmful additives: mechanism + population warnings
- Source attribution for credibility

---

## Section F: User Fit Score (computed on-device)

Source: `user_profile` + `reference_data` + `product_detail_cache.ingredients[]`

```dart
class FitScoreResult {
  final double scoreFit20;        // 0-20
  final double scoreCombined100;  // (scoreQuality80 + scoreFit20) * 100 / 100
  final double maxPossible;       // depends on which profile fields are filled

  // Sub-scores
  final double dosageAppropriate; // E1: 0-7
  final double goalMatch;         // E2a: 0-2
  final double ageAppropriate;    // E2b: 0-3
  final double medicalCompat;     // E2c: 0-8

  // Missing profile handling
  final List<String> missingFields; // ["age", "conditions"]
  final String displayText;       // "85/96 (88.5%) - Complete profile for full scoring"
}
```

**This is NEVER stored in the DB or pipeline output.** Always computed fresh on-device
from the user's current profile state.

---

## Barcode Lookup Query

```sql
-- Primary: exact UPC match
SELECT * FROM products_core
WHERE upc_sku = ?
ORDER BY CASE product_status WHEN 'active' THEN 0 ELSE 1 END,
         score_quality_80 DESC,
         dsld_id
LIMIT 1;

-- Fallback: FTS search
SELECT p.* FROM products_core p
JOIN products_fts f ON p.rowid = f.rowid
WHERE products_fts MATCH ?;
```

---

## Filter/Search Queries

```sql
-- Vegan products with score > 70, sorted by score
SELECT * FROM products_core
WHERE is_vegan = 1 AND score_quality_80 > 56  -- 56/80 = 70/100
ORDER BY score_quality_80 DESC;

-- Products with allergen risks
SELECT * FROM products_core WHERE has_allergen_risks = 1;

-- Gluten-free multivitamins
SELECT * FROM products_core
WHERE is_gluten_free = 1 AND supplement_type = 'multivitamin';

-- Text search
SELECT p.* FROM products_core p
JOIN products_fts f ON p.rowid = f.rowid
WHERE products_fts MATCH 'omega fish oil';
```

---

## What the App Does NOT Get from the Pipeline

| Data | Where it comes from |
|---|---|
| `score_fit_20` | Computed on-device |
| `score_combined_100` | Computed on-device |
| Price / daily cost | User enters manually |
| Offline images | Runtime cache or placeholder |
| Product-level recalls | Future: separate FDA data source |
| Account data | Supabase user_sync_data |

---

## Implementation Notes for Flutter Developers

### 1. Mixed naming conventions in ingredient JSON

The detail blob uses **both** camelCase and snake_case on the same ingredient object.
This is intentional — they come from different pipeline stages:

- `standardName` — from label parsing (camelCase, label provenance)
- `standard_name` — from IQM quality mapping (snake_case, scoring provenance)
- `bio_score`, `matched_form`, `extracted_forms` — IQM fields (snake_case)
- `normalizedKey`, `rawSourceText` — label fields (varies)

**Do NOT normalize these.** Use explicit `@JsonKey` annotations:
```dart
@JsonKey(name: 'standardName')
final String standardName;     // label-parsed canonical

@JsonKey(name: 'standard_name')
final String standardNameIqm;  // IQM-resolved canonical
```

### 2. Warnings are polymorphic

The `type` field determines which optional fields are populated.
Do not use one flat model — use a sealed class or discriminated union:

```dart
sealed class Warning {
  String get type;
  String get severity;
  String get title;
  String get detail;
  String get source;
}

class BannedSubstanceWarning extends Warning { ... }
class HarmfulAdditiveWarning extends Warning { ... }
class AllergenWarning extends Warning { ... }
class InteractionWarning extends Warning { ... }
// etc.
```

Or use a single `Warning` class with nullable type-specific fields.
Either way, the parsing must check `type` before accessing fields like
`action`, `populationWarnings`, or `supplementContext`.

### 3. score_quality_80 can be NULL

Products with `verdict == "NOT_SCORED"` have `score_quality_80 = NULL`,
`grade = NULL`, `score_display_80 = NULL`, etc. Every score display path
needs a null guard. Show "Not Scored" or equivalent — never show 0.

### 4. image_url may be a PDF link

Many DSLD products have label PDF URLs, not actual image URLs.
Check for `.pdf` extension and show a placeholder image instead.
The `thumbnail_key` field is NULL at export — the app populates it
at runtime when it caches a real image.

### 5. reference_data is TEXT JSON — parse once at startup

The `reference_data` table stores large JSON blobs (up to ~200KB each).
Parse these once at app startup and hold the parsed objects in memory.
Do not re-parse on every product view or fit score calculation.

```dart
// At app startup:
final rdaData = jsonDecode(db.query('reference_data', where: 'key = ?', whereArgs: ['rda_optimal_uls']).first['data']);
// Cache rdaData in a singleton/provider — reuse for all fit score calculations.
```

### 6. diabetes_friendly / hypertension_friendly default to false

When dietary sensitivity data is absent or incomplete, these fields
default to `0` (false). This is the cautious/safe default for a medical app.
Do NOT interpret `false` as "confirmed not friendly" — it means
"insufficient data to confirm friendly." The UI should distinguish between
"not friendly" (explicit data) and "unknown" (data absent) if needed
by checking whether `dietary_sensitivity_detail` is populated in the
detail blob.

### 7. UPC collisions

Multiple products can share the same `upc_sku`. The barcode scan query
uses deterministic ordering (active first, highest score, lowest dsld_id)
to pick one, but consider showing a chooser when `COUNT(*) > 1` for a UPC.

### 8. User condition ID mapping

The app profile Health Concerns chips must map to the exact `condition_id` values
used in the pipeline taxonomy. This table is the single source of truth:

| App UI Chip | `condition_id` | Category | Notes |
|---|---|---|---|
| Pregnancy | `pregnancy` | reproductive | Teratogenicity, retinoid exposure, uterine stimulants |
| Lactation/Breastfeeding | `lactation` | reproductive | Transfer via breast milk, infant safety |
| Trying to Conceive (TTC) | `ttc` | reproductive | Fertility impact — clinically distinct from pregnancy |
| Hypertension | `hypertension` | cardiovascular | BP elevation, sympathomimetics |
| Heart Disease | `heart_disease` | cardiovascular | Cardiac risk, QT prolongation |
| Diabetes/Blood Sugar | `diabetes` | metabolic | Covers type 1 and type 2 (merged) |
| High Cholesterol | `high_cholesterol` | cardiovascular | Statin interactions, liver load |
| Liver Disease | `liver_disease` | hepatic | Hepatotoxicity, metabolism impairment |
| Kidney Disease | `kidney_disease` | renal | Accumulation risk, electrolyte imbalance |
| Thyroid Condition | `thyroid_disorder` | endocrine | Absorption interference, iodine sensitivity |
| Autoimmune | `autoimmune` | immunologic | Immune stimulation contraindications |
| Epilepsy/Seizures | `seizure_disorder` | neurologic | Seizure threshold lowering |
| Bleeding Disorders | `bleeding_disorders` | hematologic | Anticoagulant potentiation |
| Upcoming Surgery | `surgery_scheduled` | perioperative | Bleeding risk, anesthesia interactions |

Drug class chips (from user's medication list):

| App UI Chip | `drug_class_id` | Notes |
|---|---|---|
| Blood Thinners | `anticoagulants` | Warfarin, heparin, DOACs |
| Antiplatelet Agents | `antiplatelets` | Aspirin, clopidogrel |
| NSAIDs | `nsaids` | Ibuprofen, naproxen |
| Blood Pressure Meds | `antihypertensives` | ACE inhibitors, ARBs, CCBs |
| Diabetes Medications | `hypoglycemics` | Metformin, insulin, sulfonylureas |
| Thyroid Medications | `thyroid_medications` | Levothyroxine |
| Sedatives/Sleep Aids | `sedatives` | Benzodiazepines, Z-drugs |
| Immunosuppressants | `immunosuppressants` | Cyclosporine, tacrolimus |
| Statins/Cholesterol | `statins` | Atorvastatin, simvastatin |

**TTC vs Pregnancy vs Lactation**: These are three separate conditions because
the clinical risks differ. Pregnancy warnings are about teratogenicity (birth defects).
TTC warnings are about fertility impact (e.g., high-dose vitamin A reducing
fertility). Lactation warnings are about transfer through breast milk. The user
can select one or more. The app should match against all selected conditions.

### 9. Instant condition flagging on scan

When a user scans a product, use `interaction_summary` from the detail blob
for instant flagging — do NOT re-compute from warnings:

```dart
// Instant check from detail blob
final summary = blob['interaction_summary'];
if (summary != null) {
  final userConditions = userProfile.conditions; // {'pregnancy', 'diabetes'}
  final flagged = userConditions.intersection(
    summary['condition_summary'].keys.toSet()
  );

  for (final condition in flagged) {
    final info = summary['condition_summary'][condition];
    // info.highest_severity = "contraindicated"
    // info.ingredients = ["Vitamin A Palmitate"]
    // info.actions = ["Do not use preformed Vitamin A..."]
    showConditionAlert(condition, info);
  }
}
```

For detailed per-warning view with dose thresholds, filter the `warnings` array
by `condition_id` matching the user's conditions.
