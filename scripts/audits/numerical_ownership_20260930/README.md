# Six-pillar numerical ownership inventory

Status: **DRAFT — inventory only.** This artifact records the numerical rules reachable from the
production v4 scorer at `7cf7100d22276e430981333b275a36718475bc2c`. It changes no score, config,
test, catalog or release artifact. Rows marked **DRAFT POLICY** depend on the unresolved Phase 1
Evidence-to-Dose transfer or Phase 5 calibration/overlap decision. Their present implementation is
reported as fact; it is not ratified by this document.

## Owner check and production reachability

- Owner: `scripts/score_supplements_v4.py::score_product_v4` -> `_score_v4_core` is the public
  scoring entry point.
- Owner: `scripts/scoring_v4/quality_score.py::assemble_quality_score` -> `_build_pillars` assembles
  the six public pillars and their literal sum.
- Owner: `scripts/scoring_v4/config/quality_score.json` owns the public pillar weights and the
  config-backed magnitudes named below. It is not the only live numerical source: route modules,
  `scripts/data/omega_rubric.json`, RDA/UL data and therapeutic-dose data also own live rules.
- Owner: `scripts/scoring_v4/penalty_registry.py::PENALTY_REGISTRY` owns penalty placement and the
  two explicit consumer-mirror groups.
- Will NOT create: a second scorer, post-route Dose engine, Evidence subject set, prominence
  classifier, penalty registry or app-side score calculation.

Production path:

```text
score_product_v4
  -> _score_v4_core
  -> router dispatch (generic, probiotic, multi/prenatal, B-complex,
                      omega, sports, fiber/digestive)
  -> route dimension scorers
  -> assemble_quality_score
  -> _build_pillars
  -> literal sum of the six published pillars
```

## Required numerical-ownership table

“Observer” means the named pillar may consume or display the canonical fact for its own distinct
judgment. It may not repeat the listed numerical judgment. A currently implemented second deduction
is called out explicitly rather than silently described as observation.

