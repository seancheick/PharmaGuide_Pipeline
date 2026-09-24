# Task 2 — shared identity and benchmark exposure

Local engineering checkpoint only. No catalog regeneration, export, publication, or release was performed.

Ported to `v41-recovery` from redesign 38406274. This file describes the v41 implementation; the redesign's own replay is kept below as history.

## Contract (v41)

- **One exposure owner.** `scoring_v4/exposure.py` returns an immutable `Exposure`: basis, unit, per-serving amount, daily bounds, source path, defaulted-frequency flag, quantity operator, `uncertainty`, and `benchmark_amount`.
- **Dose always scores an amount.** `benchmark_amount` is the label's stated number at the resolved daily range. A qualified amount ("<1 g") keeps its stated number; a label with no daily frequency uses one serving a day (`serving_frequency.resolve_daily_serving_range`, unchanged from main). The qualifier and the defaulted frequency are recorded in `uncertainty` / `frequency_defaulted` as provenance and never turn Dose into 0 or "not evaluable". `exact` is true only when nothing is uncertain.
- **Unresolved amounts are held back, not scored.** When a row's quantity columns conflict and none is selected (`quantity_operator: ambiguous`), or a nutrition scalar disagrees with its source row (`unknown`), there is no `benchmark_amount`, and the completeness gate records `unresolved_source_quantity`, so the product is NOT_SCORED and stays out of the live catalog until the source column is fixed upstream. Nothing public says "pending".
- **Caffeine.** Per use, never multiplied by servings a day; a qualified caffeine amount ("<200 mg") is scored on its stated number like any other qualified amount.
- **Daily versus per use.** Creatine, beta-alanine and HMB are benchmarked per day; caffeine per use. A creatine label whose directions describe a loading regimen (`serving_frequency.has_loading_protocol`: explicit loading wording, or a defined first period followed by maintenance) earns full credit up to 20 g/day, the reviewed NIH ODS loading amount; workout timing, as-needed use, cycling or "phase" names alone do not. Fiber is benchmarked per day, from the nutrition-facts dietary fiber when the label declares it, otherwise from reviewed fiber rows.
- **Directed ranges.** Adequacy uses the maximum directed daily use (`daily_interval_selection: maximum_directed_use`), the pipeline's existing policy. A minimum-versus-maximum shadow comparison is reported separately; the policy is unchanged until that report is reviewed. UL/safety always uses maximum exposure.
- **Fiber identity.** `route_features.is_fiber_row` is the one fiber predicate: a reviewed canonical fiber identity or verified PHGG. Category text ("fibers") is not identity, so glucosamine tagged `fibers` no longer counts.
- **Routing.** Definite material fiber or verified PHGG is not its own competing non-digestive claim; dual-purpose beta-glucan/prebiotic claims still compete without explicit digestive intent.
- **Not ported (held policy).** The redesign's P6 missing-frequency policy and its "qualified amount certifies no credit" rule.

Basis sources checked during the task: [NIH ODS exercise fact sheet](https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/) and [21 CFR 101.81](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-101/subpart-E/section-101.81). These support distinguishing daily versus per-use exposure, not a wholesale validation of old score bands.

## v41 measurement

**Arms.** Before = `v41-recovery` at 7b031050 (pre-Task-2). After = the Task 2 tree (base 9f7ff8da plus working diff sha1 `d58012651797`, unchanged from start to end of the run). Both arms ran the production entry points (`clean_dsld_data.py` → `enrich_supplements_v3.py` → `score_products_v4.py`) through `audits/quarantine_triage_20260919/drive_pipeline_ab.py`, compared by `compare_scored_arms.py`. Both tools were extended in this task with route, eligibility, identity and exposure projections.

**Affected-product cohort (2,507 raw labels, 35 brands, all 7 routes).** Selection reasons per product are recorded in `~/pg_quality/recon/t2_cohort.json`: fiber/sports route or daily-exposure actives, fiber identities and fiber titles, the 212 products with an enrichment override of a cleaner UNII identity, 58 raw labels with conflicting quantity operators, the 51 redesign route-change products, 30 reference cases, the four targeted labels, and a seeded control of up to 25 products per route from brands outside the four-brand diagnostic.

