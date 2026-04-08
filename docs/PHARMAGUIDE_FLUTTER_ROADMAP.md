# PharmaGuide Flutter App — Development Roadmap v1.0

> **Version:** 1.0 — 2026-04-07  
> **Backend:** Export Schema v1.3.0 (87 columns, 22 new fields for optimization)  
> **Target:** MVP launch with validated profile setup and FitScore engine

---

## 🎯 DEVELOPMENT PHILOSOPHY

### Core Principles

1. **Offline-First:** SQLite cache → Supabase hydration (graceful degradation)
2. **Privacy-First:** User health data never leaves device (E1-E2c scoring computed locally)
3. **Performance-First:** 80% reduction in network calls via pre-computed fields
4. **Safety-First:** Medical interaction warnings before user adds to stack

### Architecture

- **Local DB:** `pharmaguide_core.db` (90MB, ~180K products) + `user_data.db` (profile, stack, favorites)
- **Remote:** Supabase storage (detail blobs on-demand, OTA DB updates)
- **Scoring:** Read A+B+C+D from pipeline, compute E1+E2a+E2b+E2c on-device
- **Reference Data:** Bundle 4 JSON files (~290KB) for RDA/UL, goal mappings, taxonomy

---

## 📅 SPRINT BREAKDOWN

### ✅ Sprint 0: Foundation (Week 1-2) — VALIDATED

#### User Profile Setup (CRITICAL)

**Status:** Schema-validated against pipeline databases  
**Documentation:** `docs/PROFILE_SETUP_VALIDATION_GUIDE.md`

**Screens:**

1. **Welcome/Onboarding** (Skip-able)
   - App benefits overview
   - Privacy statement
   - "Get Started" CTA

2. **Profile Setup Flow** (Multi-step form)

   **Step 1: Basic Info** (Required for FitScore)
   - Nickname (optional, text input)
   - Age Bracket (required, dropdown)
     - ✅ **VALIDATED:** 5 exact values from `rda_optimal_uls.json`
     - Options: "14-18", "19-30", "31-50", "51-70", "71+"
   - Sex (required, radio buttons)
     - ✅ **VALIDATED:** Male, Female, Other, Prefer not to say
     - Fallback: Other/Prefer not to say → Use highest UL for all nutrients

   **Step 2: Health Goals** (Optional, max 2)
   - ✅ **VALIDATED:** All 18 goal IDs from `user_goals_to_clusters.json`
   - UI: Modal with multi-select chips
   - Sorting: High priority → Medium → Low
   - Validation: Enforce max 2 selections, detect conflicting goals
   - Display: Use `user_facing_goal` field for labels

   **Step 3: Health Profile** (Optional, critical for safety)
   - **Section A: Health Concerns** (14 conditions)
     - ✅ **VALIDATED:** All 14 from `clinical_risk_taxonomy.json`
     - Sort by `display_priority` (pregnancy, lactation, TTC first)
     - Max recommended: 5-7 selections
   - **Section B: Medications You Take** (9 drug classes)
     - ✅ **VALIDATED:** All 9 from `clinical_risk_taxonomy.json`
     - Quick-select helpers (e.g., "Taking BP meds?" if hypertension selected)
     - No max limit

   **Step 4: Allergies** (Optional)
   - ✅ **VALIDATED:** All 17 from `allergens.json`
   - ❌ **REMOVE:** Medication allergies (Penicillin, Sulfa, NSAIDs) — not relevant
   - Sort by prevalence (high → moderate → low)
   - No max limit

   **Step 5: Review & Save**
   - Profile completeness score (0-100%)
   - "Save & Continue" button
   - "Skip for now" option (minimum: age + sex required for FitScore)

**Data Models:**

```dart
class UserProfile {
  String? nickname;
  String? ageBracket;  // "14-18", "19-30", etc.
  String? sex;         // "Male", "Female", "Other", "Prefer not to say"
  List<String> goals;  // max 2, e.g., ["GOAL_SLEEP_QUALITY", "GOAL_REDUCE_STRESS_ANXIETY"]
  List<String> conditions;  // e.g., ["pregnancy", "diabetes"]
  List<String> drugClasses; // e.g., ["anticoagulants", "statins"]
  List<String> allergens;   // e.g., ["ALLERGEN_SOY", "ALLERGEN_MILK"]
  DateTime createdAt;
  DateTime lastUpdated;
}
```

**Critical Fixes from Validation:**

- ❌ **Remove medication allergies** (use only 17 food/supplement allergens)
- ⚠️ **Add Medications field** (missing from current draft)
- ⚠️ **Enforce max 2 goal selections** (currently unlimited)
- ✅ **Use exact schema IDs** (no free text options)

**Profile Completeness Scoring:**

