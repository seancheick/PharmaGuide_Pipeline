# Reference-Data Lookup Pattern — Opportunities Catalog

**Last updated:** 2026-05-02 (all 25 vocabs delivered end-to-end; pipeline + Flutter both green)
**Pattern:** ship controlled vocabulary as Flutter bundled asset; per-row blob carries stable ID; descriptions live ONCE in the vocab and are joined at render time.
**Why we want this everywhere applicable:** offline-first lookup (no network at render time), clean architecture, smaller blobs, single source of truth per taxonomy, future i18n-ready, clinician-locked + version-pinnable.

This doc lists **25 concrete opportunities** found across the pipeline + Flutter, ranked by ROI. **Status as of 2026-05-02: all 25 LOCKED end-to-end with drift contracts.**

**Build cadence (locked 2026-04-30):** P0 + P1 + P2 ship in the **same release**. Tier ordering below is informational priority signal for review/clinician sequencing inside the build, not a multi-release schedule. The doc still tiers by ROI so reviewers know which vocabs to scrutinize first; nothing gets deferred to a later sprint.

---

## Status snapshot (2026-05-02) — DELIVERY COMPLETE

**All 25 vocabs LOCKED + bundled to Flutter + drift-tested. Total bundle size 119,690 bytes.**

| Vocab | Entries | Tier | Notes |
|---|---|---|---|
| `functional_roles_vocab.json` | 32 | (existing) | First successful vocab; clinician sign-off complete |
| `verdict_vocab.json` | 6 | P0 | LOCKED — SAFE/CAUTION/POOR/BLOCKED/UNSAFE/NUTRITION_ONLY; NOT_SCORED stays review-queue-only |
| `severity_vocab.json` | 6 | P0 | LOCKED — `info` → `informational` rename complete (0 remaining `info` in source data; 39 `informational`) |
| `condition_vocab.json` | 14 | P0 | LOCKED — matches 14 distinct condition_ids in interaction_rules ✓ |
| `drug_class_vocab.json` | 21 | P0 | LOCKED — 13 user_selectable + 8 rule-only (see D3) |
| `user_goals_vocab.json` | 18 | P0 | LOCKED — matches 18 entries in user_goals_to_clusters; cross-references condition + drug_class vocabs |
| `evidence_level_vocab.json` | 5 | P1 | LOCKED for clinical_studies; multipliers verified against scoring_config.json |
| `evidence_strength_vocab.json` | 6 | P1 | LOCKED for interaction_rules strength tiers (D2 split) |
| `study_type_vocab.json` | 7 | P1 | LOCKED — matches 7 study_type values in backed_clinical_studies |
| `clinical_indication_vocab.json` | 22 | P1 | LOCKED — 22 categories used by backed_clinical_studies; cross-references condition_vocab |
| `iqm_category_vocab.json` | 12 | P1 | LOCKED — 12 parent buckets for ingredient_quality_map's 621+ parents |
| `banned_status_vocab.json` | 4 | P1 | LOCKED — display contract for B0-gate (banned/recalled/high_risk/watchlist) |
| `clinical_risk_vocab.json` | 5 | P1 | LOCKED — display contract for clinical_risk_enum (critical/high/moderate/dose_dependent/low) |
| `legal_status_vocab.json` | 10 | P1 | LOCKED — regulatory classifications with FDA/DEA/WADA/state/EU authority |
| `ban_context_vocab.json` | 5 | P1 | LOCKED — substance/adulterant_in_supplements/contamination_recall/watchlist/export_restricted |
| `effect_direction_vocab.json` | 5 | P1 | LOCKED — multipliers verified against scoring_config.json |
| `signal_strength_vocab.json` | 3 | P1 | LOCKED — display contract; CAERS scoring layer disabled per V1.1 ROADMAP §5.1 |
| `allergen_prevalence_vocab.json` | 3 | P2 | LOCKED — display contract for allergen prevalence chip |
| `allergen_regulatory_status_vocab.json` | 3 | P2 | LOCKED — fda_major/eu_major/eu_allergen |
| `manufacturer_trust_tier_vocab.json` | 4 | P2 | LOCKED — derived from top_manufacturers_data + manufacturer_violations join |
| `efsa_status_vocab.json` | 10 | P2 | LOCKED — see v1.1 followup for 3 near-duplicate consolidation |
| `efsa_genotoxicity_vocab.json` | 7 | P2 | LOCKED — EFSA genotoxicity classifications |
| `match_mode_vocab.json` | 3 | P2 | LOCKED — active/disabled/historical with fires_in_scoring flag |
| `confidence_tier_vocab.json` | 3 | P2 | LOCKED — display contract; high/medium/low |
| `score_contribution_tier_vocab.json` | 3 | P2 | LOCKED — display contract; tier_1/tier_2/tier_3 |
| `primary_outcome_vocab.json` | 15 | P2 | LOCKED — snake_case canonical IDs + legacy_display round-trip until v1.1 source-data migration |

