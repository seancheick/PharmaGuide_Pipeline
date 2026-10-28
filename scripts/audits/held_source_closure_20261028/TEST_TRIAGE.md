# Test triage — held-source closure batch (2026-10-28)

Validation class: tests-only. Production code and data were not edited by this triage.
Round 1: the 54 local failures in `~/pg_quality/held_closure_20261028/tests3.log`. Round 2: the
PR #273 CI failures (commit a78f78bf9), including one collection error that round 1 caused. Each
class-A edit asserts the ruled state and keeps its safeguard. The agent report has the per-test table.
This file holds the class-B findings, the movements explained by rulings, and data follow-ups.

## Open class-B findings

### B2: a reviewed exclusion-only scope drops the UC-II heading floor

- Test: `test_evidence_prominence_ownership.py::test_real_heading_that_names_its_brand_anchors_that_brands_floor[evidence_subject_321604_raw.json-...]`
  (left failing on purpose).
- Label: 321604 "Ultra Triple Action Joint Health". `ingredientRows[0]` is "UC-II Proprietary Cartilage
  Blend 401 mg", with one undosed member, "Collagen Type II, Undenatured".
- Owner: `scripts/clinical_applicability.py::assess_clinical_applicability`, in the `exclusion_only`
  branch reached via `_linked_rows(..., evidence_only=True)`. Its provider-anchor rule binds "its
  unique named/canonical child, never ... the parent's mass". The trigger is the new
  `BRAND_UCII.applicability`, which carries only `excluded_form_terms` plus outcome/population text.
- Probe:
  - With the current data, `BRAND_UCII` is `applicable` but rebound to `ingredientRows[0].nestedRows[0]`.
    The floor is `None` and Evidence drops from 14.0 to 5.0 (points under `collagen`).
  - With only the origin/main BRAND_UCII record swapped in (in memory), the match stays on
    `ingredientRows[0]`, the floor is `uc ii undenatured type ii collagen` at 18.0, and Evidence is
    14.0 (joint cap).
  - Probe scripts: `probe_old.py`, `probe_prom.py` in the session scratchpad.
- Why it is wrong: the ruling credits exactly undenatured type-II collagen for knee outcomes and accepts
  the UC-II credit as scoped. It does not withdraw the designed rule that a heading which names a
  verified brand anchors that brand's floor. The loss comes only from which `_linked_rows` path a
  record's policy shape selects. Sensoril shows the asymmetry: its policy has `supported_outcomes`,
  so it is not exclusion-only, and it binds to its heading and keeps 18.0.
- The ruling note "distinguish ingredient mass from native collagen content" concerns the 40 mg
  material versus native-collagen content. It is a Dose concern and does not touch the Evidence floor.
- Recommended minimal fix (code; needs a `/pg-scoring-change` measurement): in the exclusion-only
  branch, keep an existing exact ref to a provider-owned anchor when that anchor's heading names the
  matched branded record (the `test_a_brand_identifier_matches_as_labels_spell_it` matcher), instead
  of rebinding to the child. If Sean and Dr. Pham decide instead that a scoped brand record may never
  anchor on a blend heading, update the test to that decision.

### B3: the BCAA soreness credit is rejected by the product-line name "GNC Pro Performance"

- Test: `test_evidence_prominence_ownership.py::test_real_bcaa_record_still_binds_to_its_disclosed_aggregate`
  (left failing on purpose).
- Owner: `backed_clinical_studies.json::INGR_BRANCHED_CHAIN_AMINO_ACIDS.applicability.excluded_claim_terms`
  = `["muscle growth", "muscle building", "strength", "endurance", "performance"]`, enforced
  product-wide by `clinical_applicability.py::_excluded_claim_matches`.
- Probe (220827 Essential Amino Complete):
  - The match is rejected `label_purpose_evidence_mismatch`. The only hit among the five terms is
    "performance", in "GNC Pro Performance" and "Pro Performance Essential Amino Complete" (the
    product line).
  - With only "performance" removed (in memory), the match binds to the BCAA aggregate
    (`ingredientRows[6].nestedRows[0]`) with floor `bcaa` 9.35. That is identical to origin/main.
  - The label's own positioning is "Supports recovery" (post-workout), which is compatible with the
    ruled soreness outcome.