```dart
// Required (40%)
- Age bracket: 20%
- Sex: 20%

// Optional (60%)
- Goals: 20%
- Conditions/Medications: 20%
- Allergies: 10%
- Nickname: 10%

Thresholds:
- 0-39%: Incomplete
- 40-59%: Basic
- 60-79%: Good
- 80-100%: Complete
```

---

### Sprint 1: Database & Core Services (Week 3-4)

#### 1.1 Local Database Setup

- SQLite initialization
- Table schemas:
  - `products_core` (mirror of pipeline export, 87 columns)
  - `products_fts` (full-text search)
  - `reference_data` (4 JSON files: RDA/UL, goals, taxonomy, interaction rules)
  - `user_profile` (profile data)
  - `user_stack` (my supplements)
  - `user_favorites` (bookmarked products)
  - `detail_blob_cache` (on-demand product details)

#### 1.2 Supabase Integration

- Connection setup
- OTA update check (compare `export_manifest.json` checksums)
- Download `pharmaguide_core.db` on first launch
- Download detail blobs on-demand

#### 1.3 Reference Data Bundler

- Bundle 4 JSON files into `reference_data` table:
  1. `rda_optimal_uls.json` (199KB) — E1, E2b
  2. `user_goals_to_clusters.json` (11KB) — E2a
  3. `clinical_risk_taxonomy.json` (5KB) — UI labels, E2c
  4. `interaction_rules.json` (75KB) — Reference only
- Total: ~290KB (compressed: ~80KB)

#### 1.4 Core Services

- `DatabaseService` (SQLite operations)
- `ProfileService` (CRUD for user profile)
- `SyncService` (Supabase sync)
- `ReferenceDataService` (load bundled JSON)

---

### Sprint 2: Product Catalog & Search (Week 5-6)

#### 2.1 Home Screen

- Search bar (placeholder)
- Profile completeness widget (if < 60%)
- Quick filters: "Omega-3", "Probiotics", "Adaptogens", etc.
- "My Stack" preview (3 products max, "View All" CTA)

#### 2.2 Search & Filter

- Full-text search (FTS5 index on `products_fts`)
- Category filters using new v1.3.0 fields:
  - `primary_category`
  - `contains_omega3`, `contains_probiotics`, etc.
  - `key_ingredient_tags`
- Sort options: Quality score, Goal match, Alphabetical
- Fast filtering (no detail blob fetch) ← **v1.3.0 enhancement**

#### 2.3 Product Card (Scan Results)

- Product name + brand
- Quality score (80-point, color-coded)
- Verdict badge (RECOMMENDED/REVIEW/MODERATE/UNSAFE/BLOCKED)
- Goal match badge (if profile complete) ← **v1.3.0 field: `goal_matches`**
- Allergen warning (if matches user allergies) ← **v1.3.0 field: `allergen_summary`**
- "Add to Stack" button

---

### Sprint 3: Product Detail Screen (Week 7-8)

#### 3.1 Detail View (Fetch detail blob)

- Product overview (image, name, brand, form factor)
- Score breakdown (A+B+C+D sections) — Read from pipeline
- **NEW:** FitScore (E section) — Compute on-device
  - E1: Dosage appropriateness (age/sex-specific RDA/UL)
  - E2a: Goal alignment
  - E2b: Age appropriateness
  - E2c: Medical compatibility
- Combined score (A+B+C+D+E) = 100-point final score

#### 3.2 Warnings & Safety

- Interaction warnings (condition + drug class)
  - Read from `interaction_summary` ← Pre-computed in pipeline
  - Display severity-coded banners (contraindicated/avoid/caution/monitor)
- Banned/recalled gate (BLOCKED verdict)
- Harmful additives list
- Allergen warnings

#### 3.3 Evidence & Research

- Clinical studies (PMID links)
- Evidence tier badges
- Synergy clusters ← **v1.3.0 field: `synergy_detail`**

#### 3.4 Actions

- "Add to Stack" (with stack interaction check)
- "Share" ← **v1.3.0 fields: `share_title`, `share_description`, `share_highlights`**
- "Save to Favorites"

---

### Sprint 4: FitScore Engine (Week 9-10)

**CRITICAL:** This is the ONLY on-device scoring. Everything else is pre-computed by pipeline.

#### 4.1 E1: Dosage Appropriateness (7 pts)

```dart
class E1Calculator {
  Future<double> calculate(
    List<Ingredient> nutrients,
    String? ageBracket,
    String? sex,
  ) async {
    // Load rda_optimal_uls.json from reference_data
    // For each nutrient:
    //   1. Get age/sex-specific RDA and UL
    //   2. Calculate percent of RDA
    //   3. Apply scoring:
    //      - UL exceeded: -5 pts
    //      - 50-200% of RDA: +7/n pts
    //      - 25-50% of RDA: +4/n pts
    //      - < 25% of RDA: +2/n pts
    // Clamp to [-5, 7]
  }
}
```