| Fact | Judgment | Pillar | Exact numerical owner | Other pillars allowed to observe but not deduct | Status |
|---|---|---|---|---|---|
| IQM `forms[].bio_score`, delivery, absorption and standardization | Ingredient-form quality | Formulation | `generic_formulation.score_formulation`; `quality_score.json::formulation_magnitudes` | Evidence may determine preparation applicability; Dose may assess amount | Current owner |
| Harmful-additive severity | Formula-quality cost | Formulation | `generic_formulation.shared_formulation_penalty_detail`; `quality_score.json::formulation_penalties.b1_harmful_additive_points/b1_harmful_additive_cap` | Safety currently applies a second capped judgment through `_formulation_additive_safety_penalty` | **DRAFT POLICY** |
| Added sugar, sugar alcohol, syrup and glycemic load | Formula-quality cost | Formulation | `generic_formulation._dietary_sugar_penalty`; `quality_score.json::formulation_magnitudes.dietary_sugar_*` | Safety currently applies the same capped mirror as harmful additives | **DRAFT POLICY** |
| Moderate/watchlist ingredient | Formula-quality concern | Formulation | `generic_formulation.score_formulation`; `quality_score.json::formulation_magnitudes.b0_*` | Safety gate may own a distinct safety verdict | Current owner |
| High-variability immune botanical stack | Formulation-complexity penalty | Formulation | `immune_support.immune_support_formulation_adjustment`; `quality_score.json::category_magnitudes.immune_support.high_variability_botanical_stack_*` | Evidence assesses studies; Dose assesses amounts | Current owner |
| Botanical identity, plant part, extract, standardization and brand | Botanical formulation quality | Formulation | `botanical_profile.score_botanical_formulation`; `quality_score.json::formulation_variant_magnitudes.botanical.*`; hard-coded component values in that function | Evidence and Dose may consume canonical identity/form | Current owner |
| Collagen hydrolysis, type, source, amount disclosure and branded formula | Collagen formulation quality | Formulation | `collagen_profile.score_collagen_formulation`; `quality_score.json::formulation_variant_magnitudes.collagen.collagen_formulation_cap`; hard-coded component values in that function | Dose assesses clinical amount | Current owner |
| Multi/prenatal form quality and structural panel disclosure | Panel formulation quality | Formulation | `multi_prenatal_formulation.score_formulation`; `quality_score.json::formulation_variant_magnitudes.multi_prenatal.*` | Transparency assesses identity/amount disclosure | Current owner |
| Probiotic potency disclosure, strain identity and delivery survivability | Probiotic formulation quality | Formulation | `probiotic_formulation.score_formulation`; `quality_score.json::formulation_variant_magnitudes.probiotic.*` | Dose assesses potency; Transparency assesses disclosure | Current owner |
| Omega IQM form and EPA+DHA concentration | Omega formulation quality | Formulation | `omega_formulation.score_formulation`; `quality_score.json::formulation_variant_magnitudes.omega.cap_formulation`; `omega_rubric.json::formulation.iqm_form_quality/epa_dha_concentration` | Dose owns EPA+DHA exposure | Current owner |
| Sustainability certification | Consumer sourcing metadata, currently zero quality points | Formulation metadata | `omega_formulation._sustainability_cert_verified`; `omega_rubric.json::formulation.sustainability_cert.score` | Verification may score qualifying quality/testing certification | Current owner: zero |
| Sports protein source, formula design and amino-spiking/opaque-blend concerns | Sports formulation quality | Formulation | `sports_formulation.score_formulation`; hard-coded route components/bands; `quality_score.json::formulation_variant_magnitudes.sports` | Dose owns sports-active amounts | Current owner |
| Fiber source, disclosure, focus and practicality | Fiber formulation quality | Formulation | `fiber_digestive_formulation.score_formulation`; hard-coded `_source_quality`, `_fiber_disclosure`, `_fiber_focus`, `_practicality`; `quality_score.json::formulation_variant_magnitudes.fiber_digestive` | Dose owns grams/day; Evidence owns literature | **DRAFT POLICY**: overlap below |
| B-complex profile construction | B-complex formulation quality | Formulation | `b_complex.score_b_complex`; hard-coded profile rules; `quality_score.json::category_magnitudes.b_complex.formulation_cap` | Dose and Evidence may consume nutrient identity | Current owner |
| Generic RDA/AI or reviewed clinical-anchor exposure | Amount appropriateness | Dose | `generic_dose.score_dose`; `quality_score.json::dose_magnitudes.generic.*`; enrichment `rda_ul_data.adequacy_results` | Evidence may retain trial amount as a source fact only | **DRAFT POLICY**: Phase 1 transfer |
| Missing benchmark with disclosed amount | Limited assessability fallback | Dose | `generic_dose._score_no_reference_quantified_dose`; `quality_score.json::dose_magnitudes.generic.no_reference_*` | Transparency may reward disclosure | **DRAFT POLICY**: Phase 4 packet |
| UL exceedance | Dose appropriateness/risk deduction | Dose | `dose_safety.evaluate_dose_safety`; `quality_score.json::dose_safety_policy` | Safety currently applies a second capped risk-visibility judgment | **DRAFT POLICY**: Phase 4/5 |
| Botanical studied range | Botanical amount appropriateness | Dose | `botanical_profile.score_botanical_dose`; `quality_score.json::formulation_variant_magnitudes.botanical.botanical_dose_*`; `rda_therapeutic_dosing.json` | Evidence must not repeat adequacy | Current owner |
| Collagen studied range | Collagen amount appropriateness | Dose | `collagen_profile.score_collagen_dose`; hard-coded 21/16/10/12/7/0 bands and 0.8/1.2 near-range bounds | Evidence observes preparation/literature applicability | Current owner |
| Melatonin and 5-HTP exposure | Sleep-support amount appropriateness | Dose | `sleep_support.score_sleep_support_dose`; hard-coded `_melatonin_score` and `_five_htp_sleep_score` | Evidence assesses clinical strength | Current owner |
| Joint-active exposure | Joint-support amount appropriateness | Dose | `joint_support.score_joint_support_dose`; `quality_score.json::category_magnitudes.joint_support.target_dose_mg`; hard-coded 20/22 outcomes | Evidence has a separate strength cap | Current owner |
| Immune-active exposure and high-dose design | Immune-support amount appropriateness | Dose | `immune_support.score_immune_support_dose`; `quality_score.json::category_magnitudes.immune_support.dose_*` | Formulation observes botanical-stack complexity | Current owner |
| Multi/prenatal RDA/AI coverage, breadth and critical nutrients | Panel amount adequacy | Dose | `multi_prenatal_dose.score_dose`; `quality_score.json::dose_magnitudes.multi_prenatal.*`; hard-coded coverage curves | Evidence owns nutritional-authority judgment | Current owner |
| B-vitamin RDA/UL fit | B-complex amount adequacy | Dose | `b_complex.score_b_complex`; hard-coded `_dose_fit`; `quality_score.json::category_magnitudes.b_complex.dose_cap` | Evidence owns authority | Current owner |
| Probiotic per-strain and aggregate CFU | Potency adequacy and assessability | Dose | `probiotic_dose.score_dose`; `quality_score.json::dose_magnitudes.probiotic.*` | Transparency assesses whether allocation is disclosed | **DRAFT POLICY**: Phase 1 transfer |
| Explicit EPA+DHA exposure | Omega amount adequacy | Dose | `omega_dose.score_dose`; `quality_score.json::dose_magnitudes.omega.cap_dose`; `omega_rubric.json::dose` | Evidence may use identity/purpose, not amount adequacy | **DRAFT POLICY**: Phase 1 transfer |
| Sports-active exposure | Sports amount adequacy | Dose | `sports_dose.score_dose`; hard-coded sports bands/support/completeness; `quality_score.json::dose_magnitudes.sports.dimension_cap` | Evidence owns research strength | Current owner |
| Fiber grams/day and fiber type | Fiber amount adequacy | Dose | `fiber_digestive_dose.score_dose`; hard-coded `_fiber_effective_dose_points` and `_fiber_type_bonus`; `quality_score.json::dose_magnitudes.fiber_digestive.dimension_cap` | Formulation may assess source quality | Current owner |
| Study design and evidence level | Human-evidence strength | Evidence | `generic_evidence._entry_raw_points`; hard-coded `STUDY_TYPE_BASE_POINTS` and `EVIDENCE_LEVEL_MULTIPLIERS` | Dose owns amount adequacy | Current owner |
| Effect direction, enrollment, per-ingredient cap, top-N and depth | Evidence aggregation | Evidence | `generic_evidence.score_evidence`; `quality_score.json::evidence_magnitudes.generic.*` | Other pillars may consume final assessment state | Current owner |
| Primary/branded/authority Evidence floors | Focused-ingredient or nutritional-authority Evidence | Evidence | `generic_evidence._primary_mass_floor`, `_mass_dominant_essential_canonical`; `quality_score.json::evidence_magnitudes.generic.primary_*/nutrition_authority_floor` | Role selection must come from `classify_ingredient_roles`; Dose owns amount | **DRAFT POLICY**: Phase 1/2 |
| Immune and joint route Evidence ceilings | Route-specific Evidence ceiling | Evidence | `immune_support_evidence_cap`, `joint_support_evidence_cap`; `quality_score.json::category_magnitudes.*.evidence_cap` | Dose remains independent | Current owner |
| Probiotic strain studies | Strain-specific human-evidence strength | Evidence | `probiotic_evidence._score_native_clinical_strain_evidence`; `quality_score.json::evidence_magnitudes.probiotic.*` | Dose owns CFU/trial amount | **DRAFT POLICY**: remove amount component only with transfer |
| Omega-purpose studies | Applicable EPA/DHA literature/purpose | Evidence | `omega_evidence.score_evidence` via resolver; `quality_score.json::evidence_magnitudes.omega.purpose_standards` | Dose owns EPA+DHA exposure | **DRAFT POLICY**: Phase 1 transfer |
| Multi/prenatal nutritional authority | Nutrient-panel Evidence | Evidence | `multi_prenatal_evidence.score_evidence`; `quality_score.json::evidence_magnitudes.multi_prenatal.*` | Dose owns panel adequacy | Current owner |
| Identity and individual amount disclosure | Label transparency | Transparency | Route `score_transparency` functions; `quality_score.json::transparency_magnitudes.*` | Dose may mark an amount unassessable without adding a disclosure penalty | Current owner |
| False allergen-free claim | Label-integrity deduction | Transparency | `generic_transparency._score_b2_false_allergen_claim_penalty`; `quality_score.json::transparency_magnitudes.generic.b2_*` | Safety may display allergen facts | Current owner |
| Proprietary-blend opacity | Disclosure deduction | Transparency | `generic_transparency._score_b5_proprietary_blend_penalty`; `quality_score.json::transparency_magnitudes.generic.b5_*` | Dose observes unavailable member amounts | **DRAFT POLICY**: overlap below |
| Disease/marketing claims | Label-integrity deduction | Transparency | `generic_transparency._score_b6_disease_claim_penalty`; `quality_score.json::transparency_magnitudes.generic.b6_disease_claim_penalty` | Evidence must not infer support from claims | Current owner |
| Probiotic strain identity and CFU disclosure | Probiotic transparency | Transparency | `probiotic_transparency.score_transparency`; `quality_score.json::transparency_magnitudes.probiotic.*` | Dose owns potency | Current owner |
| Multi/prenatal panel identity and amount disclosure | Panel transparency | Transparency | `multi_prenatal_transparency.score_transparency`; `quality_score.json::transparency_magnitudes.multi_prenatal.*` | Dose owns adequacy | Current owner |
| Omega identity/source/form disclosure | Omega transparency | Transparency | `omega_transparency.score_transparency`; `quality_score.json::transparency_magnitudes.omega.cap_transparency`; omega-rubric disclosure components | Formulation and Dose consume canonical facts | Current owner |
| Unknown verification data | Neutral fail-open score | Verification | `quality_score._pillar_verification`; `quality_score.json::verification_subscale.neutral_baseline` | No other pillar scores absence of verification | Current owner |
| Certification, audited GMP, own testing, COA/batch and reputation | Verification tier | Verification | `quality_score._pillar_verification`; `quality_score.json::verification_subscale.*`; upstream `verification_magnitudes.*` | Formulation's sustainability certification has zero points | Current owner |
| Non-critical quality-system violation | Verification deduction | Verification | `quality_score._manuf_violation_split` -> `_pillar_verification`; magnitude from `generic_manufacturer.score_manufacturer_violations` | Safety handles only Class I/critical recall | Current owner |
| Banned/recalled/watchlisted ingredient | Product safety base | Safety/Hygiene | `safety_hygiene.score_safety_hygiene_base`; public assembly in `quality_score._pillar_safety_hygiene` | Gate owns verdict precedence | Current owner |
| Critical/Class I recall | Safety deduction | Safety/Hygiene | `quality_score._manuf_violation_split` -> `_pillar_safety_hygiene` | Verification must not also deduct | Current owner |
| Restricted clean-label material | Graduated preference deduction | Safety/Hygiene | `quality_score._clean_label_penalty`; `quality_score.json::clean_label_subscale.*`; source magnitude from `clean_label_policy.json` | Formulation B1 may describe a related fact | **DRAFT POLICY**: overlap census needed |
| Additive/sweetener safety visibility | Capped second judgment | Safety/Hygiene | `quality_score._formulation_additive_safety_penalty`; `quality_score.json::safety_hygiene_subscale.additive_or_sweetener_max_penalty` | Formulation remains primary quality owner | **DRAFT POLICY**: Phase 5 ratification |
| Material dose-safety visibility | Capped second judgment | Safety/Hygiene | `quality_score._dose_safety_penalty`; `quality_score.json::safety_hygiene_subscale.over_ul_max_penalty` | Dose remains primary appropriateness/risk owner | **DRAFT POLICY**: Phase 4/5 ratification |
| Raw route dimension to public pillar maximum | Pillar normalization | Respective pillar | `quality_score._pillar_formulation`, `_pillar_dose`, `_pillar_evidence`, `_pillar_from_dim`; `quality_score.json::pillars.*.weight` and subscale references | No consumer may renormalize | Current owner |
| Six pillars to public score and tier | Literal sum, shipped rounding and tier | Public score | `quality_score.assemble_quality_score`, `shipped_whole_score`, `_tier`; `quality_score.json::tiers` | Export and Flutter consume only | Current owner |

