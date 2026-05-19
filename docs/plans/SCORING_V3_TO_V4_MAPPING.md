# Scoring v3 → v4 — Engineering Bridge

**Status:** REFERENCE — engineering companion to [SCORING_V4_PROPOSAL.md](SCORING_V4_PROPOSAL.md)
**Audience:** engineers implementing the v4 shadow scorer
**Started:** 2026-05-18

This doc is the **code-grounded** bridge between today's v3 scoring
pipeline and the v4 redesign. Every v3 sub-section is mapped to its v4
target with:

- v3 config key (in `scripts/config/scoring_config.json`)
- v3 code location (file:line)
- v3 test file(s)
- v4 module/dimension where it lands
- What changes for the engineer

If a v3 sub-section is not in this table, it has not been classified
yet — flag it before implementation. **Nothing is silently dropped.**

For the architectural rationale, decision log, canary set, anchor
methodology, and Flutter UI design, see [SCORING_V4_PROPOSAL.md](SCORING_V4_PROPOSAL.md).

---

## How to read this doc

```
v3 sub-section
  ├─ config key:       section_X.sub_Y
  ├─ code:             scripts/score_supplements.py:LINE
  ├─ test:             scripts/tests/test_FOO.py
  ├─ v4 location:      <module> → <dimension>
  └─ v4 change:        preserved / reweighted / replaced / removed
```

The four `v4 change` outcomes:

- **preserved** — same logic, same scale, just renamed/relocated
- **reweighted** — same logic, different scale in v4
- **replaced** — different mechanism for the same goal
- **removed** — no longer applies (rare; only listed with rationale)

---

## Section A — Ingredient Quality (v3 cap 25 + 5 category pool)

### A1 — Bioavailability form (IQM `bio_score`)