#### 4.2 E2a: Goal Alignment (2 pts)

```dart
class E2aCalculator {
  double calculate(
    List<String> productClusters,  // from detail_blob.synergy_detail
    List<String> userGoals,         // from user_profile
  ) {
    // Load user_goals_to_clusters.json
    // For each user goal:
    //   Calculate weighted match against product clusters
    // Normalize to 0-2 scale
  }
}
```

#### 4.3 E2b: Age Appropriateness (3 pts)

```dart
class E2bCalculator {
  Future<double> calculate(
    List<Ingredient> nutrients,
    String? ageBracket,
  ) async {
    // Load rda_optimal_uls.json
    // For each nutrient:
    //   Get age-group average RDA
    //   Penalize if way outside range (< 10% or > 500%)
    // Clamp to [0, 3]
  }
}
```

#### 4.4 E2c: Medical Compatibility (8 pts)

```dart
class E2cCalculator {
  double calculate(
    Map<String, dynamic> interactionSummary,  // from detail_blob
    List<String> userConditions,
    List<String> userDrugClasses,
  ) {
    // Start with 8 pts
    // Check condition_summary for matches
    //   contraindicated: -8 (product disqualified)
    //   avoid: -5
    //   caution: -3
    //   monitor: -1
    // Check drug_class_summary for matches (same penalties)
    // Clamp to [0, 8]
  }
}
```

#### 4.5 Combined FitScore

```dart
class FitScoreCalculator {
  Future<FitScoreResult> calculate(
    ProductsCore product,
    DetailBlob blob,
    UserProfile profile,
  ) async {
    final e1 = await E1Calculator().calculate(...);
    final e2a = E2aCalculator().calculate(...);
    final e2b = await E2bCalculator().calculate(...);
    final e2c = E2cCalculator().calculate(...);

    final scoreFit20 = e1 + e2a + e2b + e2c;  // 0-20
    final scoreCombined100 = (product.scoreQuality80 + scoreFit20) * 100 / 100;

    return FitScoreResult(
      scoreFit20: scoreFit20,
      scoreCombined100: scoreCombined100,
      e1: e1,
      e2a: e2a,
      e2b: e2b,
      e2c: e2c,
    );
  }
}
```

---

### Sprint 5: Stack Management & Interaction Checking (Week 11-12)

**CRITICAL:** Uses new v1.3.0 `ingredient_fingerprint` for instant multi-product safety validation.

#### 5.1 My Stack Screen

- List view: All products in stack
- Per-product: Name, brand, dosing summary ← **v1.3.0 field: `dosing_summary`**
- Total products count
- Stack health score (aggregate safety)

#### 5.2 Stack Interaction Checker

```dart
class StackInteractionChecker {
  Future<List<StackWarning>> checkSafety(
    ProductsCore newProduct,
    List<ProductsCore> stackProducts,
  ) async {
    final warnings = <StackWarning>[];

    // Parse ingredient fingerprints (NO DETAIL BLOB FETCH NEEDED)
    final newFp = jsonDecode(newProduct.ingredientFingerprint);
    final stackFps = stackProducts.map((p) => jsonDecode(p.ingredientFingerprint)).toList();

    // Check 1: Cumulative nutrient doses
    for (final nutrient in newFp['nutrients'].keys) {
      double totalDose = newFp['nutrients'][nutrient]['amount'];
      for (final stackFp in stackFps) {
        if (stackFp['nutrients'].containsKey(nutrient)) {
          totalDose += stackFp['nutrients'][nutrient]['amount'];
        }
      }

      // Check against UL from rda_optimal_uls.json
      final ul = await lookupUL(nutrient, userProfile);
      if (totalDose > ul) {
        warnings.add(StackWarning(
          type: 'cumulative_dose_exceeded',
          severity: 'high',
          nutrient: nutrient,
          totalDose: totalDose,
          ul: ul,
        ));
      }
    }

    // Check 2: Conflicting pharmacological effects
    final hasStimulant = newProduct.containsStimulants == 1;
    final hasSedativeInStack = stackProducts.any((p) => p.containsSedatives == 1);

    if (hasStimulant && hasSedativeInStack) {
      warnings.add(StackWarning(
        type: 'antagonistic_effects',
        severity: 'moderate',
        message: 'Stack contains both stimulants and sedatives',
      ));
    }

    // Check 3: Duplicate ingredients (same herb/nutrient in multiple products)
    // ... implementation

    return warnings;
  }
}
```

**Performance:** <100ms (no network, all data in `products_core`) ← **v1.3.0 enhancement**

#### 5.3 Add to Stack Flow

