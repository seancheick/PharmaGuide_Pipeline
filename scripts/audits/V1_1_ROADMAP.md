# PharmaGuide V1.1 — Consolidated Roadmap

**Last updated:** 2026-04-30
**Owner:** pipeline team + Dr Pham (clinical sign-off)
**Status:** V1 shipped 2026-04-30 (commit `7ede3a1`); V1.1 work catalogued below

This doc consolidates all the V1.1 follow-ups deferred during V1 functional-roles work. It's the single source of truth — everything previously scattered across commit messages, phase research notes, and the plan file.

---

## How to read this doc

Each item below is **scoped, prioritized, and unblocked** — no new design decisions needed. Sections are grouped by subsystem. "Effort" is rough developer-days assuming the V1 patterns hold (~40-entry batches, atomic commits, regression tests).

Priority legend:
- **P0** — blocks meaningful Flutter UX work
- **P1** — important polish; ships soon after P0
- **P2** — nice-to-have; flag for clinician interest before scoping

---

## 1. Functional roles — outstanding work

### 1.1 [P1] Expand `is_branded_complex` heuristic *(Effort: 1-2 days)*

**Where it stands:** Phase 6 (commit `7ede3a1`) flagged 3 branded complexes via name-pattern heuristic (BioCell / Tonalin / AstraGin family). Conservative — there are ~24 more known branded complexes in `other_ingredients.json` that should also carry `attributes.is_branded_complex: true`.

**What to do:**
- Extend the `BRAND_MARKERS` set in `scripts/audits/functional_roles/phase_6_attributes/backfill.py`
- Run heuristic + manual spot-check against the ~117 entries flagged `is_active_only`
- Goal: capture all entries whose `standard_name` contains a registered branded-complex marker

**Reference:** `scripts/audits/functional_roles/CLINICIAN_REVIEW.md` Section 6 attribute table

### 1.2 [P0] `additive_type` field physical drop + scoring migration *(Effort: 3-4 days)*

**Why deferred:** Touches scoring logic. `additive_type` (snake_case) → `additiveType` (camelCase) is read by the cleaner/normalizer and feeds `ADDITIVE_TYPES_SKIP_SCORING` in `enrich_supplements_v3.py:2779-2782, 3043-3047`. Removing the field without migrating those references would break active/inactive classification.

**What to do (in order):**
1. Find all references to `additiveType` / `additive_type` in `scripts/`:
   ```
   enrich_supplements_v3.py: 2779, 2781, 2782, 2920, 3015, 3043, 3044, 3046, 3047, 3549
   enhanced_normalizer.py:    1432, 1646, 1651, 1665, 1666, 3107, 3117, 3125, 3219
   constants.py:              1137 (SKIP_REASON_ADDITIVE_TYPE)
   ```
2. Define `FUNCTIONAL_ROLES_SKIP_SCORING` set in `constants.py` — should mirror what the existing `ADDITIVE_TYPES_SKIP_SCORING` set was meant to skip
3. Migrate scoring rules: `if any(r in FUNCTIONAL_ROLES_SKIP_SCORING for r in ingredient.get('functional_roles', []))`
4. Drop `additive_type`/`additiveType` from `enhanced_normalizer.py` outputs
5. Drop `additive_type` field from `other_ingredients.json` (mechanical) — currently marked DEPRECATED in `_metadata`
6. Drop `category_enum` value `excipient` if no entries land there post-migration
7. Run full test battery (5,800+ tests must still pass)

**Reference:** `scripts/SCORING_README.md` v3.5.1 changelog; `scripts/audits/functional_roles/phase_4a/research.md` (deferred-work section)

### 1.3 [P1] Move-to-actives physical relocation *(Effort: 2-3 days)*

**Where it stands:** 117 entries in `other_ingredients.json` carry `is_active_only: true` and `category: active_pending_relocation`. They're suppressed from Flutter `inactive_ingredients[]` but physically still live in `other_ingredients.json`.

