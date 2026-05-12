# Profile Setup Field Validation Guide v1.0

> **Date:** 2026-04-07  
> **Purpose:** Ensure Flutter profile setup UI aligns exactly with pipeline database schemas  
> **Critical for:** FitScore calculations (E1, E2a, E2b, E2c), interaction warnings, allergen flagging

---

## ✅ VALIDATION CHECKLIST

### Field 1: Nickname (Optional)

- **UI:** Text input
- **Storage:** `user_data.db → user_profile.nickname`
- **Validation:** None required (display name only)
- **Schema Dependency:** None
- **Status:** ✅ VALID AS-IS

---

### Field 2: Age Bracket (Required for E1, E2b)

**MUST MATCH:** `scripts/data/rda_optimal_uls.json` → `_metadata.age_brackets`

#### ✅ VALIDATED OPTIONS (5 total):

```dart
enum AgeBracket {
  young14_18('14-18'),   // Adolescent
  adult19_30('19-30'),   // Young adult
  adult31_50('31-50'),   // Middle adult
  senior51_70('51-70'),  // Senior
  elderly71Plus('71+');  // Elderly

  final String value;
  const AgeBracket(this.value);
}
```

**UI Implementation:**

- Display: Dropdown or radio buttons
- Labels: Use age ranges directly ("14-18", "19-30", etc.)
- Default: None (force selection)
- Storage: Store the string value ("14-18", "19-30", etc.) exactly as shown

**Used For:**

- E1: Age/sex-specific RDA/UL lookups
- E2b: Age appropriateness scoring (penalize if nutrients way outside age-appropriate range)

**Status:** ✅ EXACT MATCH — Use these 5 values verbatim

---

### Field 3: Sex (Required for E1)

**MUST MATCH:** `scripts/data/rda_optimal_uls.json` → `nutrient_recommendations[].data[].group`

#### ✅ VALIDATED OPTIONS:

```dart
enum Sex {
  male('Male'),
  female('Female'),
  other('Other'),              // Default to highest UL for safety
  preferNotToSay('Prefer not to say');  // Default to highest UL for safety

  final String value;
  const Sex(this.value);

  String getRdaGroup() {
    switch (this) {
      case Sex.male:
        return 'Male';
      case Sex.female:
        return 'Female';
      case Sex.other:
      case Sex.preferNotToSay:
        return 'highest_ul_fallback';  // Use highest UL for all nutrients
    }
  }
}
```

**UI Implementation:**

- Display: Radio buttons or dropdown
- Labels: "Male", "Female", "Other", "Prefer not to say"
- Default: None (force selection)
- Storage: Store the enum value

**Safety Handling:**

- For "Other" or "Prefer not to say": Use `highest_ul` from each nutrient entry (conservative approach)
- E1 scoring: Still apply UL penalties based on highest UL
- E2b scoring: Use average RDA for age group (not sex-specific)

**Used For:**

- E1: Sex-specific RDA/UL lookups (Male vs Female have different values)

**Status:** ✅ VALID — "Other" and "Prefer not to say" handled conservatively

---

### Field 4: Health Goals (Optional, max 2 selections)

**MUST MATCH:** `scripts/data/user_goals_to_clusters.json` → `user_goal_mappings[].id`

#### ✅ ALL 18 VALIDATED GOAL IDS:

