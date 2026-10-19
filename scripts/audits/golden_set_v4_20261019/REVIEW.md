# v4 golden set proposal — canary_products.json (October 19, 2026)

**Status: APPROVED by Sean on 2026-10-19 (D1 schema, D2 ±5 tier band, D3 the 18 additions,
D4 211448 class unchanged, D5 F1/F2 kept as failing expectations) and APPLIED to
`scripts/data/canary_products.json` (schema 1.1.0, 53 canaries).**

Apply evidence:
- `proposal.py --apply`: 517 checks, 2 failures (F1 and F2, as approved).
- `data_batch.py check --since origin/main --expect canaries[0..52]`: 53 entries changed (35 modified,
  18 added), 0 problems. No pre-existing curated field value changed; the original order is kept.
- `scripts/test.sh fast test_pipeline_integrity.py test_v4_canary_coverage.py test_iqm_vinpocetine_entry.py test_ci_skip_guard.py`:
  85 passed, 1 skipped (the catalog-presence test skips without a local build).
- With `PG_RELEASE_CANDIDATE_ROOT=reports/dose_v41_release_audit_20261019/catalog_candidate`,
  `test_v4_canary_coverage.py` ran 13 tests and all passed, including that test (all 53 are in the
  candidate catalog).

Lane: branch `claude/epic-mayer-1cf186`. The Dashboard v4 Coverage & Calibration page
(branch `claude/dashboard-v4`) reads the result and raises a finding whenever a canary breaks
an expectation.

## What this proposes

1. **Expectations for all 35 existing canaries** plus **18 new real products**, for **53** in
   total. Every expectation states behaviour, not a brand ranking, and cites its owner.
2. **Seven flat fields per canary**, following the existing `expected_*` naming.
   `expected_quality_score_status` already exists on 294063 and is reused.
   - `expected_v4_module`: the route (artifact `_v4_module`).
   - `expected_quality_score_status`: scored, not_scored or suppressed_safety.
   - `expected_quality_assessment_status`: complete or partial.
   - `expected_product_safety_status`: no_known_catalog_concern, caution or blocked.
   - `expected_quality_tier_band`: `[lowest, highest]` tier, or null when there is no score.
   - `expected_pillar_invariants`: ids from `_metadata.golden_set.pillar_invariants`.
   - `allowed_movement_reasons`: ids from `_metadata.golden_set.movement_reasons`.
3. **A `_metadata.golden_set` block** with the following:
   - one owner citation per expectation field;
   - the invariant catalog, each entry with a rule, an owner (path::symbol or a
     quality_score.json key) and machine checks (`[path, op, value]` over one scored product,
     so the dashboard can evaluate them without its own copy of the logic);
   - the movement-reason vocabulary.

   It also bumps `schema_version` 1.0.0 → 1.1.0 (namespace 1 is fixed by `reference_data_schema.py::_SCHEMA_V1_FILES`; the fields are additive), adds the primary class `b_complex` and sets
   `last_updated` to 2026-10-19.
4. **Preserved:** every curated field, including `v3_shipped_*`, the legacy B5/dose-route
   fields, and `expected_safety_verdict` on 294063. New entries carry
   `v3_shipped_score/verdict = null` because they are not in the v3 baseline.

## How it was checked

- **Production path:** Score stage `score_supplements_v4.py::score_product_v4` →
  `scoring_v4/scored_artifact.py::build_scored_artifact`.
- **Artifact layer:** `scripts/products/output_*_scored/scored/scored_cleaned_batch_*.json` in
  the main checkout. That is 15,426 products from run `20261019T070203540018Z`, using
  quality_score.json `1.29.1-dose-v41-omega-integration` on main e6f2dd103.
- **Catalog presence:**
  `reports/dose_v41_release_audit_20261019/catalog_candidate/final_db_output/pharmaguide_core.db`.
  All 53 canaries are in `products_core`, including the 3 blocked ones, which ship with their
  reason.
- **Reproduce:**
  `source scripts/python_env.sh; "$PG_PYTHON" scripts/audits/golden_set_v4_20261019/proposal.py`.
  This writes `proposed_canaries.json` (the full proposed file), `evaluation.json` (517 checks)
  and `review_tables.md`.
- **Result:** 517 checks, **515 pass and 2 fail**. Both failures are real findings (F1 and F2
  below). The expectations were not bent to fit the current score.
- **Adversarial check:** I injected six breaks into copies of real artifacts:
  - Verification moved off its neutral;
  - Dose raised above the UL ceiling;
  - a BLOCKED product given a number;
  - an applicability gap reworded as "no qualifying research";
  - a tier moved outside its band;
  - a second ceiling receipt entry.

  Each break was flagged, along with the pillar-sum mismatch the injected Dose value caused.
- **Tier band rule:** the band holds every tier reachable within ±5 points of the reviewed score,
  using display rounding. It is a drift tolerance, not policy. Moving outside the band requires
  an allowed movement reason. The status fields and pillar invariants are the policy part.

