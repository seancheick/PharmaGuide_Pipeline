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
| A4 | Factual part only: possible-presence subjects for generic carotenoid wording, and the label-declared share of a mixed vitamin A row (identity and attribution). The warning rules and thresholds are P4 | `data/ingredient_interaction_rules.json`, `data/clinical_risk_taxonomy.json`, `identity/interaction.py`, `enrich_supplements_v3.py` (possible presence, form-scope share), `data/views/by_condition/*` | 92f3c297 f49d8118 ea2e5953 7fc94b0e e609fb40 | test_beta_carotene_lung_cancer_rule | Not ported: the approved P4 (7ee85a26) needs neither fact. Generic carotenoid wording stays form-unknown (its amount cannot establish 15 mg, so no warning); mixed retinyl + beta-carotene rows are excluded by form_scope_match "all". The redesign thresholds carried here were never approved |
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
| P4 | Beta-carotene lung-cancer warnings (current/former smokers, asbestos exposure), thresholds and severities | `data/ingredient_interaction_rules.json`, `data/clinical_risk_taxonomy.json`, views | 92f3c297 f49d8118 ea2e5953 7fc94b0e e609fb40 | Ported 7ee85a26 (card consolidated a6222c7d) from the approved policy: Dr. Pham, PharmaGuide Clinical Team, 2026-09-21 (PHASE3_CLINICAL_POLICY_20260921.md section 5). The redesign's thresholds and severities (engineering review only) were not ported |
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
| 5c9996f4 | A10 A12 B2 B9 (fact only) | Production A/B on a 2,507-label affected cohort (35 brands, 7 routes): 159 score changes (128 up, 31 down, each decrease read against its label), 53 route changes (the 51 reviewed fiber -> generic + the 2 FiberSMART quarantines), 26 verdict changes (12 reviewed route, 12 POOR -> SAFE daily exposure, 2 FiberSMART), 0 safety changes. Oat Bran identity kept (UNII + literal; reviewed oat_generic > oat_bran). Unresolved quantity columns fail completeness. Creatine loading up to 20 g/day via has_loading_protocol. Min/max shadow reported, policy unchanged. Full receipt: quality_redesign/TASK2.md |
| de63b205 | tooling | A/B harness records route, eligibility, identity, exposure; comparator buckets; tooling only |
| da8a572b | data (/data-fix) | FiberSMART 233404/233406: resistant dextrin (GRN 1045), no equivalent canonical; label corrections make it the unmapped active, both NOT_SCORED; approved on the evidence (engineering review: Claude; independently verified: Codex) |

| 36d7ff82 | data | FiberSMART review provenance recorded (engineering review: Claude; independently verified: Codex) |
| 25decbf5 e8c6da11 | A13 + data | EPA+DHA reads one serving column: the cleaner's column merge now merges repeated nested blocks (224615 1,563 -> 1,042 mg; 206295, 219942); 77225 life'sDHA Oil is the algal source oil (label correction). Combined A13+A15 cohort, 1,432 labels: 22 score changes, 3 verdict (77225, 206295, 219942 SAFE -> POOR), 1 safety signal (69374 caffeine ELEVATED -> MODERATE, CAUTION kept) |
| 33ba3973 | A15 | quantity disclosure owner; enzyme activity units count as disclosed in Transparency (2505, 82372, 333715 up) |
| 2da82226 9aeb7fbc | A16 + data | verification state/readiness pairs agree; attribution audit of 871 matches found one wrong product (9080 iron vs the multivitamin-with-iron USP record); resolver guard + one override to the live-verified Iron 65 mg record |
| e44ceee8 | A17 | Flutter projection renders the manifest's app columns; output byte-identical for 2.4.0/2.5.0/3.0.0 |
| 7ee85a26 | P4 | beta-carotene lung-cancer warnings per Dr. Pham 2026-09-21 (under 15 mg none; 15 mg caution; 20 mg stronger caution; 20 mg unknown risk contextual card). Conditions current_smoker, former_smoker, asbestos_exposure (ICD-10-CM verified at NLM); PMIDs 8127329, 8602180, 23644932 verified at PubMed. Owner decisions 2026-09-24: both tiers caution with 20 mg tier copy; card without verdict change |
| 7db29838 f7b73abb a6222c7d | one-brain consolidation | EPA/DHA amounts, quantity disclosure and the P4 card each have one owner (contract provider; row-based disclosure owner; ADR v6 pure-dose threshold projected generically). Byte parity: disclosure outputs on every frozen row identical; 15,412-product re-score 0 differences; beta-carotene blob warnings identical on 11 real products |


## Integration comparison (A10-A17 + P4), 2026-09-24

Production A/B over every raw label, one sequential chain (drive_pipeline_ab + compare_scored_arms): before `origin/main` 0b7bf3f7, after `v41-recovery` 7ee85a26 (clean tree, unchanged during the run). 9 frozen submissions without raw labels replayed with replay.py on both checkouts.