| Result | Count | Review |
|---|---:|---|
| Records compared, errors | 2,507, 0 | |
| Score changes | 159 (128 up, 31 down) | 50 belong to reviewed route changes |
| Route changes | 53 | 51 = the reviewed fiber → generic table below; 2 = FiberSMART quarantine |
| Verdict changes | 26 | 12 reviewed route changes; 2 FiberSMART → NOT_SCORED; 12 POOR → SAFE from daily exposure (e.g. "Daily Fiber" 1-3 × daily) |
| Quarantine entries / eligibility changes | 2 / 2 | 233404 and 233406, intentional (FiberSMART unmapped active) |
| Quarantine exits, safety changes | 0, 0 | |
| Identity changes | 64 products | Oat Bran → `oat_bran` (UNII + literal or reviewed parent link), Cayenne, Coconut Water, *S. cerevisiae*; same-canonical `taxonomy_only` → `clean` label changes (L-arginine, L-glutamic acid, citrus bioflavonoids; score-neutral); FiberSMART → unmapped |
| Bookkeeping-only | 627 | only the new Dose exposure metadata |

Decreases outside route changes, each read against the raw label: 321360 and 273824 (−20.6, −17.3: a 16.25 g whole-food blend was credited as 16.25 g fiber on a label with 8 g total carbohydrate); 287495 (−4.8: label fiber 1 g × 2 servings, previously carbohydrate + fiber + blend summed); 28491 (−4.0: a blend member inherited the blend weight); 278325 (−1.4: whole-food "Flax seed Fiber" is not a fiber identity, as the redesign review recorded); 331630 (−0.8: "prebiotic" text was counted as fiber).

Regressions found by the cohort and fixed before acceptance: creatine loading labels (DSLD prints the loading servings as the daily maximum; 7 products) now use `serving_frequency.has_loading_protocol` and are bounded to the reviewed NIH loading amount (≤ 20 g/day); a first "contingent → minimum" attempt was reverted after it hurt Beta-Alanine 3200 and Thisilyn Daily Cleanse. `oligosaccharides` joined the fiber identities (prebiotic, not material). After the final cohort run, the loading band was bounded to ≤ 20 g/day and the FiberSMART receipts were tightened; those were validated on every cohort creatine product above 10 g/day (the same 7, all 20 g/day, Dose 20) and on 233404/233406 (NOT_SCORED).

**Min-vs-max shadow (report only; policy unchanged).** All 3,704 raw labels with a directed daily range, enriched once and scored at the maximum and at the minimum directed daily use: 0 errors; 77 score differently (65 fiber, 12 sports); maximum is higher by 6.6 on average (0.8 to 12.0); 10 would move SAFE → POOR at the minimum. Adequacy stays at the maximum; UL/safety already uses the maximum (`enrich_supplements_v3.py` `amount_for_ul = per_day_max`).

**Follow-up (not changed here).** DSLD blend rows with a positive quantity, no children and no canonical: 2,961 rows on 1,873 frozen products; 1,735 are named like blends (opaque proprietary blends needing separate handling) and 212 like a single item (mostly marketing blend names, a few single branded ingredients such as Sytrinol, Oligonol, VitaBerry). FiberSMART was resolved on its own (separate commit). "FiberSmart"-style single branded rows need per-entry review before any global rule.

**Tests.** Full `scripts/test.sh fast` on the final tree (after the loading bound and receipt fixes): 16,267 passed, 0 failed. Real-label fixtures cover Oat Bran (293400, 293280), the boulardii control (306383) and FiberSMART (233404, 233406), so CI runs them without the local staging directory.

**Receipts (SHA-256, under `~/pg_quality`).**