## Decisions for Sean

- **D1. Approve the schema.** That covers the seven flat fields, the `golden_set` metadata
  block, and the checks being declared in data so the dashboard evaluates them without a second
  copy of the logic.
- **D2. Approve the ±5-point tier band rule** above.
- **D3. Approve the 18 additions** in the table. They fill the gaps the current set does not
  exercise:
  - **No canary is currently blocked.** The three v3 BLOCKED canaries are now SAFE or CAUTION
    and scored. The proposal adds three blocked products:
    - 18924, partially hydrogenated oils (PHO);
    - 220094, brominated vegetable oil (BVO);
    - 252358, NON_ROUTINE_CHELATOR, a different blocking reason that also proves a block
      wins over the completeness gate.
  - **No b_complex route.**
  - **No Dose-zero UL case.**
  - **No caffeine ceiling.**
  - **No pending-Evidence partial.**
  - **No reviewed-zero Evidence.**
  - **No adult completeness-gate product.**
- **D4. 211448 Equate Glucosamine** (`primary_class: blocked_verdict`, subclass
  `blocked_unexpected`). The old v3 block came from titanium dioxide, a watchlist excipient.
  Current policy informs and deducts but never blocks (`clean_label_subscale`), and the canary
  now pins that as `watchlist_excipient_not_blocking`. The option is to move it to
  `primary_class: specialty` with subclass `watchlist_excipient_former_block`. That is not in
  the proposed file. With the three new blocked canaries, `blocked_verdict` stays covered
  either way.
- **D5. Keep F1 and F2 as failing expectations.** The dashboard would show them red until they
  are fixed at their owners. The other option is to drop that invariant from those two
  canaries. My recommendation is to keep them, because a canary that is green on a known defect
  hides it.

## Findings (expectations that fail on the current candidate)

### F1. A single-active label with a resolved evidence owner is reported as "nothing to assess"

| | |
|---|---|
| Canary | 294063, Pure Encapsulations Vinpocetine 20 mg |
| Artifact | `quality_pillars_v4.evidence.evidence_result_state = no_assessable_actives` |
| Display state | `not_applicable` |
| Shown text | "No active ingredient on this label could be assessed for clinical evidence." |
| Assessment status | `complete` |
| Driver field | `_v4_module_breakdown.dimensions.evidence.metadata.evidence_owner_canonicals = ["vinpocetine"]` |

The label's one active has a verified IQM identity and an evidence owner. Under
`quality_score.py::evidence_display_state`, `not_applicable` means "nothing on this label to
assess", which contradicts that. The honest states would be one of these:

- a review conclusion (`evaluated_*` or `no_qualifying_human_evidence`);
- pending (`clinical_review_not_covered`), which makes the assessment `partial`.

**Corpus scope** (one bounded pass over all 15,426 scored artifacts): 545 products are in
`no_assessable_actives`. 524 of them carry a non-empty `evidence_owner_canonicals`.

- Many of those owners look legitimately non-efficacy, for example flavours, `protein`,
  `fiber` and excipients.
- Others are efficacy actives, for example `dhea` (28), `yohimbe` (19), `cascara_sagrada`
  (19), `7_keto_dhea` (12) and `vinpocetine` (2: 294063 and 295535).

**Likely seams:**
- `scripts/scoring_v4/modules/generic_evidence.py`: `_assessable_active_ingredients` →
  `scoring_input_contract.get_assessable_evidence_ingredients`;
- or `result_state_for_disposition`, where `NOT_EFFICACY_RELEVANT` maps to
  `no_assessable_actives`.

**Confidence:** high that the state contradicts the display doctrine for vinpocetine. The
corpus split between legitimate and defective cases has not been classified.

**Not fixed here.** This lane owns only the canary file. The fix belongs to the Evidence owner
in a separate task.

### F2. A branded single-ingredient extract (Prosterol, saw palmetto) is read as a blend header

| | |
|---|---|
| Canary | 269286, Doctor's Best Saw Palmetto 320 mg |
| Label row | `name "Prosterol"`, `standardName "Saw Palmetto"`, 320 mg, `canonical_id saw_palmetto` |
| Cleaner role | `cleaner_row_role = blend_header_total` |
| Quality-data identity | `ingredient_quality_data` → `BLEND_GENERAL` |
| Score status | scored, `partial` |

Downstream, every pillar treats the label as a blend:

- **Formulation 0:** "Botanical identity could not be confirmed".
- **Dose 0:** "The blend total is disclosed, but individual ingredient amounts aren't". The
  label has no blend.
- **Evidence:** `no_assessable_actives`.
- **Result:** the public score is 31.0 (Poor).

The `partial` status is honest, but the root cause is the cleaner's role classification of a
branded extract name. 269589 is the same product.