**Verification (2026-05-02):**
- Pipeline contract tests: **225 passed, 0 failed**
- Pipeline regression suite (severity rename + touched code paths): **691 passed, 0 failed, 7 env-gated skips**
- Flutter `test/core/` (25 drift tests + widget tests): **305 passed, 0 failed**
- Flutter `flutter analyze` (lib/core/data/ + test/core/): **0 issues**
- `db_integrity_sanity_check.py`: **0 errors, 0 warnings**
- **Total: 1221 tests passing across both repos, 0 failures**

**Discovery items (all resolved):**

**Discovery items (decisions needed before next vocabs land):**

- **D1 — resolved 2026-05-01: verdict vocab includes `NUTRITION_ONLY`.** Code reality (`build_final_db.py:343-347`) ships SAFE, CAUTION, POOR, BLOCKED, UNSAFE, **NUTRITION_ONLY** (6 verdicts). `scripts/data/verdict_vocab.json` is now locked at those 6 IDs. `NOT_SCORED` remains intentionally absent because the export contract routes those products to the review queue before Flutter.
- **D2 — resolved 2026-05-01: `evidence_level` field carries two different vocabs.** `backed_clinical_studies.evidence_level` is a study-design tier (5 IDs: branded-rct, product-human, ingredient-human, strain-clinical, preclinical). `ingredient_interaction_rules.evidence_level` is a strength tier (6 IDs: established, probable, theoretical, limited, moderate, no_data). Same field name, different semantics, now split into `evidence_level_vocab.json` (clinical_studies) + `evidence_strength_vocab.json` (interaction_rules). Follow-on cleanup remains: rename interaction_rules field → `evidence_strength` for self-documenting schema.
- **D3 — drug_class_vocab is 21 IDs, not the doc's earlier "~13" estimate.** 13 user-facing classes + 8 internal CYP-substrate / narrow-family classes (CYP2D6/CYP3A4 substrates, anticholinergics, anticonvulsants, cardiac glycosides, immunosuppressants, oral contraceptives, sedatives, statins, thiazide diuretics — used by interaction rules but not in user-selectable lists). The shipped vocab uses the `user_selectable: true/false` flag pattern to preserve interaction coverage while filtering UX.

---

## How to read this catalog

Each opportunity has:
- **Where the data lives** (pipeline file or Flutter source)
- **Where it's used** (blob field / Flutter UI component)
- **Distinct values** (size of the vocabulary — verified live, not estimated)
- **ROI signal** (cardinality × repetition × current pain-level)
- **Sample shape** (what the vocab entry would look like)

**ROI bands:**
- 🔥 **P0 — biggest impact** (touches user-facing copy + currently scattered across blob/Flutter code)
- ⭐ **P1 — strong yes** (clear repetition + clean migration path)
- ✓ **P2 — good hygiene** (smaller scale; defensible per pattern consistency)

---

## Display Contract Ownership (cross-cutting rule, locked 2026-04-30)

**Rule:** vocab owns presentation, Flutter renders. When a vocab feeds a UI surface, the vocab entry MUST carry the full display contract — not just a label. Flutter is a renderer, not a decision-maker for tone/color/icon/action.

**Required fields on UI-bound vocabs (severity, verdict, banned_status, clinical_risk, allergen_prevalence, signal_strength, confidence_tier, score_contribution_tier):**

```json
{
  "id": "caution",
  "name": "Use caution",
  "short_label": "Caution",
  "tone": "warning",
  "ui_color": "orange",
  "ui_icon": "warning",
  "action": "Monitor usage",
  "notes": "..."
}
```

| Field | Purpose | Allowed values (initial) |
|---|---|---|
| `name` | Full display label | clinician-authored string |
| `short_label` | Compact chip / pill label | ≤12 chars |
| `tone` | Semantic intent for theming | `positive` \| `neutral` \| `info` \| `warning` \| `danger` |
| `ui_color` | Color hint (Flutter resolves to theme color) | `green` \| `blue` \| `gray` \| `yellow` \| `orange` \| `red` |
| `ui_icon` | Icon hint (Flutter resolves to icon asset) | `check` \| `info` \| `warning` \| `alert` \| `block` |
| `action` | Suggested user action verb-phrase | clinician-authored string ≤40 chars |

**Why this earns its keep:**
- Flutter cannot drift on tone/color across surfaces — `severity_pill`, `banner`, `alert_summary_card`, `score_breakdown_card` all read the same contract
- Voice/tone tunable without a Flutter release (vocab JSON ships as bundled asset; future hot-deploy via API is straightforward)
- Clinician owns "Avoid" vs "Not recommended" wording AND the orange-vs-red signal — single review surface
- Catches the bug class that produced the allergen `evidence` leak (raw IDs surfacing because Flutter inferred presentation from a raw string)