| Artifact | SHA-256 |
|---|---|
| `t2_cohort_ab/before/scored_records.jsonl` | `37d164c467dbacd7cbba86a290ca1c46dc4daa3040b3cc832faa642e4542e2c5` |
| `t2_cohort_ab/final/scored_records.jsonl` | `b7857c306d57c5d5d9fe4ae03bab82882ae63b3f5065d715a860d0b844fdd6b8` |
| `t2_cohort_ab/scored_diff_final.json` | `fbaea856c7610ffc13ca4a52a172d00fd82c003269047e86db3ae07d49683280` |
| `recon/t2_cohort.json` | `c14f856592a29bbd143bf14f7a67a34e172664c3996f7e0988ee9d9dcc0282b0` |
| `recon/t2_shadow_minmax.jsonl` | `ca1d08de230aca51e26568b884b7f854cea82ba89540ba1ca10a96b8df65d135` |
| `recon/childless_blend_census.txt` | `bb2d25a54f5d164f9f69ef14c14924d6f4ce1c7b919137701260448d8006aa42` |

The single full 15,421-product comparison runs once, after A13, A15, A16, A17 and P4 are integrated.

## History: redesign replay (branch codex/product-quality-redesign)

Recorded on the redesign branch before the port. Its receipts lived under `/tmp/pg_quality` and were lost in the 2026-09-24 reboot; the counts below are not reproducible from this branch and describe the redesign's behavior, including the qualifier/frequency rules v41 did not port.

### Accepted frozen-corpus replay (redesign)

- 15,421 products; zero scorer errors; source and HEAD unchanged throughout capture.
- 1,202 diagnostic records changed; 184 total scores changed; 51 routes changed. No status changes.
- Exact captured `reasons.safety_gate` and `reasons.dose_safety` equality for all 15,421 products. The replay has no independent top-level verdict field; no wider verdict-parity claim is made.
- Total-score delta range: -22.6 to +15.7. Changed-score scope: fiber_digestive → fiber_digestive: 108, fiber_digestive → generic: 50, sports → sports: 26.
- 457 products carry daily exposure. 160 have frequency/range/uncertainty affecting that exposure ({'fiber_digestive': 102, 'sports': 58}). 52 retain the same total; 54 retain the same raw Dose dimension, including 1 already at its 25-point cap. Every affected exposure, including these unchanged cases, is retained in the detailed ledger.
- 7 affected products have unknown daily frequency (33 row exposures); 152 row exposures retain a variable daily interval.

Diagnostic-record scope: 908 sports records, 233 records retaining fiber/digestive, 51 fiber/digestive → generic, and 10 omega records. Each omega difference is only `dose.metadata.servings_defaulted: false → true`; all other captured fields, including pillars, evidence/formulation outputs, route, and totals, are identical.

All 160 affected exposure cases were checked against their actual strict source row or nutrition field, canonical frequency, normalized amount, and arithmetic daily bounds. The exhaustive case classification is **28 fixed multiple-serving regimens, 125 directed ranges, and 7 unknown-frequency products**. Effects partition all 160: **106 raw-Dose/total changes, 52 unchanged raw rubric components/penalties and unchanged totals, and 2 unchanged raw-Dose cases with formulation-only changes**. No cases were omitted as merely capped or unchanged.

The latter two are 278325 PureLean Fiber (71.8 → 70.4) and 63293 Fiber-Immune Support (65.8 → 64.4; raw Dose remains capped at 25). In both, the existing `fiber_formula_focus` component changes 5 → 3 as fiber rows change 5 → 3. Strict membership excludes aggregate/unreviewed canonical identities (`proprietary_fiber_blend`, `fiber_unspecified`) and whole-food `flaxseed` that previously qualified by text. Fiber source class/quality and dose components remain unchanged. No new formulation formula or threshold was introduced.

All route changes below were reviewed against strict canonical rows and claim roles. Each has a prominent nonfiber owner, so material fiber alone no longer chooses the fiber/digestive adapter. This is a conservative generic fallback, not validation of a new clinical purpose.