**What to do:**
- Define a target schema in the active-ingredient pipeline (whatever file the Flutter blob's `ingredients[]` reads from)
- Migrate 117 entries: BioCell Collagen, LactoSpore, Tonalin, AstraGin, glandular tissues (10), amino_acid_derivatives (7), botanical_extract (14), phytocannabinoids, marine extracts, Black Pepper Extract, NHA_GLYCOLIPIDS
- Specifically also: `Senna` (currently in harmful_additives) + `Synthetic B Vitamins` + `Synthetic Vitamins` + `Cupric Sulfate` per clinician 4F
- Preserve B1 caution: if Senna found in non-laxative product, fire safety penalty (mirrors existing Cascara Sagrada match_mode='active' guard)

### 1.4 [P2] V1 holdouts (clinician 4F) — per-product disambiguation *(Effort: per-cycle)*

These entries currently carry `functional_roles: []` and stay on the V1.1 manual-review queue. Resolved as per-product data lands or as the attributes layer expands:

| Entry | Why deferred | Resolution path |
|---|---|---|
| `ADD_CARAMEL_COLOR` | Class i-iv distinction (Class III/IV carry 4-MEI / Prop 65) | Add `attributes.caramel_class` per-product; B1 logic fires on iii/iv |
| `ADD_CANDURIN_SILVER` | Brand covers multiple pearlescent-mineral formulations | Per-product source verification; resolve to colorant_natural / colorant_artificial per product |
| `ADD_TIME_SORB` | Brand covers multiple cellulose-based sustained-release excipients | Per-product source verification; assign coating/binder/etc. per actual product use |

---

## 2. Attributes layer expansion

Per `CLINICIAN_REVIEW.md` Section 6 — the V1.1 attributes object describes what an ingredient IS or how it was made (vs functional_roles[] which says what it DOES).

### 2.1 [P0] `is_synthetic_form` for vitamin/active-form quality *(Effort: 2 days)*

**Why:** Drives the synthetic-vs-bioactive form quality flag in the active-ingredient pipeline (folate vs 5-MTHF, cyanocobalamin vs methylcobalamin, pyridoxine HCl vs P-5-P, etc.). Belongs in IQ /25 scoring pillar per clinician 4F.

**What to do:** Tag every IQM form (in `ingredient_quality_map.json` `forms` blocks) with `is_synthetic_form: true|false`. Likely 200-300 forms across the vitamin/cofactor family. Drives a future quality bonus in the scoring engine.

### 2.2 [P1] `flavor_source` / `colorant_source` for filter UX *(Effort: 1 day)*

**Why:** Enables Flutter "show me products without artificial colorants" filter without parsing `functional_roles[]` strings.

**What to do:** Add `attributes.flavor_source: "natural"|"artificial"` and `attributes.colorant_source: "natural"|"artificial"` on every entry where the role contains `flavor_*` or `colorant_*`. Mostly redundant with the role split — useful as a denormalization for filter perf.

### 2.3 [P1] `is_animal_derived` expansion (vegan filter) *(Effort: 1-2 days)*

**Where it stands:** Phase 6 only flagged Carmine (cochineal). Need full audit:
- harmful_additives: Sodium Caseinate (milk), Carmine (cochineal), Shellac (lac insect resin), Beeswax (insect), gelatin-based entries
- other_ingredients: bovine/porcine/marine/dairy-derived entries — all 117 move-to-actives entries plus carrier oils derived from animal sources
- botanical_ingredients: 1 honey entry (already plant→animal corrected)

### 2.4 [P2] `caramel_class` per-product *(Effort: per-product)*

Currently `caramel_class: null` on `ADD_CARAMEL_COLOR`. Populate as per-product Class I/II/III/IV data lands. Drives B1 safety penalty on iii/iv (4-MEI / Prop 65).

### 2.5 [P2] `e171_eu_concern` flag *(Effort: 0.5 day)*

TiO2 itself is in `banned_recalled_ingredients.json` already. The attribute would surface on *other* products mentioning TiO2 indirectly. Flutter UX use case unclear in V1.1; defer until product team prioritizes.

---

## 3. Other_ingredients deeper cleanup

### 3.1 [P2] Long-tail decomposition spot-check *(Effort: 1 day)*

**Where it stands:** Phase 4c (commit `01aecfc`) ran the deterministic `categorize.py` mapper across all 673 entries. ~85 entries went to `label_descriptor`, ~117 to `active_pending_relocation`, 1 to `manual_review`. Clinician requested 10% spot-check per CLAUDE.md.

**What to do:** Sample 67 entries (10% of 673), verify their post-categorization lands the right place. Flag any that should be reassigned. Capture in `scripts/audits/functional_roles/phase_4c_oi_categories/spot_check.md`.

### 3.2 [P1] `additive_type` removal (covered by 1.2)

---

## 4. IQM (`ingredient_quality_map.json`) follow-ups

### 4.1 [DONE] Round 1 + 2 category audit *(2026-04-30)*

41 + 13 = 54 entries reclassified out of `other` bucket. `other` shrunk 77 → 23. Remaining 23 are legitimately ambiguous (hormones, nucleotides, organic acids, sulfur compounds, plant alkaloids without clear botanical origin).

### 4.0 [DONE] Cross-file categorization sweep *(2026-04-30)*

Comprehensive scan of category-like fields across all 14 JSON reference files. Findings + targeted safe fixes applied:
- `botanical_ingredients.json` — 1 entry (rhododendron_caucasicum) with `unspecified` category → fixed to `herb`
- `backed_clinical_studies.json` — probiotic spelling normalization: `probiotic` (4) + `probiotic strain` (4) + `probiotics` (3) → all `probiotics` (11 entries normalized)
- `backed_clinical_studies.json` — Spirulina + Chlorella moved out of `other` → `antioxidant`
- All other reference files (allergens, absorption_enhancers, clinical_risk_taxonomy, proprietary_blends, functional_ingredient_groupings) — categorically clean

**Final 'other' bucket (23 entries — staying):**
- Hormones (3): 7-Keto DHEA, DHEA, Melatonin
- Nucleotides (5): Adenosine, ATP, D-Ribose, Inosine, Uridine-5'-Monophosphate, RNA/DNA
- Organic acids (3): Citric Acid, Succinic Acid, Orotic Acid
- Sulfur compounds (1): MSM
- Calcium salts (2): Calcium D-Glucarate, Calcium Pyruvate
- Polyols (1): Xylitol
- Misc/specialty (8): Acetogenins, Activated Charcoal, Bile Extract, Dietary Nitrate, Geranylgeraniol, Glucuronolactone, Vicine, palmitic_acid (already moved)

### 4.2 [P1] Cross-bucket sanity check *(Effort: 0.5 day)*

Spot-check entries in `herbs` (199), `antioxidants` (108), `fatty_acids` (64) buckets — flag any that are obviously misclassified. Particularly: borderline `herbs` vs `functional_foods`, single-compound antioxidants vs multi-compound plant extracts.

### 4.3 [P2] Form-level synthetic flag (covered by 2.1)

---

## 5. Scoring engine V1.1

### 5.1 [P0] B8 CAERS — re-enable with PRR/ROR normalization *(Effort: 5+ days)*

**Where it stands:** B8 disabled 2026-04-30 (commit `33ffbf3`) — raw report counts confounded popularity with risk (calcium 2,145 reports vs kratom 759 hit same penalty bucket).

**What to do:**
1. Rebuild `caers_adverse_event_signals.json` with **proportional reporting ratio (PRR)** or **reporting odds ratio (ROR)** instead of raw `serious_reports` counts. Divides each ingredient's reports by total CAERS volume to remove popularity bias.
2. OR: build a curated allowlist of ~10-15 ingredients with attributable causation (kratom, ephedra, yohimbe, garcinia, green-tea-extract at hepatotoxic doses, DHEA, 5-HTP, black cohosh, licorice, goldenseal, raspberry ketones)
3. Re-enable B8 in `scoring_config.json` (`enabled: true`)
4. Run full snapshot battery + verify multivitamins no longer hit -5.0 cap

**Reference:** `scripts/SCORING_ENGINE_SPEC.md` § B8 (DISABLED)

### 5.2 [P1] Caramel Color Class III/IV B1 penalty *(Effort: 1 day, depends on 2.4)*

When `attributes.caramel_class` lands per product, fire a graduated B1 penalty for Class III/IV (4-MEI Prop 65 listing). Currently the harmful_additives Caramel Color entry triggers a flat penalty regardless of class.

### 5.3 [P1] Glandular sourcing safety (BSE/prion) *(Effort: 2-3 days)*

Per clinician handoff: "Out of scope for this work; flagged for the safety-logic spec." When the active-ingredient pipeline opens up and glandular tissue entries relocate, add a B0/B1 sourcing-safety check:
- Bovine glandular tissue from non-NZ/AU sources → B1 caution (BSE/prion risk, FDA scrapie surveillance)
- Sheep/goat glandular from prion-endemic regions → B0 high_risk

Needs a `country_of_origin` attribute on the ingredient + a per-product label-claim parse.

---

## 5b. Reference-data category audits — deferred to clinician

### 5b.1 [P1] `standardized_botanicals.json` — 41 entries with non-botanical categories *(Effort: 2-3 days clinician + 1 day ours)*

**The issue:** the file is supposed to hold branded/standardized BOTANICAL extracts, but ~17% of entries (41/239) carry categories that aren't plant-part descriptors:

- **`standardized` / `standardized_extract` (19 entries):** branded extracts without their underlying plant part exposed in the category. E.g. `cran_max` (cranberry → fruit), `pine_bark_extract` (→ bark), `morosil` (blood orange → fruit), `slendesta` (potato → vegetable), `enxtra` (alpinia galanga rhizome → root). Should be re-categorized to the plant-part of the source.
- **`active_compound` / `polyphenol` / `polysaccharide` / `fatty_acid_amide` / `tripeptide` (10 entries):** chemical-class categories on entries like `gingerols`, `curcumin`, `wellmune` (beta-glucan), `levagen` (PEA), `setria` (glutathione). Either re-categorize to source plant-part OR move out of standardized_botanicals to chemistry-specific refs.
- **`mineral` / `mineral_chelate` / `mineral_complex` / `algal_oil` / `structural_protein` / `amino_acid` / `nootropic` / `hormone_analog` / `fermentate` (12 entries):** these aren't botanicals at all. Branded mineral chelates (`chromax`, `sunactive_iron`), branded amino acids (`alphawave_l_theanine`), branded fatty acids (`life_s_dha`, `levagen`), branded proteins (`keraglo`), branded fibers (`wellmune`), branded fermentates (`epicor`), branded hormone (`microactive_melatonin`). Should be migrated to their respective IQM-style references.
- **`standardized` (10 of 19) entries with brands like `bil_max`, `blue_max`, `pacran`, `flowens`, `sharp_ps_green`** — need clinician verification of the underlying source plant part.

**What to do:** clinician audit + per-entry rename to canonical plant-part categories. Migrate truly-non-botanical entries to actives/IQM. Conservative — no changes without clinician sign-off (sample table delivered for review).

### 5b.2 [P1] `backed_clinical_studies.json` — 148 distinct categories *(Effort: 2-3 days clinician + 0.5 day ours)*

**The issue:** the file holds 197 clinical-evidence entries with **148 distinct `category` values** — most appear ONLY ONCE (128/148 are single-occurrence). Categories describe clinical APPLICATION/INDICATION (e.g. "anti-inflammatory", "joint health", "cognitive"), not ingredient class.

**What's already done (2026-04-30):** safe normalizations applied — probiotic spelling collapse (3 → 1), Spirulina/Chlorella out of "other".

**What to do:** clinician-driven canonicalization to ~20 controlled clinical-application buckets:
- anti-inflammatory, antioxidant, cognitive/neurological, cardiovascular, joint/bone, skin/hair/collagen, digestive/gut, liver/detox, sleep/mood, sports/performance, immune, metabolic/blood-sugar, weight management, prebiotic/fiber, mitochondrial, hormonal, eye/vision, vitamin/nutrient, adaptogen/stress, probiotics
- Multi-benefit entries (e.g. "antioxidant / detox") use comma-separated multi-tag, not new compound categories
- Build the canonical set first, then per-entry remap with clinician spot-check

This is similar in spirit to the functional_roles vocab work but for a different taxonomic axis (clinical indication, not ingredient role).

---

## 6. Flutter integration

### 6.1 [P0] Per-chip deeper-dive screens *(Effort: Flutter-side; 3-5 days for content)*

Per clinician copy review (`CLINICIAN_REVIEW.md` Section 5): "V1.1 should pair each chip's neutral definition with a deeper-dive screen carrying safety context."

**Content needed (clinician-authored):**
- **Sugar alcohols** — FODMAP/IBS specifics, gram-threshold guidance, regional differences
- **Caramel Color** — Class III/IV 4-MEI / Prop 65 explanation
- **Titanium Dioxide (E171)** — EU vs FDA regulatory divergence (banned 2022 in EU food)
- **Magnesium Stearate** — neutral on the consumer-advocacy debate (lubricant article context)
- **Artificial Colorants** — soft framing for users who prefer to avoid
- **Artificial Sweeteners** — gut microbiome + glucose response evidence

**Where it ships:** Flutter assets bundle (separate from `functional_roles_vocab.json`). Vocab carries the chip label + 1-line `notes`; deeper-dive screens carry the multi-paragraph context.

### 6.2 [P1] Filter UX driven by attributes (covered by 2.2, 2.3)

### 6.3 [P0/P1] Reference-data lookup vocabs (24 opportunities) *(Effort: 5-7 days P0 + 7-10 days P1 + 5-7 days P2)*

Pipeline + Flutter audit found 24 opportunities to apply the same reference-data lookup pattern that worked for `functional_roles_vocab.json`. Full catalog: **`scripts/audits/REFERENCE_DATA_LOOKUP_OPPORTUNITIES.md`**.

**P0 (5 vocabs — biggest impact):**
- `verdict_vocab.json` (6 IDs) — replaces hardcoded labels in Flutter `verdict_badge.dart`
- `severity_vocab.json` (6 IDs) — replaces 437+ inline severity strings across interaction_rules + Flutter `severity.dart` enum
- `condition_vocab.json` (~14 IDs) — replaces hardcoded `conditionLabels` map in Flutter `schema_ids.dart`
- `drug_class_vocab.json` (~13 IDs) — replaces hardcoded `drugClassLabels` map
- `user_goals_vocab.json` (~18 IDs) — replaces hardcoded `goalLabels` map

**P1 (10 vocabs — strong yes):**
- `evidence_level_vocab.json` (3-5 IDs)
- `study_type_vocab.json` (7 IDs)
- `clinical_indication_vocab.json` (22 IDs — the buckets we just canonicalized)
- `iqm_category_vocab.json` (12 IDs)
- `banned_status_vocab.json` (4 IDs)
- `clinical_risk_vocab.json` (5 IDs)
- `legal_status_vocab.json` (10 IDs)
- `ban_context_vocab.json` (5 IDs)
- `effect_direction_vocab.json` (4 IDs)
- `signal_strength_vocab.json` (3 IDs)

**P2 (9 vocabs — good hygiene):**
- allergen_prevalence, allergen_regulatory, manufacturer_trust, efsa_status, efsa_genotoxicity, match_mode, confidence_tier, score_contribution_tier, primary_outcome

**Net impact:**
- Bundle size: all 24 vocabs ≈ 95 KB (one-time per app install)
- Per-blob savings: ~1-2 KB/product × millions of blobs = **multi-GB catalog savings**
- Architectural: clinician owns user-facing copy (no Dart code edits needed for taxonomy changes)
- i18n-ready: vocab schema migrates cleanly to localized `Map<locale, string>` payloads
- **Offline-first** (no network at render time)

**Reusable Flutter scaffolding** already exists (`FunctionalRole` template + `ReferenceDataRepository` central loader). Future vocabs cost ~1 day vocab authoring + 1 day Flutter wiring.

---

## 7. Data quality / testing

### 7.1 [P1] coverage_gate.py — extend to other contracts *(Effort: 0.5 day)*

`scripts/coverage_gate_functional_roles.py` (Phase 5, commit `4bab104`) currently covers only the functional_roles domain. Extend to cover:
- `attributes.source_origin` populated on all botanicals (already enforced; add to gate)
- `is_branded_complex` populated on flagged is_active_only entries (after 1.1 expansion)
- `is_synthetic_form` populated on vitamin forms (after 2.1)

### 7.2 [P2] Pipeline integrity test cleanup

`test_drug_classes_schema` and `test_scoring_snapshot_v1` — pre-existing failures unrelated to functional_roles work. Address in a separate cycle.

---

## Where work is currently documented (for reference)

This roadmap consolidates. The following files reference V1.1 work fragmentarily:

| File | What |
|---|---|
| `~/.claude/plans/golden-painting-umbrella.md` | Original 5-phase plan + V1.1 attributes section |
| `scripts/audits/functional_roles/CLINICIAN_REVIEW.md` | Clinician-locked spec (Section 6 = attributes architecture) |
| `scripts/audits/functional_roles/FLUTTER_HANDOFF.md` | Flutter integration brief; V1.1 deeper-dive note at end |
| `scripts/data/functional_roles_vocab.json` | `_metadata.v1_1_followups` array |
| `scripts/SCORING_README.md` § B8 | B8 disable rationale + re-enable criteria |
| `scripts/SCORING_ENGINE_SPEC.md` § B8 | DISABLED status with PRR/ROR re-enable path |
| `scripts/audits/functional_roles/phase_4a/research.md` | What's deferred to 4b/4c |
| `scripts/audits/functional_roles/phase_4b/research.md` | additive_type drop deferred + reasoning |
| `scripts/audits/functional_roles/phase_4c_oi_categories/backfill.py` (header) | Phase 4 line-of-sight |
| `scripts/audits/functional_roles/phase_6_attributes/backfill.py` (header) | V1.1 attribute follow-ups |
| `scripts/coverage_gate_functional_roles.py` (header) | V1.1 architectural exclusion list |
| Commit messages (`af45574` → `7ede3a1`) | Per-commit deferred-work mentions |

**Going forward:** add new V1.1 items here in this single doc. Other refs are historical context.