| | |
|---|---|
| **config key** | `section_A_ingredient_quality.A1_bioavailability_form` |
| **v3 max** | 18 |
| **v3 code** | [`scripts/score_supplements.py:870`](../../scripts/score_supplements.py#L870) — `_compute_bioavailability_score()`; config read at [:958](../../scripts/score_supplements.py#L958) |
| **v3 test** | `scripts/tests/test_score_supplements.py::test_a1_*` |
| **v4 location** | Generic module → Formulation Quality (one line, single source of truth for form mapping) |
| **v4 max** | 15 |
| **v4 change** | **reweighted** (18 → 15 to make room for A2–A6 to stay distinct). Logic identical: IQM `bio_score` weighted by ingredient share of formula. The **double-count bug** (some drafts had "Mapped to a form 10" AND "Bioavailability 10") is fixed — there is **one line** |
| **multivitamin smoothing** | preserved: factor 0.7, floor 9 |

### A2 — Premium forms

| | |
|---|---|
| **config key** | `section_A_ingredient_quality.A2_premium_forms` |
| **v3 max** | 5 |
| **v3 code** | [`scripts/score_supplements.py:982`](../../scripts/score_supplements.py#L982) — `_compute_premium_forms_bonus()` |
| **v4 location** | Generic module → Formulation Quality |
| **v4 max** | 4 |
| **v4 change** | **reweighted**. `skip_first_premium_form=True` rule preserved (A2 only counts ADDITIONAL premium forms beyond the primary that A1 already scored) |

### A3 — Delivery system

| | |
|---|---|
| **config key** | `section_A_ingredient_quality.A3_delivery_system` |
| **v3 max** | 3 (Tier 1=3, Tier 2=2, Tier 3=1) |
| **v3 code** | [`scripts/score_supplements.py:1030`](../../scripts/score_supplements.py#L1030) — `_compute_delivery_score()` |
| **v4 location** | Generic module → Formulation Quality; Probiotic module → Formulation Quality |
| **v4 max** | 3 (Generic), 4 (Probiotic — enteric/lyophilized matter more for live organisms) |
| **v4 change** | **preserved** in Generic; **reweighted** in Probiotic |

### A4 — Absorption enhancer

| | |
|---|---|
| **config key** | `section_A_ingredient_quality.A4_absorption_enhancer` |
| **v3 max** | 3 (Bioperine+curcumin, vit C+iron pairings) |
| **v3 code** | [`scripts/score_supplements.py:1052`](../../scripts/score_supplements.py#L1052) — `_compute_absorption_bonus()` |
| **v4 location** | Generic module → Formulation Quality |
| **v4 max** | 3 |
| **v4 change** | **preserved** |

### A5 — Formulation excellence (rollup including 4-tier synergy)

| | |
|---|---|
| **config key** | `section_A_ingredient_quality.A5_formulation_excellence` |
| **v3 max** | 4 |
| **v3 code** | [`scripts/score_supplements.py:1127`](../../scripts/score_supplements.py#L1127) — `_compute_formulation_bonus()`; synergy at [:1064](../../scripts/score_supplements.py#L1064) — `_synergy_cluster_qualified()` |
| **v3 data** | `scripts/data/synergy_cluster.json` |
| **v4 location** | Generic module → Formulation Quality (rollup) |
| **v4 max** | 4 |
| **v4 change** | **preserved**, all 5 components kept: organic +1, standardized botanical +1, **4-tier synergy cluster (tier 1 proven 1.0 / tier 2 supported 0.75 / tier 3 promising 0.5 / tier 4 popular 0.25)**, non-GMO Project Verified +0.5, natural source +1 |

### A6 — Single-ingredient efficiency

| | |
|---|---|
| **config key** | `section_A_ingredient_quality.A6_single_ingredient_efficiency` |
| **v3 max** | 3 (tiers: bio≥14 → 3, ≥12 → 2, ≥10 → 1) |
| **v3 code** | [`scripts/score_supplements.py:1200`](../../scripts/score_supplements.py#L1200) — `_compute_single_efficiency_bonus()` |
| **v4 location** | Generic module → Formulation Quality |
| **v4 max** | 1 |
| **v4 change** | **reweighted** (3 → 1). Rationale: A1 bio_score already heavily credits premium chelated singles; A6 was double-rewarding. v4 keeps a small +1 for the cleanest case (single-ingredient + bio≥14) |

### Category bonus pool (v3 shared cap 5)

The v3 `category_bonus_pool` was a shared cap across probiotic, omega-3, and enzyme bonuses. **v4 dissolves the pool** and folds each bonus into its class module.

#### probiotic_bonus

| | |
|---|---|
| **config key** | `section_A_ingredient_quality.probiotic_bonus` |
| **v3 max** | 3 default / 10 extended |
| **v3 code** | [`scripts/score_supplements.py:1420`](../../scripts/score_supplements.py#L1420) — `_compute_probiotic_category_bonus()` |
| **v3 gate** | `non_probiotic_strict_gate` (viable CFU, ≥1 named strain, CFU guarantee, explicit intent) |
| **v4 location** | Probiotic module → Formulation Quality (folded into module's 25-pt dimension) |
| **v4 change** | **replaced** — distributed across Formulation lines (total CFU, ≥10B appropriate, named species, exact clinical strain codes, delivery, prebiotic complement) rather than as a flat pool bonus |

#### probiotic_cfu_adequacy

| | |
|---|---|
| **config key** | `section_A_ingredient_quality.probiotic_cfu_adequacy` |
| **v3 max** | 5 uplift (`per_product_max_uplift`) |
| **v3 mechanism** | `tier_points × support_level_caps` — tier: low 0 / adequate 1 / good 2 / excellent 3; support: high 1.0 / moderate 0.75 / weak 0.5 |
| **v3 code** | [`scripts/score_supplements.py:1594`](../../scripts/score_supplements.py#L1594) |
| **v4 location** | Probiotic module → Dose / Clinical Relevance dimension (the "Strain CFU adequacy" line) |
| **v4 max** | 10 (scaled up to 10/25 of the Probiotic Dose dimension) |
| **v4 change** | **reweighted** (5 → 10). Mechanism identical: per-strain CFU compared to clinical-trial dose, weighted by evidence support |

#### omega3_dose_bonus

| | |
|---|---|
| **config key** | `section_A_ingredient_quality.omega3_dose_bonus` |
| **v3 max** | 2 |
| **v3 code** | [`scripts/score_supplements.py:1614`](../../scripts/score_supplements.py#L1614) — `_compute_omega3_dose_bonus()` |
| **v3 history** | Was `section_E_dose_adequacy` in v3.0–v3.2, moved to A.category_bonus_pool in v3.3 |
| **v4 location** | Generic module → Dose dimension (when omega-3 falls through to Generic in v1) OR new Omega module → Dose dimension (if P1.5 gate triggers omega module) |
| **v4 change** | **preserved**; relocated by class |

#### enzyme_recognition

| | |
|---|---|
| **config key** | `section_A_ingredient_quality.enzyme_recognition` |
| **v3 max** | 2.5 (+0.5 per named enzyme) |
| **v3 mechanism** | `require_named_enzyme=True`; min_activity_gate present but disabled |
| **v3 code** | within [`scripts/score_supplements.py`](../../scripts/score_supplements.py) `_compute_formulation_bonus()` integration |
| **v4 location** | Generic module → Formulation Quality (single-ingredient enzyme products); enzymes inside blends route through B5 opacity |
| **v4 max** | 2 |
| **v4 change** | **reweighted** (2.5 → 2). Eventually moves to a dedicated `enzyme` module if canary justifies it |

---

## Section B — Safety & Purity (v3 base 25, bonus 5, cap 30)

v3 formula: `B = clamp(0, 30, base_score(25) + min(5, bonuses) − penalties)`

### B0 — Immediate fail

| | |
|---|---|
| **config key** | `section_B_safety_purity.B0_immediate_fail` |
| **v3 range** | `moderate_penalty: 10`, `high_risk_penalty: 10`, `watchlist_penalty: 5` |
| **v3 code** | [`scripts/score_supplements.py:703`](../../scripts/score_supplements.py#L703) — `_evaluate_safety_gate()` |
| **v3 test** | `scripts/tests/test_score_supplements.py::test_b0_*` |
| **v4 location** | Layer 1 Safety Gate (severe cases route to BLOCKED) + Generic/Multi Formulation penalty (moderate/watchlist) |
| **v4 change** | **replaced** — severe cases now go through the hierarchical Safety Gate; moderate/watchlist penalties stay as score penalties |

### B1 — Harmful additives

| | |
|---|---|
| **config key** | `section_B_safety_purity.B1_harmful_additives` |
| **v3 range** | up to −15 (cap), critical −3 / high −2 / moderate −1 / low −0.5 per additive |
| **v3 code** | [`scripts/score_supplements.py:1847`](../../scripts/score_supplements.py#L1847) — `_compute_harmful_additives_penalty()` |
| **v3 data** | `scripts/data/harmful_additives.json` (115 entries) |
| **v4 location** | Generic/Multi/Probiotic → Formulation Quality (negative) |
| **v4 max penalty** | up to −15 |
| **v4 change** | **preserved** — same scale, same data, same per-tier weights |

### B1 — Dietary sugar penalty

| | |
|---|---|
| **config key** | `section_B_safety_purity.B1_dietary_sugar_penalty` |
| **v3 range** | moderate −0.5, high −1.5, cap −1.5 |
| **v4 location** | Generic/Multi → Formulation Quality (negative) |
| **v4 change** | **preserved** |

### B2 — Allergen presence

| | |
|---|---|
| **config key** | `section_B_safety_purity.B2_allergen_presence` |
| **v3 range** | up to −2 (high 2.0 / moderate 1.5 / low 1.0) |
| **v3 data** | `scripts/data/allergens.json` (Big 8 classification) |
| **v3 code** | [`scripts/score_supplements.py:1991`](../../scripts/score_supplements.py#L1991) — `_compute_allergen_penalty()` |
| **v4 location** | Transparency dimension penalty (allergen presence is a disclosure fact) **AND** Layer 1 CAUTION when user has the allergen in their Flutter profile (via Your Fit E2c) |
| **v4 change** | **reweighted location** — the penalty stays the same, but it's accounted in Transparency (engineering view) and surfaced via Your Fit personalization on the Flutter side |

### B3 — Claim compliance (bonus, not penalty)

| | |
|---|---|
| **config key** | `section_B_safety_purity.B3_claim_compliance` |
| **v3 range** | up to +4 (allergen-free +2, gluten-free +1, vegan/vegetarian +1) |
| **v4 location** | Transparency dimension (display claims contribute to transparency credit) |
| **v4 change** | **preserved** — same cap, folded into Transparency |

### B4 — Quality certifications (the big fix)

| | |
|---|---|
| **config key** | `section_B_safety_purity.B4_quality_certifications` |
| **v3 cap_total** | 21 |
| **v3 B4a** | `points_per_program: 5`, `cap: 15` — pure stacking, no SKU verification |
| **v3 B4b** | `certified: 4`, `fda_registered: 2` |
| **v3 B4c** | `coa: 1`, `batch_lookup: 1` |
| **v3 code** | [`scripts/score_supplements.py:2073`](../../scripts/score_supplements.py#L2073) — `_compute_certifications_bonus()` |
| **v3 bug** | Manufacturer-level injection at [`scripts/enrich_supplements_v3.py:9089`](../../scripts/enrich_supplements_v3.py#L9089) propagates brand-level certs to every SKU of that brand |
| **v4 location** | Testing & Trust dimension (hard-clamped at 15) |
| **v4 max** | 15 (clamp `realized_testing_trust = min(15, sum(verified_cert_points) + gmp_points + batch_traceability_points)`) |
| **v4 change** | **replaced** — B4a now requires SKU-scope verification against public registries (NSF Sport, USP, IFOS, Informed Sport); manufacturer-level injection is rerouted to `manufacturer_cert_signals` (display-only, never scores) per the three-tier cert field split in v4 §10 |
| **v4 diminishing returns** | first SKU cert 8, second 4, third 2; product-line 6/3/1; brand_only 1 (routes to Manufacturer Trust D, not B4a); claimed_only 0 |

### B5 — Proprietary blends (class-aware now)

| | |
|---|---|
| **config key** | `section_B_safety_purity.B5_proprietary_blends` |
| **v3 range** | up to −10 (cap), `presence_penalty.partial: 1`, `proportional_coef.partial: 3`/`none: 5` |
| **v3 code** | within `score_supplements.py` blend resolution; see also `enhanced_normalizer.py` blend detection |
| **v3 memory** | `project_blend_classifier_4state` — 4-state DSLD-aware blend classifier (DISCLOSED_BLEND / BLEND_HEADER / OPAQUE_BLEND / fake-transparency-as-OPAQUE) using category + quantity + nestedRows |
| **v4 location** | v4 §5 B5 Opacity Policy (class-aware penalty table) |
| **v4 change** | **replaced with class-aware version** — same data, same blend classifier (preserved), but penalty severity now depends on what the hidden information prevents the user from evaluating: probiotic-with-named-strains light, stimulant blend severe |

### B6 — Marketing penalty

| | |
|---|---|
| **config key** | `section_B_safety_purity.B6_marketing_penalty` |
| **v3 penalty** | −5 flat for forbidden claims |
| **v4 location** | Layer 1 CAUTION verdict + Transparency dimension penalty |
| **v4 change** | **preserved**, dual-routed |

### B7 — Dose safety

| | |
|---|---|
| **config key** | `section_B_safety_purity.B7_dose_safety` |
| **v3 values** | `threshold_pct: 150`, `single_penalty: 2.0`, `cap: 3.0` |
| **v3 reality** | **Penalty, not verdict.** At >150% UL: −2 per offense, cap −3 total. Verdict stays SAFE unless other gates fire |
| **v4 location** | Dose / Clinical Relevance dimension (penalty); Layer 1 ONLY for life-stage-sensitive nutrients (retinol/iron in pregnancy) |
| **v4 change** | **preserved penalty; replaced framing** — early v4 drafts wrongly equated B7 with the UNSAFE verdict. UNSAFE verdict only fires via Layer 1 hierarchy, not B7 alone |

### B8 — CAERS adverse events

| | |
|---|---|
| **config key** | `section_B_safety_purity.B8_caers_adverse_events` |
| **v3 status** | `enabled: False` currently |
| **v3 range** | strong −4, moderate −2, weak −1, cap −5 |
| **v4 location** | Layer 1 CAUTION verdict when re-enabled |
| **v4 change** | **preserved framework**, re-enable timing TBD |

---

## Section C — Evidence & Research (v3 cap 20)

**Multiplicative pipeline, NOT a flat sum.** This entire pipeline is
preserved verbatim in v4. The multipliers come from `scoring_config.json`:

```python
score = (
    study_type_base_points[study_type]
    × evidence_level_multipliers[evidence_level]
    × effect_direction_multipliers[effect_direction]
    × enrollment_quality_band(participant_count)
    × dose_guard(product_dose, clinical_dose)  # sub_clinical_dose_guard_multiplier
    × top_n_weight[rank_in_product]            # [1.0, 0.7, 0.5, 0.3]
    + depth_bonus(published_studies_count)     # 20-39 → +0.25, ≥40 → +0.5
)
final_C = clamp(0, cap_per_ingredient=7, score) summed across top-4 ingredients, capped at 20 total
```

| Config component | v3 values | v4 change |
|---|---|---|
| `study_type_base_points` | meta 6 / multi-RCT 5 / single RCT 4 / clinical_strain 4 / observational 2 / animal 2 / in_vitro 1 | **preserved** |
| `evidence_level_multipliers` | product-human 1.0 / branded-RCT 0.9 / ingredient-human 0.8 / strain-clinical 0.65 / preclinical 0.3 | **preserved** |
| `effect_direction_multipliers` | positive_strong 1.0 / weak 0.85 / mixed 0.6 / null 0.25 / negative 0.0 | **preserved** |
| `enrollment_quality_bands` | <50 → 0.6 / 50-199 → 0.8 / 200-499 → 1.0 / 500-999 → 1.1 / ≥1000 → 1.2 | **preserved** |
| `sub_clinical_dose_guard_multiplier` | 0.25 | **preserved** |
| `supra_clinical_multiple` | 3.0 max | **preserved** |
| `top_n_weights` | [1.0, 0.7, 0.5, 0.3] | **preserved** |
| `depth_bonus_bands` | [[20, 0.25], [40, 0.5]] | **preserved** |
| `cap_per_ingredient` | 7 | **preserved** — single over-evidenced ingredient cannot dominate |
| `cap_total` | 20 | **preserved** in Generic; **reweighted to 15** in Multi/Prenatal |

**v3 data:** `scripts/data/backed_clinical_studies.json` (197 entries, all PMID-backed per CLAUDE.md). Every PMID is content-verified — never trust existence alone.

**v4 module reweight:** Generic and Probiotic keep Evidence at 20. Multi/Prenatal reweights to 15 because that class earns more in Dose (full panel coverage matters more than per-nutrient evidence for a multi).

---

## Section D — Brand Trust (v3 cap 5)

Renamed to **Manufacturer Trust** in v4 for clarity (distinct from
Testing & Trust which is the cert dimension).

| v3 sub | v3 max | v4 max | Change |
|---|---:|---:|---|
| D1 manufacturer_reputation (trusted) | 2 | 2 | **preserved** |
| D1 mid_tier_reputation (NSF GMP / FDA / USP) | 1 | 1 | **preserved** |
| D2 disclosure_quality | 1 | 1 | **preserved** |
| D3 physician_formulated | 0.5 | 0.5 | **preserved** |
| D4 high_standard_region | 1 | 1 | **preserved** |
| D5 sustainability | 0.5 | 0.5 | **preserved** |
| D3+D4+D5 combined cap | 2.0 | 2.0 | **preserved** |

**v3 data:** `scripts/data/top_manufacturers_data.json`, `manufacturer_trust_tier_vocab.json`.

**v3 code:** Manufacturer trust resolution happens in [`scripts/enrich_supplements_v3.py:9089`](../../scripts/enrich_supplements_v3.py#L9089) — note this is where the manufacturer-cert injection bug also lives. The trust resolver itself is fine; the cert injection is the bug being rerouted.

---

## Manufacturer Violations (top-level, separate from Section D)

| | |
|---|---|
| **config key** | `manufacturer_violations` (top-level, not nested under section_X) |
| **v3 cap_total** | −25 |
| **v3 data** | `scripts/data/manufacturer_violations.json` (89 entries) + `scripts/data/manufacture_deduction_expl.json` (rules) |
| **v3 per-entry deduction** | CRITICAL −12 to −20, HIGH −10 to −12, MODERATE smaller |
| **v3 recency multiplier** | 1.0 within 1yr → 0.25 after 3yr |
| **v3 application** | `total_deduction_applied` field on the manufacturer entry, added directly to `quality_raw` (per the `_note` in config) |
| **v4 location** | **§16 Manufacturer Violations dimension (separate, 0 to −25)** — NOT inside Testing & Trust |
| **v4 change** | **preserved scale and mechanism**; explicitly broken out as its own dimension so the engineering separation is auditable. Flutter UI rolls it into the user-facing "Trust" pillar (see v4 §18) but the column stays distinct |

---

## Section E — Dose adequacy (deprecated)

| | |
|---|---|
| **config key** | `section_E_dose_adequacy` (kept for backward compat) |
| **v3 cap** | 2.0 |
| **v3 status** | `_E_dose_adequacy_deprecated: "Moved to section_A_ingredient_quality.omega3_dose_bonus in v3.3"` |
| **v4 location** | Folded into Omega module (or Generic module's Dose dimension when omega falls through) |
| **v4 change** | **preserved logic**, fully relocated. Section E label can be deleted from config after v4 cutover |

---

## Verdict / safety logic

| v3 mechanism | v3 source | v4 location |
|---|---|---|
| `verdict_logic`, `verdict_rules` | `scoring_config.json` top-level | v4 Layer 1 Safety Gate (hierarchical precedence preserved) |
| Banned/recalled gating | `scripts/data/banned_recalled_ingredients.json` (143 entries) | v4 Layer 1: Regulatory tier → BLOCKED |
| Curated drug interactions | `scripts/data/curated_interactions/curated_interactions_v1.json` | v4 Layer 1: Interaction tier → CAUTION (profile-gated via Flutter Your Fit E2c) |
| Score floors and ceilings | `scoring_config.json.score_floors_and_ceilings` | v4 §4 Score scale anchors |
| Grade scale | `scoring_config.json.grade_scale` | Flutter UI bands; engineering value is the raw score_100 |

---

## SQLite schema migration (`products_core` columns)

| v3 column | v4 column | Migration |
|---|---|---|
| `score_quality_80` | `score_quality_80` retained for one release cycle; new authoritative `score_100` | Both populated during shadow; v3 column dropped at P5 cutover |
| `score_display_100_equivalent` | `score_100` (renamed, no ratio conversion) | v3 column dropped at P5 |
| `score_100_equivalent` | `score_100` | v3 column dropped at P5 |
| `score_ingredient_quality` + `score_ingredient_quality_max` | `score_formulation_quality` + `score_dose_relevance` (split) | Split — old column maps to sum of new two during shadow |
| `score_safety_purity` + `score_safety_purity_max` | (redistributed; no direct replacement) | Replaced by Verdict + per-dimension penalties; old column kept for one cycle then dropped |
| `score_evidence_research` + `score_evidence_research_max` | `score_evidence_strength` | Renamed |
| `score_brand_trust` + `score_brand_trust_max` | `score_trust_combined` (Flutter user-facing) + `score_testing_trust` + `score_manufacturer_trust` + `manufacturer_violation_deduction` (engineering) | Split into 3 engineering columns + 1 user-facing rollup |
| `grade` | `grade` | preserved |
| `verdict` | `verdict` | semantics expanded (Layer 1 hierarchy) |
| (new) | `is_live_eligible BOOLEAN` | added |
| (new) | `confidence_band TEXT` | added |
| (new) | `confidence_drivers_json TEXT` | added (typed sub-categories per v4 §4 Layer 4) |
| (new) | `class_module TEXT` | added (`generic` / `probiotic` / `multi_or_prenatal` / future `omega`) |
| (new) | `score_breakdown_v4_json TEXT` | added (full audit trail) |

---

## Shadow scorer comparison points

Every v3 sub-section that has a `v4 max` and a `v4 change ≠ removed`
must be testable in the shadow comparison report. Suggested
`scripts/scoring_v4/audit/score_diff_v3_v4.py` columns:

```
dsld_id | product | class_module |
  v3.A1, v4.formulation.bio_score |
  v3.A2, v4.formulation.premium_forms |
  v3.A3, v4.formulation.delivery |
  v3.A4, v4.formulation.absorption |
  v3.A5, v4.formulation.excellence |
  v3.A5c_synergy, v4.formulation.synergy_4tier |
  v3.A6, v4.formulation.single_efficiency |
  v3.enzyme, v4.formulation.enzyme |
  v3.probiotic_bonus, v4.probiotic_module.formulation_rollup |
  v3.probiotic_cfu_adequacy, v4.probiotic_module.dose.cfu_adequacy |
  v3.omega3_dose_bonus, v4.<generic|omega>.dose.omega_bonus |
  v3.B0, v4.layer1_gate.b0 + v4.<module>.formulation.b0_penalty |
  v3.B1_additives, v4.<module>.formulation.b1_additives |
  v3.B1_sugar, v4.<module>.formulation.b1_sugar |
  v3.B2_allergen, v4.<module>.transparency.b2_allergen_penalty |
  v3.B3_claim_compliance, v4.<module>.transparency.b3_claims_bonus |
  v3.B4a, v4.<module>.testing_trust.b4a_verified |
  v3.B4b, v4.<module>.testing_trust.b4b_gmp |
  v3.B4c, v4.<module>.testing_trust.b4c_batch |
  v3.B5, v4.<module>.transparency.b5_opacity_class_aware |
  v3.B6, v4.layer1_gate.b6 + v4.<module>.transparency.b6_penalty |
  v3.B7, v4.<module>.dose.b7_penalty |
  v3.B8, v4.layer1_gate.b8 (when enabled) |
  v3.C_evidence, v4.<module>.evidence_strength |
  v3.D, v4.manufacturer_trust |
  v3.manufacturer_violations, v4.manufacturer_violations |
  v3.score_quality_80, v4.score_100 |
  delta_per_dimension |
  flags: bio_score_double_count_caught, b4_cert_inflation_caught, b7_verdict_change_caught
```

Each row in the report = one product. The bottom three `flags` columns
catch the v3 bugs (bio_score double-count was in some draft v4 rubrics
that need to be reconciled; B4 inflation comes from manufacturer
injection; B7 verdict change came from early v4 misclassification).

---

## Quick reference — what NEVER changes from v3

The following are not touched by v4 in v1:

- `scripts/data/ingredient_quality_map.json` (610 IQM parents)
- `scripts/data/banned_recalled_ingredients.json` (143 entries)
- `scripts/data/harmful_additives.json` (115 entries)
- `scripts/data/backed_clinical_studies.json` (197 PMID-backed entries)
- `scripts/data/allergens.json`
- `scripts/data/rda_optimal_uls.json`
- `scripts/data/synergy_cluster.json`
- `scripts/data/curated_interactions/curated_interactions_v1.json`
- `scripts/data/top_manufacturers_data.json`
- `scripts/data/manufacturer_violations.json` (89 entries)
- `scripts/data/manufacture_deduction_expl.json`
- `scripts/data/manufacturer_trust_tier_vocab.json`
- `scripts/enrich_supplements_v3.py` enrichment logic EXCEPT the
  manufacturer-cert injection block at [:9089](../../scripts/enrich_supplements_v3.py#L9089)
  which gets rerouted to `manufacturer_cert_signals` (display-only)

Major enrichment upgrades (per-strain CFU extraction, omega EPA/DHA
breakdown, branded-extract identity expansion) are P6+ and out of scope
for v4 v1.

---

## Reading order for an engineer new to v4

1. **This doc** (SCORING_V3_TO_V4_MAPPING.md) — engineering bridge
2. [SCORING_V4_PROPOSAL.md](SCORING_V4_PROPOSAL.md) §2 Pipeline shape — visual flow
3. [SCORING_V4_PROPOSAL.md](SCORING_V4_PROPOSAL.md) §4 Architecture — 4 layers
4. [SCORING_V4_PROPOSAL.md](SCORING_V4_PROPOSAL.md) §6/§7/§8 Per-class rubrics — what the scorer actually computes
5. [SCORING_V4_PROPOSAL.md](SCORING_V4_PROPOSAL.md) §10 Cert verification — the cert resolver pipeline
6. [SCORING_V4_PROPOSAL.md](SCORING_V4_PROPOSAL.md) §19 Phased migration — what gets built when
7. [SCORING_V4_PROPOSAL.md](SCORING_V4_PROPOSAL.md) §17 v3 → v4 dimension mapping — the architectural mirror of this doc (concept-level)
8. [CLINICIAN_VERIFICATION_QUEUE.md](CLINICIAN_VERIFICATION_QUEUE.md) — async queue for edge cases