```dart
enum HealthGoal {
  sleepQuality('GOAL_SLEEP_QUALITY', 'Sleep Quality', 'high'),
  reduceStressAnxiety('GOAL_REDUCE_STRESS_ANXIETY', 'Reduce Stress/Anxiety', 'high'),
  increaseEnergy('GOAL_INCREASE_ENERGY', 'Increase Energy', 'high'),
  digestiveHealth('GOAL_DIGESTIVE_HEALTH', 'Digestive Health', 'medium'),
  weightManagement('GOAL_WEIGHT_MANAGEMENT', 'Weight Management', 'high'),
  cardiovascularHeartHealth('GOAL_CARDIOVASCULAR_HEART_HEALTH', 'Cardiovascular/Heart Health', 'high'),
  healthyAgingLongevity('GOAL_HEALTHY_AGING_LONGEVITY', 'Healthy Aging/Longevity', 'high'),
  bloodSugarSupport('GOAL_BLOOD_SUGAR_SUPPORT', 'Blood Sugar Support', 'medium'),
  immuneSupport('GOAL_IMMUNE_SUPPORT', 'Immune Support', 'high'),
  focusMentalClarity('GOAL_FOCUS_MENTAL_CLARITY', 'Focus & Mental Clarity', 'high'),
  moodEmotionalWellness('GOAL_MOOD_EMOTIONAL_WELLNESS', 'Mood & Emotional Wellness', 'medium'),
  muscleGrowthRecovery('GOAL_MUSCLE_GROWTH_RECOVERY', 'Muscle Growth & Recovery', 'medium'),
  jointBoneMobility('GOAL_JOINT_BONE_MOBILITY', 'Joint & Bone Mobility', 'medium'),
  skinHairNails('GOAL_SKIN_HAIR_NAILS', 'Skin, Hair, & Nails', 'low'),
  liverDetox('GOAL_LIVER_DETOX', 'Liver & Detox Support', 'low'),
  prenatalPregnancy('GOAL_PRENATAL_PREGNANCY', 'Prenatal/Pregnancy Support', 'high'),
  hormonalBalance('GOAL_HORMONAL_BALANCE', 'Hormonal Balance', 'medium'),
  eyeVisionHealth('GOAL_EYE_VISION_HEALTH', 'Eye & Vision Health', 'low');

  final String id;
  final String label;
  final String priority;
  const HealthGoal(this.id, this.label, this.priority);
}
```

**UI Implementation:**

- Display: Modal with multi-select chips
- Instruction: "Select up to 2 goals for personalized recommendations"
- Sort order: High priority first, then medium, then low
- Max selections: 2 (enforce in UI)
- Storage: Array of goal IDs (e.g., `["GOAL_SLEEP_QUALITY", "GOAL_REDUCE_STRESS_ANXIETY"]`)

**Conflicting Goals Validation:**
Load `user_goals_to_clusters.json` and check `conflicting_goals` field:

```dart
// Example conflicts:
// GOAL_SLEEP_QUALITY conflicts with GOAL_INCREASE_ENERGY, GOAL_FOCUS_MENTAL_CLARITY
// GOAL_WEIGHT_MANAGEMENT conflicts with GOAL_PRENATAL_PREGNANCY
```

**Display Warning:**
"⚠️ Sleep Quality and Increase Energy may have opposing effects. Consider choosing complementary goals."

**Used For:**

- E2a: Goal alignment scoring (match product synergy clusters to user goals)
- Product recommendations

**Status:** ✅ ALL 18 GOALS VALIDATED — Use exact IDs, implement conflict detection

---

### Field 5: Health Concerns (Critical for E2c, max 5-7 selections recommended)

**MUST MATCH:** `scripts/data/clinical_risk_taxonomy.json` → `conditions[].id`

#### ✅ ALL 14 VALIDATED CONDITION IDS:

```dart
enum HealthCondition {
  pregnancy('pregnancy', 'Pregnancy', 1),
  lactation('lactation', 'Breastfeeding', 2),
  ttc('ttc', 'Trying to Conceive', 3),
  surgeryScheduled('surgery_scheduled', 'Upcoming Surgery', 4),
  hypertension('hypertension', 'High Blood Pressure', 5),
  heartDisease('heart_disease', 'Heart Disease', 6),
  diabetes('diabetes', 'Diabetes', 7),
  bleedingDisorders('bleeding_disorders', 'Bleeding Disorders', 8),
  kidneyDisease('kidney_disease', 'Kidney Disease', 9),
  liverDisease('liver_disease', 'Liver Disease', 10),
  thyroidDisorder('thyroid_disorder', 'Thyroid Condition', 11),
  autoimmune('autoimmune', 'Autoimmune Condition', 12),
  seizureDisorder('seizure_disorder', 'Epilepsy/Seizures', 13),
  highCholesterol('high_cholesterol', 'High Cholesterol', 14);

  final String id;
  final String label;
  final int displayPriority;
  const HealthCondition(this.id, this.label, this.displayPriority);
}
```