| ID | Product | Total before → after | Prominent nonfiber owner(s) |
|---|---|---:|---|
| 17226 | Super Greens | 55 → 58.5 | super_greens_digestive_enzyme_blend, super_greens_probiotic_blend, super_greens_whole_food_blend, super_greens_herb_blend, super_greens_vegetable_blend, super_greens_fruit_blend, super_greens_mushroom_blend |
| 36250 | Control & Reduce Fruit Punch | 51.7 → 52 | garcinia_cambogia |
| 178716 | Organic Greens Original Flavor | 63.5 → 47.7 | superfood_greens_herbal_blends, couch_grass, beet |
| 178733 | Organic Greens Natural Chocolate Flavor | 60.3 → 37.7 | superfood_greens_herbal_blends, cocoa, beet |
| 202690 | Renewable Energy Pomegranate, Berry & Beet Flavor | 51.1 → 40.1 | organic_energy_and_electrolyte_blend, pii_corn_starch, pomegranate |
| 204605 | Elderberry Immune Syrup | 53 → 50.7 | elderberry, organic_immune_blend, aronia |
| 204665 | Turmeric Boost | 48.6 → 46.5 | organic_boost_blend, turmeric |
| 204676 | Turmeric Gummy | 47.8 → 49.3 | turmeric |
| 204739 | Raw Organic Perfect Food Green Superfood Chocolate | 59.6 → 61.5 | organic_u_s_a_farmed_green_juice_blend, barley_unspecified |
| 208540 | Good as Gold. | 40.4 → 31.9 | ora_good_as_gold_blend, mct_oil |
| 208543 | Good as Gold. | 40.4 → 31.9 | ora_good_as_gold_blend, mct_oil |
| 214586 | Ipriflavone 200 mg | 57.3 → 56.8 | ipriflavone |
| 219865 | Slimvance Core Slimming Complex Raspberry Iced Tea | null → null | slimvance_patented_blend |
| 233340 | Kids Organic Elderberry with Vitamin C | 63.3 → 65.3 | vitamin_c, elderberry |
| 233668 | Raw Organic Perfect Food Green Superfood Chocolate | 59.6 → 61.5 | organic_u_s_a_farmed_green_juice_blend, barley_unspecified |
| 235592 | Organic Plant-Based Recovery Blackberry Lemonade Flavor | 57.7 → 64.1 | organic_antioxidant_recovery_blend, fruits |
| 235619 | Organic Plant-Based Energy + Focus Blackberry Flavor | 46.6 → 47.6 | organic_antioxidant_energy_blend, baobab |
| 236845 | Organic Plant-Based Energy + Focus Blackberry Flavor | 46.6 → 47.6 | organic_antioxidant_energy_blend, baobab |
| 236853 | Organic Plant-Based Energy + Focus Blackberry Cherry Flavor | 54.3 → 55.9 | organic_antioxidant_energy_blend, baobab |
| 236855 | Organic Plant-Based Energy + Focus Blackberry Cherry Flavor | 54.3 → 55.9 | organic_antioxidant_energy_blend, baobab |
| 243271 | Golden Milk | 55.8 → 45.7 | organic_golden_milk_blend, turmeric |
| 250775 | Relax + Calm Magnesium Soft Chews Grape Flavor | 60.6 → 67.4 | magnesium |
| 259854 | Good as Gold. | 45.4 → 32 | ora_good_as_gold_blend, mct_oil |
| 259855 | Renewable Energy. Raspberry Lemonade | 44.9 → 32.3 | organic_energy_and_electrolyte_blend, nha_sugar_sweeteners |
| 259856 | Renewable Energy. Beet & Pomegranate | 46.8 → 31.8 | organic_energy_and_electrolyte_blend, pii_corn_starch, pomegranate |
| 259883 | Aloe Gorgeous Double Fudge Chocolate | 52.1 → 54 | ora_organic_aloe_gorgeous_blend, aloe |
| 259884 | Aloe Gorgeous Peanut Butter | 48.7 → 48.3 | ora_organic_aloe_gorgeous_blend, aloe |
| 259885 | Aloe Gorgeous Vanilla | 51.7 → 51.3 | ora_organic_aloe_gorgeous_blend, aloe |
| 259891 | Renewable Energy. Ceremonial Matcha | 32 → 39.5 | organic_energy_and_electrolyte_blend, green_tea_extract |
| 273729 | Elderberry & Sleep | 47.4 → 44.9 | elderberry, organic_herbal_sleep_blend, lemon |
| 273756 | Fermented Organic Turmeric Booster | 47.7 → 47.8 | organic_booster_blend, sweet_orange |
| 274355 | Vitamin D3 20 mcg (800 IU) Orange Flavor | 64.7 → 70.1 | vitamin_d |
| 274418 | Elderberry Immune Syrup | 53 → 50.7 | elderberry, organic_immune_blend, acerola_cherry |
| 274428 | Golden Milk | 55.8 → 45.7 | organic_golden_milk_blend, turmeric |
| 274561 | Turmeric Gummy | 55.3 → 56.8 | turmeric |
| 274826 | Organic Plant-Based Energy + Focus Blackberry Cherry | 67.2 → 68.9 | organic_antioxidant_energy_blend, baobab |
| 275464 | Fitbiotic Weight Management 50 Billion Guaranteed Unflavored | 63 → 45.1 | raw_fitbiotic_blend |
| 277520 | Kids Elderberry & Sleep | 52.5 → 50 | elderberry |
| 278416 | Raw Organic Perfect Food Green Superfood Juiced Greens Powder Apple | 59.6 → 61.5 | organic_u_s_a_farmed_green_juice_blend, barley_unspecified, fruits |
| 282638 | Raw Organic Perfect Food Green Superfood Juiced Greens Powder Original | 59.6 → 61.5 | organic_u_s_a_farmed_green_juice_blend, barley_unspecified |
| 297661 | Elderberry Immune Syrup | 53 → 50.7 | elderberry, organic_immune_blend, acerola_cherry |
| 297681 | Magnesium with Pre & Probiotics Gummies Raspberry Flavor | 70.3 → 68.2 | magnesium |
| 306368 | Organic Greens Unflavored | 61.2 → 53 | superfood_greens_herbal_blends, couch_grass |
| 311680 | Organic Greens Mixed Berry | 61.2 → 53 | superfood_greens_herbal_blends, couch_grass |
| 326696 | Raw Organic Perfect Food Green Superfood Juiced Greens Powder Original | 61.6 → 63.5 | organic_u_s_a_farmed_green_juice_blend, barley_unspecified |
| 326702 | CoQ10 150 mg Gummies Strawberry Flavor | 57.6 → 52.7 | coq10, strawberry |
| 326706 | Gummies Vitamins D3 50 mcg (2,000 IU) & K2 100 mcg Raspberry Lemon Flavor | 48.8 → 55.6 | vitamin_d |
| 326761 | Magnesium with Pre & Probiotics Gummies Peach Flavor | 70.3 → 68.2 | magnesium |
| 327406 | Perfect Food Original Super Green Formula | 53.8 → 55.1 | perfect_green_juice_blend, perfect_whole_food_matrix, perfect_veggie_juice_blend, barley_unspecified, rice_bran, cabbage_extract |
| 327579 | Relax + Calm Magnesium Soft Chews Grape Flavor | 60.6 → 67.4 | magnesium |
| 328846 | Melatonin 3 mg Strawberry Flavored | 61.2 → 63.7 | melatonin |