## Overlap findings

### 1. Evidence amount judgments overlap Dose — confirmed

- Generic Evidence rejects a match below `min_clinical_dose` in
  `generic_evidence.score_evidence` and uses amount in `_primary_mass_floor`.
- Probiotic Evidence was separated from CFU adequacy by the integrated redesign; its current family/applicability/replication components are amount-independent. The old eight-point dose-applicability description is superseded.
- Omega Evidence selects/graduates purpose standards using EPA+DHA or DHA exposure.

The generic and omega amount gates remain live. Their removal is blocked by the transfer invariant documented in
`../evidence_dose_transfer_20260930/`: Dose must own an equivalent assessment in the same change,
and replacement magnitudes remain unapproved.

### 2. Proprietary-blend nondisclosure — partial consolidation

Missing individual amounts can both lower a positive disclosure component and incur B5 inside
Transparency. Probiotic consolidates pure strain-allocation opacity. Multi/prenatal caps B5 when
the panel is sufficiently disclosed and only adjunct blends remain. Generic, omega and mixed blends
can retain both effects. Dose's inability to assess an undisclosed member amount is a distinct
amount judgment, but copy and numerical ownership must keep it separate from disclosure punishment.

### 3. Certification — no current cross-pillar numerical duplicate found

Public certification credit is assembled in Verification. Omega sustainability certification is
retained as metadata with zero Formulation points. `_pillar_verification` also suppresses mid-tier
reputation when it derives from certification or audited GMP.

