# Reference-Data Lookup Pattern — Opportunities Catalog

**Last updated:** 2026-04-30
**Pattern:** ship controlled vocabulary as Flutter bundled asset; per-row blob carries stable ID; descriptions live ONCE in the vocab and are joined at render time.
**Why we want this everywhere applicable:** offline-first lookup (no network at render time), clean architecture, smaller blobs, single source of truth per taxonomy, future i18n-ready, clinician-locked + version-pinnable.

This doc lists **24 concrete opportunities** found across the pipeline + Flutter, ranked by ROI. Already shipped: `functional_roles_vocab.json`.

---

## How to read this catalog

Each opportunity has:
- **Where the data lives** (pipeline file or Flutter source)
- **Where it's used** (blob field / Flutter UI component)
- **Distinct values** (size of the vocabulary)
- **ROI signal** (cardinality × repetition × current pain-level)
- **Sample shape** (what the vocab entry would look like)

**ROI bands:**
- 🔥 **P0 — biggest impact** (touches user-facing copy + currently scattered across blob/Flutter code)
- ⭐ **P1 — strong yes** (clear repetition + clean migration path)
- ✓ **P2 — good hygiene** (smaller scale; defensible per pattern consistency)

---

## P0 — Highest ROI (do these first, ~5 vocabs)

### 1. 🔥 `verdict_vocab.json`
- **Size:** 6 IDs (`BLOCKED`, `UNSAFE`, `CAUTION`, `POOR`, `SAFE`, `NOT_SCORED`)
- **Today:**
  - Pipeline emits `verdict` field on every product blob
  - Flutter renders via `verdict_badge.dart` lines 61-88 — **hardcoded label map in Dart**
  - User-facing explanation copy currently inlined OR missing per verdict
- **Vocab payload per entry:** display label, color/icon hint, when-to-show guidance, suggested user action, regulatory rationale
- **Why P0:** every product carries a verdict; user-facing copy currently scattered between Dart strings + blob `top_warnings` text. Centralizing locks the taxonomy + saves bytes.

### 2. 🔥 `severity_vocab.json`
- **Size:** 6 IDs (`contraindicated`, `avoid`, `caution`, `monitor`, `safe`, `info`)
- **Today:**
  - Pipeline files using it: `ingredient_interaction_rules` (437 occurrences across condition/drug/pregnancy/lactation), `allergens` (15), `harmful_additives` (59), `functional_ingredient_groupings` (7), `banned_recalled_ingredients`
  - Flutter `lib/core/constants/severity.dart` — **enum-embedded labels**
  - UX color/icon mapping currently scattered in widgets
- **Vocab payload per entry:** display label, action verb (e.g. "Do not use" / "Use caution"), color hint, icon hint, plain-English description
- **Why P0:** This is the most-repeated descriptive token in the entire blob ecosystem. Every interaction warning, every allergen flag, every banned-recalled hit references one of 6 severity values. Centralizing pays for itself many times over.

### 3. 🔥 `condition_vocab.json`
- **Size:** ~14-20 IDs (`pregnancy`, `lactation`, `kidney_disease`, `liver_disease`, `hypertension`, `diabetes`, etc.)
- **Today:**
  - Pipeline: `interaction_rules.condition_rules[].condition_id`, `clinical_risk_taxonomy.conditions`
  - Flutter: `lib/core/constants/schema_ids.dart` lines 26-41 — **hardcoded `conditionLabels` map (14 entries)**
- **Vocab payload per entry:** display label, plain-English description, common synonyms, ICD-10 reference (optional)
- **Why P0:** condition_id appears in every condition-triggered warning. Currently the source-of-truth labels live in Flutter Dart code rather than a clinician-reviewed asset. Migrating gives clinician control of the user-facing condition copy.

### 4. 🔥 `drug_class_vocab.json`
- **Size:** ~13-15 IDs (`anticoagulants`, `nsaids`, `ssri_snri`, `antihypertensives`, `mao_inhibitors` (after our additions), `lithium`, etc.)
- **Today:**
  - Pipeline: `interaction_rules.drug_class_rules[].drug_class_id`, `clinical_risk_taxonomy.drug_classes`
  - Flutter: `lib/core/constants/schema_ids.dart` lines 59-73 — **hardcoded `drugClassLabels` map (13 entries)**