Positive control: 62810 LuraLean retains its fiber/digestive route. The original full-corpus review caught its erroneous demotion when the competitor feature counted fiber itself; the accepted capture includes the corrected material-fiber predicate and dual-purpose safeguards.

### Source-quantity verification and limitations (redesign)

- Fresh normalization of the real raw DSLD 214586 source preserves dietary fiber `<1 g` at `ingredientRows[0].nestedRows[0]`; enrichment summary and shared exposure retain the operator and directed three-times-daily interval (upper bound `<3 g/day`). [Not ported to v41: v41 scores the stated amount and records the qualifier.] It remains unassessable for exact-band credit. The minimal committed regression uses the same raw shape without depending on an absolute data path.
- Frozen enriched 214586 had already lost `<` and stored scalar `1 g`; frozen replay cannot recover that sign. Historical unqualified scalars retain the established shared semantics. Regenerate cleaner/enrichment outputs before relying on the new qualifier chain in shipping data.
- 275464 Fitbiotic has probiotic title intent but its frozen typed payload has no CFU, named strain, or probiotic-product evidence. Its generic fallback avoids inventing 50 billion CFU from the title; intended-purpose validation remains an upstream/rulebook task.
- [Not ported to v41] Unknown daily frequency produces explicit `not_evaluable` metadata and no effective daily-band credit internally. Public partial/null presentation is a later task; this checkpoint must not be published as a completed clinical score redesign.
- Variable intervals remain fully represented, and the scorer selects maximum directed use (v41: unchanged pending the min/max shadow comparison). Whole-interval policy and purpose-specific clinical thresholds remain later tasks. Unsupported course duration is not invented.