**Confidence:** high on the trace. The fix owner is the cleaner role classifier
(`scripts/enhanced_normalizer.py`), in a separate task.

## Observations (recorded, not asserted as expectations)

- **74124 Nordic Prenatal DHA** and **184421 PE Digestive Enzymes** now route to `omega` and
  `fiber_digestive`. The legacy `expected_b5_class` (`generic`) is a different, B5-era field and
  is kept. `expected_v4_module` carries the v4 route.
- **288740 Nordic Ultimate Omega + CoQ10** gets an Evidence applicability gap (0/20), while
  ordinary fish oils get 10.4. The applicability-gap invariant holds. Whether the CoQ10
  companion should take the omega Evidence headline was not investigated, so it is not asserted
  as a defect.
- **24809 vs 184058:** both are 125 mcg D3 per softgel. The directed maximum daily use (250% vs
  125% of the UL) puts them in different ceiling bands (Dose 0 vs 10). That is intended Dose
  V4.1 D1 behaviour, so both are kept as a pair.
- **306381 vs 308247:** two DSLD versions of the same pre-workout (300 vs 600 mg caffeine/day
  at maximum use). Only the 600 mg version reaches the caffeine ceiling.

## Apply procedure (done 2026-10-19)

1. Set `_metadata.golden_set.approval` to Sean's recorded decision and apply D2/D4/D5 choices
   in `proposal.py`.
2. Run `proposal.py --apply`. It writes through `data_batch.load/save`; `--apply` refuses
   while approval reads PENDING.
3. Run `data_batch.py check scripts/data/canary_products.json --since origin/main --expect
   <53 dsld_ids>`.
4. Run `scripts/test.sh fast scripts/tests/test_v4_canary_coverage.py
   scripts/tests/test_iqm_vinpocetine_entry.py scripts/tests/test_ci_skip_guard.py`.
5. Commit on this branch only.

**Consumers checked (Owner Check):**
- `scripts/tests/test_v4_canary_coverage.py`: REQUIRED_FIELDS present on all 53, no undeclared
  or empty classes, all B5 routes covered, largest class 9/53 (17%), no duplicate ids.
- `scripts/tests/test_iqm_vinpocetine_entry.py`: the 294063 subclass,
  `expected_safety_verdict` and `expected_quality_score_status` are unchanged.
- `scripts/api_audit/v4_canary_report.py`: tolerates a null `v3_shipped_score`
  (`_num(...) is not None` filter).
- `scripts/audit_raw_to_final.py::_load_current_canary_set`: subclass keys are unique.
- `scripts/reference_data_schema.py`: lists the file name only.

## Required route coverage

| Behaviour | Canaries |
|---|---|
| Omega, ordinary | 327776, 203390 (new, unverified) |
| Prenatal | 328830, 178711 (new), 274081 (prenatal probiotic), 74124 (prenatal DHA, omega route) |
| Probiotic | 1650, 178346, 274081, 250851 (new) |
| Botanical | 305203, 82300, 302651, 255449, 183275, 202811 (new), 209389 (new), 269286 (new) |
| Sports | 306381, 308247 (new), 2722, 268690, 325587, 269425, 229913, 274376 |
| Multivitamin | 173888, 173918, 256977 (new), 256962 (new, not_scored), 178520 (not_scored, pediatric hold) |
| B-complex | 239458 (new), 278523 (new) |
| Blocked (suppressed_safety) | 18924, 220094, 252358 (all new) |
| CAUTION and still scored | 184058, 232923, 294063, 278523, 24809, 25539, 256977, 308247 |
| Unverified (neutral 6) | 184058, 178346, 82300, 302651, 255449, 211448, 239458, 278523, 25539, 239467, 203390, 178711, 202811, 209389, 269286 |
| Evidence applicability gap | 1650, 178346, 288740, 204739, 202811 (new) |
| Evidence reviewed zero | 232923 (evaluated_null), 209389 (no qualifying evidence, new) |
| Evidence pending → partial | 239467, 212388 (new) |
| UL exceedance, Dose capped at 10 | 184058, 256977 (new) |
| UL exceedance, Dose 0 | 24809, 25539, 278523 (new) |
| Caffeine ceiling | 308247 (new); 306381 below the ceiling |
| Not scored | 178520 (pediatric dose-safety hold), 256962 (adult completeness gate, new) |

## Pillar invariants

