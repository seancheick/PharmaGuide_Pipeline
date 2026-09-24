# v4.1 recovery: reconciliation of the purpose-quality redesign

Status 2026-09-24. The parallel `purpose_quality` scorer is frozen and archived
at tag `archive/purpose-quality-redesign-2026-09-24` (branch
`codex/product-quality-redesign`, 129 commits past `main` 0b7bf3f7, local only).
This branch (`v41-recovery`, from `origin/main` 0b7bf3f7) is the one active
recovery branch. The target is the existing v4 architecture plus verified
correctness fixes plus controlled recalibration inside the existing v4 modules.

Porting is by change, not by commit: many redesign commits mix a correctness fix
with new scoring policy. "Prod" means the change alters live v4 output (scores,
verdicts, warnings or blobs) and needs a frozen-corpus replay before merge.

**Rule (2026-09-24):** keep facts and correctness fixes after independent
validation; simulate and review scoring-policy changes before adoption; retire
duplicate architecture. Items that mix a factual correction with clinical or
calibration policy are split: the factual part is ported (A), the policy part
is held (P, clinical/safety review; C, shadow calibration).

**Validation standard for every port:** reproduce the defect on current main
with the real raw label, port the smallest change to its canonical owner, add a
focused regression, measure the affected real corpus, and state in the commit:
reproduced defect, canonical owner, real-product validation, affected-product
count, and whether it changes scores, safety verdicts or display only. A green
synthetic test alone is not validation.

**Recalibration gate:** no recalibrated Formulation, Dose, Evidence,
Transparency or penalty formula enters production v4 until a read-only
candidate evaluator (same frozen v4 facts, no change to the scorer, export or
Flutter contract) has compared current v4 with at least two candidates on
reference ordering and full frozen-corpus effects, and Sean has reviewed the
report. Verification is excluded from recalibration (audit only attribution,
recency, scope and stacking).

## A. Correctness fixes to port into v4