### 4. Fiber detox/laxative — confirmed same-pillar double effects

- A name containing `cleanse` or `detox` reduces practicality from 2 to 0.5 and also adds
  `fiber_cleanse_detox_penalty = -3`.
- A stimulant laxative reduces focus, commonly from 5 to 1, and also adds
  `fiber_stimulant_laxative_penalty = -8`.

Each source fact changes Formulation twice. Phase 5 must either justify two distinct judgments or
consolidate each signal under one magnitude.

### 5. Additive/sugar and UL mirrors — explicit cross-pillar second judgments

The penalty registry declares B1 as Formulation-owned and B7 as Dose-owned, then public Safety
applies separately capped deductions of four and three points. Code describes these as Safety
truthfulness/visibility judgments. They still require an explicit Phase 5 row-level rationale because
the same underlying fact moves two pillars.

### 6. Clean-label policy versus B1 — possible overlap

A restricted additive can appear in `clean_label_flags_v4` and the B1 harmful-additive ledger. A
product-level census is required before calibration to separate distinct policy facts from a duplicate
charge.

### 7. Role/prominence — planned owner correction

Generic Evidence floors still select a mass-dominant ingredient independently. That conflicts with
the intended `classify_ingredient_roles` prominence seam and remains a Phase 2 defect, not a policy
ratification in this draft.