| id | rule | owner |
|---|---|---|
| `tier_matches_display_score` | quality_tier is the configured tier of the public display score. | scripts/scoring_v4/quality_score.py::_tier, scripts/scoring_v4/quality_score.py display rounding (floor(x+0.5)); scripts/scoring_v4/config/quality_score.json tiers |
| `pillars_sum_to_score` | The six public pillars add up to quality_score_v4_100 (within rounding). | scripts/scoring_v4/quality_score.py::assemble_quality_score; scripts/scoring_v4/config/quality_score.json pillars |
| `verification_unknown_neutral` | Verification stays at the neutral 6/15 when no verification evidence is on file (unknown is not a penalty). | scripts/scoring_v4/quality_score.py::_pillar_verification; scripts/scoring_v4/config/quality_score.json verification_subscale.neutral_baseline |
| `verification_claim_or_brand_ceiling` | Label claims, own testing and reputation without independent verification stay at or below 8/15. | scripts/scoring_v4/quality_score.py::_pillar_verification; scripts/scoring_v4/config/quality_score.json verification_subscale.tier_ceilings.claim_or_brand |
| `verification_manufacturing_ceiling` | Verified facility or brand-scoped evidence without product-level certification stays at or below 10/15. | scripts/scoring_v4/quality_score.py::_pillar_verification; scripts/scoring_v4/config/quality_score.json verification_subscale.tier_ceilings.manufacturing |
| `verification_product_floor` | Registry-backed product-level certification earns at least 11/15. | scripts/scoring_v4/quality_score.py::_pillar_verification; scripts/scoring_v4/config/quality_score.json verification_subscale.product_level_floor |
| `dose_unbenchmarked_neutral` | A disclosed amount with no applicable benchmark takes the shared Dose neutral 11.4, never a studied-range claim. | scripts/scoring_v4/config/quality_score.json dose_subscale.unbenchmarked_neutral_public |
| `dose_ul_partial_ceiling` | A confirmed UL exceedance above 100% and below 150% at maximum directed daily use caps public Dose at 10. | scripts/scoring_v4/dose_safety.py::DoseSafetyResult.dose_ceiling; scripts/scoring_v4/config/quality_score.json dose_safety_ceiling.exceeds_above_pct/zero_at_pct/partial_ceiling_public |
| `dose_ul_zero_ceiling` | A confirmed UL exceedance at or above 150% at maximum directed daily use sets public Dose to 0. | scripts/scoring_v4/dose_safety.py::DoseSafetyResult.dose_ceiling; scripts/scoring_v4/config/quality_score.json dose_safety_ceiling.zero_at_pct |
| `dose_caffeine_zero_ceiling` | Declared caffeine of 600 mg/day or more at maximum directed daily use sets public Dose to 0 through the same ceiling. | scripts/scoring_v4/dose_safety.py::DoseSafetyResult.dose_ceiling; scripts/scoring_v4/config/quality_score.json dose_safety_ceiling.caffeine |
| `dose_caffeine_below_ceiling` | Declared caffeine at or below 400 mg/day at maximum directed daily use sets no Dose ceiling. | scripts/scoring_v4/config/quality_score.json dose_safety_ceiling.caffeine.exceeds_above_mg_day |
| `dose_ceiling_applied_once` | One product-level Dose ceiling, applied once after route aggregation (at most one ceiling receipt entry). | scripts/scoring_v4/config/quality_score.json dose_safety_ceiling (_doc: applied once after route aggregation and normalization) |
| `ul_exceedance_not_double_counted` | A UL exceedance is charged once in Dose; Safety/Hygiene says so instead of deducting again. | scripts/scoring_v4/quality_score.py::_pillar_safety_hygiene ('Not deducted here') |
| `evidence_applicable_assessed` | Reviewed applicable research is shown as an assessed Evidence result. | scripts/scoring_v4/quality_score.py::evidence_display_state (EVIDENCE_ASSESSED_STATES) |
| `evidence_authority_assessed` | Essential nutrients are assessed through established nutritional authority. | scripts/scoring_v4/quality_score.py::evidence_display_state; scripts/scoring_v4/modules/generic_evidence.py::authority_panel_result_state |
| `evidence_applicability_gap_not_no_research` | An Evidence applicability gap is shown as research that does not apply to this label, never as no research, and it is a completed conclusion. | scripts/scoring_v4/quality_score.py::evidence_display_state, scripts/scoring_v4/quality_score.py::_EVIDENCE_ZERO_REASON; scripts/scoring_v4/scored_artifact.py::UNASSESSED_EVIDENCE_DISPLAY_STATES |
| `evidence_reviewed_zero_is_assessed` | A reviewed null or no-qualifying-evidence result is an assessed conclusion, distinct from a pending review. | scripts/scoring_v4/quality_score.py::evidence_display_state (EVIDENCE_ASSESSED_STATES) |
| `evidence_pending_marks_partial` | An Evidence review PharmaGuide has not finished is shown as pending (not 0/20 research) and marks the assessment partial. | scripts/scoring_v4/quality_score.py::evidence_display_state (EVIDENCE_COVERAGE_GAP_STATES); scripts/scoring_v4/scored_artifact.py::_quality_assessment_status |
| `evidence_single_active_not_nothing_to_assess` | A label whose only active has a resolved evidence owner is never reported as having nothing to assess; it is reviewed or pending. | scripts/scoring_v4/quality_score.py::evidence_display_state ('not_applicable - nothing on this label to assess'); scripts/scoring_v4/modules/generic_evidence.py (evidence_owner_canonicals) |
| `omega_carrier_mass_not_epa_dha` | Fish-oil carrier mass never becomes EPA+DHA dose: undisclosed EPA/DHA earns no Dose credit. | scripts/scoring_v4/config/quality_score.json _metadata.description (1.10.1 omega label ownership); scripts/scoring_v4/modules/omega*.py |
| `suppressed_hides_score_keeps_reason` | A BLOCKED product ships with its reason and no public quality number or tier. | scripts/scoring_v4/quality_score.py::assemble_quality_score (hard safety failure first); scripts/scoring_v4/scored_artifact.py::_public_verdict; AGENTS.md 'Banned/recalled products always ship' |
| `safety_block_precedes_completeness` | A safety block wins over an incomplete-data gate: the product is BLOCKED, not NOT_SCORED. | scripts/scoring_v4/quality_score.py::assemble_quality_score (suppressed_safety before not_scored); scripts/scoring_v4/scored_artifact.py::_public_verdict |
| `not_scored_has_no_number` | A not-scored product carries no number, tier or pillars and an honest partial assessment. | scripts/scoring_v4/quality_score.py::assemble_quality_score; scripts/scoring_v4/scored_artifact.py::_quality_assessment_status |
| `unresolved_dose_safety_hold` | Material but unresolved dose safety (e.g. no reference for the label's age band) holds the product from scoring instead of guessing. | scripts/dose_assessment.py (pediatric_reference_gap); scripts/scoring_v4/dose_safety.py state material_but_unresolved |
| `caution_keeps_quality_score` | Quality and safety are separate outputs: a CAUTION product keeps its quality score. | scripts/scoring_v4/config/quality_score.json _metadata.description ('Quality tiers are independent of safety'); scripts/scoring_v4/scored_artifact.py::_product_safety_status |
| `high_risk_active_zeroes_safety_hygiene` | A confirmed high-risk active zeroes the Safety/Hygiene base while the product stays scored with CAUTION. | scripts/scoring_v4/quality_score.py::_pillar_safety_hygiene |
| `watchlist_excipient_not_blocking` | A watchlist excipient (titanium dioxide) informs and takes a small Safety/Hygiene deduction; it never blocks or forces CAUTION. | scripts/scoring_v4/config/quality_score.json clean_label_subscale; scripts/scoring_v4/quality_score.py::_clean_label_penalty |
| `unfinished_identity_marks_partial` | PharmaGuide's own unresolved identity marks the assessment partial instead of presenting a finished verdict. | scripts/scoring_v4/scored_artifact.py::unfinished_source_assessment; scripts/scoring_v4/scored_artifact.py::_quality_assessment_status |

## Canary expectations and current result

Status columns are expected values (a list means policy allows either). Current = tier and score on the reviewed run. Result = every check on that canary (statuses, band, global and pillar invariants).

| # | dsld_id | product | route | score status | assessment | safety | tier band | current | invariants | extra movement reasons | result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 202992 | Doctor's Best High Absorption CoQ10 100 mg with BioPerine | generic | scored | complete | no_known | Good–Very good | Good 79.4 | `verification_claim_or_brand_ceiling`, `dose_unbenchmarked_neutral`, `evidence_applicable_assessed` | verification_registry_change | PASS |
| 2 | 298074 | Thorne Magnesium Bisglycinate | generic | scored | complete | no_known | Very good–Exceptional | Excellent 91.6 | `verification_product_floor`, `evidence_applicable_assessed` | verification_registry_change | PASS |
| 3 | 184058 | Spring Valley Vitamin D3 5000 IU | generic | scored | complete | caution | Good–Very good | Good 78.1 | `dose_ul_partial_ceiling`, `dose_ceiling_applied_once`, `ul_exceedance_not_double_counted`, `caution_keeps_quality_score`, `verification_unknown_neutral`, `evidence_applicable_assessed` | safety_policy_change | PASS |
| 4 | 298053 | Thorne Vitamin K2 | generic | scored | complete | no_known | Good–Very good | Very good 82.8 | `verification_product_floor`, `evidence_authority_assessed` | verification_registry_change | PASS |
| 5 | 219203 | Solgar NAC 600 mg | generic | scored | complete | no_known | Needs improvement–Good | Needs improvement 67.8 | `verification_claim_or_brand_ceiling`, `dose_unbenchmarked_neutral`, `evidence_applicable_assessed` | — | PASS |
| 6 | 294020 | Pure Encapsulations Melatonin 0.5 mg | generic | scored | complete | no_known | Needs improvement–Good | Good 74.0 | `verification_manufacturing_ceiling`, `dose_unbenchmarked_neutral`, `evidence_applicable_assessed` | — | PASS |
| 7 | 241894 | Double Wood Supplements NMN Nicotinamide Mononucleotide 250  | generic | scored | complete | no_known | Needs improvement–Good | Good 70.0 | `verification_claim_or_brand_ceiling`, `dose_unbenchmarked_neutral`, `evidence_applicable_assessed` | — | PASS |
| 8 | 173888 | Garden Of Life MyKind Organics Men's Multi Organic Berry | multi_or_prenatal | scored | complete | no_known | Good–Very good | Good 77.8 | `verification_claim_or_brand_ceiling`, `evidence_authority_assessed` | — | PASS |
| 9 | 173918 | Garden Of Life MyKind Organics Women's Multi Organic Berry | multi_or_prenatal | scored | complete | no_known | Good–Very good | Good 78.3 | `verification_claim_or_brand_ceiling`, `evidence_authority_assessed` | — | PASS |
| 10 | 178520 | Equate Children's Multivitamin Gummies | multi_or_prenatal | not_scored | partial | caution | none | NOT_SCORED | `not_scored_has_no_number`, `unresolved_dose_safety_hold` | safety_policy_change | PASS |
| 11 | 328830 | Thorne Basic Prenatal | multi_or_prenatal | scored | complete | no_known | Excellent–Exceptional | Exceptional 95.4 | `verification_product_floor`, `evidence_authority_assessed` | verification_registry_change | PASS |
| 12 | 274081 | Garden of Life Dr. Formulated Probiotics Once Daily Prenatal | probiotic | scored | complete | no_known | Needs improvement–Good | Good 72.5 | `verification_product_floor`, `dose_unbenchmarked_neutral`, `evidence_applicable_assessed` | evidence_review_completed | PASS |
| 13 | 74124 | Nordic Naturals Prenatal DHA Unflavored Formula | omega | scored | complete | no_known | Good–Very good | Very good 81.6 | `verification_manufacturing_ceiling`, `evidence_authority_assessed` | — | PASS |
| 14 | 1650 | GNC Probiotics Ultra Probiotic Rescue & Refresh Kit 150 Bill | probiotic | scored | complete | no_known | Poor–Needs improvement | Poor 51.4 | `evidence_applicability_gap_not_no_research`, `verification_claim_or_brand_ceiling`, `dose_unbenchmarked_neutral` | evidence_review_completed | PASS |
| 15 | 178346 | Spring Valley Advanced Strength Probiotic 50 Billion | probiotic | scored | complete | no_known | Poor–Needs improvement | Poor 49.9 | `evidence_applicability_gap_not_no_research`, `verification_unknown_neutral`, `dose_unbenchmarked_neutral` | evidence_review_completed | PASS |
| 16 | 327776 | Sports Research Omega-3 1055 mg Fish Oil 1250 mg | omega | scored | complete | no_known | Very good–Exceptional | Excellent 90.4 | `verification_product_floor`, `evidence_applicable_assessed` | verification_registry_change | PASS |
| 17 | 288740 | Nordic Naturals Ultimate Omega + CoQ10 Lemon | omega | scored | complete | no_known | Needs improvement | Needs improvement 61.8 | `evidence_applicability_gap_not_no_research`, `verification_manufacturing_ceiling` | evidence_review_completed | PASS |
| 18 | 305203 | Transparent Labs KSM-66 | generic | scored | complete | no_known | Good–Very good | Very good 83.9 | `verification_claim_or_brand_ceiling`, `dose_unbenchmarked_neutral`, `evidence_applicable_assessed` | — | PASS |
| 19 | 82300 | Doctor's Best Ashwagandha With Sensoril 125 mg | generic | scored | complete | no_known | Good–Very good | Very good 80.9 | `verification_unknown_neutral`, `dose_unbenchmarked_neutral`, `evidence_applicable_assessed` | — | PASS |
| 20 | 302651 | Doctor's Best Curcumin Phytosome with Meriva | generic | scored | complete | no_known | Needs improvement | Needs improvement 63.0 | `verification_unknown_neutral`, `dose_unbenchmarked_neutral`, `evidence_applicable_assessed` | — | PASS |
| 21 | 255449 | Goli Nutrition Ashwagandha Gummies Mixed Berry | generic | scored | complete | no_known | Good–Very good | Good 78.4 | `verification_unknown_neutral`, `dose_unbenchmarked_neutral`, `evidence_applicable_assessed` | — | PASS |
| 22 | 183275 | Pure Encapsulations Silymarin | generic | scored | complete | no_known | Good–Very good | Very good 82.0 | `verification_manufacturing_ceiling`, `dose_unbenchmarked_neutral`, `evidence_applicable_assessed` | — | PASS |
| 23 | 306381 | Nutricost Performance PRE Pre-Workout Complex Blue Raspberry | sports | scored | complete | no_known | Good–Very good | Good 75.7 | `dose_caffeine_below_ceiling`, `verification_claim_or_brand_ceiling`, `evidence_applicable_assessed` | — | PASS |
| 24 | 2722 | GNC Pro Performance RapidDrive Pre-Workout Amino Complex Fru | sports | scored | complete | no_known | Good–Very good | Good 77.5 | `verification_claim_or_brand_ceiling`, `evidence_applicable_assessed` | — | PASS |
| 25 | 268690 | SR Sports Research Whey Protein Isolate Dutch Chocolate | sports | scored | complete | no_known | Very good–Excellent | Very good 85.6 | `verification_manufacturing_ceiling`, `evidence_applicable_assessed` | — | PASS |
| 26 | 325587 | Transparent Labs Creatine HMB Strawberry Lemonade | sports | scored | complete | no_known | Very good–Exceptional | Excellent 94.0 | `verification_product_floor`, `evidence_applicable_assessed` | verification_registry_change | PASS |
| 27 | 269425 | Nutricost Creatine Monohydrate 3 g | sports | scored | complete | no_known | Very good–Exceptional | Excellent 92.5 | `verification_claim_or_brand_ceiling`, `evidence_applicable_assessed` | — | PASS |
| 28 | 229913 | GNC Beyond Raw Precision BCAA Gummy Worm | sports | scored | complete | no_known | Needs improvement | Needs improvement 64.3 | `verification_claim_or_brand_ceiling`, `dose_unbenchmarked_neutral`, `evidence_applicable_assessed` | — | PASS |
| 29 | 184421 | Pure Encapsulations Digestive Enzymes Ultra with Betaine HCl | fiber_digestive | scored | complete | no_known | Needs improvement | Needs improvement 62.9 | `verification_manufacturing_ceiling`, `dose_unbenchmarked_neutral`, `evidence_applicable_assessed` | — | PASS |
| 30 | 278343 | Pure Encapsulations Quercetin | generic | scored | complete | no_known | Needs improvement–Good | Needs improvement 66.0 | `verification_manufacturing_ceiling`, `dose_unbenchmarked_neutral`, `evidence_applicable_assessed` | — | PASS |
| 31 | 204739 | Garden of Life Raw Organic Perfect Food Green Superfood Choc | generic | scored | complete | no_known | Poor | Poor 46.4 | `evidence_applicability_gap_not_no_research`, `verification_claim_or_brand_ceiling`, `dose_unbenchmarked_neutral` | evidence_review_completed | PASS |
| 32 | 232923 | Life Extension Cognitex Elite Pregnenolone | generic | scored | complete | caution | Poor | Poor 43.4 | `high_risk_active_zeroes_safety_hygiene`, `caution_keeps_quality_score`, `evidence_reviewed_zero_is_assessed`, `verification_manufacturing_ceiling`, `dose_unbenchmarked_neutral` | safety_policy_change | PASS |
| 33 | 211448 | Equate Triple Strength Glucosamine Chondroitin MSM | generic | scored | complete | no_known | Poor–Needs improvement | Poor 51.7 | `watchlist_excipient_not_blocking`, `verification_unknown_neutral`, `dose_unbenchmarked_neutral`, `evidence_applicable_assessed` | safety_policy_change | PASS |
| 34 | 274376 | Legion Whey+ Dutch Chocolate | sports | scored | complete | no_known | Very good–Excellent | Very good 88.6 | `verification_claim_or_brand_ceiling`, `evidence_applicable_assessed` | — | PASS |
| 35 | 294063 | Pure Encapsulations Vinpocetine 20 mg | generic | scored | complete/partial | caution | Poor | Poor 44.4 | `high_risk_active_zeroes_safety_hygiene`, `caution_keeps_quality_score`, `evidence_single_active_not_nothing_to_assess`, `verification_manufacturing_ceiling`, `dose_unbenchmarked_neutral` | safety_policy_change, evidence_review_completed, identity_resolution | FAIL: evidence_single_active_not_nothing_to_assess (F1) |
| 36 | 18924 (new) | Centrum Centrum Silver Chewables Citrus Berry | multi_or_prenatal | suppressed | complete | blocked | none | BLOCKED | `suppressed_hides_score_keeps_reason` | safety_policy_change | PASS |
| 37 | 220094 (new) | GNC Beyond Raw LIT Beyond Dew | sports | suppressed | complete | blocked | none | BLOCKED | `suppressed_hides_score_keeps_reason` | safety_policy_change | PASS |
| 38 | 252358 (new) | BulkSupplements.com EDTA Disodium | generic | suppressed | complete | blocked | none | BLOCKED | `suppressed_hides_score_keeps_reason`, `safety_block_precedes_completeness` | safety_policy_change, identity_resolution | PASS |
| 39 | 239458 (new) | CVS Health Super B Complex with Vitamin C | b_complex | scored | complete | no_known | Good–Very good | Very good 84.4 | `evidence_authority_assessed`, `verification_unknown_neutral` | — | PASS |
| 40 | 278523 (new) | CVS Health B-100 Complex | b_complex | scored | complete | caution | Needs improvement | Needs improvement 63.7 | `dose_ul_zero_ceiling`, `dose_ceiling_applied_once`, `ul_exceedance_not_double_counted`, `caution_keeps_quality_score`, `evidence_authority_assessed`, `verification_unknown_neutral` | safety_policy_change | PASS |
| 41 | 24809 (new) | Doctor's Best Vitamin D3 5000 IU | generic | scored | complete | caution | Needs improvement–Good | Good 70.1 | `dose_ul_zero_ceiling`, `dose_ceiling_applied_once`, `ul_exceedance_not_double_counted`, `caution_keeps_quality_score`, `evidence_applicable_assessed`, `verification_claim_or_brand_ceiling` | safety_policy_change | PASS |
| 42 | 25539 (new) | Doctor's Best Real Niacin (As Nicotinic Acid) 500 mg | generic | scored | complete | caution | Needs improvement | Needs improvement 59.9 | `dose_ul_zero_ceiling`, `dose_ceiling_applied_once`, `ul_exceedance_not_double_counted`, `caution_keeps_quality_score`, `evidence_applicable_assessed`, `verification_unknown_neutral` | safety_policy_change | PASS |
| 43 | 256977 (new) | Centrum Centrum Specialist Energy Multivitamin | multi_or_prenatal | scored | complete | caution | Needs improvement–Good | Needs improvement 67.2 | `dose_ul_partial_ceiling`, `dose_ceiling_applied_once`, `ul_exceedance_not_double_counted`, `caution_keeps_quality_score`, `evidence_authority_assessed`, `verification_claim_or_brand_ceiling` | safety_policy_change | PASS |
| 44 | 308247 (new) | Nutricost Performance PRE Pre-Workout Complex Blue Raspberry | sports | scored | complete | caution | Needs improvement | Needs improvement 63.1 | `dose_caffeine_zero_ceiling`, `dose_ceiling_applied_once`, `caution_keeps_quality_score`, `verification_claim_or_brand_ceiling`, `evidence_applicable_assessed` | safety_policy_change | PASS |
| 45 | 239467 (new) | CVS Health Fish Oil 1000 mg | omega | scored | partial | no_known | Poor | Poor 27.7 | `evidence_pending_marks_partial`, `omega_carrier_mass_not_epa_dha`, `verification_unknown_neutral` | evidence_review_completed, identity_resolution | PASS |
| 46 | 212388 (new) | GNC Triple Strength DHA 1000 | omega | scored | partial | no_known | Needs improvement | Needs improvement 61.5 | `evidence_pending_marks_partial`, `verification_claim_or_brand_ceiling` | evidence_review_completed, identity_resolution | PASS |
| 47 | 203390 (new) | Doctor's Best Purified & Clear Omega 3 Fish Oil 1000 mg | omega | scored | complete | no_known | Needs improvement–Good | Good 69.9 | `evidence_applicable_assessed`, `verification_unknown_neutral` | verification_registry_change | PASS |
| 48 | 178711 (new) | Equate One Daily Prenatal | multi_or_prenatal | scored | complete | no_known | Good–Very good | Very good 82.6 | `evidence_authority_assessed`, `verification_unknown_neutral` | verification_registry_change | PASS |
| 49 | 250851 (new) | Culturelle Digestive Daily Probiotic | probiotic | scored | complete | no_known | Good–Very good | Very good 79.6 | `evidence_applicable_assessed`, `verification_product_floor`, `dose_unbenchmarked_neutral` | evidence_review_completed, verification_registry_change | PASS |
| 50 | 202811 (new) | Doctor's Best Extra Strength Ginkgo 120 mg | generic | scored | complete | no_known | Poor–Needs improvement | Needs improvement 55.6 | `evidence_applicability_gap_not_no_research`, `verification_unknown_neutral`, `dose_unbenchmarked_neutral` | evidence_review_completed | PASS |
| 51 | 209389 (new) | Doctor's Best Noni Fruit Powder 650 mg | generic | scored | complete | no_known | Poor–Needs improvement | Poor 54.4 | `evidence_reviewed_zero_is_assessed`, `verification_unknown_neutral`, `dose_unbenchmarked_neutral` | evidence_review_completed | PASS |
| 52 | 269286 (new) | Doctor's Best Saw Palmetto 320 mg | generic | scored | partial | no_known | Poor | Poor 31.0 | `unfinished_identity_marks_partial`, `evidence_single_active_not_nothing_to_assess`, `verification_unknown_neutral` | identity_resolution | FAIL: evidence_single_active_not_nothing_to_assess (F2) |
| 53 | 256962 (new) | Centrum Centrum Men's Multi | multi_or_prenatal | not_scored | partial | no_known | none | NOT_SCORED | `not_scored_has_no_number` | identity_resolution | PASS |