### Verification (redesign)

One consolidated invocation of `scripts/test.sh fast` over 16 distinct affected test files: **454 passed, 1 skipped** in 25.59 seconds. The sole skip requires local enriched output absent from this worktree. Earlier overlapping test runs are not added to this count. Full suite/release gates were not run.

Test files: `test_quality_exposure_identity.py`, `test_phgg_formulation_identity.py`, `test_serving_basis_daily_servings.py`, `test_v4_fiber_digestive_module.py`, `test_v4_sports_dose_p171.py`, `test_v4_sports_dose_preworkout_actives.py`, `test_nutrition_panel_complete_capture.py`, `test_nutrition_facts_extended.py`, `test_malformed_row_containment.py`, `test_submission_review_nutrition.py`, `test_v4_sports_router_p170.py`, `test_v4_sports_final_assembly_p172.py`, `test_interaction_serving_frequency_unified.py`, `test_serving_frequency_audit.py`, `test_v4_sports_protein_formulation.py`, `test_enrichment_regressions.py`.

Independent spec and quality reviews approved the final patch, including both dual-purpose rejection and positive definite-fiber/PHGG controls.

### Reproducibility receipts (redesign, lost)

- Capture HEAD: `629ac0beb776ec55e59528db8c3388d56abed06c`.
- Source unchanged: `true`; capture exit: `0`; expected/actual products: `15421/15421`.
- Input manifest SHA-256: `7f6a11e5a46c817176418a898dd19dac5696a2d8a9e597c5fd489e3007d2818e`.

Full detailed JSON remains under `/tmp/pg_quality`; accepted artifacts and exact SHA-256:

| Artifact | SHA-256 |
|---|---|
| `baseline.jsonl` | `047478177666a3992e72ec3f2230487e7396ff1dab22b2c0a039d37e3e2dcf2a` |
| `task2-reviewed.jsonl` | `e519a3dcc4e745a0607dce6bd5953d88be6a62745b2679b0ef5771b8e3315fc2` |
| `task2-reviewed.jsonl.meta.json` | `19f02b7483e32aa149c3eb7d3f1ec6c1ab464cdba1fccde0aa2825eb391b0a59` |
| `task2-reviewed-audit.json` | `af91ca0683c4295bde0d15c0a725364a141877657df3151ddcf24f013adb91e1` |
| `task2-reviewed-analysis.json` | `6979de37885e66f07bcb65504cb1ae6c8cf382ac7aed8542c2068cdb67ee6a18` |
| `task2-route-owner-review.json` | `25aca12245206e84fe126bbdcee7bc6ff2ea2745a70b83157cce40a8df3dc597` |
| `task2-214586-quantity-receipt.json` | `f7b08a6288f19347d52ce2bca5238b0fb6e9aa86bb4446ee313684ca85e98d61` |
| `task2-focused-tests.log` | `5462714598d3b061799079e0129f398688674c321b5142d9f62cc43b46c1df79` |
| `task2-exposure-case-classification.json` | `45d7560167bf930a631f5a2ff96e1e0b5116ebf7566b9099a4997df64e5a80c5` |
| `task2-omega-metadata-review.json` | `a16dea7d39bd92927909bcc81640505e4ba6b52d35a04e53c31f1f8c6e15c420` |
| `task2-reviewed-full-diff.json` | `2d3b0cc44a63d08657b18508904e3fb4034a562404ece350dbacee0af85b610e` |