1. User taps "Add to Stack" on product detail
2. Run `StackInteractionChecker.checkSafety()`
3. If warnings:
   - Display modal with warnings (high → moderate → low severity)
   - User confirms or cancels
4. If no warnings or confirmed:
   - Add to `user_stack` table
   - Show success toast
   - Navigate to My Stack screen

#### 5.4 Stack Actions

- Remove from stack
- View product detail
- Check for interactions (re-run checker)

---

### Sprint 6: Social Sharing (Week 13)

**USES:** New v1.3.0 pre-computed fields (`share_title`, `share_description`, `share_highlights`)

#### 6.1 Share Button (Product Detail)

```dart
void shareProduct(ProductsCore product) {
  final highlights = (jsonDecode(product.shareHighlights) as List).join('\n• ');

  Share.share('''
${product.shareTitle}

${product.shareDescription}

✨ Why it's great:
• $highlights

Analyzed by PharmaGuide 📊
''',
    subject: product.shareTitle,
  );
}
```

**Performance:** Instant (no detail blob fetch) ← **v1.3.0 enhancement**

#### 6.2 Instagram Story Template (Optional)

- Generate branded story image
- Include product photo, score, top highlight
- Deep link to product detail

---

### Sprint 7: Settings & Profile Management (Week 14)

#### 7.1 Settings Screen

- Edit profile (re-open profile setup flow)
- Privacy settings
- Notification preferences
- About / Legal

#### 7.2 Profile Edit

- Allow updating all profile fields
- Re-compute FitScores for all favorited products
- Show impact: "3 products now have higher fit scores!"

#### 7.3 Data Export

- Export user data (profile, stack, favorites) as JSON
- GDPR compliance

---

### Sprint 8: Polish & Testing (Week 15-16)

#### 8.1 UI/UX Polish

- Loading states
- Empty states
- Error handling
- Animations (micro-interactions)

#### 8.2 Performance Optimization

- Lazy loading for product lists
- Image caching
- Database query optimization

#### 8.3 Testing

- Unit tests (FitScore calculators)
- Widget tests (profile setup, search)
- Integration tests (full user flows)
- Manual QA (iOS + Android)

---

## 📊 FEATURE COMPARISON: Before vs After v1.3.0

| Feature            | Before v1.3.0               | After v1.3.0          | Improvement       |
| ------------------ | --------------------------- | --------------------- | ----------------- |
| Stack safety check | 2-5s (fetch 5 detail blobs) | <100ms (fingerprints) | **20-50x faster** |
| Social share       | 500ms (fetch detail blob)   | <10ms (pre-computed)  | **50x faster**    |
| Category filter    | 1-2s (FTS scan)             | <50ms (indexed)       | **20-40x faster** |
| Goal match badge   | 500ms (fetch detail blob)   | <10ms (pre-computed)  | **50x faster**    |
| Dosing info        | 500ms (fetch detail blob)   | <10ms (pre-computed)  | **50x faster**    |
| Allergen warning   | 500ms (fetch detail blob)   | <10ms (pre-computed)  | **50x faster**    |

**Overall:** ~80% reduction in detail blob fetches

---

## 🔐 PRIVACY & SECURITY

### Local Storage

- User profile: Encrypted SQLite (`flutter_secure_storage`)
- Health data NEVER uploaded to Supabase
- FitScore calculations 100% on-device

### Supabase

- Only stores: Product catalog, detail blobs, images
- No PII, no health data
- Read-only access (user can't modify product data)

### OTA Updates

- Checksum verification (`export_manifest.json`)
- Rollback on corruption
- Silent background sync

---

## 🚀 MVP LAUNCH CRITERIA

### Must-Have (Blockers)

- [x] Profile setup validated against schemas
- [ ] All 7 profile fields implemented with exact IDs
- [ ] FitScore engine (E1, E2a, E2b, E2c) complete
- [ ] Stack interaction checker complete
- [ ] Search & filter working
- [ ] Product detail screen complete
- [ ] At least 180K products loaded

### Nice-to-Have (Post-MVP)

- [ ] Social sharing with Instagram templates
- [ ] Barcode scanning
- [ ] Offline mode (full local catalog)
- [ ] Push notifications (FDA recalls)
- [ ] Personalized recommendations

---

## 📈 SUCCESS METRICS

### Technical

- App size: <60MB (iOS/Android)
- Cold start: <3s
- Search latency: <200ms
- FitScore calculation: <100ms
- Stack interaction check: <100ms
- Detail blob fetch: <500ms (on cache miss)

### User Experience

- Profile completion rate: >60%
- Stack adoption: >40% of users add ≥1 product
- Average session time: >3 minutes
- Interaction warning engagement: >80% read rate

---

**Next Steps:** Implement Sprint 0 profile setup with validated schemas, then proceed sequentially through sprints.