**UI Implementation:**

- Display: Modal with multi-select chips
- Instruction: "Select any health conditions that apply to you"
- Sort order: By `displayPriority` (1 = highest priority)
- Max selections: No hard limit, but recommend cap at 5-7 for UX
- "None" option: Implicit (empty array `[]`)
- Storage: Array of condition IDs (e.g., `["pregnancy", "diabetes"]`)

**Special Handling:**

- If "pregnancy" is selected AND user selects "diabetes", display info:
  "💡 If you have gestational diabetes, your doctor should review all supplements."

**Used For:**

- E2c: Medical compatibility scoring (check `interaction_summary.condition_summary` from detail blob)
- Critical interaction warnings (contraindicated/avoid/caution/monitor)

**Status:** ✅ ALL 14 CONDITIONS VALIDATED — Use exact IDs, sort by display_priority

---

### Field 6: Medications (Critical for E2c, separate from conditions)

**MUST MATCH:** `scripts/data/clinical_risk_taxonomy.json` → `drug_classes[].id`

#### ✅ ALL 9 VALIDATED DRUG CLASS IDS:

```dart
enum DrugClass {
  anticoagulants('anticoagulants', 'Anticoagulants', 1),
  antiplatelets('antiplatelets', 'Antiplatelet Agents', 2),
  nsaids('nsaids', 'NSAIDs', 3),
  antihypertensives('antihypertensives', 'Antihypertensives', 4),
  hypoglycemics('hypoglycemics', 'Glucose-Lowering Medications', 5),
  thyroidMedications('thyroid_medications', 'Thyroid Medications', 6),
  sedatives('sedatives', 'Sedatives', 7),
  immunosuppressants('immunosuppressants', 'Immunosuppressants', 8),
  statins('statins', 'Statins', 9);

  final String id;
  final String label;
  final int displayPriority;
  const DrugClass(this.id, this.label, this.displayPriority);
}
```

**UI Implementation:**

- Display: **SEPARATE modal from Health Concerns** (or same modal with clear section divider)
- Title: "Medications You Take"
- Instruction: "Select the types of medications you currently take"
- Sort order: By `displayPriority`
- Max selections: No limit
- "None" option: Implicit (empty array `[]`)
- Storage: Array of drug class IDs (e.g., `["anticoagulants", "statins"]`)

**Quick-Select Helpers (Recommended):**

```dart
// If user selects condition "hypertension", show:
"💊 Are you taking blood pressure medication?" → Auto-selects "antihypertensives"

// If user selects condition "diabetes", show:
"💊 Are you taking diabetes medication?" → Auto-selects "hypoglycemics"

// If user selects condition "high_cholesterol", show:
"💊 Are you taking cholesterol medication?" → Auto-selects "statins"
```

**Used For:**

- E2c: Medical compatibility scoring (check `interaction_summary.drug_class_summary` from detail blob)
- Critical drug-supplement interaction warnings

**Status:** ✅ ALL 9 DRUG CLASSES VALIDATED — Use exact IDs, separate from conditions

---

### Field 7: Allergies (Food/Supplement Allergies)

**MUST MATCH:** `scripts/data/allergens.json` → `allergens[].id`

#### ✅ ALL 17 VALIDATED ALLERGEN IDS:

```dart
enum Allergen {
  soy('ALLERGEN_SOY', 'Soy & Soy Lecithin', 'high'),
  milk('ALLERGEN_MILK', 'Milk/Dairy', 'high'),
  eggs('ALLERGEN_EGGS', 'Eggs', 'moderate'),
  fish('ALLERGEN_FISH', 'Fish', 'moderate'),
  shellfish('ALLERGEN_SHELLFISH', 'Shellfish/Crustacean', 'high'),
  treeNuts('ALLERGEN_TREE_NUTS', 'Tree Nuts', 'high'),
  peanuts('ALLERGEN_PEANUTS', 'Peanuts', 'high'),
  wheat('ALLERGEN_WHEAT_GLUTEN', 'Wheat/Gluten', 'high'),
  sesame('ALLERGEN_SESAME', 'Sesame', 'low'),
  sulfites('ALLERGEN_SULFITES', 'Sulfites', 'low'),
  lupin('ALLERGEN_LUPIN', 'Lupin', 'low'),
  celery('ALLERGEN_CELERY', 'Celery', 'low'),
  mustard('ALLERGEN_MUSTARD', 'Mustard', 'low'),
  mollusks('ALLERGEN_MOLLUSKS', 'Mollusks', 'low'),
  coconut('ALLERGEN_COCONUT', 'Coconut', 'low'),
  gelatin('ALLERGEN_GELATIN', 'Gelatin', 'moderate'),
  corn('ALLERGEN_CORN', 'Corn', 'low');

  final String id;
  final String label;
  final String prevalence;
  const Allergen(this.id, this.label, this.prevalence);
}
```

**UI Implementation:**

- Display: Modal with multi-select chips
- Title: "Food & Supplement Allergies"
- Instruction: "Select any food or supplement allergies"
- Sort order: High prevalence first (soy, milk, shellfish, tree nuts, peanuts, wheat/gluten)
- "None" option: Implicit (empty array `[]`)
- Storage: Array of allergen IDs (e.g., `["ALLERGEN_SOY", "ALLERGEN_MILK"]`)

**⚠️ IMPORTANT: MEDICATION ALLERGIES NOT INCLUDED**

- DO NOT include: Penicillin, Sulfa drugs, NSAIDs, Anticonvulsants, Chemotherapy drugs
- Reason: These are medication allergies, not food/supplement allergies
- Our allergen database is strictly limited to FDA FALCPA/FASTER Act major allergens and EU Annex II allergens
- Medication allergies belong in medical history (not relevant for supplement safety)

**Used For:**

- Section B2: Allergen warning flags (no score penalty, flag only)
- Product filtering ("Hide products with my allergens")

**Status:** ✅ ALL 17 ALLERGENS VALIDATED — DO NOT add medication allergies

---

## 🔴 CRITICAL ISSUES FOUND

### Issue 1: Medication Allergies in Current Draft ❌

**Problem:** Current draft includes medication allergies (Penicillin, Sulfa, NSAIDs, etc.)
**Fix:** Remove all medication allergies. Use only the 17 food/supplement allergens from `allergens.json`
**Reason:** Our allergen database is strictly limited to regulatory food allergens per FDA/EU standards

### Issue 2: Missing Medications Field ⚠️

**Problem:** Health Concerns modal doesn't include drug classes
**Fix:** Add separate "Medications You Take" section with 9 drug classes
**Reason:** Required for E2c drug-supplement interaction warnings

### Issue 3: Max Goal Selection Not Enforced ⚠️

**Problem:** Current draft allows unlimited goal selections
**Fix:** Enforce max 2 selections in UI with validation
**Reason:** Scoring algorithm designed for 2 goals max (E2a normalization)

---

## ✅ VALIDATION SUMMARY

| Field           | Status        | Schema Match            | Max Selections  |
| --------------- | ------------- | ----------------------- | --------------- |
| Nickname        | ✅ Valid      | N/A                     | N/A             |
| Age Bracket     | ✅ Valid      | Exact match (5 options) | 1 (required)    |
| Sex             | ✅ Valid      | Exact match + fallback  | 1 (required)    |
| Health Goals    | ✅ Valid      | Exact match (18 IDs)    | 2 (enforce)     |
| Health Concerns | ✅ Valid      | Exact match (14 IDs)    | 5-7 (recommend) |
| Medications     | ⚠️ MISSING    | Exact match (9 IDs)     | No limit        |
| Allergies       | ❌ WRONG LIST | Exact match (17 IDs)    | No limit        |