- **Vocab payload per entry:** display label, plain-English description, common brand/generic examples (e.g. "Anticoagulants" → "warfarin, rivaroxaban, apixaban"), prescription/OTC indicator
- **Why P0:** Same logic as condition_vocab — drug_class_id appears in every drug-interaction warning. Brand examples are clinically useful UX content that clinician should own.

### 5. 🔥 `user_goals_vocab.json`
- **Size:** ~18 IDs (Sleep Quality, Reduce Stress, etc.)
- **Today:**
  - Pipeline: `user_goals_to_clusters.json` (raw mapping)
  - Flutter: `lib/core/constants/schema_ids.dart` lines 96-115 — **hardcoded `goalLabels` + priorities map**
- **Vocab payload per entry:** display label, description, priority weight, related condition_ids, related drug_class_ids
- **Why P0:** Goals drive the personalization layer. Centralizing makes the goal taxonomy locked and clinician-controlled.

---

## P1 — Strong yes (do these second, ~10 vocabs)

### 6. ⭐ `evidence_level_vocab.json`
- **Size:** 3-5 IDs (`product-human`, `branded-rct`, `ingredient-human`, `strain-clinical`, `preclinical`)
- **Today:** repeated in `backed_clinical_studies` (197 entries), `interaction_rules` (210+ occurrences), some IQM forms
- **Flutter:** `lib/core/constants/severity.dart` `EvidenceLevel` enum — hardcoded labels
- **Vocab payload:** label, weight (already in scoring config), plain-English description, hierarchy hint

### 7. ⭐ `study_type_vocab.json`
- **Size:** 7 IDs (`rct_multiple`, `rct_single`, `systematic_review_meta`, `clinical_strain`, `observational`, `animal_study`, `in_vitro`)
- **Today:** `backed_clinical_studies` (197 entries), all carry one
- **Flutter:** no dedicated UI yet (would render in evidence detail screen)
- **Vocab payload:** label, hierarchy weight, plain-English description, what-it-means-for-quality

### 8. ⭐ `clinical_indication_vocab.json`
- **Size:** 22 IDs (the buckets we just created: anti_inflammatory, joint_bone, cognitive_neurological, etc.)
- **Today:** `backed_clinical_studies.category` (197 entries, just canonicalized 148→22)
- **Flutter:** no display copy yet
- **Vocab payload:** label, plain-English description, related condition_ids, sample evidence-bearing ingredients

### 9. ⭐ `iqm_category_vocab.json`
- **Size:** 12 IDs (`amino_acids`, `antioxidants`, `enzymes`, `fatty_acids`, `fibers`, `functional_foods`, `herbs`, `minerals`, `other`, `probiotics`, `proteins`, `vitamins`)
- **Today:** IQM 616 parents each carry one; integrity gate enforces enum
- **Flutter:** no display copy yet
- **Vocab payload:** label, plain-English description, sample ingredient examples per bucket

### 10. ⭐ `banned_status_vocab.json`
- **Size:** 4 IDs (`banned`, `recalled`, `high_risk`, `watchlist`)
- **Today:** `banned_recalled_ingredients.json` (146 entries) all carry one; drives the B0 verdict gate
- **Flutter:** ban_context labels currently fetched per-blob
- **Vocab payload:** label, color/icon hint, what-it-means, regulatory authority basis

### 11. ⭐ `clinical_risk_vocab.json`
- **Size:** 5 IDs (`critical`, `moderate`, `dose_dependent`, etc.)
- **Today:** `banned_recalled_ingredients.clinical_risk_enum` (145 entries)
- **Vocab payload:** label, dose-context guidance, severity weight

### 12. ⭐ `legal_status_vocab.json`
- **Size:** 10 IDs (`controlled_substance`, `adulterant`, `not_lawful_as_supplement`, `restricted`, `under_review`, `lawful`, `wada_prohibited`, etc.)
- **Today:** `banned_recalled.legal_status_enum` (146 entries)
- **Vocab payload:** label, regulatory authority (FDA/DEA/WADA), plain-English implication