## Numerical-source placement finding

`quality_score.json` owns the public weights and many magnitudes, but it is not the only live policy
source. The final Phase 5 artifact must continue to name exact production symbols because live numbers
also reside in:

- `scripts/data/omega_rubric.json`;
- RDA/UL and therapeutic-dose data;
- hard-coded sports, fiber, sleep, B-complex, botanical, collagen, multi/prenatal, joint and Evidence
  tables.

This inventory does not propose moving those numbers. Moving them would be a separate owner/complexity
decision and is unnecessary for completing the overlap audit.

## Provenance and commands

Baseline inspected: `7cf7100d22276e430981333b275a36718475bc2c` on
`codex/quality-completion`.

```bash
git status --short --branch
git rev-parse HEAD
rg -n 'class_for_product|score_(generic|probiotic|omega|multi_prenatal|b_complex|sports|fiber_digestive)' scripts/score_supplements_v4.py
rg -n 'quality_pillars_v4|def _pillar_|assemble_quality_score' scripts/scoring_v4/quality_score.py
rg -n 'FORMULA_QUALITY_MIRROR|DOSE_LIMIT_MIRROR|mirrored_penalty_magnitude' scripts/scoring_v4
rg -n 'detox|laxat|fiber' scripts/scoring_v4/modules
rg -n 'certif|B4|b4a|verification' scripts/scoring_v4/modules scripts/scoring_v4/quality_score.py
rg -n 'return [0-9]|>= [0-9]|> [0-9]|<= [0-9]|< [0-9]' scripts/scoring_v4/modules/*.py
python3 scripts/audit_dead_code.py keys
```