| # | Change | Owning files | Redesign commits | Tests | Prod |
|---|---|---|---|---|---|
| A1 | IQM alias corrections: generic names move to the parent's unspecified form (B12, vitamin D x2, vitamin C, thiamine, B6, niacin, trace minerals, mixture/anion/legacy/class names); Magnesium Biotinate is not d-biotin; anhydrous creatine is not monohydrate | `data/ingredient_quality_map.json` | 38285b53 a4322b7b ac9adb66 ced7e264 4f227907 7f6f9bba 6d4d6bfe 6528eed1 d57c750c 185d6585 fcb2e0ec | test_ingredient_matching_regression, test_creatine_integrity | yes: bio_score of affected rows |
| A2 | Cleaner: a literal form name outranks generated variants (generic creatine aliases stay unspecified) | `enhanced_normalizer.py` (register_form) | da20b9ef | test_cleaner_exact_form_precedence | yes |
| A3 | Moved to P1-P3 (UL selection and scope are clinical policy) | `data/rda_optimal_uls.json` | baa0981b 6d40da3c f78a7de6 a4e6efe8 | test_vitamin_b6_efsa_ul, test_vitamin_e_ul_scope | yes: B6 CAUTION on ~215 products (measured on the redesign) |
| A4 | Factual part only: possible-presence subjects for generic carotenoid wording, and the label-declared share of a mixed vitamin A row (identity and attribution). The warning rules and thresholds are P4 | `data/ingredient_interaction_rules.json`, `data/clinical_risk_taxonomy.json`, `identity/interaction.py`, `enrich_supplements_v3.py` (possible presence, form-scope share), `data/views/by_condition/*` | 92f3c297 f49d8118 ea2e5953 7fc94b0e e609fb40 | test_beta_carotene_lung_cancer_rule | yes: new warnings. Engineering review only; clinician approval pending |
| A5 | Profile gate: a form exclusion holds only when every declared form is excluded (mixed vitamin A rows) | `profile_gate_evaluator.py`, `data/profile_gate_test_cases.json`, enricher `_interaction_rule_applies` | 2578adb3 | test_profile_gate_* | yes (app side already shipped: PharmaGuide ai 908c4bc) |
| A6 | Label unit corrections: 299069, 228355, 311646 | `data/curated_overrides/product_label_corrections.json` | 21ebd0db 5b7d9694 (311646 part) | test_product_label_corrections | yes |
| A7 | Enricher form matching: label synonyms of one form key are not a dual form; unresolved declared forms kept as provenance; culture sources and DSLD placeholders are not forms; one source-descriptor predicate | `enrich_supplements_v3.py` | 18c33bb8 5c5b2ed4 d5671bfd | test_quality_declared_forms, test_enrich_* | yes (dual-form flag, bio_score averaging) |
| A8 | Curated context override survives enrichment (259304/259306 barley grass) | `enrich_supplements_v3.py` | 514602bf | test_context_canonical_overrides_2026_05_24 | yes |
| A9 | Units: one owner for activity units (mcg DFE, mg NE, mcg RAE) and analyte mass (mg alpha-tocopherol); mixed natural+synthetic vitamin E is a medium-confidence upper bound | `normalization.py`, `unit_converter.py`, enricher `_normalize_threshold_unit` | ffe6315a a8b08b11 aa7f5d3c 732dc573 | test_quality_exposure_identity (unit parts) | yes (threshold units) |
| A10 | Daily exposure: fiber and sports (creatine, beta-alanine, HMB) Dose multiply per-serving amounts by the directed daily frequency; caffeine is per use. The missing/defaulted-frequency behavior is P6 | `serving_frequency.py`, `scoring_v4/modules/fiber_digestive_dose.py`, `fiber_digestive_helpers.py`, `sports_dose.py` (+ B2 exposure provider) | 38406274 96812fba 7e334ccb 5967d7fb | test_quality_dose_path_parity, test_v4_fiber_digestive_module, test_v4_sports_* | yes: the plan's "Task 2 live-path change"; needs its own replay |
| A11 | Moved to P5 (conversion policy for an unnamed form) | `scoring_v4/exposure.py` | 58caff1e | test_quality_exposure_identity | yes once v4 Dose reads B2 |
| A12 | Routing: partially hydrolyzed guar gum is fiber; prominent non-digestive claims keep a product off the fiber route | `scoring_v4/route_features.py`, `scoring_input_contract.py` (_route_fiber_digestive_decision), `enhanced_normalizer.py` (fiber source provenance) | 38406274 | test_phgg_formulation_identity, test_route_* | yes: route changes |
| A13 | EPA+DHA amount has one owner: separate vs combined rows never double-count; carrier oil mass is never EPA+DHA; qualified or repeated rows are unknown | `scoring_input_contract.py` (epa_dha_label_amount_mg) | b6f1d3ae 5b7d9694 | test_quality_omega_supply (amount parts) | yes when v4 omega Dose reads it |
| A14 | Moved to P7 (which population's UL applies is clinical policy) | `label_audience.py` (new), enricher `_safety_at_strictest_audience_age` | 10945a2d | test_audience_specific_ul | yes in principle; 0 verdict changes on 3,166 rows today |
| A15 | Dose-disclosure status has one owner (blend nondisclosure vs missing capture) for the blob and scoring | `scoring_input_contract.py` (dose_disclosure_status), `build_final_db.py` | 7fc94b0e 900547fe | test_dose_disclosure_status | yes: blob display labels |
| A16 | Verification readiness pairs state and readiness exactly (no "verified absent" on incomplete readiness) | `assessment_readiness.py` | 93b95dcb | test_assessment_readiness | check on replay |
| A17 | Flutter projection generator reads the manifest's app_core columns | `generate_flutter_core_projection.py` | 26865c63 (fix part) | test_core_export_model | no (tooling) |

## P. Held for clinical/safety policy review (factual parts ported separately)

| # | Policy | Owning files | Commits | Record needed before adoption |
|---|---|---|---|---|
| P1 | Adopt EFSA 2023 vitamin B6 adult UL (12 mg/day) over the US 100 mg/day | `data/rda_optimal_uls.json` | baa0981b 6d40da3c | source receipt, population, exposure basis, approval; measured ~215 new CAUTION verdicts on the redesign |
| P2 | B6 UL applies to every vitamer (pyridoxine, pyridoxal, pyridoxamine, phosphates) | `data/rda_optimal_uls.json` | f78a7de6 | same |
| P3 | Vitamin E UL covers all supplemental alpha-tocopherol, natural and synthetic | `data/rda_optimal_uls.json` | a4e6efe8 | same |
| P4 | Beta-carotene lung-cancer warnings (current/former smokers, asbestos exposure), thresholds and severities | `data/ingredient_interaction_rules.json`, `data/clinical_risk_taxonomy.json`, views | 92f3c297 f49d8118 ea2e5953 7fc94b0e e609fb40 | clinician approval (engineering review only so far) |
| P5 | Vitamin E IU with no named form bounded by the synthetic and natural factors | `scoring_v4/exposure.py` | 58caff1e | conversion policy review |
| P6 | Missing or defaulted daily frequency fails closed (Dose pending) | `serving_frequency.py` | 38406274 | calibration: affected counts and pending rate by route |
| P7 | UL taken at the strictest age among the printed audience | `label_audience.py`, enricher | 10945a2d | clinical policy review (0 verdict changes on 3,166 rows today) |
| P8 | New probiotic study contexts and the 299v outcome split | `data/clinically_relevant_strains.json` | b6f1d3ae 5b7d9694 | clinical review of each context; see C7/C8 |

## B. Reusable infrastructure to port

| # | Item | Owning files | Commits | Prod |
|---|---|---|---|---|
| B1 | Frozen-corpus replay, snapshot/compare and resumable regeneration tooling; reference cases | `audits/quality_redesign/replay.py`, `regenerate.py`, `reference_cases.json`, BASELINE.md | e102ab36 10945a2d | no |
| B2 | Shared exposure object (per-serving, daily min/max, basis, unit, source path, fail-closed reason) | `scoring_v4/exposure.py` | 38406274 96812fba b01be06c efdf3d57 ffe6315a aa7f5d3c | via A10/A11 |
| B3 | Explicit incomplete-assessment facts in the safety gate (resolver failures, capture gaps) without changing verdicts; inactive resolver surfaces initialization errors | `scoring_v4/gate_safety.py`, `inactive_ingredient_resolver.py` | 155643d1 | no |
| B4 | Per-nutrient UL attribution and certified-amount checks (`nutrient_ul_state`, `nutrient_amount_confirmed`, printed %DV check) for per-slot excess handling | `scoring_v4/dose_safety.py`, `scoring_input_contract.py`, `data/daily_values.json` | 74767ca5 995f8118 f773c37f 58df259b 00a2d59e aa7f5d3c | no until step 8 |
| B5 | Enrichment systemic-failure guard; shadowed-definition guard | `enrich_supplements_v3.py`, test_no_shadowed_definitions | bffbcee4 | no |
| B6 | Probiotic review attribution (clinician vs owner from the stored receipt) | `probiotic_measurements.py` | b6f1d3ae | no |
| B7 | Label administration route owner (oral/sublingual/nonoral from every direction; statutory and meal-timing cues) as lightweight purpose metadata | `label_administration.py` | 87fc0db5 62c3a670 35daac17 dc917058 | no until used |
| B8 | Multivitamin purpose signal (basic/prenatal/child/specialized) as routing and comparison metadata | `data/multivitamin_purpose_terms.json`, `scoring_input_contract.py` (multivitamin_purpose) | ea2e5953 | no until used |
| B9 | Daily-use direction state (daily vs contingent loading/workout directions) | `serving_frequency.py` | 2a9bac52 | no until used |

## C. Scoring policies requiring separate calibration (not ported as-is)

| # | Policy | Where it lived | Status |
|---|---|---|---|
| C1 | Parent-relative IQM denominator (bio_score / parent reference) and IQM reference-eligibility flags | `form_quality_facts.py`, IQM `formulation_reference_eligible` | Not ported. Needs a reviewed, authored `formulation_reference_score` per parent, never a dynamic maximum |
| C2 | Activity-equivalence sets (vitamin E, folate, vitamin A) | IQM `formulation_activity_equivalence` | Not ported; revisit with C1 |
| C3 | Audience-specific Dose benchmarks (highest RDA/AI among printed-audience cells) | `scoring_v4/benchmark_population.py` | Candidate for v4 Dose; needs replay and review |
| C4 | UL excess treatment (cliff vs graduated bands, per-slot before aggregation) | `dose_policy.py`, `panel_assessment.py` | Step 8 comparison |
| C5 | Evidence tiers 20/15/10/0/pending; single-strain fairness; omega floors | `strain_purpose.py`, `omega_purpose.py`, `purpose_assessment.py` | Step 9, inside existing v4 modules |
| C6 | Transparency 15/15 for full factual disclosure; one deduction owner per fact | `purpose_assessment.py` (shared criteria) | Step 10 |
| C7 | 299v outcome split (abdominal pain frequency primary, severity secondary) in the strain registry | `data/clinically_relevant_strains.json` | Owner-approved data correction; moves live v4 Evidence (archetype 87.1 -> 93.1). Port with A-items only after the probiotic replay |
| C8 | LGG IBS and 299v context arms added to the registry | `data/clinically_relevant_strains.json` | Registry data; port with C7 |
| C9 | Proposed IQM bio_score corrections (B12, vitamin C, calcium, folate, thiamine) | IQM | Awaiting team approval (review page 2026-09-24); never tuned for score recovery |

## D. Duplicate architecture to retire (not ported)

- Public assembler and generation: `scoring_v4/purpose_quality_assessment.py`, `scored_artifact._apply_purpose_generation`, `score_supplements_v4` hook, `config_registry` purpose_quality entry.
- Duplicated criterion engine: `scoring_v4/criteria.py`, `purpose_assessment.py`, `dose_policy.py`, `panel_assessment.py`, `purpose.py`, `strain_purpose.py`, `omega_purpose.py`.
- Rule registry: `scoring_v4/config/purpose_quality.json` (27 rules, 5 panels, 6 strain purposes, 1 omega purpose), its schema and validator.
- Per-rule form points (79 entries) and the frozen form-quality fields (`form_quality.py`, `form_quality_facts.py`, enricher `formulation_*` fields): v4 already reads the enriched `bio_score` and caps provisional parents.
- Replacement probiotic-purpose coverage (6 purposes) competing with the 132-strain registry.
- Export schema 2.6.0 generation columns, gates and percentile keying (`build_final_db`, `core_export_model`, `export_schema`, `audit_contract_sync` keys) and the Flutter purpose-quality plan.

## Port order on this branch

1. Done: A1 A2 A7 A8 A9 A6. Then the targeted-brand main-vs-v41 replay for them.
2. A4 (factual part) and A5 (profile gate: every declared form counts).
3. B1 B2 B3 B5 (tooling, exposure object, incomplete facts, guards).
4. A10 (daily multiplication; not the P6 missing-frequency policy), A12, A13, A15, A16, A17, each with its real-product validation, then one frozen-corpus replay against `main`.
5. P items go to clinical/safety review with their receipts; none is ported without approval.
6. Build the read-only candidate evaluator and the first calibration report (C items). Stop there for Sean's review.

## Ported so far (v41-recovery)

| Commit | Items | Validation |
|---|---|---|
| aba89280 47d17d4b 50323975 a455c655 e16c782e 0e55886b ddcb353e adb4d6ca 81139b24 9acff28e 13c47521 52c233a5 4e24ba05 097a65f0 9224cd21 | A1 A2 A7 | identity regression suite (158). Targeted replay main vs v41 on 3,018 real products (Nature Made, Centrum, Doctors Best, Kirkland, Nature's Bounty, Jarrow, Nature's Way; 0 errors): 490 products change an identity/form fact (253 vitamin D synonym rows no longer a false dual form; 229 generic 'Vitamin B12' rows now unspecified B12, not cyanocobalamin; 190 generic 'Niacin' rows now unspecified, not nicotinic acid). Scores change on 42 (mean -0.43; largest 236915 'Niacin 250 mg' -5.3 Formulation, verified form-less on the raw label). No verdict change from these items |
| f363f795 | A8 | the four reviewed overrides asserted on enriched rows; targeted replay: 259304 and 259306 barley grass 53.7 -> 55.6, POOR -> SAFE (the only verdict changes in the batch). The enricher hunk had been committed inside e7c98160 by a staging slip in a shared worktree |
| cdacec15 | A9 | focused unit tests plus 787 unit/threshold tests |
| 0374508d | A6 | real labels main -> v41: 299069 77.7 -> 78.5; 228355 unchanged; 311646 86.6 -> 74.6 (Dose 20 -> 8) |
| 8722ebc9 | A5 | 331488 and 12012 now carry the vitamin A pregnancy/TTC rule; 395 products gain it in the regenerated corpus; profile-gated warnings only |
| c9634ec0 | B5 | systemic-failure guard + no-shadowed-definitions test; no score path |
| c3ad0955 | B1 | replay/regenerate tooling and reference cases; tooling only |
| 7b031050 | B3 | safety gate records whether its ingredient assessment completed; fact fields only |
| e46897f5 | A10 A12 B2 | 5,289 labels (BulkSupplements, Legion, Nature's Way, Double Wood): 40 score changes (34 up, 6 down, mean +5.6). Daily exposure: 331143 inulin Dose 7.2 -> 16.0, 312819 HMB 3.5 -> 12.8. Honest fiber identity: 287495 Dose 12.0 -> 7.2 (label fiber 1 g x2, main summed carbohydrate + fiber + blend), SAFE -> POOR. 293400 SAFE -> POOR on Formulation -1.4: 'Oat Bran'/'Fiber (unspecified)' rows lack a fiber identity (mapping follow-up). The redesign's "qualified amount or unstated frequency zeroes Dose" was NOT ported (it flipped four cleanse kits); Dose benchmarks the stated amount, qualifier kept as provenance |