### 13. ⭐ `ban_context_vocab.json`
- **Size:** 5 IDs (`adulterant_in_supplements`, `substance`, `export_restricted`, `contamination_recall`, `processing_aid_concern`)
- **Today:** `banned_recalled.ban_context` (146 entries)
- **Vocab payload:** label, when-it-applies, action recommendation

### 14. ⭐ `effect_direction_vocab.json`
- **Size:** 4 IDs (`positive_strong`, `positive_weak`, `mixed`, `negative`, `null`)
- **Today:** `backed_clinical_studies.effect_direction` (197 entries); also `effect_direction_multipliers` in scoring config
- **Vocab payload:** label, multiplier weight (already in config), plain-English description

### 15. ⭐ `signal_strength_vocab.json` (CAERS)
- **Size:** 3 IDs (`weak`, `moderate`, `strong`)
- **Today:** `caers_adverse_event_signals.json` (159 entries — currently disabled at scoring layer per V1.1 ROADMAP §5.1)
- **Vocab payload:** label, threshold definition, penalty weight (when re-enabled with PRR/ROR)

---

## P2 — Good hygiene (do these as time allows, ~9 vocabs)

### 16. ✓ `allergen_prevalence_vocab.json`
- **Size:** 3 IDs (`high`, `moderate`, `low`)
- **Today:** `allergens.json` (11 entries); also as `severity_level` (15 entries) in same file

### 17. ✓ `allergen_regulatory_status_vocab.json`
- **Size:** 3 IDs (`eu_allergen`, `fda_major`, `eu_major`)
- **Today:** `allergens.json` (17 entries)

### 18. ✓ `manufacturer_trust_tier_vocab.json`
- **Size:** ~3-4 IDs (trusted/untrusted/under_review/etc.)
- **Today:** scattered across `top_manufacturers.json` + `manufacturer_violations.json`
- **Flutter:** hardcoded "Trusted manufacturer" string in `score_breakdown_card.dart`

### 19. ✓ `efsa_status_vocab.json`
- **Size:** 10 IDs (`under_review`, `contaminant_monitored`, `approved_with_restrictions`, etc.)
- **Today:** `efsa_openfoodtox_reference.json` (91 entries)

### 20. ✓ `efsa_genotoxicity_vocab.json`
- **Size:** 7 IDs (`under_review`, `negative`, `insufficient_data`, etc.)
- **Today:** `efsa_openfoodtox_reference.json` (91 entries)

### 21. ✓ `match_mode_vocab.json`
- **Size:** 3 IDs (`active`, `disabled`, `historical`)
- **Today:** `banned_recalled.match_mode` (146 entries)

### 22. ✓ `confidence_tier_vocab.json`
- **Size:** 3 IDs (`high`, `medium`, `low`)
- **Today:** `harmful_additives.confidence` (106 entries) + `clinical_studies.effect_direction_confidence` (191 entries)

### 23. ✓ `score_contribution_tier_vocab.json`
- **Size:** 3 IDs (`tier_1`, `tier_2`, `tier_3`)
- **Today:** `backed_clinical_studies.score_contribution` (197 entries)

### 24. ✓ `primary_outcome_vocab.json`
- **Size:** ~15 IDs (Blood Sugar Support, Cardiovascular/Heart Health, Sleep Quality, etc.)
- **Today:** `backed_clinical_studies.primary_outcome` (197 entries)

---

## Estimated impact

| Tier | Vocabs | Total vocab size (asset) | Per-blob savings | Implementation effort |
|---|---|---|---|---|
| P0 (5) | verdict, severity, condition, drug_class, user_goals | ~25 KB total | ~50-100 bytes/warning × ~5-10 warnings/product = **0.5-1 KB/blob** | 5-7 days |
| P1 (10) | evidence_level, study_type, clinical_indication, iqm_category, banned_status, clinical_risk, legal_status, ban_context, effect_direction, signal_strength | ~40 KB total | ~30-60 bytes per affected blob | 7-10 days |
| P2 (9) | allergen_prevalence, allergen_regulatory, manufacturer_trust, efsa_status, efsa_genotoxicity, match_mode, confidence_tier, score_contribution_tier, primary_outcome | ~30 KB total | ~10-30 bytes/blob | 5-7 days |