- Why it is wrong: this is the same defect class as B1. An excluded claim term matches a brand or
  product-line word, not a claim. The fourth ruling limits BCAA credit to exercise-related muscle
  soreness, and that is expressed by `supported_outcomes`. A brand name is not a performance claim.
- Recommended minimal fix (data): drop the bare `"performance"` term, or replace it with phrases that
  only occur as claims, such as "improves performance" or "performance enhancement". The coordinator
  removed beta-alanine's `excluded_claim_terms` for B1 the same way. Longer term, have
  `_excluded_claim_matches` skip brand and product-line text.

## Resolved

- B1 (beta-alanine rejected by "energy" in a blend description): resolved by the coordinator's data
  change (no `excluded_claim_terms`). Both Tri-Phase nodes pass unchanged.
- Whey-only labels losing whey credit (round 1, `required_form_terms` checked on the protein macro
  row): resolved by the whey-only aliases change. The later lean-mass-only change still passes.
- Collection error `test_botanical_lost_match_dispositions.py`: round 1 renamed
  `_eligible_cranberry_fixture` without updating its importer. The importer now asserts the real
  registry is eligible, which is the semantics it needed. `rg` finds no other importer of a renamed
  helper.

## Locked or score movements explained by a ruling (class A)

| Test | Before → after | Cause and ruling |
|---|---|---|
| `test_v4_archetype_fixtures[immune_support__ideal]` | 91.4 → 90.7; Evidence 15.6 → 14.9 (raw 13.2651 → 12.6981) | Only INGR_QUERCETIN recovery is lost; swapping that one record back restores 13.2651. Quercetin evidence is blood pressure, with immune claims excluded (fourth ruling set: "tight claims"; fifth: wellness words never make an unrelated study applicable). |
| `test_v4_archetype_fixtures[sports_pre_workout__failure]` | 58.0 "Needs improvement" → 42.4 "Poor"; Evidence 15.6 → 0.0 (raw 14.0 → 0.0) | Only INGR_BETA_ALANINE is lost; swapping it back restores 14.0. 500 mg is below the studied 2.4 g/day repeated-use regimen (fourth ruling set: a single small pre-workout serving does not inherit it). |
| `test_nonscorable_identity_kept[315814]` | 50.6 → 43.3; owners and Dose unchanged | INGR_GABA is reference-only (first ruling set: very limited stress evidence, no points until the calibration batch). |
| `test_evidence_prominence_ownership::test_when_the_owner_names_no_purpose…` (315700) | floor selenium 14.0 → iodine 9.35 | INGR_SELENIUM is scoped to Hashimoto thyroid labs (fifth ruling set); the label claims none. |
| `…::test_a_single_branded_intervention…[True]` | floor 0.0 → 18.0 | The new BRAND_SENSORIL scope binds the match to the single Sensoril heading; the withanolide marker no longer withholds the floor. This matches the test's own title. |

## Data follow-ups (not test defects)

1. `INGR_WHEY_PROTEIN.notes` still lists casein, milk, soy and pea, and `standard_name` is still
   "Protein Supplementation".
2. The chondroitin and glucosamine `effect_direction_rationale` texts are stale and not identical,
   as the third ruling asks.
3. BRAND_THERACURMIN's remaining acceptance (memory 29246725) is named only in the patch receipt.
4. INGR_DIGESTIVE_ENZYMES has no contexts, and its notes do not state the fifth-ruling remaining item.
5. BRAND_RELORA keeps a 17-point floor under "limited" (calibration batch).
6. INGR_WHITE_KIDNEY_BEAN: the approved context says "activity units not verified in this session",
   yet the Dose exposure still reports `matches` for "Phaseolean aqueous extract 20,000 AIU/g DNS
   assay" (`test_exact_source_verified_phaseolean_regimens`, `test_phaseolean_source_specification_survives_full_enrichment`).
   One of the two statements is stale.
7. INGR_QUERCETIN (`supported_outcomes: ["blood_pressure"]`) still credits labels with no
   blood-pressure claim (Quercefit 309492, `evaluated_supported`), because its context is not
   condition-gated. PRECLIN_QUERCETIN_PHYTOSOME's allergy context is gated. Confirm that the ruling's
   "tight claims" intends ungated BP credit.
8. INGR_GABA: the first and fourth ruling sets require the wording to state the preliminary, mixed
   stress findings, never "no evidence". Not checked by this triage.