---

## 📋 IMPLEMENTATION CHECKLIST

- [ ] **Age Bracket:** Use exact 5 values from `rda_optimal_uls.json` metadata
- [ ] **Sex:** Implement "Other"/"Prefer not to say" → highest UL fallback
- [ ] **Goals:** Load all 18 from `user_goals_to_clusters.json`, enforce max 2, validate conflicts
- [ ] **Conditions:** Load all 14 from `clinical_risk_taxonomy.json`, sort by display_priority
- [ ] **Medications:** ADD NEW SECTION with 9 drug classes, separate from conditions
- [ ] **Allergies:** REPLACE current list with 17 food/supplement allergens from `allergens.json`
- [ ] **Remove:** All medication allergies (Penicillin, Sulfa, NSAIDs, etc.)
- [ ] **Quick-Select:** Implement condition → medication suggestions
- [ ] **Conflict Detection:** Warn when conflicting goals selected
- [ ] **"None" Handling:** Use empty array `[]`, not string "none"
- [ ] **Privacy Notice:** Keep as-is (good)
- [ ] **Action Button:** Change to "Save & Continue" (clearer than "Save Progress")

---

## 🎯 ANSWERS TO CLARIFICATION QUESTIONS

### Q1: Should we support "Other (free text)" for conditions/medications?

**A:** ❌ **NO** — Only use the 14 conditions and 9 drug classes from the taxonomy.
**Reason:** Free text cannot be mapped to interaction rules. If user has a condition not listed, they should consult a doctor (we don't have interaction data for unlisted conditions).
**Recommendation:** Add "Other medical condition" as final option that shows message: "Please consult your healthcare provider before taking any supplements."

### Q2: What happens if user selects "Prefer not to say" for sex?

**A:** ✅ **Use highest UL for all nutrients for safety**
**Implementation:** In E1 scoring, look up `highest_ul` field from each nutrient entry (already exists in schema).
**Example:** Vitamin A has different ULs for males (3000 mcg) and females (3000 mcg) → use 3000 mcg.

### Q3: Should medication selection be separate from health conditions, or combined?

**A:** ✅ **SEPARATE for clarity**
**UI Options:**

1. Two separate modals: "Health Concerns" and "Medications You Take"
2. One modal with two sections (clear divider between conditions and medications)

**Recommendation:** Option 2 (one modal, two sections) for fewer taps, but clearly labeled.

### Q4: Do we need "Upcoming Surgery" condition in the UI?

**A:** ✅ **YES** — It's in `clinical_risk_taxonomy.json` as `surgery_scheduled` with priority 4
**Reason:** Many supplements (blood thinners, immune modulators) should be stopped 1-2 weeks before surgery.
**Label:** "Upcoming Surgery" (display priority: 4, appears early in the list)

---

## 📊 PROFILE COMPLETENESS SCORING

```dart
int calculateProfileCompleteness(UserProfile profile) {
  int score = 0;

  // Required fields (40% total)
  if (profile.ageBracket != null) score += 20;  // Required for E1, E2b
  if (profile.sex != null) score += 20;         // Required for E1

  // Optional fields (60% total)
  if (profile.goals.isNotEmpty) score += 20;         // E2a (goal matching)
  if (profile.conditions.isNotEmpty || profile.drugClasses.isNotEmpty) score += 20;  // E2c (safety)
  if (profile.allergens.isNotEmpty) score += 10;     // Allergen filtering
  if (profile.nickname != null && profile.nickname!.isNotEmpty) score += 10;  // Personalization

  return score;  // 0-100
}
```

**Thresholds:**

- 0-39%: Incomplete (missing required fields)
- 40-59%: Basic (required only)
- 60-79%: Good (some optional fields)
- 80-100%: Complete (all fields filled)

**Display:**
"Profile 75% complete — Add your health goals for better recommendations"

---

**Next:** Update Flutter roadmap with validated profile setup screens.