**Net Flutter asset bundle:** all 24 vocabs ≈ **95 KB** (one-time per app install). **Net per-blob savings:** ~1-2 KB/product × millions of blobs = **multi-GB catalog savings**.

---

## Implementation pattern (re-usable recipe)

Already proven with `functional_roles_vocab.json`. For each new vocab:

1. **Inventory** distinct values + cardinality (script: scan all data files for the field)
2. **Design** the vocab (5-field lean: `id`, `name`, `notes` ≤200 char, `references[]`, `examples[]` — extend per vocab needs)
3. **Clinician sign-off** on labels + descriptions (CLINICIAN_REVIEW.md per vocab)
4. **Author** `<field>_vocab.json` with `_metadata.status: "LOCKED"`
5. **Add 2 contract tests:**
   - Vocab schema test (shape, IDs, char limits, no dups)
   - Cross-file membership test (every blob field value is in vocab.IDs)
6. **Wire integrity gate** (`db_integrity_sanity_check.py`) — reject unknown IDs
7. **Bundle to Flutter** — copy to `assets/data/<field>_vocab.json`, register in `pubspec.yaml`, add to `ReferenceDataRepository`
8. **Migrate Flutter consumers** — replace hardcoded label maps in Dart with `vocab[id].name` lookups
9. **Document** in `V1_1_ROADMAP.md` (this catalog) — mark vocab DONE

The whole pattern is now scripted; future vocabs cost ~1 day each (vocab authoring) + 1 day Flutter wiring.

---

## Reusable Flutter helpers (per Flutter audit)

The Flutter app already has the right scaffolding from the functional_roles work:

- **`FunctionalRole` + `loadFunctionalRolesVocab()`** template (`lib/features/product_detail/data/functional_roles_vocab.dart`) — typed entry class, async loader, process-lifetime cache, test seam (`debugSetFunctionalRolesVocabForTesting`)
- **`ReferenceDataRepository`** (`lib/data/repositories/reference_data_repository.dart`) — centralized asset loader with per-asset caching and `_loadJson()` helper

Future vocab loaders should follow the `FunctionalRole` template exactly. Wire everything through `ReferenceDataRepository` for centralized caching.

---

## i18n readiness

Currently English-only. Pipeline-side, `intl: ^0.19.0` is in pubspec but used only for date formatting; no ARB files yet. Future i18n-ready vocab schema:

```json
{
  "id": "caution",
  "label": { "en": "Use caution", "es": "Usar precaución", "fr": "Utiliser avec prudence" },
  "notes": { "en": "...", "es": "..." }
}
```

For V1, English-only `label`/`notes` fields are fine; the migration path to localized objects is straightforward (Flutter loader checks for `Map` vs `String` types).

---

## What's NOT a vocab candidate (skip these)

- **Free-form authored copy** — `alertHeadline`, `alertBody`, `mechanism`, `management`, `notes` (per-entry on warning rules). These are unique narrative copy per ingredient. Keep in the data file / blob.
- **Per-product custom values** — `product_name`, `manufacturer_name`, `dsld_id`, score values. No commonality.
- **PMIDs / DOIs / regulatory citations** — too many unique values. Keep as inline arrays.
- **Per-ingredient quality data** (IQM `bio_score`, `score`, `natural`) — these aren't repeating descriptive values; they're the data itself.

---

## Cross-references

- Single-source-of-truth doc: `~/.claude/plans/V1_1_ROADMAP.md` (consolidated V1.1 work)
- First successful vocab: `scripts/data/functional_roles_vocab.json` (LOCKED, 32 entries)
- Flutter handoff: `scripts/audits/functional_roles/FLUTTER_HANDOFF.md`
- Pattern recipe: `CLINICIAN_REVIEW.md` per future vocab
- Coverage gate: `scripts/coverage_gate_functional_roles.py` (template for future vocab gates)