**Vocabs that DON'T need display contract:** internal taxonomy IDs not directly user-facing — `iqm_category_vocab`, `study_type_vocab`, `match_mode_vocab`, `efsa_status_vocab`, `efsa_genotoxicity_vocab`, `effect_direction_vocab`. These keep the lean 5-field shape (`id`, `name`, `notes`, `references[]`, `examples[]`).

**What stays per-row, NOT in vocab:** alert text, mechanism explanations, ingredient-specific warnings, management copy. Hard rule: vocab is for repeated descriptive tokens; per-row narrative copy stays on the row.

---

## P0 — Highest ROI (do these first, ~5 vocabs)

### 1. 🔥 `verdict_vocab.json` — **LOCKED at 6 shipped IDs**

- **Verified size:** **6 IDs shipped** (SAFE, CAUTION, POOR, BLOCKED, UNSAFE, NUTRITION_ONLY). `build_final_db.py:343-347` includes NUTRITION_ONLY for food-shape products (gummies, drinks where bioactive scoring doesn't apply).
- **NOT_SCORED stays out of vocab.** Pipeline contract: `build_final_db.py:4300` raises `ValueError` on NOT_SCORED → product never ships to Flutter. (If shipped SQLite contains NOT_SCORED entries, that's a stale build, not a vocab issue.)
- **Today:**
  - Pipeline emits `verdict` on every shipped product blob
  - Flutter renders via `verdict_badge.dart` lines 61-88 — **hardcoded label map in Dart** (migrated to surface SAFE/CAUTION/POOR per Flutter sprint commit `bb621eb`; BLOCKED/UNSAFE shown via dedicated alert page)
- **Vocab payload per entry:** display label, color/icon hint, when-to-show guidance, suggested user action, regulatory rationale
- **Seed display contract (clinician-reviewed):**
  | ID | name | short_label | tone | ui_color | ui_icon | action |
  |---|---|---|---|---|---|---|
  | `SAFE` | Safe | Safe | positive | green | check | Use as directed |
  | `CAUTION` | Caution | Caution | warning | yellow | warning | Review before use |
  | `POOR` | Poor quality | Poor | warning | orange | warning | Consider alternatives |
  | `BLOCKED` | Do not use | Blocked | danger | red | block | Do not use |
  | `UNSAFE` | Unsafe | Unsafe | danger | red | alert | Do not use |
  | `NUTRITION_ONLY` | Food product — see ingredients | Food | info | gray | info | Read ingredients label |

### 2. 🔥 `severity_vocab.json` — **LOCKED at 6 IDs, rename complete**

- **Verified size:** **6 IDs LOCKED** (`contraindicated`, `avoid`, `caution`, `monitor`, `informational`, `safe`)
- **Verified rename status:** `info` → `informational` rename **complete** in source data. Live counts (2026-05-01):
  - `info` literal occurrences: **0** in `ingredient_interaction_rules.json`, `ingredient_interaction_rules_Reviewed.json`, `clinical_risk_taxonomy.json` ✓
  - `informational` literal occurrences: **39** total (matches the 39 originally renamed)
- **Note:** `clinical_risk_taxonomy.severity_levels[]` carries 6 entries: contraindicated, avoid, caution, monitor, informational, **`no_data`**. The shipped severity_vocab uses `safe` instead of `no_data`. These are distinct concepts — the vocab is for UI-surfaced severity tiers (where `safe` is the absence-of-warning state), the taxonomy includes `no_data` as a gap-fill state. Vocab and taxonomy can both be correct; document the difference.
- **Today:**
  - Pipeline files using new `informational` ID across `ingredient_interaction_rules.json` (~12 occurrences), `ingredient_interaction_rules_Reviewed.json` (~8), `clinical_risk_taxonomy.json` (1 in severity_levels) — total 39 occurrences match
  - Flutter `lib/core/constants/severity.dart` — enum-embedded labels (already canonical at `informational`)
  - UX color/icon mapping was scattered in widgets; migration to vocab-driven contract in progress
- **Vocab payload:** display label, action verb, color hint, icon hint, plain-English description (already shipped per locked vocab)

### 3. 🔥 `condition_vocab.json` — **LOCKED at 14 IDs**

- **Verified size:** **14 IDs** in vocab — matches **14 distinct `condition_id` values** found across `ingredient_interaction_rules.json`. Live IDs: `autoimmune, bleeding_disorders, diabetes, heart_disease, high_cholesterol, hypertension, kidney_disease, lactation, liver_disease, pregnancy, seizure_disorder, surgery_scheduled, thyroid_disorder, ttc`
- **Today:**
  - Pipeline: `interaction_rules.condition_rules[].condition_id`, `clinical_risk_taxonomy.conditions` (14 entries)
  - Flutter: `lib/core/constants/schema_ids.dart` — labels migrated from this Dart map to vocab 2026-04-30
- **Vocab payload:** display label, plain-English description, common synonyms, ICD-10 reference (optional)
- **Coverage status:** ✅ 14/14 condition_ids in vocab, no orphans

### 4. 🔥 `drug_class_vocab.json` — **LOCKED at 21 IDs (D3 documented)**

- **Verified size:** **21 IDs** — matches **21 distinct `drug_class_id` values** in `ingredient_interaction_rules.json`. Live IDs: `antiarrhythmics, anticholinergics, anticoagulants, anticonvulsants, antidepressants_ssri_snri, antihypertensives, antiplatelets, calcium_channel_blockers, cardiac_glycosides, cyp2d6_substrates, cyp3a4_substrates, hypoglycemics, immunosuppressants, lithium, maois, nsaids, oral_contraceptives, sedatives, statins, thiazide_diuretics, thyroid_medications`
- **Pattern:** vocab uses `user_selectable: true/false` flag. ~13 user-facing classes (the originals from `schema_ids.dart`) + ~8 internal classes (CYP substrates, narrow drug families) used only by interaction rules but not surfaced in user "what meds are you on?" picker.
- **Today:**
  - Pipeline: `interaction_rules.drug_class_rules[].drug_class_id`, `clinical_risk_taxonomy.drug_classes` (21 entries)
  - Flutter: labels migrated from `schema_ids.dart` 2026-04-30
- **Vocab payload:** display label, plain-English description, common brand/generic examples, prescription/OTC indicator, **`user_selectable` flag**

### 5. 🔥 `user_goals_vocab.json` — **LOCKED at 18 IDs**

- **Verified size:** **18 IDs** in vocab — matches **18 entries** in `user_goals_to_clusters.json:user_goal_mappings`
- **Today:**
  - Pipeline: `user_goals_to_clusters.json:user_goal_mappings` (raw mapping, 18 entries)
  - Flutter: `lib/core/constants/schema_ids.dart` — labels migrated to vocab 2026-04-30
- **Vocab payload:** display label, description, priority weight, related condition_ids, related drug_class_ids
- **ID format:** uses `GOAL_SLEEP_QUALITY` / `GOAL_REDUCE_STRESS_ANXIETY` etc. (UPPER_SNAKE prefix). Documented for cross-repo consistency.

---

## P1 — Strong yes (do these second, ~10 vocabs)

### 6a. ⭐ `evidence_level_vocab.json` — **LOCKED at 5 IDs (clinical_studies scope)**

- **Verified size:** **5 IDs** (`branded-rct`, `product-human`, `ingredient-human`, `strain-clinical`, `preclinical`) — scope is `backed_clinical_studies.evidence_level` only.
- **Verified distribution** (`backed_clinical_studies.json`, 197 entries): branded-rct=38, product-human=17, ingredient-human=132, strain-clinical=6, preclinical=4 → **197 covered** ✓
- **Flutter:** `lib/core/constants/severity.dart` `EvidenceLevel` enum
- **Vocab payload:** label, weight (already in scoring config), plain-English description, hierarchy hint

### 6b. ⭐ `evidence_strength_vocab.json` — **LOCKED at 6 IDs (D2 split)**

- **Verified size:** **6 IDs** (`established`, `probable`, `theoretical`, `limited`, `moderate`, `no_data`) — scope is `ingredient_interaction_rules.evidence_level` semantically distinct from #6a.
- **Verified distribution** (`ingredient_interaction_rules.json`): established=154, probable=240, theoretical=71, limited=13, moderate=6, no_data=84 → **568 occurrences** ✓
- **Why split from #6a:** field name collision; #6a is study-design ("WHERE the evidence comes from"), #6b is strength tier ("HOW STRONG"). Conflating into one vocab forces every consumer to disambiguate at runtime.
- **Migration plan:** keep field name `evidence_level` for now (no breaking rename); per-file validators in `db_integrity_sanity_check.py` enforce per-vocab. Schedule follow-on PR to rename `interaction_rules.evidence_level` → `evidence_strength` for self-documenting schema.
- **Note:** `clinical_risk_taxonomy.evidence_levels[]` already lists these 6 IDs (verified live).

### 7. ⭐ `study_type_vocab.json` — **LOCKED at 7 IDs**

- **Verified size:** **7 IDs** (`rct_multiple`, `rct_single`, `systematic_review_meta`, `clinical_strain`, `observational`, `animal_study`, `in_vitro`)
- **Verified distribution** (`backed_clinical_studies.json`, 197 entries): systematic_review_meta=79, rct_multiple=72, rct_single=30, observational=6, clinical_strain=5, animal_study=3, in_vitro=2 → **197 covered** ✓
- **Flutter:** no dedicated UI yet (would render in evidence detail screen)
- **Vocab payload:** label, hierarchy weight, plain-English description, what-it-means-for-quality

### 8. ⭐ `clinical_indication_vocab.json` — **NEEDED**

- **Verified size:** **22 IDs** (live distinct count of `category` values in `backed_clinical_studies.json`). Top 5: cognitive_neurological=18, joint_bone=15, metabolic_blood_sugar=14, immune=13, adaptogen_stress=12.
- **Today:** `backed_clinical_studies.category` (197 entries, canonicalized 148→22 in earlier audit)
- **Flutter:** no display copy yet
- **Vocab payload:** label, plain-English description, related condition_ids, sample evidence-bearing ingredients
- **Note:** P1's largest vocab; budget for an audit pass before authoring.

### 9. ⭐ `iqm_category_vocab.json` — **NEEDED**

- **Verified size:** **12 IDs** (`amino_acids`, `antioxidants`, `enzymes`, `fatty_acids`, `fibers`, `functional_foods`, `herbs`, `minerals`, `other`, `probiotics`, `proteins`, `vitamins`)
- **Verified distribution** across **621 IQM parents** (live count): herbs=199, antioxidants=110, fatty_acids=64, amino_acids=57, probiotics=47, minerals=29, functional_foods=27, other=23, vitamins=22, fibers=17, proteins=16, enzymes=10 → **621 covered** ✓
- **Today:** integrity gate enforces enum (validated in `db_integrity_sanity_check.py`)
- **Flutter:** no display copy yet
- **Vocab payload:** label, plain-English description, sample ingredient examples per bucket

### 10. ⭐ `banned_status_vocab.json` — **NEEDED**

- **Verified size:** **4 IDs** (`banned`, `recalled`, `high_risk`, `watchlist`)
- **Verified distribution** (`banned_recalled_ingredients.json`, 146 entries): banned=93, high_risk=29, recalled=13, watchlist=11 → **146 covered** ✓
- **Drives the B0 verdict gate**
- **Vocab payload:** label, color/icon hint, what-it-means, regulatory authority basis

### 11. ⭐ `clinical_risk_vocab.json` — **NEEDED**

- **Verified size:** **5 IDs** (`critical`, `high`, `moderate`, `dose_dependent`, `low`)
- **Verified distribution** (`banned_recalled_ingredients.json:clinical_risk_enum`, 146 entries): critical=98, high=33, moderate=13, dose_dependent=1, low=1 → **146 covered** ✓
- **Vocab payload:** label, dose-context guidance, severity weight

### 12. ⭐ `legal_status_vocab.json` — **NEEDED**

- **Verified size:** **10 IDs** (`adulterant`, `not_lawful_as_supplement`, `banned_federal`, `restricted`, `high_risk`, `banned_state`, `contaminant_risk`, `lawful`, `controlled_substance`, `wada_prohibited`)
- **Verified distribution** (`banned_recalled.legal_status_enum`, 146 entries): not_lawful_as_supplement=44, high_risk=28, adulterant=24, banned_federal=18, contaminant_risk=16, controlled_substance=7, restricted=5, wada_prohibited=2, banned_state=1, lawful=1 → **146 covered** ✓
- **Vocab payload:** label, regulatory authority (FDA/DEA/WADA), plain-English implication

### 13. ⭐ `ban_context_vocab.json` — **NEEDED**

- **Verified size:** **5 IDs** (`adulterant_in_supplements`, `substance`, `export_restricted`, `contamination_recall`, `watchlist`)
- **Verified distribution** (`banned_recalled.ban_context`, 146 entries): substance=95, adulterant_in_supplements=29, watchlist=12, contamination_recall=9, export_restricted=1 → **146 covered** ✓
- **Note:** doc earlier listed `processing_aid_concern` — that ID does NOT appear in source data; correct ID is `watchlist` per live count.
- **Vocab payload:** label, when-it-applies, action recommendation

### 14. ⭐ `effect_direction_vocab.json` — **NEEDED**

- **Verified size:** **4 IDs** (`positive_strong`, `positive_weak`, `mixed`, `null`) — live distribution shows no `negative` instances in `backed_clinical_studies.json`
- **Verified distribution** (197 entries): positive_strong=125, positive_weak=40, mixed=28, null=4 → **197 covered** ✓
- **Note:** `negative` is RESERVED in the scoring config (`effect_direction_multipliers`) but no entries currently use it. Vocab can include `negative` for future-proofing or scope to the 4 in-use IDs.
- **Vocab payload:** label, multiplier weight (already in config), plain-English description

### 15. ⭐ `signal_strength_vocab.json` (CAERS) — **NEEDED**

- **Verified size:** **3 IDs** (`weak`, `moderate`, `strong`)
- **Verified distribution** (`caers_adverse_event_signals.json`, 159 entries): moderate=66, weak=56, strong=37 → **159 covered** ✓
- **Note:** currently disabled at scoring layer per V1.1 ROADMAP §5.1; vocab can ship pre-emptively
- **Vocab payload:** label, threshold definition, penalty weight (when re-enabled with PRR/ROR)

---

## P2 — Good hygiene (do these as time allows, ~9 vocabs)

### 16. ✓ `allergen_prevalence_vocab.json` — **NEEDED**

- **Verified size:** **3 IDs** (`high`, `moderate`, `low`)
- **Verified distribution** (`allergens.json`, 17 entries): high=3, moderate=8, low=6 → **17 covered** ✓
- **Note:** distinct from `allergens.severity_level` (separate vocab in #16-companion or merge — clinician decision)

### 17. ✓ `allergen_regulatory_status_vocab.json` — **NEEDED**

- **Verified size:** **3 IDs** (`fda_major`, `eu_allergen`, `eu_major`)
- **Verified distribution** (`allergens.json`): fda_major=9, eu_allergen=7, eu_major=1 → **17 covered** ✓

### 18. ✓ `manufacturer_trust_tier_vocab.json` — **NEEDED, smaller scope than originally planned**

- **Verified scope:** `manufacturer_violations.json` has **79 entries** with violation tracking. `top_manufacturers.json` does NOT exist in current `scripts/data/` — earlier doc reference was stale.
- **Today:** scattered string status across `manufacturer_violations.json`
- **Flutter:** hardcoded "Trusted manufacturer" string in `score_breakdown_card.dart`
- **Recommendation:** smaller scope than originally tiered — single-file vocab covering `manufacturer_violations` status field. Defer until V1.1 trust-tier work formalizes.

### 19. ✓ `efsa_status_vocab.json` — **NEEDED**

- **Verified size:** **10 IDs** (`approved`, `approved_with_restrictions`, `approved_restricted`, `banned_eu`, `restricted_eu`, `not_authorised_eu`, `contaminant_monitored`, `under_review`, `extraction_solvent`, `food_ingredient`)
- **Verified distribution** (`efsa_openfoodtox_reference.json:substances`, 91 entries): approved=64, banned_eu=7, contaminant_monitored=6, approved_with_restrictions=4, approved_restricted=2, restricted_eu=2, food_ingredient=2, under_review=2, not_authorised_eu=1, extraction_solvent=1 → **91 covered** ✓
- **Note:** `approved` and `approved_with_restrictions` and `approved_restricted` look near-duplicates — consolidate during clinician review.

### 20. ✓ `efsa_genotoxicity_vocab.json` — **NEEDED**

- **Verified size:** **7 IDs** (`negative`, `indirect`, `cannot_be_excluded`, `equivocal`, `positive`, `insufficient_data`, `under_review`)
- **Verified distribution** (`efsa_openfoodtox_reference.json:substances`, 91 entries; field name is `genotoxicity`): negative=67, insufficient_data=8, indirect=7, positive=4, equivocal=3, under_review=1, cannot_be_excluded=1 → **91 covered** ✓

### 21. ✓ `match_mode_vocab.json` — **NEEDED**

- **Verified size:** **3 IDs** (`active`, `disabled`, `historical`)
- **Verified distribution** (`banned_recalled.match_mode`, 146 entries; **top-level field, not nested under `match_rules`**): active=142, historical=3, disabled=1 → **146 covered** ✓

### 22. ✓ `confidence_tier_vocab.json` — **NEEDED**

- **Verified size:** **3 IDs** (`high`, `medium`, `low`)
- **Verified distribution** across two source files:
  - `harmful_additives.confidence`, 116 entries: medium=54, high=53, low=9 → 116 covered ✓
  - `backed_clinical_studies.effect_direction_confidence`, 197 entries: medium=124, high=67, low=6 → 197 covered ✓
- **Total:** 313 occurrences across the two files

### 23. ✓ `score_contribution_tier_vocab.json` — **NEEDED**

- **Verified size:** **3 IDs** (`tier_1`, `tier_2`, `tier_3`)
- **Verified distribution** (`backed_clinical_studies.score_contribution`, 197 entries): tier_1=163, tier_2=24, tier_3=10 → **197 covered** ✓

### 24. ✓ `primary_outcome_vocab.json` — **NEEDED**

- **Verified size:** **15 distinct IDs** (live count, not estimated). Examples: `Reduce Stress/Anxiety, Sleep Quality, Focus & Mental Clarity, Immune Support, Healthy Aging/Longevity, Cardiovascular/Heart Health, Digestive Health, Increase Energy, ...`
- **Verified distribution** (`backed_clinical_studies.primary_outcome`, 197 entries): 15 distinct values cover all 197 ✓
- **Note:** value format is human-readable strings ("Reduce Stress/Anxiety") rather than snake_case IDs. Consider snake_case normalization during vocab authoring (`reduce_stress_anxiety`) so vocab IDs are consistent with rest of catalog.

---

## Estimated impact

| Tier | Vocabs | Total vocab size (asset) | Per-blob savings | Implementation effort |
|---|---|---|---|---|
| P0 (5) | verdict (6 with NUTRITION_ONLY), severity (6), condition (14), drug_class (21), user_goals (18) | ~25 KB total | ~50-100 bytes/warning × ~5-10 warnings/product = **0.5-1 KB/blob** | 5 of 5 LOCKED today |
| P1 (11 — #6 split into 6a + 6b) | evidence_design (5), evidence_strength (6), study_type (7), clinical_indication (22), iqm_category (12), banned_status (4), clinical_risk (5), legal_status (10), ban_context (5), effect_direction (4), signal_strength (3) | ~40 KB total | ~30-60 bytes per affected blob | 3 of 11 LOCKED; 8 remaining |
| P2 (9) | allergen_prevalence (3), allergen_regulatory (3), manufacturer_trust (TBD), efsa_status (10), efsa_genotoxicity (7), match_mode (3), confidence_tier (3), score_contribution_tier (3), primary_outcome (15) | ~30 KB total | ~10-30 bytes/blob | 0 of 9 LOCKED |

**Total release effort:** ~17-22 days end-to-end (vocab authoring + clinician review + integrity-gate wiring + Flutter migration + drift tests). All tiers ship together per build-cadence decision 2026-04-30.

**Net Flutter asset bundle:** all ~25 vocabs ≈ **95 KB** (one-time per app install). **Net per-blob savings:** ~1-2 KB/product × millions of blobs = **multi-GB catalog savings**.

---

## Sequencing & co-render rules (per Flutter team feedback 2026-04-30)

### All vocabs ship in a single coordinated release

Per build-cadence decision (2026-04-30): P0 + P1 + P2 land together. The original "ship severity + verdict together" rule is now subsumed — *everything* ships together. Co-render risk (mixed-source labels on `alert_summary_card`, `severity_pill`, `banner`, `score_breakdown_card`) is structurally eliminated because no vocab is left in the old hardcoded state at release time.

**Rule:** vocabs do not merge to main piecemeal. The release branch must carry all vocab JSONs + their integrity-gate wiring + Flutter migration commits before merging. Half-shipped state never reaches users.

### Migration test seed (mandatory per vocab)

When migrating a hardcoded Flutter label map to a vocab asset, add a **drift contract test** that asserts every formerly-hardcoded label EQUALS its `vocab[id].name` post-migration. This catches accidental copy drift during cutover.

Template (Dart side):
```dart
// test/contract/severity_vocab_drift_test.dart
test('severity_vocab labels match severity.dart enum (no drift during cutover)', () async {
  final vocab = await loadSeverityVocab();
  expect(vocab['contraindicated'].name, 'Do not use');
  expect(vocab['avoid'].name,           'Not recommended');
  expect(vocab['caution'].name,         'Use caution');
  expect(vocab['monitor'].name,         'Monitor');
  expect(vocab['informational'].name,   'Informational');
  expect(vocab['safe'].name,            'Safe');
});
```

This test is the cutover safety net — keeps both sources of truth in lockstep until the hardcoded map is physically removed from Dart code.

### `ReferenceDataRepository` parallel-load capability check

The Flutter `ReferenceDataRepository` (`lib/data/repositories/reference_data_repository.dart`) already exists with per-asset caching, but **confirm it supports parallel cold-start fetch** (e.g. `Future.wait([_loadJson(a), _loadJson(b), ...])` in `init()`) before all P0 vocabs ship. Otherwise sequential P0 asset loads on app boot = noticeable first-render delay.

If the loader is sequential today, adding a `Future.wait` is a one-line fix; the catalog currently assumes parallel-load is supported.

---

## Implementation pattern (re-usable recipe)

Already proven with `functional_roles_vocab.json` (32 entries) and the 5 P0 vocabs locked 2026-04-30. For each new vocab:

1. **Inventory** distinct values + cardinality (script: scan all data files for the field — see "verified distribution" data-pull commands above)
2. **Design** the vocab. Internal taxonomy → 5-field lean shape (`id`, `name`, `notes` ≤200 char, `references[]`, `examples[]`). UI-bound (severity, verdict, banned_status, clinical_risk, allergen_prevalence, signal_strength, confidence_tier, score_contribution_tier) → extend with the **Display Contract** fields (`short_label`, `tone`, `ui_color`, `ui_icon`, `action`) per the cross-cutting rule above.
3. **Clinician sign-off** on labels + descriptions (CLINICIAN_REVIEW.md per vocab)
4. **Author** `<field>_vocab.json` with `_metadata.status: "LOCKED — <signoff context>"`
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
- **Strain ID lists** — `BLOCKED_PROBIOTIC_STRAINS` (4 strains) and `HOLD_PROBIOTIC_STRAINS` (4 strains) live in `scripts/constants.py` because they're code-enforced gates, not display content. Don't migrate to a vocab.
- **Blend header allowlist** — `BLEND_HEADER_EXACT_NAMES` (67 entries in constants.py) is a regex/pattern safety net, not a user-facing taxonomy.

---

## Cross-references

- Single-source-of-truth doc: `~/.claude/plans/V1_1_ROADMAP.md` (consolidated V1.1 work)
- First successful vocab: `scripts/data/functional_roles_vocab.json` (LOCKED, 32 entries)
- Flutter handoff: `scripts/audits/functional_roles/FLUTTER_HANDOFF.md`
- Pattern recipe: `CLINICIAN_REVIEW.md` per future vocab
- Coverage gate: `scripts/coverage_gate_functional_roles.py` (template for future vocab gates)

---

## Verification methodology (this revision)

All counts in this doc are pulled live from source data files — no estimates. The verification commands are inline above each P0/P1/P2 entry. To re-verify:

```bash
# Count distinct values in any field
python3 -c "
import json
from collections import Counter
d = json.load(open('scripts/data/<file>.json'))
key = [k for k,v in d.items() if isinstance(v, list)][0]
c = Counter(e.get('<field>') for e in d[key] if isinstance(e, dict))
print(c)
"
```

---

## ✅ Delivery complete (2026-05-02) — Next Steps

### What this batch ships
- **25 vocab JSONs** in `scripts/data/*_vocab.json` (locked, drift-tested)
- **25 pipeline contract tests** in `scripts/tests/test_*_vocab_contract.py`
- **25 Flutter assets** in `assets/data/*_vocab.json` (byte-identical to pipeline)
- **25 Flutter loaders** in `lib/core/data/*_vocab.dart` (FunctionalRole template)
- **25 Flutter drift tests** in `test/core/*_vocab_drift_test.dart`
- **`pubspec.yaml`** registers all 25 assets
- **Severity rename** `info` → `informational` across 3 source data files + 2 Python emitters
- **Doc** updated with verified counts + status snapshot

### Net user-visible UX change after this PR ships
**ZERO.** Drift tests prove vocab labels match the existing hardcoded labels in `verdict_badge.dart`, `Severity` enum, and `schema_ids.dart`. The vocabs are bundled-and-waiting for the next PR.

### Next-step PRs (recommended order)

1. **Wire integrity gate** in `db_integrity_sanity_check.py`. Currently only `functional_roles` has gate hooks there. Add `_check_severity / _check_condition_id / _check_drug_class_id / _check_banned_status / _check_clinical_risk / _check_legal_status / _check_ban_context` etc. patterned after `_check_functional_roles` (lines 167–225). Each is ~15 LOC. Forces unknown IDs in source data to fail the gate at pipeline build time.
2. **Migrate Flutter consumers to vocab-as-source-of-truth**:
   - `lib/core/widgets/verdict_badge.dart` — replace `colorFor`/`labelFor` switches with `verdictVocab[id]` lookup
   - `lib/core/constants/severity.dart` — replace enum's hardcoded `label`/`color` with `severityVocab[id].name`/`uiColor`
   - `lib/core/constants/schema_ids.dart` — delete `conditionLabels`, `drugClassLabels`, `goalLabels`, `goalPriorities` maps (drift tests already enforce equivalence; safe to delete after vocab consumption verified)
   - **Prerequisite:** ensure `ReferenceDataRepository.init()` parallel-loads the new vocabs (one-line `Future.wait` if not already supported per doc §"parallel-load capability check")
3. **Pipeline contract: divert NOT_SCORED out of `products_core`** (`build_final_db.py`). Currently 18 NOT_SCORED + 14 NUTRITION_ONLY products ship. NUTRITION_ONLY is intentional (food-shape products); NOT_SCORED should route to review queue per doc spec.
4. **EFSA status consolidation** (v1.1, in `efsa_status_vocab.json` metadata): clinician review to consolidate `approved` + `approved_with_restrictions` + `approved_restricted` → 2 IDs.
5. **`primary_outcome` source-data canonicalization** (v1.1, in `primary_outcome_vocab.json` metadata): migrate `backed_clinical_studies.primary_outcome` from human-readable strings to snake_case IDs. Update enricher emitters. Vocab already supports round-trip via `legacy_display`.
6. **Rename `ingredient_interaction_rules.evidence_level` → `evidence_strength`** for self-documenting schema (the field semantically holds strength, not level). The vocab is already split (D2 resolved); only the source-data field name remains misleading.

### Future-state (not blocking)
7. **i18n migration**: vocab `name`/`notes`/`action` fields can morph from `String` to `Map<String,String>` (e.g. `{"en":"...", "es":"..."}`). Loaders structured to support this with minor changes.
8. **Hot-deploy via Supabase**: vocabs ship as bundled assets today. Future enhancement = fetch from Supabase at app boot, fall back to bundled. Requires versioned vocab API endpoint.

### Verification commands

```bash
# Pipeline (all vocab tests + integrity gate)
cd /Users/seancheick/Downloads/dsld_clean
python3 -m pytest scripts/tests/ -q -k vocab_contract
python3 scripts/db_integrity_sanity_check.py

# Flutter (all drift tests + analyze)
cd "/Users/seancheick/PharmaGuide ai"
/Users/seancheick/development/flutter/bin/flutter test test/core/
/Users/seancheick/development/flutter/bin/flutter analyze lib/core/data/ test/core/
```

When updating this doc, re-run the inventory commands and update the "verified distribution" lines. The doc is the contract; numbers must match code.
