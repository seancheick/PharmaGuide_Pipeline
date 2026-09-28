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
| C1 | Parent-relative IQM denominator (bio_score / parent reference) and IQM reference-eligibility flags | `form_quality_facts.py`, IQM `formulation_reference_eligible` | Superseded in part, 2026-09-25: IQM 5.6.1 defines bio_score as a within-parent 0-15 scale (best eligible form 15), authored so far for B12 and BCAA; every other parent is scaled at runtime to its best eligible named form (`scoring_reference_resolver.parent_relative_form_quality`, dd2cf1ff dda033c7 afb71c6c 6a3ab83f, empty commit bodies; the 2026-09-25 archetype and contract-snapshot re-locks accepted the movements). That runtime maximum is the dynamic reference this row ruled out: open for Sean in `scripts/audits/rr_correctness_20260928/CALIBRATION_PACKET.md` |
| C2 | Activity-equivalence sets (vitamin E, folate, vitamin A) | IQM `formulation_activity_equivalence` | Not ported; revisit with C1 |
| C3 | Audience-specific Dose benchmarks (highest RDA/AI among printed-audience cells) | `scoring_v4/benchmark_population.py` | Candidate for v4 Dose; needs replay and review |
| C4 | UL excess treatment (cliff vs graduated bands, per-slot before aggregation) | `dose_policy.py`, `panel_assessment.py` | Step 8 comparison |
| C5 | Evidence tiers 20/15/10/0/pending; single-strain fairness; omega floors | `strain_purpose.py`, `omega_purpose.py`, `purpose_assessment.py` | Step 9, inside existing v4 modules |
| C6 | Transparency 15/15 for full factual disclosure; one deduction owner per fact | `purpose_assessment.py` (shared criteria) | Step 10 |
| C7 | 299v outcome split (abdominal pain frequency primary, severity secondary) in the strain registry | `data/clinically_relevant_strains.json` | Owner-approved data correction; moves live v4 Evidence (archetype 87.1 -> 93.1). Port with A-items only after the probiotic replay |
| C8 | LGG IBS and 299v context arms added to the registry | `data/clinically_relevant_strains.json` | Registry data; port with C7 |
| C9 | Proposed IQM bio_score corrections (B12, vitamin C, calcium, folate, thiamine) | IQM | B12 applied 2026-09-25 (IQM 5.6.1 `parent_relative_b12_recalibration`: six disclosed forms tie at 15, unspecified 14; basis Dr Pham's C2 finding of no established absorption advantage, pinned in test_b35_dr_pham_signoff_integrity). Vitamin C, calcium, folate and thiamine still await team approval; never tuned for score recovery |

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

### Final acceptance — requested items 1 and 2 (2026-09-26)

Code checkpoint: `2b9a0454`, existing `v41-recovery` branch.
`scripts/test.sh fast`: **16,333 passed, 171 skipped, 0 failed**, 432.96 seconds.
Log: `~/pg_quality/candd/final_ownership_fast.log`. This supersedes the failed
intermediate gate; no code changed during this successful run.

Final fixed-input comparison: 1,353 products; exactly 14 sports Evidence changes,
no other pillar changes, no omega score changes, and no changes to route, status,
safety, completeness or readiness. Receipt:
`~/pg_quality/candd/runs/protein_omega_verified_diff_20260926.json`.
The final ownership extraction was additionally equal on all 1,353 inputs.
These are sample/stored-input results, not a full fresh-corpus release validation.

The 14 reductions require source-family evidence review before release: three
egg-containing blends, two hemp/rice, seven plant/alternative-source products,
and two whey labels without usable source declarations in these inputs. Do not
restore generic protein aliases or create product exceptions to hide those gaps.

Items 1/2 are implemented and verified; the overall calibration is not complete.
Continue existing generic/fiber Evidence ownership, iron-oxide/non-delivering Dose,
botanical exposure/basis and population-reference work, then validate integration
with fresh representative inputs and export/Flutter consumers. No push, merge,
release, new worktree, or new public contract was performed for this batch.

## 2026-09-26 continuation: botanical daily exposure

Owner: `serving_frequency.py::resolve_daily_serving_range` supplies daily exposure;
`scoring_v4/modules/botanical_profile.py::score_botanical_dose` owns its comparison.
Evidence: `rg "daily|Adequacy exposure" scripts/GLOSSARY.md scripts/serving_frequency.py`.
Will NOT create: a serving resolver, field, registry or new dose policy.

A failing regression demonstrated that 150 mg twice daily was compared as 150 mg
against the existing daily reference. The adapter now uses minimum directed daily
exposure. 50 botanical profile/role tests passed. Stored-input adapter probe of
1,353 products found 11 payload changes (including metadata-only changes); receipt
`~/pg_quality/candd/runs/botanical_daily_20260926.json`. Preparation/basis scope still
requires review; this checkpoint alone does not establish route or release readiness.

### Protein source loss in skipped inactive blend headers

Owner: `enhanced_normalizer.py::_process_ingredients_sequential` preserves source
forms through its existing header expansion; `scoring_input_contract.py::declared_protein_source_rows`
projects the resulting rows. Evidence: `rg 'structural_form_container|should_skip_inactive|declared_protein_source_rows' scripts`.
Will NOT create: a source parser, registry, public field or product exception.

Both 42306 and 42289 disclose sources in raw Other Ingredients; the skip-list
path discarded their proprietary headers with their forms. Two failing cleaner
regressions preceded the expansion fix. A failing real-label Evidence regression
then exposed that expanded rows use `category`, not `raw_category`; the projection
now accepts that existing field. 80 focused cleaner/matcher/Evidence tests pass.
42306 recovers whey evidence; 42289 preserves its casein/egg/soy/whey sources but
still fails this record's current scope. Fresh real-label outputs are recorded in
`~/pg_quality/candd/runs/protein_source_loss_20260926.json` (62.6 and 32.9 respectively).
These totals are fresh outputs, not an isolated before/after score measurement.
Combined fresh validation and broader preservation checks remain pending.

### Generic/fiber Evidence purpose ownership

Owner: `evidence_resolver.py::evidence_owner_canonicals` consumes
`scoring_input_contract.py::classify_ingredient_roles`; generic Evidence remains
`generic_evidence.py::score_evidence`. Existing route_features digestive sets and
immune_support._active_id define their respective purpose ingredients.
Evidence: `rg 'owner_scoped|role_driver_canonicals|_active_id|FIBER_CANONICALS' scripts`.
Will NOT create: an owner resolver, identity set, module, registry or public field.

Five failing regressions established adjunct Evidence, activity-unit ownership,
a nutrition-authority floor bypass, and mass-only exclusion of immune nutrients.
Generic/fiber callers now opt into the same scope as sports. Authority floors
must belong to an owner. Digestive roles reuse existing identity sets; immune
roles reuse the existing profile rather than privileging milligram mass over
micrograms. 163 focused tests pass. The immune ideal fixture changes 93.0 -> 94.6
because existing reviewed quercetin/elderberry records are recovered despite
other pre-existing matches (raw Evidence 11.8881 -> 13.2651); no magnitudes changed.
Frozen score/route/safety comparison follows at the combined checkpoint.

### Non-delivering nutrient forms: absorption and Dose

Owner: `scoring_reference_resolver.py::delivers_parent_nutrient` reads IQM
parent_relationship; enrichment owns absorption pairing and adequacy projection.
Physical source joins use `scoring_input_contract.py::source_linked_rows`.
Evidence: `rg 'delivers_parent_nutrient|source_linked_rows|_collect_absorption_data' scripts`.
Will NOT create: a form-quality table, a delivery policy, field or status.

Two failing normalize->enrich regressions showed iron oxide + vitamin C earned
an enhancer bonus and emitted unknown rather than zero adequacy. Absorption now
excludes source-linked non-delivering IQM rows. Adequacy emits pct_rda=0 while
keeping its noneligible flag and UL assessment. Generic Dose consequently counts
zero instead of dropping that exposure from its average (vitamin C + oxide 20 ->
10 public Dose in the regression). Evidence unchanged; glycine-chelated iron
still qualifies for pairing. 163 focused form/absorption/generic/multi tests pass.
Existing equal-Dose regression was corrected to pin zero contribution rather
than denominator exclusion. Fresh regeneration is required for these fields.

### Omega exposure and population reference check

Owner: `serving_frequency.py::resolve_daily_serving_range`; the glossary defines
adequacy as per_day_min and safety as per_day_max. Evidence already uses minimum.
`omega_dose.py::score_dose` still averaged endpoint scores, yielding 15.0 versus
12.4 for the same 700 mg minimum dose when the permitted maximum doubled.
A failing regression preceded alignment to the existing minimum-adequacy contract,
including prenatal DHA. Interval metadata and maximum-exposure flags are retained.
Will NOT create: an exposure resolver, reference population or scoring magnitude.

104 focused omega, prenatal, multi and serving-basis tests passed; 20 tests skipped
because this checkout has no generated catalog yet. Existing prenatal tests verify
Pregnancy RDA (including iron/iodine) and unchanged adult reference behavior.
This is a contract alignment with measurable score impact, not a new dose target.

### Frozen replay finding: blend quantity is not an individual dose

Owner: `generic_evidence.py::_recover_verified_primary_ingredient_matches`.
Evidence: `rg 'exact_nested_identity|identity_bearing_blend_header_mass_from_nested_child' scripts`.
Will NOT create: an alternate mass owner or blend policy.

The first continuation replay exposed 333746, Fiber Fusion: 3.1 g is the total
of psyllium, oat bran, guar and further constituents, not a disclosed psyllium
dose. The prior recovery exception trusted a nested identity as though it owned
all blend mass. A failing regression preceded removing that exception. Existing
protein-source and complete BCAA aggregate paths remain; branded formula recovery
is separate. The old synthetic creatine test lacked dose ownership and now pins
no recovery. 176 focused Evidence/source/contract/archetype tests pass.

The initial broad run was interrupted for this correction: 7,118 passed, 112
skipped, one stale omega endpoint-average expectation failed before interruption.
It is NOT an acceptance run. The first 1,353-input continuation replay had 153
changed pillar payloads, 155 readiness payload changes and no route/status/safety
changes. Those intermediate results require a replacement after this finding.

### Botanical preparation containment and interim test correction

Owner: `botanical_profile.py::_dosing_entry_for` consumes the existing therapeutic
reference; `_forms_text` retains the row's preparation. A failing whole-herb
regression showed 500 mg root powder receiving extract-range credit. When a
reference explicitly names extract and the disclosed row is whole herb/powder
without extract evidence, it now returns disclosed/no-reference rather than
inventing equivalence. Will NOT create: an extract conversion ratio or registry.

Content re-verified through Europe PMC MED API on 2026-09-26: PMID 31517876 used
240 mg/day standardized Shoden extract; PMID 23439798 used 300 mg extract twice
daily. Neither establishes an equivalent dose of plain root powder.
Sources: https://pubmed.ncbi.nlm.nih.gov/31517876/ and
https://pubmed.ncbi.nlm.nih.gov/23439798/. Preparation-specific branded-carrier
ranges (including phytosome mass versus constituent mass) remain a review gap;
this narrow correction does not assert full botanical clinical closure.
59 focused botanical/role/omega-standard checks passed. The stale omega test
now expects 16.8 at the 1,200 mg minimum, rather than 18.4 endpoint averaging.

### Protein mover dispositions — current registry coverage, not a quality judgment

Owner: `backed_clinical_studies.json::INGR_WHEY_PROTEIN` and existing source
projection/recovery. Will NOT create: broad aliases, a source-family registry,
product exceptions, or implied equivalence between isolated and blended evidence.
Raw labels were read from the existing frozen sample's source paths, alongside
active/inactive rows and `declared_protein_source_rows`. Fourteen dispositions:

| Product | Source finding | Disposition |
|---|---|---|
| 42306 | Raw inactive proprietary whey blend was dropped | Cleaner/projection fixed; Evidence recovers on fresh input |
| 42289 | Raw casein/egg/soy/whey blend was dropped | Source loss fixed; mixed-egg applicability remains unrepresented |
| 25694 | Casein/egg/milk/soy/whey declared | Mixed-egg applicability gap; no isolated-egg alias added |
| 259796 | Casein/whey/egg declared | Mixed-egg applicability gap |
| 317624 | Casein/whey/egg declared | Mixed-egg applicability gap |
| 330181 | Hemp protein declared | Outside current record; hemp-specific trial reviewed below |
| 330187 | Rice protein declared | Outside current record; rice-specific trials reviewed below |
| 264831 | Fava isolate plus rice source declared | Outside current record; fava cannot borrow whey/pea scope |
| 273676 | Fava/barley/rice blend | Outside current record |
| 273685 | Fava/barley/rice blend | Outside current record |
| 273696 | Fava/pea/salmon blend | Outside current record; raw salmon row has misleading pea ingredientGroup |
| 277517 | Fava/pea/ProGo salmon blend | Outside current record; same misleading raw taxonomy; rejected by complete-source rule |
| 29098 | Sprouted rice and additional plant/Chlorella sources | Mixed source scope unrepresented |
| 180692 | Mixed pea/rice/flax/hemp/quinoa/other greens blend | Macro/title is not a complete reviewed protein-source declaration |

Content verified 2026-09-26 via Europe PMC REST MED records and fullTextXML for
PMC5867436. PMID 28698222 explicitly includes egg-containing **blends** among
its sources; it does not establish isolated-egg applicability. The current flat
alias join cannot express that conditional scope without also admitting isolated
egg. Keep these four entries as a representation gap, not a claim of absent
human evidence. PMID 39303495 is whey-specific in older adults; it does not
broaden this scope to alternative plants or fish sources.

PMID 33261645 compared 24 g rice versus whey in 24 trained males for eight weeks;
PMID 23782948 studied 48 g rice versus whey. These active-comparator results do
not inherit the 49-trial meta-analysis rating by adding a rice alias. PMID
37847288 studied 60 g hemp supplement (40 g protein and 9 g oil) versus soy in
34 adults, with sex-specific findings; this is not proof that 11 g hemp protein
on product 330181 receives the same rating. No curated record was edited and
no clinician approval is asserted.

Sources: https://pubmed.ncbi.nlm.nih.gov/28698222/,
https://pubmed.ncbi.nlm.nih.gov/39303495/,
https://pubmed.ncbi.nlm.nih.gov/33261645/,
https://pubmed.ncbi.nlm.nih.gov/23782948/,
https://pubmed.ncbi.nlm.nih.gov/37847288/.
These are completed source-coverage dispositions, with explicitly unresolved
registry representation/curation; they are not fourteen restored scores.

### Readiness shares recovered clinical matches

Owner: `generic_evidence.py::resolved_clinical_matches` — evidence: `rg -n
'resolved_clinical_matches|owner_scoped' scripts/assessment_readiness.py
scripts/scoring_v4/modules/*.py`. Will NOT create: a second matcher or readiness
state. A failing NAC regression reproduced score recovery alongside an existing
incidental match while readiness omitted the recovered evidence. Readiness now
uses the same recovery mode for the three owner-scoped scoring modules.
115 focused readiness/Evidence checks passed. The preceding stable code checkpoint
at a4cc5c6b passed 16,347 fast tests, 171 skipped (372.01 s); that checkpoint
predates this final readiness alignment and is not its complete-suite proof.

### Fresh 12-brand run and nutrient-total correction

All 7,412 raw labels completed Clean/Enrich/Score at674a2ec9 across Culturelle,
GNC, Garden_of_life, Life_Extension, Nature_Made, Natures_Way, Ora,
Pure_Encapsulations, Solgar, Sports_Research, Thorne and nordic-naturals.
Pipeline-only log: `~/pg_quality/candd/fresh_12brands_20260926.log`.
First-pass records preserved: `runs/fresh12_firstpass_674a2ec9.jsonl`.

Owner: `evidence_resolver.py::resolve_evidence_for_row` and
`is_essential_dietary_nutrient` — evidence: `rg -n 'is_parent_total|is_essential'
scripts/evidence_resolver.py`. Will NOT create: a nutrient identity list or a
new evidence state. Fresh GNC224672 reproduced a false undisclosed-blend finding:
Folate1333mcgDFE was a declared nutrient total with a Folic Acid800mcg child.
The existing essential-nutrient classifier now distinguishes that total from an
opaque blend; explicitly proprietary rows remain blocked. Regression failed
before the fix; all46 resolver tests passed afterward. Scoring rescore follows.

Owner: `generic_evidence.py::_mass_dominant_essential_canonical` consumes the
existing `evidence_owner_canonicals` result — evidence: `rg -n
'_mass_dominant_essential_canonical|owner_canonicals' scripts/scoring_v4/modules/generic_evidence.py`.
Will NOT create: a floor magnitude or another owner selector. The same Folic Acid
label had65mg calcium, so choosing the heaviest nutrient before scope silently
removed the folate authority floor. Scope now filters the existing competitors
before selection; non-nutrient purpose competitors still prevent a trace vitamin
from earning a floor. Regression failed before the fix.203 focused checks passed.
Real224672 now resolves by authority and earns the existing raw10-point nutrition
floor (11.1 public), with an assessed explanation rather than false identity debt.
Its old15.6 points came from calcium and are not restored.

### Continuation measurements at6bdffe33 — provisional policy, not release approval

Owner: the existing scorer, `evidence_resolver`, `scoring_input_contract`, IQM,
`serving_frequency`, and their current export/Flutter consumers. Evidence: the
11 local commits after69c08dbc and the recorded boundary regressions. Will NOT
create: a second scorer, source registry, product exception, or public field.

- Fresh Clean/Enrich/Score:7,412 labels across12brands; all stages succeeded.
  After the two nutrient fixes, every brand was rescored successfully at6bdffe33.
- Coverage:generic4,528; multi/prenatal1,063; sports598; omega528;
  probiotic398; fiber/digestive215; B-complex82. Statuses:6,077scored,
  1,294not_scored,41suppressed_safety.
- Isolated frozen replay:1,353inputs,119score changes (111Evidence,8Dose).
  Zero route/status/safety/dose-safety/completeness changes.258readiness payloads
  differ (Evidence258,Dose details81,shadow dimensions52); eligibility unchanged.
  Source unchanged during replay; SHA256
  315df72aeafbf11a60de6fde92f4bb5b3123dcac98dff238a8baf61b6ccc17af.
- Fresh/frozen join:798overlapping labels,149pillar movers,194readiness changes;
  no compared route/status/safety/dose-safety/completeness differences.22IQD
  projections changed, all disclosed omega form recovery. This projection covers
  source path, identity and matched form; the inactive protein-source boundary is
  covered separately by the two real-label regressions.
- First-pass/final fresh nutrient correction:91score/conclusion changes; maximum
  absolute11.1. Zero safety, route, eligibility, exposure, or quarantine changes.
  GNC224672 ends57.6overall with11.1Evidence, rather than borrowing calcium credit.
- Route leaders inspected:337856Curcumin Phytosome100 (preparation-basis gap,
  not clinical approval);328090probiotic81.4;328830prenatal96.5;
  218637psyllium93;59360omega91.5;175321creatine100;209616B-complex98.6.
  Numerical leaders are diagnostic examples, not an endorsement or a90+target.
- Flutter:59focused score/pillar/projection/detail-blob/tradeoff checks passed.
  No Flutter source edited. Exported-candidate validation remains a separate gate.

Artifacts under `~/pg_quality/candd/runs/`: `continuation_final_6bdffe33.jsonl`
(and metadata), `continuation_final_diff_6bdffe33.json`,
`fresh12_firstpass_674a2ec9.jsonl`, `fresh12_final_6bdffe33.jsonl`,
`fresh12_nutrient_fix_diff.json`, `fresh12_vs_frozen.json`,
`fresh12_identity_diff.json`, `fresh12_coverage.json`.

**Unresolved acceptance decisions:** strict digestive ownership sends315334 and
315850Stress & Gut Health Evidence20→0 by excluding substantial stress actives.
Sean's mixed-purpose ownership decision is pending; this candidate is provisional.
Conditional mixed-egg source applicability and alternative-source curation remain
open. Preparation-specific carrier/extract references also remain a clinical
review gap. Do not describe those gaps as fixed or all14protein scores restored.

Main was fetched at a5bc92b7 and includes separate clinical/scoring changes in19
production/data files relative to69c08dbc. The combined main+continuation result
has not been tested. No merge, push, release or worktree deletion occurred.

Testing workflow correction requested by Sean: batch related fixes; use focused
regressions; one broad fast checkpoint; stop on an early failure, but after roughly60–70%
let the run finish and collect failures. Repair related failures together before restarting. Do not run a broad suite per
individual fix, or automatically add release/full-suite runs to a provisional
candidate. No broad suite is running; finish the collected export findings before another checkpoint.

### Test-cost defect found by the final checkpoint

The broad fast run was interrupted at its first reported failure under Sean's
then-current instruction:11,951passed,111skipped,1timeout in762.20seconds.
`test_no_corpus_red_yeast_rice_label_is_unmatched` timed out decoding the full
corpus at120seconds; it did not report an unmatched safety label. Sean then
refined the workflow: after60–70% allow completion and batch the failures.

Owner: `test_profiles.py::RELEASE_TEST_FILES/ARTIFACT_TEST_FILES` already owns
`test_active_banned_recalled_parity.py`. Evidence: `rg -n
'ARTIFACT_TEST_FILES|RELEASE_TEST_FILES|test_active_banned_recalled_parity'
scripts/test_profiles.py`. Will NOT create: a second profile or bypass a safety
assertion. The two whole-corpus tests were moved from fast unit-test files into
that existing artifact/release file. The178791 lookup also reads the real enriched
`id` key and avoids decoding batches that do not contain that ID.

The35fast label/form tests passed together (0.77seconds). The full-corpus red
yeast rice check passed under the existing600-second artifact/slow budget;
178791 was absent and explicitly skipped (1passed,1skipped,32.42seconds).
No scorer or clinical data changed; another pipeline rebuild is unnecessary.


### Export checkpoint and batched follow-up (2026-09-26)

The guarded candidate export stopped at the existing scoring snapshot gate:
30 failures, 5 passes. Of the failures, 14 require brands outside this 12-brand
sample; 16 differ from the saved score/status expectations. The source matrix,
IQM, cleaner, enrichment, clinical drift, and RDA/UL stamp gates passed first.
The snapshot manifest is dated 2026-09-08. No snapshots were refreshed, no gate
was weakened, and no candidate was promoted.

Diagnostics: `/Users/seancheick/pg_quality/candd/runs/export_snapshot_failures.json`.
The two score-withheld cases were reproduced through the current input owner:

- 182730 Athletic Pure Pack: `disclosed_form_unmapped`; vitamin E retains an
  unresolved `Tocopherol` token beside its matched succinate form; vanadium's
  `Bis-Glycinato OxoVanadium` form is unresolved. This needs form provenance/
  curation review, not an automatic restoration of the old 79-point score.
- 323080 Catalyte: IQD excludes sodium/chloride from its form-scoring rows;
  `get_scoring_ingredients` adds label-active projections, and the sodium
  projection carries its three disclosed salts as unmapped. The strict input
  gate therefore withholds the score. Whether the projection should inherit
  the exclusion needs owner-level review before changing this behavior.

Owner: `scripts/scoring_input_contract.py::get_scoring_ingredients` and
`derive_product_scoring_evidence`; form status is owned by
`scripts/enrich_supplements_v3.py::_row_form_match_status`.
Evidence: direct probes of enriched/scored 182730 and 323080, plus
`rg -n 'DISCLOSED_FORM_UNMAPPED_FINDING|identity_bearing_active_anchor_mass'
scripts/scoring_input_contract.py`.
Will NOT create: a second form policy, product exceptions, or replacement
snapshot expectations without reviewing the differences.

A separate strict diagnostic build uses the canonical builder and an explicit
output directory, `/Users/seancheick/pg_quality/candd/diagnostic_export_20260926`.
It is not a validated release candidate. All 16 snapshot score/status drifts
were already present in the first-pass fresh run at 674a2ec9; none was introduced
by the later nutrient fixes.


The diagnostic build exported 6,114 products, quarantined 1,298, and reported
zero builder errors. Its field-completeness audit passed with no undeclared
blob keys, and identity containment passed. The separate strict scoring source
audit failed with 1,286 findings, so release acceptance remains blocked.
Direct comparison of all 6,114 exported score/status/verdict triples to the
scored inputs found zero differences after applying the existing
`quality_score.py::shipped_whole_score` rounding rule.

**Export defect found and fixed as a batch:** three BLOCKED GNC products
(220094, 220098, 220101) were excluded solely by `disclosed_form_unmapped`,
hiding their confirmed ban warning. The existing `validate_export_contract`
owner now permits that finding only for a confirmed ban/recall with
`suppressed_safety`, null numeric scores and `N/A` display. Other contract
findings and identity/display defects remain blocked. This implements the
existing AGENTS safety-visibility requirement; no new clinical policy or
public field was introduced.

Owner: `scripts/build_final_db.py::validate_export_contract`; confirmation is
reused from `scripts/release_catalog_artifact.py::is_confirmed_ban_or_recall`.
Evidence: `rg -n 'validate_export_contract|is_confirmed_ban_or_recall'
scripts/build_final_db.py scripts/release_catalog_artifact.py` and the real
three-product export probe. Will NOT create: a second safety decision or any
numeric score for suppressed products.

The new regression batch reproduced two expected failures before the fix.
Afterward, the two export test files passed together: **340 passed in 11.87s**.
A strict canonical build of the three real inputs exported all three with
BLOCKED, suppressed_safety, null score, and banned flag true; zero errors or
quarantines. Artifact: `~/pg_quality/candd/safety_export_regression_20260926`.
The earlier full diagnostic output is preserved as pre-fix evidence; it was
not silently patched or presented as the fixed candidate. Source scores and
verdicts were unchanged by this export-only fix.

One broad fast checkpoint completed for the batch: **16,390 passed, 137 skipped
in 410.05 seconds (6m50s)**. Log: `~/pg_quality/candd/batched_fast_20260926.log`.
No further broad run is needed for this unchanged code. The guarded candidate
remains blocked by the snapshot/source findings and pending policy decision.
No merge, push, release, or worktree deletion occurred.


### Independent continuation audit — 2026-09-26; policy stop

Fetched all remotes before inspection. Main and origin/main are 8dbd621b;
candidate v41-recovery is 00a0c5f9 with a clean tree. `git rev-list
--left-right --count main...HEAD` reports 145 main-only and 13 candidate-only
commits. Claude pending-fixes is 786d318b, four commits beyond main; no merge
performed. No pipeline or pytest process was running at inspection.

Recounted the preserved diagnostic_scoring_contract.log: 1,267 findings contain
only disclosed_form_unmapped; 19 contain that plus
identity_disposition_not_scoreable:identity_conflict. Total 1,286. This classifies
reported gate reasons, not root causes or accepted curation exceptions.
The snapshot failure JSON contains 14 missing references and 16 drifts; its
passed list contains only 3 entries (the prior summary says 5 passes). Do not
use that partial JSON to assert the total number of passing gate checks.

Reproduced both 315334 and 315850 from current GNC enriched batch 3 through
build_scored_artifact: scored, overall 50.1, Evidence 0/20,
applicability_unestablished. classify_ingredient_roles marks ashwagandha and
l_theanine major; digestive_enzymes and protease primary. The current
Evidence owner set contains only digestive_enzymes and protease. The existing
explicit-owner precedence excludes the major stress ingredients.

Owner: scripts/evidence_resolver.py::evidence_owner_canonicals and
scripts/scoring_input_contract.py::classify_ingredient_roles — evidence:
`rg -n 'evidence_owner_canonicals|classify_ingredient_roles' scripts/evidence_resolver.py
scripts/scoring_input_contract.py`, matrix scoring_input_contract entry,
GLOSSARY V4 module/archetype entries, and the real-product probe above.
Will NOT create: a second scorer/resolver, new field, product whitelist, or
unapproved mixed-purpose scoring policy.

Stop for Sean's policy decision: should material actives serving another
explicit product purpose participate in Evidence alongside route drivers,
or should route-driver precedence remain exclusive? Including them must
retain form/dose/population applicability and must not automatically restore
historical 20/20 Evidence. Required by AGENTS autonomy boundary and
pg-scoring-change step 1. No scoring/data changes, snapshot refresh, test rerun,
new pipeline rebuild, export promotion, merge, push, release, or worktree
removal. Existing fast checkpoint is historical evidence, not a new test run.
Remaining acceptance sequence in the original handoff stays outstanding.


### Approved multi-purpose policy implementation — 2026-09-26 (measurement pending)

Sean approved assessing substantial explicitly purpose-driving actives alongside
route drivers, retaining every clinical/identity/source gate and the 20-point cap.
The existing role classifier now recognizes affirmative formulation statements
that name a material non-nutrient active as the subject of a function claim.
Statement locations are retained in role_source; role_reason is
named_in_label_function_claim. Generic Evidence retains its shared owner selection
and clinical-record-ID deduplication and emits explicit-label-owner flags.
No clinical registry or scoring magnitudes changed.

Owner: scoring_input_contract.py::classify_ingredient_roles and
evidence_resolver.py::evidence_owner_canonicals — evidence: current symbol search,
matrix scoring_input_contract entry, and two real-label regressions.
Will NOT create: a purpose registry, alternate scorer, whitelist or public field.

Two new regressions failed before implementation. Focused batch: 148 passed
in 2.43s, log ~/pg_quality/candd/multipurpose_focused.log. Both real labels
315334/315850 move 50.1 to 70.1, Evidence 0 to 20, via ashwagandha and
L-theanine. Duplicating statements/clinical records does not add points;
removing statements restores Evidence 0. These are measured provisional results,
not release acceptance. New real enriched fixtures preserve original provenance.

Additional reproduced pre-existing resolver inconsistency: projected scoring rows
carry quantity, while resolve_evidence_for_row reads amount/dose_value, so disclosed
L-theanine200mg reports dose_undisclosed. Ashwagandha240mg with a standardized
marker child is_parent_total and reports structural_blend_header despite explicit
non-proprietary/non-blend flags. Generic scoring still awards points; resolver
reports identity_material_unresolved. Resolve this through existing owners before
acceptance. Fresh-context review and frozen replay remain pending.


Fresh-context review reproduced two parser defects: manufacturing-function text
could earn Evidence and conjunction splitting lost governing negation. A real-label
regression failed before the repair. The parser now rejects negated sentences
before splitting and requires a recognized health indication. The existing
probiotic indication categorizer moved to evidence_resolver for shared consumption;
no duplicate map was created. Mood synonyms include relax/relaxation/cortisol.
Role reasons retain the indication; generic Evidence and resolver match it against
the clinical record's stated endpoints/goals, never broad notes. A stress record
cannot substantiate a bone/digestive-only claim. Focused parser/role/probiotic
batch:95passed2.56s; broader prior batch163passed2.31s. Final resolver alignment
and full replay remain required.


Resolver row-contract correction: four regressions failed before the fix.
The resolver now uses generic_evidence's existing dose-map/conversion path,
restricted to the exact row, for unit and directed daily exposure. A study with
an unmet higher threshold no longer vetoes an independently applicable record.
Explicit blend flags remain blocking; parenthood alone does not make a disclosed
standardized extract an undisclosed blend. No registry or dose policy was added.
Focused resolver/generic/readiness batch:170passed2.87s;
~/pg_quality/candd/resolver_row_contract_{red,green}.log. Tests cover the real
extract/theanine rows, equivalent mg/g/mcg, two daily servings, sibling dose
non-borrowing, multiple study minima and true blends. Whole frozen replay pending.

Owner: generic_evidence.py::_dose_map/_converted_product_dose and
scoring_input_contract.py::_positive_quantity/_row_unit/_role_is_blend_member.
Evidence: shared-provider calls and failing-then-passing regression batch above.
Will NOT create: a second conversion, daily-dose policy, or applicability flag.


Second adversarial review: union all explicit purposes across statements and
coordinated objects so label order cannot change scores. Preserve a new subject's
claim boundary; reject oxidative/physical stress as psychological stress.
The positive literature-resolution branch now shares the backed-study purpose
check. Both new regressions failed before fixes. Final focused batch205passed
3.77s; log ~/pg_quality/candd/multipurpose_review_complete.log. No score pin was
raised or bypassed; same clinical record still counted once. Final broad/replay
measurements follow after this batch.


Broad checkpoint at 220c4e5e: 16,399 passed, 137 skipped, one failed in
420.40s. The sole failure was two stale raw quantity/unit read exceptions
in the contract leak audit after shared accessor adoption. Removed only
those obsolete entries. Owner: audit_scoring_contract_leaks.py::ALLOWLIST —
evidence: test_scoring_contract_leak_audit live-tree failure.
Will NOT create: new audit exceptions or bypasses.


Source review: free nicotinamide extraction no longer matches the compound
prefix in nicotinamide riboside/mononucleotide/adenine names. Four regressions
failed first; form extraction suite then 97 passed. Real 182475 clean/enrich/score
now retains nicotinamide_riboside identity with mapped form status, no invented
niacinamide token, strict findings empty, score 75.5. No IQM form or alias added.
Owner: form_vocab.py::extract_forms using data/form_keywords_vocab.json — evidence:
rg form_vocab/form_keywords/normaliz in matrix/glossary and four red tests.
Will NOT create: a new identity, registry, clinical mapping, or form fallback.
Boundary artifact: ~/pg_quality/candd/runs/source_boundary_real_probe.json.


Catalyte 323080: propagate the existing IQD Nutrition Facts exclusion into generic
active projections and contain old native generic anchors by the same source path.
Keep typed protein/omega recovery and original dose/safety inputs. Sodium 485 mg
and chloride 80 mg remain in IQD/RDA records; neither becomes a generic anchor.
Real fresh clean/enrich/score: 72.4, scored, strict findings empty. Two regressions
failed before correction. Combined source/contract batch: 168 passed in 2.02s.
Fresh independent reviewer found no actionable regression and verified RDA
records and unchanged input. Owner: scoring_input_contract.py::
derive_product_scoring_evidence / _product_scoring_evidence_rows using
is_nutrition_fact_declaration — evidence: real 323080 boundary and red tests.
Will NOT create: new Nutrition Facts policy, public fields, score exceptions.
Full checkpoint and clean-HEAD measurement remain pending.


Follow-up checkpoint stopped on one early protein regression: 8,417 passed,
87 skipped, one failed at interruption (253.92s). Real 42306 previously relied
on a generic anchor because its display ledger called Protein mapped_ingredient
while IQD correctly marked the source Nutrition Facts. Extend the existing typed
protein projection to accept that exact source-path match; keep title intent,
gram-validated nutrition summary and exact Protein ledger requirements. Normalized
product-level sports-primary protein evidence is distinct from its excluded source
row. Clinical recovery still requires complete qualifying source identities.
The paired real 42306/42289 regression now asserts typed protein evidence and
removes ingredient-list sources to verify that macro/title alone earns no recovery.
Fresh reviewer verified the containment; original NF rows and sodium/chloride
anchors remain excluded. Owner: scoring_input_contract.py::
_derive_declared_nutrition_protein_evidence / is_nutrition_fact_declaration.
Will NOT create: a generic Nutrition Facts exception or protein evidence alias.
Focused source/clinical/Evidence batch: 164 passed (see protein_typed_projection_green.log).
Flutter consumer checks: 122 passed, app HEAD 4c5ff2b7, no app changes.


2026-09-26 nutrition capture correction: source ingredient names containing
"fiber" or "protein" could overwrite the panel total. Bind capture to the panel
name; retain exact fiber source paths. Real Sunfiber 228873 now retains 5 g
from ingredientRows[1].nestedRows[0], replacing the incorrect 0 NP child value.
It remains not_scored; this change does not introduce a fiber scoring policy.
Four capture regressions failed before correction; combined focused source batch
passed 262 tests in 34.48s (~/pg_quality/candd/fiber_source_green.log).
Owner: scripts/enhanced_normalizer.py::_extract_nutritional_info — evidence:
matrix/glossary searches, real raw 228873 and source-versus-panel regressions.
Will NOT create: a new normalizer, evidence type, clinical alias or public field.

97b8a0ed checkpoint: 16,408 passed, 137 skipped, 458.47s. Frozen 1,353-input
replay completed unchanged with no errors; 154 totals, 86 statuses and 5 routes
changed versus continuation_final_6bdffe33. No safety_gate or dose_safety reason
changes. The 12-brand diagnostic was intentionally stopped after 7 completed
brands when source defects surfaced; preserve fresh12_release_97b8a0ed.
Not final acceptance. Two named-konjac products currently expose a separate
PGX alias/identity-projection defect; their numeric 63.0 results are NOT accepted.
A single curated alias removal and NF-only fiber policy decision await Sean.


Konjac projection containment: required repaired identities that explicitly
exclude scoring under a different safety-recognition tuple now enter the existing
identity conflict ledger. This blocks derived and persisted native generic
anchors without globally rejecting recognized preparations or taxonomy flags.
Real 252564/255063 regressions failed first (scored instead of not_scored);
228 focused tests then passed. Persisted-anchor tests with and without a valid
peer passed (2), retaining one unresolved exposure and blocking numeric scoring.
Owner: scripts/scoring_input_contract.py::_identity_projection_rejection_reason
and required_identity_conflicts — evidence: matrix scoring_input_contract and
mapping_coverage_contract, real saved IQD tuple and red tests.
Will NOT create: new status, safety registry, identity resolver or public field.
The PGX alias and misleading Polydextrose recognition remain upstream findings;
this containment does not claim they are clinically corrected.


Named fiber source precedence: an approved, dose-bearing active whose own name
is recognized cannot be excluded solely because standardName becomes generic
Fiber. Exact source Nutrition Facts exclusions remain authoritative; downstream
identity/form gates remain active. Fresh raw 259395 resolves scoreable fiber and
scores 61.8; 252564/255063 retain contradictory PGX/Polydextrose identities and
are held by the prior containment fix. No aliases or curated entries changed.
Owner: scripts/enrich_supplements_v3.py::_should_skip_from_scoring — evidence:
existing source-role ownership, real raw fixtures and named-fiber red regressions.
Will NOT create: a whitelist, alternative identity resolver or NF evidence type.
Independent fresh review found no actionable issue in the final combined diff.
Final fast checkpoint and clean-HEAD replay follow this commit; full fresh
12-brand acceptance remains incomplete while clinical decisions are pending.


Final verification for source batch a0eee3e5: scripts/test.sh fast completed
16,414 passed, 137 skipped, 1 expected Pillow decompression-bomb test warning,
1,133.57 seconds. Log: ~/pg_quality/candd/final_fast_fiber_source.log.
Fresh-context reviewer found no actionable issue. No unchanged suite rerun.
Clean-HEAD replay captured all 1,353 frozen products, exit 0, source_unchanged=true:
~/pg_quality/candd/runs/release_candidate_a0eee3e5.jsonl (+ .meta.json).
Incremental comparison with 97b8a0ed: zero changes in total, status, route,
all-six-pillar payloads, safety_gate reasons or dose_safety reasons.
The frozen replay does not re-exercise cleaning/enrichment; fresh four-product
raw probes are stored in runs/fiber_source_a0eee3e5.json. They confirm
252564/255063 not_scored/null, 259395 scored/61.8, 228873 not_scored/null with
5 g retained. The prior 63.0 Konjac projections are invalid diagnostic history.

Pending approval is concrete: remove only the exact alias "Konjac root extract"
from ingredient_quality_map.json pgx_fiber.forms["PGX fiber"].aliases; retain the
entry and all evidence, add no replacement alias. Health Canada identifies PGX
as a glucomannan/xanthan/sodium-alginate complex:
https://www.canada.ca/content/dam/hc-sc/migration/hc-sc/fn-an/alt_formats/pdf/label-etiquet/claims-reclam/assess-evalu/glucose-complex-polysaccharides-complexe-glycemique-eng.pdf
No curated deletion performed. Also pending: retain NF-only fiber holds versus
authorize a typed verified-source fiber contract. Do not infer approval.
Final fresh 12-brand rebuild, export audits, snapshot acceptance and clinical
curation remain open. Prior 122 Flutter tests passed, but no fresh final bundle
was produced. Candidate is NOT release-ready.

Latest fetched observation: main 6767a383, origin/main 6c4a130e; before this
receipt candidate a0eee3e5 has 160 main-only / 25 candidate-only commits.
Other agents continue changing main. Combined state unverified; no integration,
push or release. Preserve the active worktree and partial brand diagnostics.


2026-09-26 approved fiber decisions, final implementation at 7cf610e1. Raw DSLD
inspection established the section contract before code changed:
`ingredientRows` is the active/Supplement Facts source;
`otheringredients.ingredients` is the inactive source. Nutrition is a separate
consumer of the same label ledger, not a second ingredient classifier. The
typed `declared_active_fiber` projection exists only when `nutrition_summary`
grams and source amount/unit join to the exact `raw_source_path` of a current
active row whose cleaner-owned identity is scoreable canonical fiber and whose
raw DSLD category is fiber. Title, unmatched totals, inactive/other rows and
non-fiber rows cannot create the projection. Persisted projections are caches:
the scoring boundary rejects them when the current exact join no longer exists.

The exact `Konjac root extract` alias was removed from the proprietary PGX form;
no replacement alias or clinical claim was added. PGX remains the documented
glucomannan/xanthan-gum/sodium-alginate complex. Fresh raw results: DSLD
178797, 270961, 277404, 305905, 67530 and fixture 228873 move from not_scored to
scored at 52.0, 58.5, 47.7, 49.4, 61.9 and 60.5 through one mapped
`declared_active_fiber` row. 252564 and 255063 move from held contradictory PGX
identity to scoreable generic fiber at 63.0; 259395 remains 61.8 with identical
pillars. Evidence credit remains zero where no applicable clinical record
exists. Inactive ingredients supplied no scoring row in every probe.

Nutrition export remains independent and complete: `build_final_db.py` emits
`nutrition_detail` plus the canonical `display_ingredients` label ledger, and
Flutter filters all nutrition label rows into its separate Nutrition Facts
card. Real raw/export probes retained cholesterol, sugars, saturated/trans fat,
sodium and nested rows as printed; the Flutter card regression passed 9 tests.

Clean-HEAD replay against merge baseline dafdf860 captured the same 1,353 frozen
inputs in both arms with zero score/status/route/distribution changes; those
stored enriched inputs did not include the eight freshly re-enriched affected
labels. Affected raw-label artifacts are
`~/pg_quality/candd/runs/fiber_affected_{baseline_dafdf860,candidate_7cf610e1}.json`;
replay artifacts are `fiber_{baseline_dafdf860,candidate_7cf610e1}.jsonl` and
`fiber_report_7cf610e1.json` in the same directory.

Fresh review found and then verified the fix for one P1 stale-native-evidence
bypass. Owner removal, inactive ownership, source-path/amount/unit mismatch now
reject persisted fiber evidence and yield not_scored; a valid updated dose
replaces the stale row without duplication. Post-merge focused pipeline batch:
92 passed; stale-evidence batch: 9 passed; IQM integrity batch: 22 passed.

Owner: scripts/scoring_input_contract.py::_derive_declared_active_fiber_evidence
and _product_scoring_evidence_rows — evidence: matrix concepts
scoring_input_contract and mapping_coverage_contract plus fresh raw probes.
Owner: scripts/scoring_v4/route_features.py::MATERIAL_FIBER_CANONICALS — evidence:
matrix concept fiber_identity and imported canonical set.
Owner: scripts/enrich_supplements_v3.py::_collect_nutrition_summary and
scripts/build_final_db.py::build_detail_blob — evidence: exact source-path probe
and Flutter canonical-ledger consumer.
Will NOT create: another normalizer, fiber registry, title inference, inactive
fallback, public/export field, status, verdict or app-side scoring rule.
Commits: b42b5b39, a40880a9, 7cf610e1. Full fast and final fresh 12-brand
acceptance remain pending; no push or release.

Full fast checkpoint at tracked receipt head 7b055d5b: **16,527 passed,
265 skipped, zero failures in 511.65 seconds**. Log:
`~/pg_quality/candd/final_fast_7b055d5b.log`. The skip increase relative to the
earlier checkpoint is explained by the current main test inventory and missing
Node/local-review opt-ins listed in the report; it is not a failing gate.
Final fresh 12-brand pipeline/export acceptance remains pending.

## 2026-09-26: final raw-label and Nutrition Facts acceptance

The fresh export first reproduced 35 `UNRESOLVED_SCORE_ACTIVE` failures. Raw
inspection showed 34 nested `Insoluble Fiber` rows and one `Omega-9 Fatty Acid`
row that the identity analysis had already classified as
`excluded_nutrition_fact`, while the display ledger still called them scored
ingredients. `SupplementEnricherV3._enrich_display_ingredients` now projects
that exact path-owned decision as `display_type=nutrition_fact`,
`score_included=false`, `display_disposition=label_context`. The strict export
gate was not weakened. Commit: a54cca7b. Focused export/ledger batch: 491 passed.

The same raw review found the cleaner summary allowed nested fiber and sugar
children to overwrite their label totals. Product 241368 therefore reported
3 g insoluble fiber instead of 8 g Dietary Fiber and 0 g Added Sugars instead
of `<1 g` Total Sugars. `enhanced_normalizer._record_nutrition_fact` now applies
label-semantic source precedence: Dietary/Total Fiber over generic fiber over
soluble/insoluble, and Total Sugars over sugar over Added Sugars. Every raw row
still remains in the canonical display ledger; only the aggregate summary owner
changed. Commit: e8a0817e. Focused cleaner/scoring batch: 184 passed.

Owner: `scripts/enrich_supplements_v3.py::_enrich_display_ingredients` —
evidence: exact `raw_source_path` join to `ingredient_quality_analysis` and the
35-product strict-export reproduction. Owner:
`scripts/enhanced_normalizer.py::_record_nutrition_fact` /
`_extract_nutritional_info` — evidence: raw 241368 parent/child hierarchy and
red aggregate regressions. Owner:
`scripts/build_final_db.py::_validate_active_count_reconciliation` — evidence:
the unchanged strict gate now passes. Flutter consumer:
`lib/features/product_detail/v2/sections/nutrition_section.dart` — evidence:
canonical nutrition-ledger and `nutrition_detail` focused tests. Will NOT
create: a second normalizer, nutrition registry, inactive/text inference,
export field, app scoring rule or weaker reconciliation gate.

Final fresh 12-brand raw -> clean -> enrich -> score replay at
`~/pg_quality/candd/fresh12_final_e8a0817e` completed all 12 logs with zero error
lines and 4,617 products at every stage. Status distribution is unchanged:
4,021 scored, 562 not_scored, 34 suppressed_safety. Against the pre-summary-fix
candidate, 163 nutrition summaries changed and 18 scores moved. Each movement
was traced to raw JSON: six are corrected total Dietary Fiber doses; twelve are
corrected Total Sugars values that nested Added Sugars had overwritten. Five
fiber corrections cross POOR -> SAFE; one 5 g total-sugar correction crosses
SAFE -> POOR. No scoring status distribution changed. Full delta artifact:
`candidate_delta_report.json` in that run root.

Strict export from the final enriched and scored artifacts completed with
4,054 products, zero errors, zero contract failures and 563 expected review
queue quarantines. `UNRESOLVED_SCORE_ACTIVE` is absent. Contract sync scanned
all 4,054 detail blobs: zero required/optional RED fields, zero undeclared
top-level/active/inactive keys. Products 270961 and 277404 export 4 g and 5 g
Dietary Fiber as Nutrition Facts; 241368 exports 8 g Dietary Fiber and 1 g
Total Sugars with its child rows retained; 282948 exports Omega-9 Fatty Acid as
a Nutrition Fact. Core DB score/status rows agree with the scored artifacts.

Final pipeline checkpoint at e8a0817e: `scripts/test.sh fast` passed **16,657**,
skipped 137 and failed zero in 448.42 seconds. Flutter focused consumer sweep
passed 70 tests across the Nutrition Facts card, canonical ledger and connected
product detail. The app-wide `make test` completed 3,601 tests with seven
unrelated screenshot/golden failures (nutrient progress, probiotic light/dark,
unfinished-evidence hero and two reviewer screenshot cases); no nutrition
contract test failed. Logs: `~/pg_quality/candd/final_fast_e8a0817e.log`,
`flutter_nutrition_contract_e8a0817e.log`, and `flutter_make_test_e8a0817e.log`.
This is a verified local candidate only: no merge, push, catalog promotion or
release was performed.