No test was required for this documentation-only, read-only inventory. Before any scoring rule changes,
the master acceptance sequence remains: failing production-boundary regression, owner fix, focused
tests, frozen-raw replay with unaffected controls, fast checkpoint and independent review.


## October 1 current-owner clarification

The table above remains a historical draft at its named SHA; it is not current
calibration approval. Q47 has since closed the probiotic Evidence transfer through
`probiotic_evidence::score_evidence`: family certainty /10, identity/purpose
applicability /6 and independent same-condition replication /4. CFU/trial amount
is Dose-owned; `_score_native_clinical_strain_evidence` above is historical.

| Fact | Judgment | Pillar | Numerical owner | Other pillars allowed to observe but not deduct |
|---|---|---|---|---|
| Reviewed probiotic study family | Certainty, identity/purpose applicability, independent same-condition confirmation | Evidence | `probiotic_evidence::score_evidence`, `_strongest_single_family_certainty`; `quality_score.json::evidence_magnitudes.probiotic` | Dose consumes study amounts; no Evidence amount deduction |
| Label CFU count and its own warranty timing | Potency confidence adjustment, unchanged expiry1.0/manufacture0.9/unknown0.85 | Dose | `probiotic_dose::_cfu_guarantee_adjustment`, applied by `score_dose`; enrichment owns count/warranty facts | Other pillars may display the canonical fact; no duplicate warranty-timing deduction |

The CFU source-binding correction changes the facts supplied to the existing
numerical owner, not these magnitudes. The complete numerical inventory still
requires refresh after D26 and policy approval; this amendment does not ratify
other draft rows or establish final calibration.


## October 2 current remaining calibration boundary

Whole clinical/Dose decision preparation is now in the existing transfer packet and research register. The former serial source tasks are completed as a combined bounded batch. This table remains a draft numerical audit, not approved calibration.

| Fact | Judgment | Pillar | Existing numerical owner | Other pillars / boundary |
|---|---|---|---|---|
| Acetylated ALCAR preparation | Applicable-reference identity | Dose | `RDAULCalculator::_form_scoped_reference`; candidate1d62acbb excludes the parent L-carnitine reference | Evidence retains existing clinical gate until equivalent approved Dose transfer; no new amount or benchmark |
| Native trial family | Awarded source provenance | Evidence | `probiotic_evidence::score_evidence`, existing eligibility and strongest-family selector | Shared identity/Dose assessment inventories research without asserting awarded citations |
| Detox/cleanse title | Practicality component and separate fixed penalty | Formulation | `fiber_digestive_formulation::_practicality` plus `fiber_digestive_formulation::_fiber_penalties` | Live overlap:2→0.5 component plus−3 penalty; choose one approved judgment owner/magnitude before removal |
| Stimulant laxative | Focus component and separate fixed penalty | Formulation | `fiber_digestive_formulation::_fiber_focus` plus `fiber_digestive_formulation::_fiber_penalties` | Live overlap:5→1 component plus−8 penalty; Safety risk is a distinct judgment, not an automatic duplicate |

The original per-product receipt for35Q3 historical POOR→SAFE aliases has not been located in the current audit directories; the aggregate receipt is insufficient. Those were legacy quality-threshold crossings, not improved safety. Retain the individual inspection gate and make any reconstructed measurement identify exact source/input provenance. Do not substitute current-input movements for the original35. No calibration/full-rule audit or release checkbox closes from this packet.