| Measure | Result |
|---|---|
| Records compared | 15,412 (+ 9 submissions: 0 differences) |
| Score changes | 486 (149 up, 337 down) |
| Verdict changes | 34: 26 Task 2 (reviewed routes, daily exposure, 2 FiberSMART NOT_SCORED), 3 A13 omega, 2 A8 barley grass overrides (POOR -> SAFE), 3 generic "Niacin" labels with no printed form now B3 unspecified (27420, 315848, 30565 SAFE -> POOR) |
| Route / eligibility / quarantine entries | 53 / 2 / 2 (all Task 2) |
| Safety changes | 1 (69374, above) |
| Unexplained | 0 |

Score changes outside the two measured cohorts (159) are all Formulation form identity from the A1/A2/A7 ports (77 generic Niacin -> niacinamide, 49 -> B3 unspecified, 33 cyanocobalamin -> B12 unspecified, 4 niacinamide ascorbate, 2 MK-7 -> K2 unspecified, 1 5-MTHF -> B9 unspecified), 7 Nature Made Iron 65 mg (Verification 10 -> 15: the A16 guard leaves the correct USP record), 4 rows whose "Calcium Salt" / "Mixed Carotenoids" token no longer borrows a named form (328613, 232326, 65003, 293269). Receipts `~/pg_quality/integ_ab` (sha256 before 7753c741a4ec6b33, after 6f3c94dda08679e3, diff 7e489126ba2afe40, submissions 37517e5f3dc66819).

## Form association (15823), 2026-09-24

15823 lists "Cranberry powder" under Magnesium; the parent fallback followed the word "powder" to magnesium citrate (bio 14). The same seam let a nutrient's source or its own name take a form share at an invented 5.0. Fixed at the one owner of form shares (`enrich_supplements_v3._match_multi_form` and its parent fallback):

| Commit | Change |
|---|---|
| 08351e2d | Sources (botanical/protein under a vitamin, mineral, amino acid or enzyme parent), restated nutrient names and DSLD source descriptors leave the share denominator; named salts the IQM lacks still count. The fallback never selects above the parent's unknown form. |
| e00bcdc9 | IQM alias "vitamin a fish liver oil" (vitamin A from cod liver oil). |
| c20a80b5 | IQM alias "nigella sativa seed oil" (black seed oil). |
| follow-up | One owner of form quality in the fallback: `_effective_form_bio` (IQM bio_score with the provisional-review cap; the retired `score` is never read) and `_parent_unknown_form` (exact "(unspecified)" form, deterministic; vitamin D never resolves to D2 by file order). An unmatched share takes the parent's own unknown-form value instead of 5.0; `final_score` mirrors `final_bio_score`. |

Affected-cohort comparison, final tree: every product with an unresolved form token (1,758), re-enriched from raw and scored with HEAD 4cf582b1 and with the follow-up tree. 0 errors, 0 status changes, 666 score changes (647 up, 19 down; min -1.4, max +24.0, mean +0.42). The largest rise is 231940 "Pycnogenol ... Pine extract": the old default took the first form containing "generic" by file order, the row now resolves to the `pycnogenol` form its label names, and branded evidence applies (Evidence 0 -> 20). Decreases: unknown shares of parents with no unspecified form now take the lowest named form (chlorophyllin 5 -> 3; 168 IQM parents lack an unspecified entry). The four alias products (214477, 328082, 4341, 317111) no longer move. Receipts `~/pg_quality/calib`: before 18a9486e39dfb025, after 5edcba604c19ddad, comparison `report/form_association_cohort.json` ac806f8ff70575b6.

Remaining unresolved form tokens (4,891 on the frozen corpus, `report/form_strata.json`, heuristic strata): repeated names 1,314 and sources 1,048 are resolved by this fix; open for one-entry curation or review: real forms missing from the IQM 1,222 (calcium ascorbate, potassium carbonate, monobasic calcium phosphate), salts owned by another nutrient 313, cross-parent other 805 (includes mixed-tocopherol components), Latin restatements 134, markers 28, unclassified 27.

## IQM `score` / `natural` retired, 2026-09-25

IQM owns form quality through `bio_score` alone. The natural-bonus-inclusive `score` (883 of 1,444 forms differed from `bio_score`) and the `natural` flag were physically removed rather than guarded:

- Data: both keys removed from all 1,444 IQM forms (2,888 keys; every other value verified unchanged); IQM schema 5.5.7 -> 5.6.0; metadata notes corrected.
- Runtime: removed from enrichment payloads (form match, matched_forms, additional_forms, multi-form aggregate, unmapped placeholders `score: 9` / `score: 5`, the fallback audit's `fallback_score`), the enricher and export required-field contracts, `scoring_input_contract`'s form projection, `build_final_db`'s ingredient export, and `bio_score_of`'s fallback to `score`. The v3 `natural_source` bonus left `config/scoring_config.json`.
- Gates: `db_integrity_sanity_check` now errors on either field in an IQM form; `test_iqm_retired_fields` runs enrichment and scoring over real labels with guarded IQM forms and fails on any read, and checks rows, matched forms and the export.
- Tests: assertions of the retired invariant (`score == bio_score + 3 x natural`, `natural is False/True`) removed; value pins moved to `bio_score`. The unspecified peer-min floor is now stated on `bio_score` with the agreed rule (unspecified may sit exactly one below the lowest named form: curcumin 5 vs 6); it previously passed only because the natural bonus inflated the total.
- Flutter: no consumer of either ingredient field (only an RxNorm API `score`, unrelated); removed from the export gate's Flutter ingredient-key contract.
- Clinically meaningful natural/synthetic facts are untouched: they live in form identity (d-alpha vs dl-alpha tocopherol), label-token lists and natural-colour data.

Neutrality: scorer replay of all 15,412 frozen labels against the 30af5396 baseline, 0 records differ (snapshot 61d1aaf0f48782b4); the 1,758-product form cohort re-enriched from raw is identical to the a9801685 arm (0 differ, 5edcba604c19ddad). The removal is score-neutral; the placeholder `score: 9` on unmapped rows was dead (no scorable row carried it).

## Undisclosed forms have one owner, 2026-09-25

Audit finding (Codex, reproduced): for the 168 IQM parents with no authored unspecified form, the enricher fallback returned the lowest named form as if the label had named it (an undisclosed HMB form became HMB-Ca, acacia catechu became "wood and bark extract", chlorophyll became "natural chlorophyll"), with no deduction; the scoring contract's blend-anchor path held a second copy of the same choice (an undisclosed enzyme blend became "oxidized enzymes", bio 2).

- Owner: `scoring_reference_resolver.unknown_form_quality` (dependency-neutral; enrichment and `scoring_input_contract` both import it; their own fallback arithmetic is deleted). An authored unspecified form wins, chosen deterministically; otherwise `max(0, lowest named bio_score - 1)` with `form_id` None, so no named form's notes, absorption, evidence or identifiers attach (`matched_form` reads "unspecified", a placeholder the export already recognizes). `effective_form_bio` (provisional-review cap) moved with it and now also applies to the contract's alias matches.
- A named form IQM does not recognize and a disclosed form the pipeline lost are not routed through it; both stay curation or pipeline defects.
- Data (one entry each): aliases "n-acetyl-l-tyrosine" (GSRS DA8G610ZO5 Acetyl L-tyrosine) and "n-acetyl-l-cysteine"; the hyphenated label tokens missed their forms, and the provider change had turned 318107's error from D-tyrosine 2 into L-tyrosine 14 (NALT is 8). IQM `_metadata.scoring_system` lost `natural_bonus`/`total_score`, gained `unknown_form`, and a 5.6.0 schema entry; two form notes that said a natural bonus was earned were corrected; the v3 config, export schema doc and glossary no longer describe `score`/`natural` as current.
- Tests: `test_unknown_form_quality` (provider, enricher and contract fallbacks for HMB, L-leucine, acacia catechu and chlorophyll, no form copy in the export, NALT on the real 318107 label); the source-text export assertion replaced by detail blobs built from real labels; eight brown-rice-chelate asserts, five vacuous score-formula tests, two vacuous fish-oil ceilings (now on `bio_score`) and 159 fixture keys of the retired fields removed.

Affected cohort (`~/pg_quality/calib/uf_cohort.py`): 1,323 frozen products with a row under a derived parent reached at parent level or with unmatched form shares, or an IQM blend-header anchor; re-enriched from raw with c3afa98b and with the final tree. 0 errors, 0 status changes, 535 rows changed (400 same bio: an invented form no longer appears in matched_forms), 59 product scores moved (36 up, 23 down; -1.3 to +2.3, mean +0.48). Up: chlorophyllin no longer read as natural chlorophyll (3 -> 6), lycopene no longer "synthetic" from a Tomato token, flaxseed oil no longer "meal/powder", DIM no longer the different compound I3C, NALT no longer D-tyrosine, enzyme blends no longer "oxidized enzymes". Down: unknown shares take lowest - 1 (leucine with a Calcium Caseinate token 14 -> 13.5; green-lipped mussel with no form 7 -> 6), NALT labels previously read as L-tyrosine 14 now 8. Identity: 4 products (311881-311884, "Wild Cherry Fruit Extract" as Cerasus avium) lose the sweet-cherry identity the invented form carried and become recognized non-scorable fruit; the label is self-contradictory (wild cherry is Prunus serotina) and needs one-entry review. Receipts: before c2176b0f83e7edee, after 8283c24391cc670e, comparison `report/unknown_form_cohort.json` abc8acadcf7d261d.

## Form contract closeout, 2026-09-25

Codex audit of 56314f5c, reproduced before each change.

- Named forms IQM does not recognize (59086 "L-Glutamine Alpha-Ketoglutarate" shipped as L-glutamine powder 11): `_match_multi_form` no longer counts a token that only reached the parent default as generic. `_form_token_context` is the one classifier of what an unrecognized token is (restatement of the identity or of the row's own label words, a botanical in the row's DSLD group, a standardization marker, a preparation word, a DSLD placeholder, a source recorded in botanical_marker_contributions, a curated source term, or a carrier oil); anything else is unmapped. The row keeps its identity, gets no form quality, emits `form_match_status` 'unmapped' and reason `disclosed_form_unmapped`; the scoring contract raises a blocking finding and identity readiness holds the product. `FORM_UNMAPPED_FALLBACK`, `form_unmapped`, `unresolved_form_tokens` and the report-only audit classifier are gone (their source-descriptor knowledge moved into the classifier). IQM counter-ion forms ("dicalcium phosphate (as phosphorus source)", vitamin C's redirects) are read, not held.
- One form matcher: `scoring_input_contract._form_quality_from_iqm` removed; the enricher stamps its own reading on blend-anchor evidence (`_anchor_form_reading`); the export takes `form_match_status` from enrichment and no longer re-matches aliases; the minimum-effective-dose form gate reads it too. Related defects found and fixed: the combined-forms lookup matched the row's standard name, then (once fixed) could jump identity ("triglyceride" -> DHA) until anchored to the row's parent; parent defaults named "generic" were accepted as form readings (`_is_specific_form_match`); a form-less identity match was rejected as incoherent and the row lost its identity; unit conversion used the matched form as its only context (the beta-carotene smoker warning was suppressed until the identity became the context).
- Nondisclosure floor: `unknown_floor` on IQM forms (38 ineligible, reason per form) and reviewed overrides; value = lowest eligible named bio_score - 1; `db_integrity_sanity_check` rejects an incomplete override or an undocumented value above the floor. 152 authored unspecified values set to their floor; 15 kept as overrides citing their clinician or audit lock (mineral table, vitamin A family, species-only probiotic, batch-3/6/12/13 audits, creatine, vanadyl, capsaicin, ALCAR mirror). D-tyrosine (PubChem CID 71098, (2R)) stays a form but is `wrong_stereoisomer`; tyrosine's unknown is NALT 8 - 1 = 7. Frozen legacy-restore values superseded by the floor are exempted in the manifest check; 18 forms left the Excellent-evidence backlog (250 -> 232, 195 -> 177).
- Aliases (one entry each): 31 form-inventing parent-name aliases on 18 parents moved off named forms, `3-hydroxy-3-methylbutyric acid` to HMB free acid (PubChem 69362 vs Ca salt 9860341), BCAA "(standard)" renamed "(unspecified)", parent alias "Indian pomegranate" (already the reviewed registry name), reviewed crossing vitamin K -> K2 for menaquinones.

Comparison (`~/pg_quality/calib/c2_*`): 2,386 products (1,758 with unresolved form tokens, 1,323 unknown-form cohort, 35 canaries), re-enriched from raw, c521380b vs final tree, 0 errors. 1,132 newly held, all `disclosed_form_unmapped`, over 468 distinct tokens; curating the top 50 releases 493, the top 100 releases 718. Top tokens are real IQM gaps (calcium ascorbate 163, calcium D-pantothenate 159, monobasic K/Na/Ca phosphate ~150 each, sodium bicarbonate 116, potassium chloride 105, Crominex, chromium glutamate, nickel sulfate, OptiZinc, fermented chelates, "... Glycinate Amino Acid Chelate" wordings) plus co-disclosed components held under the literal rule (alpha/beta-tocopherol under mixed tocopherols, niacinamide under NR/NMN). Identity changes: vitamin K -> K2 (4, menaquinone labels), wild cherry -> sweet cherry (4, held), one K1+K2 mixture (328644) now takes K2 as its first matched child. Still-scored products: 275 moved (20 up, 255 down, -3.3 to +9.0), mostly unknown-floor values. Canaries: 241894 held (NMN as niacinamide), 298053 +1.4 (MK-4 now read), 3 within -1.3. Receipts: before bde5fdd6cc6105e1, after b10ac12aa3d43e1a, report `report/form_contract_closeout.json` 0f3f62d34f2ec5cf.

## Form states and the curation queue, 2026-09-25

Three Codex follow-ups on 83f75fe9, each reproduced first.

- Each label form state has one outcome. No form on the label: scored at the unspecified policy, not queued. A named IQM form: that form's bio_score. A named form IQM lacks: `unmapped`, held. An unknown active: the cleaner's unmapped-active output. A known excipient: the other-ingredients route. A disclosed form the row reading dropped: `lost` (finding `pipeline_form_loss`), held. `_dropped_label_forms` asks the one form classifier (`_match_multi_form`) about a scored `n/a` row's cleaner forms. Descriptors and IQM aliases to the unspecified form are not losses. A 559-product probe found 874 `n/a` rows with label forms: 482 descriptors, 216 dropped by design at form-info build, 62 non-scored rows, 3 disagreements. Regression: `test_form_disclosure_states.py`.
- The curation queue is `form_fallback_audit_report.json`, built from each product's final state (ingredient rows and product-evidence anchors; before, an anchor could hold a product without queuing it). It has one entry per (gap, parent, token), with held product IDs, brands, and example labels, ranked by held products. The match-time `unmapped_forms_tracker` had no consumer and is removed. The dashboard read flat `reports/*.json`, so it showed 2026-07-13 reports. It now reads the newest `reports/runs/<id>/`, renders the form queue and the parent-fallback table, and names datasets whose form report predates the contract.
- Typed relationships: the 38 `unknown_floor {eligible: false, reason}` marks became `parent_relationship` (same values; NALC's then removed, below), the one owner of floor eligibility and identity. A row matching a `wrong_stereoisomer` or `different_compound` form is held as `needs_identity_verification` with no bio_score, instead of inheriting the parent (D-tyrosine is not L-tyrosine; eleuthero is not Panax ginseng). Same-nutrient relationships (degradation product, analog, iron oxide) keep their own low score.
- N-acetyl-L-carnosine's `different_compound` mark (83f75fe9) contradicted the 2026-06-22 live-verified bioactive lock (a form under L-carnosine, PubChem 9903482, bio 6; `test_iqm_bioactives_batch_2026_06`). It is an ordinary form again (37 relationship marks remain). 'l-carnosine (unspecified)' is now 'l-carnosine (free form)': its aliases name the free dipeptide, a disclosed compound (as with L-glutamine). Plain L-carnosine keeps 9, and undisclosed carnosine derives NALC 6 - 1 = 5. The 11 carnosine products in the cohort are unchanged (status and score).
- Also fixed: the integrity checker ran the absorption, notes and dosage_importance checks only on each parent's last form (the floor check sat inside the loop). A powder or oil hint on a label with no form picked any form whose alias held the word ("Ginseng, Powder" became Siberian ginseng); a hinted form now counts only if the label states its other words. `l-glutamine hydrochloride` and `l-glutamine hcl` are no longer aliases of free L-glutamine: PubChem CID 57364844 (C5H11ClN2O3) vs 5961; no GSRS UNII; 0 corpus labels. The evidence-expansion audit read the retired `form_unmapped` field.
- `multi_prenatal_formulation.py` is unchanged from main: the dosage-importance-weighted panel, neutral floor, disclosure credit and 20-point normalization stay route-owned.

Comparison (`~/pg_quality/calib/c3_*`): the same 2,386 products, 83f75fe9 vs this tree, 0 errors, 0 score changes among still-scored products, 0 released, 10 newly held. Of those, 9 are eleuthero labels held as `needs_identity_verification` (41 eleuthero rows in all; most products were already held) and 1 is an omega-3 total held as `pipeline_form_loss`. 13 rows became `lost`: 12 CurcuWIN "Curcuminoids" (the classifier reads the 95%-curcuminoid form through the alias "curcuminoids"; CurcuWIN is a carrier formulation, so the alias is the defect) and "Eicosapentaenoic Acid" under an omega-3 total (a co-component; see the component decision below). No canary changed. Receipts: before b10ac12aa3d43e1a, after fd853ad0cc60656d, report `report/form_state_closeout.json` 1d21cfa4b331d297.

## Correction: back to the existing contract, 2026-09-25

Codex audit of a7065751 plus Sean's direction: enhance what exists, no new product states or fields, no second normalizer.

- `form_match_status` again has only mapped / unmapped / n/a. `lost`, `needs_identity_verification`, `lost_forms` and their contract findings and export mapping are removed. A disclosed form dropped by the row path, and an IQM form that is not the parent's identity, both read `unmapped` (existing hold). Why the row is held (`disclosed_form_unmapped`, `pipeline_form_loss`, `identity_mismatch`) is a curation-report reason only.
- A global punctuation and plural fold in the matcher was tried and reverted. It was a second normalizer beside `normalization.py`: "Flavonoid (mixture)" became the flavonoids parent, 57 citrus-bioflavonoid rows lost their identity, and 29 releases were unreviewed. 302644 is fixed by passing the generic omega-3 row's cleaner forms (they were dropped) plus the printed alias "omega-3 fatty acids ethyl ester" on the existing ethyl ester form.
- 179514: EPA under an omega-3 total is a component. The existing IQM parent field `relationships` records fish_oil `contains` epa, dha; the one form classifier (`_form_token_context`) reads a token naming a `contains` target as `component` (excluded from the reading, like a marker).
- Non-delivering forms (IQM form `parent_relationship` non_functional_analog / degradation_product / not_a_nutrient_source). One resolver helper, `delivers_parent_nutrient`; one row filter, `generic_helpers.nutrient_delivering_rows`. Formulation reads the form's own bio_score. Dose: the adequacy owner (`_collect_rda_ul_data`) leaves pct_rda empty, the UL check stands, and the no-reference fallback skips the row. Evidence: the study matcher skips the row, and generic evidence floors read delivering rows only. Iron oxide alone: Formulation 2.7, Dose 0, Evidence 0; with vitamin C, Dose and Evidence equal vitamin C alone. The generic A4 enhancer bonus (vitamin C + iron) still fires for iron oxide; A4 is already a Candidate C review item.
- Eleuthero: its IQM form now sits under siberian_ginseng, the id the standardized_botanicals identity owns (GSRS ZQH6VH092Z ELEUTHERO, CUI C1035215, RxNorm IN 1368902). CurcuWIN aliases sit on the existing curcumin CurcuWIN form. ALCAR arginate aliases are removed in favour of other_ingredients OI_ACETYL_L_CARNITINE_ARGINATE.

Comparison (`~/pg_quality/calib/c4_*`, the same 2,386 products, 83f75fe9 vs this tree): 0 errors, 0 newly held, 0 released, no canary change. Two scores moved: 212633 -0.9 and 182704 -0.5; their eleutheroside-standardized shares now take eleuthero's unknown value (6) instead of Panax ginseng's (8). 25 rows changed status. 12 L-carnosine rows are the renamed free form (same 9). 12 CurcuWIN rows now read curcumin CurcuWIN 8; their products stay held by unrelated calcium ascorbate / D-pantothenate forms. 326161's eleuthero, a 50 mg member of an adaptogen blend, is now recognized, not scored, as for the other dual-owned botanicals (its product was already held). Receipts: before b10ac12aa3d43e1a, after 2e5984c7049748cc, report `report/form_state_correction.json` c460ff8e6a505a63.

## Tracked follow-ups (from Task 2)

- Childless positive-quantity blend rows with no canonical: 2,961 rows on 1,873 frozen products (1,735 blend-named, 212 single-item-named). Measure per entry before any global rule; true opaque blends need separate handling. Census: `~/pg_quality/recon/childless_blend_census.txt`.
- Fiber identities in IQM category "fibers" not in the reviewed fiber set: `pgx_fiber`, `larch_arabinogalactan`, `mucilage` (one-entry review each).
- A reviewed resistant-dextrin identity (would un-quarantine 233404/233406).
- Directed-range adequacy (maximum vs minimum): shadow shows 77 of 3,704 labels differ; decision deferred to calibration.
- Verification: NSF Certified + NSF Sport stack as two certifications on 28 products; NSF pages read did not state that Certified for Sport includes NSF/ANSI 173.
- Disclosed forms IQM lacks are now held, not scored (see "Form contract closeout"). The curation queue is `form_fallback_audit_report.json` per brand; its size on the frozen corpus is recorded there.
- Cross-parent co-components (alpha-carotene under beta-carotene, alpha-tocopherol under mixed tocopherols, niacinamide under NMN) are held as unmapped under the literal rule. A component rule was not added: a naive one also re-admits salts such as glutamine alpha-ketoglutarate. Decide it explicitly.
- Bare-name aliases on specific forms: census `scripts/audits/v41_recovery/bare_alias_census.py` (312 aliases on 130 multi-form parents; 128 exact, 184 parent_like). 31 form-inventing aliases on 18 parents moved (HMB, L. acidophilus LA-14, flaxseed, bacopa, Sambucol, lycopene, white willow, MCT, evening primrose, flower pollen, magnolia, pea protein, Irish moss, PE, algae oil, olive fruit, CLA, policosanol); chemical-identity aliases (biotin -> d-biotin, L-amino acids, K1 -> phylloquinone) stay. The rest are listed by corpus impact for one-entry review.
- Named salts on unspecified forms (`unspecified_named_alias_census.py`): 88 aliases on 29 parents name a salt or chelate but score as nondisclosure. Some are deliberate: an ambiguous oxidation state ("iron sulfate"), or a compound sold as one salt (DMG HCl, yohimbine HCl). Others are curation gaps: manganese carbonate/fumarate/lactate/orotate at the floor 3; chromium citrate/aspartate/ascorbate; "selenite" beside sodium selenite 8; "Tocopheryl Acetate" beside a named acetate form. Review one entry at a time.
- Eleuthero is filed as a form of Panax ginseng, but `botanical_ingredients.json` and `standardized_botanicals.json` already own it. Moving it is one `/data-fix` entry and releases its held products.
- "(standard)" census (`unspecified_census.py --standard`): 11 forms end in "(standard)" (A); 20 carry "standard" in parents with no authored unspecified form (B). Only BCAA meant unspecified (its notes say so) and was renamed; the others are single-form identities or real plain forms.
- 69374 prints "1-3 scoops" while DSLD records at most 2 daily servings (P6 frequency policy, held).
- The personalized P4 tiers reach users after the app's reference-data sync (taxonomy 5.4.0) at release.

## Architecture ownership fixes (2026-09-24)

Detached from `v41-recovery` `4cf582b1`. Not a scoring-policy change. Integrated 2026-09-25 by cherry-pick onto `56314f5c` as `4233181d` (cert) and `40efe44d` (UL), no conflicts: fast suite 16,259 passed; the 1,323-product unknown-form cohort re-enriched and scored on the integrated tree is byte-identical to the `56314f5c` arm (8283c24391cc670e). No catalog replay. The focused owner suites passed 114 tests. The post-review fast run passed 16,333 tests and skipped 172; its only failure was an existing test invoking a missing literal `python` executable. That test passed 7/7 when the pinned project interpreter was present on `PATH`.

| Commit | Defect reproduced | Canonical owner | Tests | Measured output |
|---|---|---|---|---|
| `074697a9ffd83db821c01460deb93fdc28216e69` | `generic_trust` replaced a missing, malformed, or empty marine scope with `MARINE_CERTS_FALLBACK` (`ifos`, `friend of the sea`, `msc`, `goed`) | `cert_claim_rules.json` `rules.third_party_programs` via `scoring_v4.cert_evidence.marine_cert_tokens`. An unreadable or structurally incomplete policy is a systemic error; it never invents tokens or silently erases unrelated certification credit | `test_marine_cert_registry_owner.py`; existing generic, multi/prenatal, and probiotic trust tests | Valid registry unchanged: USP sku 8, non-omega IFOS 0, omega IFOS label claim 2, Friend of the Sea still not testing credit. Invalid policy stops scoring with a named configuration error |
| child of `074697a9` (`ul_display_severity`) | Per-row enrichment, aggregated exposure, the B7 penalty chip, and the consumer warning each repeated `critical if pct >= 200 else warning` (warnings used `high`/`moderate` for the same cut) | `rda_ul_calculator.ul_display_severity`. Export derives from `pct_ul` through that owner; a stored word is compatibility input only when the percentage is unavailable. Consumer copy stays `high`/`moderate` | `test_ul_display_severity_owner.py`; `test_v4_tradeoffs_derivation.py`; `test_ul_verdict_gate.py`; `test_b7_pct_ul_none_failsafe.py` | Successful path unchanged (79 mg zinc warning, 80 mg critical, aggregate 200% critical, export high/moderate). A stale stored `warning` at 250% is corrected to critical/high. 100% confirmed exceedance, 150% score deduction, and the gate's 200% signal name were not moved |

## 2026-09-26: protein Evidence alias containment

Owner: `scripts/data/backed_clinical_studies.json::INGR_WHEY_PROTEIN` through
`SupplementEnricherV3._clinical_study_match` and existing generic Evidence recovery.
Evidence: `rg 'INGR_WHEY_PROTEIN|_clinical_study_match|_entry_identity_keys' scripts/`;
checked source-of-truth matrix and glossary. Will NOT create: second matcher,
protein whitelist, new evidence field, title-derived ingredient identity.

Reproduced 3 failures through current normalize_product -> enrich_product on public
DSLD fixtures 299952, 222864 and 204521. Removed generic macro/powder/blend aliases.
Also removed rice/hemp aliases: the cited review's source inventory identifies
whey, casein, soy, pea, milk, food and studied blends, not those two isolated sources.
This is not a claim that rice/hemp lack evidence; this record cannot establish it.

Content verified 2026-09-26 via Europe PMC REST (MED 28698222 and 39303495), plus
https://doi.org/10.1136/bjsports-2017-097608 source inventory. The former is 49 RCTs,
1863 participants, protein with sustained resistance training; benefits were modest.
The latter found lower-body strength benefit with training but many null outcomes;
entry prose now says so. No clinician review attributed.

77 focused tests pass. Three recovery fixtures now name the actual whey/pea form;
a separate negative pin rejects recovery from a title plus source-free macro.
Fresh before/after totals: 299952 89.5 -> 89.5, 222864 73.5 -> 73.2,
204521 62.6 -> 62.6. All three false protein matches removed; routes, status and
safety verdicts unchanged. Durable receipts: ~/pg_quality/candd/protein_{before,after}_full.json.
Broader regression/replay follows at the combined checkpoint; nothing published.

## 2026-09-26: omega clinical/config ownership reconciliation

Owner: `scripts/evidence_resolver.py::resolve_omega_evidence_standard` joins
`backed_clinical_studies.json::INGR_OMEGA3.purpose_evidence` (source facts) to
`quality_score.json::evidence_magnitudes.omega.purpose_standards` (editorial policy).
Evidence: `rg 'purpose_evidence|pillar_score|resolve_omega_evidence_standard' scripts/`,
matrix `quality_pillars_v4_contract`, DATABASE_SCHEMA and GLOSSARY.
Will NOT create: a second scorer, clinical registry, public field, status or approval queue.

Sean explicitly delegated source reconciliation on 2026-09-26. This is source
verification and engineering review, NOT an assertion of Dr Pham's approval.
Moved all omega point values, operational cutoffs, interpolation and eligibility
switches to the existing config. Retained current numeric behavior; version/fingerprint
bumped. Existing factual purpose records are now documented in schema/glossary/matrix.
Removed the module's stale generic-plus-prenatal-bonus description.

Source verification, live Europe PMC REST MED records, 2026-09-26:
- PMID 31567003, full text PMC6806028: 376-4000 mg/day is the range of included
  interventions. 376 is NOT a demonstrated efficacy threshold. The scoring floor
  is explicitly a conservative editorial applicability choice.
- PMID 32951855: coronary-event benefits, but not overall cardiovascular events;
  neither it nor the preceding review justifies universal cardiovascular protection.
- PMID 37264945: 90 RCTs, dose-responsive triglycerides, stronger above 2 g/day in
  hyperlipidemia/overweight populations. EFSA's primary statement:
  https://www.efsa.europa.eu/en/press/news/120727 (2-4 g/day claimed triglyceride effects).
- PMID 31422671: AHA prescription 4 g/day advisory, not OTC equivalence or proof
  that 2 g supplements treat every patient. No such claim is added.
- PMID 32114706: verified 2020 Cochrane update replaces PMID 30521670 as the cited
  triglyceride review; high-certainty dose-dependent triglyceride reduction,
  only limited/outcome-specific coronary benefit.
- PMID 18184094: average total intake >=200 mg DHA during pregnancy/lactation;
  intake guidance is not proof of a 200 mg supplement preventing preterm birth.
- PMIDs 34308309 / 34959801: ADORE primary trial / mechanistic analysis, not two
  independent efficacy trials. PMID 31509674: ORIP null early-preterm result.
  PMID 30480773: favorable broader review, with population/regimen applicability
  still material. Outcome credit remains disabled for fixed product quality.
- PMIDs 31383846 / 31480057: depression-specific EPA-predominant scope, not generic
  omega evidence. PMID 34612056: dose-related atrial-fibrillation association in
  cardiovascular-outcome trials; contextual safety remains a separate owner.

10.4/20/11.1 and the 1-2 g interpolation are editorial allocations, not numbers
proved by a paper. Scientific verification does not make those exact allocations
uniquely correct. They are retained for measurement, not increased to force 95s.
The 376 mg cutoff's abrupt boundary is an explicit calibration tradeoff.

Reproduced two failing ownership tests, then passed 62 focused tests (12 expected
missing catalog/DB skips). A pre-existing omega fixture supplied 200 mg while expecting
credit despite the existing 376 mg boundary; it now supplies 500 mg, while the exact
375/376 mg boundary remains separately pinned. No production rule weakened for a test.
Combined frozen replay/full fast verification is recorded below when complete.

### Protein correction acceptance finding: preserve disclosed source lists

The first 1,353 frozen replay found 72 sports Evidence changes. Inspection of the
largest movers (218854, 294073) showed genuine whey source rows in
`inactiveIngredients`, while the quantity-owning active row is simply Protein.
Narrowing aliases alone therefore caused an avoidable recovery regression.

Owner: `generic_evidence._recover_verified_primary_ingredient_matches` (existing
scoped recovery; verified by `rg '_recover_verified_primary|_row_identity_keys'`).
Will NOT create: title-based evidence, a protein-source registry or new payload fields.
The existing recovery now joins the primary protein macro to explicit protein
source-list rows using the SAME clinical record identity keys. Every declared
protein source must match; whey plus collagen cannot transfer the entire macro
amount to whey. The source list must retain a raw label path. Other-ingredient
rows do not become independently dosed actives. Missing source remains unproven.

New source-list regression failed first; 70 focused checks then passed. The real
Pure Encapsulations 294073 fixture passes current normalize -> enrich -> Evidence
and recovers its whey record (22 real/matcher checks). The first broad suite was
stopped after 2,524 passes when this replay finding required a code correction;
it was NOT a completed acceptance run. Re-run final frozen comparison before the
one completed full-fast checkpoint.

Source-list follow-through: existing DSLD protein identities can live in active or
inactive rows, including a blend's structured forms. Recovery now reads those
existing source names/groups. Explicit non-protein blend components (e.g. lecithin)
are not protein sources; unclassified/unknown protein forms must still match.
Missing provenance blocks the join instead of silently dropping that contributor.
Each boundary was reproduced in a failing test. Final focused batch: 80 passed.
No new source vocabulary, persisted fields, score magnitudes or title heuristic.

Final source boundary checks: an explicitly named whey ingredient remains whey
when its nested fields describe constituent proteins (alpha-lactalbumin, etc.);
those are not separate supplement sources requiring individual outcome records.
The same verified recovery is available to readiness and scoring after the existing
clear-primary guard, so their evidence IDs do not drift. Reproduced both boundaries
before correcting; 138 Evidence, real-enrichment, omega and readiness tests passed.
The next completed broad test and replay supersede the intermediate measurements.

### Completed-batch gate findings and closure

The first completed full-fast run found 5 failures (16,328 passed, 171 skipped):
two ownership guards correctly rejected a direct activeIngredients read inside the
scorer. Moved the source projection/filter into the EXISTING scoring-input contract
(`declared_protein_source_rows`), leaving Evidence identity decisions in its existing
owner. No allowlist or audit exemption was added. This is a proper boundary fix.
Owner Check: `scoring_input_contract.py::_source_tree_rows` and source projections;
`rg '^def .*source|activeIngredients|inactiveIngredients' scripts/scoring_input_contract.py`.
Will NOT create a new module, registry, persisted field or alternative normalizer.

The other failures were explicit contract updates: omega now delegates to the
resolver, magnitudes now have their reviewed config pins, and the failure archetype
with an unidentified proprietary protein matrix must not earn 15.6 Evidence.
It now correctly pins 0 Evidence and total 26.8 instead of 42.4. Other pillars and
safety are untouched. Omega record audit date corrected (metadata only).
All 210 focused owner, archetype, source, omega and readiness checks passed.
Source projection equality was checked on all 1,353 frozen products: identical
before/after the ownership-only extraction, so the final score replay remains valid.
