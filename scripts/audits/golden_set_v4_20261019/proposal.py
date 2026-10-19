#!/usr/bin/env python3
"""v4 golden-set proposal for scripts/data/canary_products.json (October 19, 2026).

Builds the proposed canary file, evaluates every proposed expectation against the
current scored artifacts, and writes the review packet. It never edits the data
file unless --apply is given, which is reserved for after Sean's approval.

  $PG_PYTHON scripts/audits/golden_set_v4_20261019/proposal.py \
      [--products DIR] [--core-db PATH] [--apply]
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts"))

CANARY_FILE = REPO / "scripts" / "data" / "canary_products.json"
MAIN = Path("/Users/seancheick/Downloads/dsld_clean")
DEFAULT_PRODUCTS = MAIN / "scripts" / "products"
DEFAULT_CORE_DB = (MAIN / "reports" / "dose_v41_release_audit_20261019" / "catalog_candidate"
                   / "final_db_output" / "pharmaguide_core.db")

QS = "scripts/scoring_v4/quality_score.py"
SA = "scripts/scoring_v4/scored_artifact.py"
CFG = "scripts/scoring_v4/config/quality_score.json"
P = "quality_pillars_v4"

# --------------------------------------------------------------------------
# Where each canary-level expectation comes from (one place, cited once).
# --------------------------------------------------------------------------
EXPECTATION_OWNERS = {
    "expected_v4_module": "scripts/scoring_input_contract.py::build_scoring_classification (route_decision.module, ROUTE_CLASSIFIER_VERSION 1.3.2) -> artifact _v4_module",
    "expected_quality_score_status": f"{QS}::assemble_quality_score; {CFG} suppression",
    "expected_quality_assessment_status": f"{SA}::_quality_assessment_status, {SA}::unfinished_source_assessment, {SA}::UNASSESSED_EVIDENCE_DISPLAY_STATES",
    "expected_product_safety_status": f"{SA}::_product_safety_status (catalog safety gate only; never legacy verdict)",
    "expected_quality_tier_band": f"{QS}::_tier over {CFG} tiers, read from the public display score; band = tiers reachable within +/-5 points of the reviewed score (drift tolerance, not a ranking)",
}

# Movement outside a band, or any status/invariant change, needs one of these.
MOVEMENT_REASONS = {
    "scoring_policy_version_change": f"An approved change to {CFG} (_metadata.version bump) or a scorer owner, measured with /pg-scoring-change.",
    "reference_data_correction": "A verified curated-data batch on an owner the pillar reads (IQM, clinical studies, RDA/UL references, dose anchors).",
    "label_source_change": "A DSLD label revision, reformulation or a verified transcription correction of this product.",
    "verification_registry_change": "Certification or audited-GMP registry evidence for this product or facility was added, expired or corrected.",
    "evidence_review_completed": "A not-yet-reviewed or unresolved Evidence state became a recorded review conclusion.",
    "identity_resolution": "PharmaGuide's own unresolved identity, role or amount reading was fixed at its owner (cleaner, enricher or resolver).",
    "safety_policy_change": "An approved banned/recalled/high-risk policy or dose-safety reference change.",
}
DEFAULT_REASONS = ["scoring_policy_version_change", "reference_data_correction", "label_source_change"]

# --------------------------------------------------------------------------
# Pillar invariants: id -> rule, owner, machine checks over the scored artifact.
# A check is [path, op, value]; paths are dotted keys into one scored product.
# --------------------------------------------------------------------------
V = f"{P}.verification"
D = f"{P}.dose"
E = f"{P}.evidence"
SH = f"{P}.safety_hygiene"
CEIL = "dose_safety_evaluation.dose_ceiling"

INVARIANTS = {
    "verification_unknown_neutral": {
        "rule": "Verification stays at the neutral 6/15 when no verification evidence is on file (unknown is not a penalty).",
        "owner": f"{QS}::_pillar_verification; {CFG} verification_subscale.neutral_baseline",
        "checks": [[f"{V}.components.tier", "eq", "unknown"], [f"{V}.components.fail_open_neutral", "eq", True], [f"{V}.score", "eq", 6.0]],
    },
    "verification_claim_or_brand_ceiling": {
        "rule": "Label claims, own testing and reputation without independent verification stay at or below 8/15.",
        "owner": f"{QS}::_pillar_verification; {CFG} verification_subscale.tier_ceilings.claim_or_brand",
        "checks": [[f"{V}.components.tier", "eq", "claim_or_brand"], [f"{V}.score", "le", 8.0]],
    },
    "verification_manufacturing_ceiling": {
        "rule": "Verified facility or brand-scoped evidence without product-level certification stays at or below 10/15.",
        "owner": f"{QS}::_pillar_verification; {CFG} verification_subscale.tier_ceilings.manufacturing",
        "checks": [[f"{V}.components.tier", "eq", "manufacturing"], [f"{V}.score", "le", 10.0]],
    },
    "verification_product_floor": {
        "rule": "Registry-backed product-level certification earns at least 11/15.",
        "owner": f"{QS}::_pillar_verification; {CFG} verification_subscale.product_level_floor",
        "checks": [[f"{V}.components.tier", "eq", "product"], [f"{V}.score", "ge", 11.0]],
    },
    "dose_unbenchmarked_neutral": {
        "rule": "A disclosed amount with no applicable benchmark takes the shared Dose neutral 11.4, never a studied-range claim.",
        "owner": f"{CFG} dose_subscale.unbenchmarked_neutral_public",
        "checks": [[f"{D}.score", "eq", 11.4]],
    },
    "dose_ul_partial_ceiling": {
        "rule": "A confirmed UL exceedance above 100% and below 150% at maximum directed daily use caps public Dose at 10.",
        "owner": f"scripts/scoring_v4/dose_safety.py::DoseSafetyResult.dose_ceiling; {CFG} dose_safety_ceiling.exceeds_above_pct/zero_at_pct/partial_ceiling_public",
        "checks": [[f"{CEIL}.kind", "eq", "established_upper_limit"], [f"{CEIL}.pct_ul", "gt", 100.0], [f"{CEIL}.pct_ul", "lt", 150.0],
                   [f"{CEIL}.cap_public", "eq", 10.0], [f"{D}.score", "le", 10.0]],
    },
    "dose_ul_zero_ceiling": {
        "rule": "A confirmed UL exceedance at or above 150% at maximum directed daily use sets public Dose to 0.",
        "owner": f"scripts/scoring_v4/dose_safety.py::DoseSafetyResult.dose_ceiling; {CFG} dose_safety_ceiling.zero_at_pct",
        "checks": [[f"{CEIL}.kind", "eq", "established_upper_limit"], [f"{CEIL}.pct_ul", "ge", 150.0], [f"{CEIL}.cap_public", "eq", 0.0], [f"{D}.score", "eq", 0.0]],
    },
    "dose_caffeine_zero_ceiling": {
        "rule": "Declared caffeine of 600 mg/day or more at maximum directed daily use sets public Dose to 0 through the same ceiling.",
        "owner": f"scripts/scoring_v4/dose_safety.py::DoseSafetyResult.dose_ceiling; {CFG} dose_safety_ceiling.caffeine",
        "checks": [[f"{CEIL}.kind", "eq", "caffeine_daily_total"], [f"{CEIL}.amount_mg_day", "ge", 600.0], [f"{D}.score", "eq", 0.0]],
    },
    "dose_caffeine_below_ceiling": {
        "rule": "Declared caffeine at or below 400 mg/day at maximum directed daily use sets no Dose ceiling.",
        "owner": f"{CFG} dose_safety_ceiling.caffeine.exceeds_above_mg_day",
        "checks": [["dose_safety_evaluation.caffeine.total_mg_day_max", "le", 400.0], [CEIL, "is_null", None]],
    },
    "dose_ceiling_applied_once": {
        "rule": "One product-level Dose ceiling, applied once after route aggregation (at most one ceiling receipt entry).",
        "owner": f"{CFG} dose_safety_ceiling (_doc: applied once after route aggregation and normalization)",
        "checks": [[f"{D}.receipt.entries", "count_id_le", ["dose_safety_ceiling", 1]]],
    },
    "ul_exceedance_not_double_counted": {
        "rule": "A UL exceedance is charged once in Dose; Safety/Hygiene says so instead of deducting again.",
        "owner": f"{QS}::_pillar_safety_hygiene ('Not deducted here')",
        "checks": [[f"{SH}.reason", "contains_text", "Not deducted here"]],
    },
    "evidence_applicable_assessed": {
        "rule": "Reviewed applicable research is shown as an assessed Evidence result.",
        "owner": f"{QS}::evidence_display_state (EVIDENCE_ASSESSED_STATES)",
        "checks": [[f"{E}.evidence_result_state", "eq", "evaluated_applicable"], [f"{E}.display_state", "eq", "assessed"], [f"{E}.score", "gt", 0.0]],
    },
    "evidence_authority_assessed": {
        "rule": "Essential nutrients are assessed through established nutritional authority.",
        "owner": f"{QS}::evidence_display_state; scripts/scoring_v4/modules/generic_evidence.py::authority_panel_result_state",
        "checks": [[f"{E}.evidence_result_state", "eq", "evaluated_authority"], [f"{E}.display_state", "eq", "assessed"]],
    },
    "evidence_applicability_gap_not_no_research": {
        "rule": "An Evidence applicability gap is shown as research that does not apply to this label, never as no research, and it is a completed conclusion.",
        "owner": f"{QS}::evidence_display_state, {QS}::_EVIDENCE_ZERO_REASON; {SA}::UNASSESSED_EVIDENCE_DISPLAY_STATES",
        "checks": [[f"{E}.evidence_result_state", "in", ["applicability_unestablished", "research_present_applicability_unestablished"]],
                   [f"{E}.display_state", "eq", "applicability_unestablished"], [f"{E}.reason", "not_contains_text", "no qualifying"],
                   ["quality_assessment_status", "eq", "complete"]],
    },
    "evidence_reviewed_zero_is_assessed": {
        "rule": "A reviewed null or no-qualifying-evidence result is an assessed conclusion, distinct from a pending review.",
        "owner": f"{QS}::evidence_display_state (EVIDENCE_ASSESSED_STATES)",
        "checks": [[f"{E}.evidence_result_state", "in", ["evaluated_null", "no_qualifying_human_evidence", "evaluated_unfavorable"]],
                   [f"{E}.display_state", "eq", "assessed"], ["quality_assessment_status", "eq", "complete"]],
    },
    "evidence_pending_marks_partial": {
        "rule": "An Evidence review PharmaGuide has not finished is shown as pending (not 0/20 research) and marks the assessment partial.",
        "owner": f"{QS}::evidence_display_state (EVIDENCE_COVERAGE_GAP_STATES); {SA}::_quality_assessment_status",
        "checks": [[f"{E}.display_state", "eq", "not_yet_reviewed"], ["quality_assessment_status", "eq", "partial"]],
    },
    "evidence_single_active_not_nothing_to_assess": {
        "rule": "A label whose only active has a resolved evidence owner is never reported as having nothing to assess; it is reviewed or pending.",
        "owner": f"{QS}::evidence_display_state ('not_applicable - nothing on this label to assess'); scripts/scoring_v4/modules/generic_evidence.py (evidence_owner_canonicals)",
        "checks": [[f"{E}.evidence_result_state", "ne", "no_assessable_actives"]],
    },
    "omega_carrier_mass_not_epa_dha": {
        "rule": "Fish-oil carrier mass never becomes EPA+DHA dose: undisclosed EPA/DHA earns no Dose credit.",
        "owner": f"{CFG} _metadata.description (1.10.1 omega label ownership); scripts/scoring_v4/modules/omega*.py",
        "checks": [[f"{D}.score", "eq", 0.0], [f"{P}.transparency.reason", "contains_text", "EPA/DHA amounts"]],
    },
    "suppressed_hides_score_keeps_reason": {
        "rule": "A BLOCKED product ships with its reason and no public quality number or tier.",
        "owner": f"{QS}::assemble_quality_score (hard safety failure first); {SA}::_public_verdict; AGENTS.md 'Banned/recalled products always ship'",
        "checks": [["quality_score_status", "eq", "suppressed_safety"], ["quality_score_v4_100", "is_null", None], ["quality_tier", "is_null", None],
                   ["product_safety_status", "eq", "blocked"], ["verdict", "eq", "BLOCKED"], ["blocking_reason", "not_null", None],
                   ["quality_score_suppressed_reason", "eq_path", "blocking_reason"]],
    },
    "safety_block_precedes_completeness": {
        "rule": "A safety block wins over an incomplete-data gate: the product is BLOCKED, not NOT_SCORED.",
        "owner": f"{QS}::assemble_quality_score (suppressed_safety before not_scored); {SA}::_public_verdict",
        "checks": [["_v4_completeness_gate.verdict", "eq", "NOT_SCORED"], ["quality_score_status", "eq", "suppressed_safety"]],
    },
    "not_scored_has_no_number": {
        "rule": "A not-scored product carries no number, tier or pillars and an honest partial assessment.",
        "owner": f"{QS}::assemble_quality_score; {SA}::_quality_assessment_status",
        "checks": [["quality_score_status", "eq", "not_scored"], ["quality_score_v4_100", "is_null", None], ["quality_tier", "is_null", None],
                   [P, "is_null", None], ["quality_assessment_status", "eq", "partial"]],
    },
    "unresolved_dose_safety_hold": {
        "rule": "Material but unresolved applicable dose safety holds a product from scoring rather than guessing. Child-only information does not change the adult catalog assessment.",
        "owner": "scripts/dose_assessment.py (pediatric_reference_gap); scripts/scoring_v4/dose_safety.py state material_but_unresolved",
        "checks": [["dose_safety_evaluation.state_counts.material_but_unresolved", "ge", 1], ["flags", "contains", "DOSE_SAFETY_UNRESOLVED_REVIEW"]],
    },
    "caution_keeps_quality_score": {
        "rule": "Quality and safety are separate outputs: a CAUTION product keeps its quality score.",
        "owner": f"{CFG} _metadata.description ('Quality tiers are independent of safety'); {SA}::_product_safety_status",
        "checks": [["product_safety_status", "eq", "caution"], ["quality_score_status", "eq", "scored"], ["quality_score_v4_100", "not_null", None]],
    },
    "high_risk_active_zeroes_safety_hygiene": {
        "rule": "A confirmed high-risk active zeroes the Safety/Hygiene base while the product stays scored with CAUTION.",
        "owner": f"{QS}::_pillar_safety_hygiene",
        "checks": [[f"{SH}.score", "eq", 0.0], ["product_safety_status", "eq", "caution"]],
    },
    "watchlist_excipient_not_blocking": {
        "rule": "A watchlist excipient (titanium dioxide) informs and takes a small Safety/Hygiene deduction; it never blocks or forces CAUTION.",
        "owner": f"{CFG} clean_label_subscale; {QS}::_clean_label_penalty",
        "checks": [["product_safety_status", "eq", "no_known_catalog_concern"], ["_v4_safety_gate.clean_label_hits", "nonempty", None], [f"{SH}.score", "lt", 10.0]],
    },
    "unfinished_identity_marks_partial": {
        "rule": "PharmaGuide's own unresolved identity marks the assessment partial instead of presenting a finished verdict.",
        "owner": f"{SA}::unfinished_source_assessment; {SA}::_quality_assessment_status",
        "checks": [["quality_assessment_status", "eq", "partial"]],
    },
}

# Applied to every scored canary.
GLOBAL_SCORED_INVARIANTS = {
    "tier_matches_display_score": {
        "rule": "quality_tier is the configured tier of the public display score.",
        "owner": f"{QS}::_tier, {QS} display rounding (floor(x+0.5)); {CFG} tiers",
    },
    "pillars_sum_to_score": {
        "rule": "The six public pillars add up to quality_score_v4_100 (within rounding).",
        "owner": f"{QS}::assemble_quality_score; {CFG} pillars",
    },
}

# --------------------------------------------------------------------------
# Per-canary proposal: module, qss, qas, pss, invariants, extra movement reasons.
# qas/pss may be a list when policy allows either outcome (documented in REVIEW.md).
# --------------------------------------------------------------------------
G, M, PB, O, SP, FD, BC = "generic", "multi_or_prenatal", "probiotic", "omega", "sports", "fiber_digestive", "b_complex"
SC, NS, SU = "scored", "not_scored", "suppressed_safety"
CO, PA = "complete", "partial"
NK, CA, BL = "no_known_catalog_concern", "caution", "blocked"
VU, VC, VM, VP = ("verification_unknown_neutral", "verification_claim_or_brand_ceiling",
                  "verification_manufacturing_ceiling", "verification_product_floor")
DN, EA, EU = "dose_unbenchmarked_neutral", "evidence_applicable_assessed", "evidence_authority_assessed"
EG = "evidence_applicability_gap_not_no_research"
UL0 = ["dose_ul_zero_ceiling", "dose_ceiling_applied_once", "ul_exceedance_not_double_counted", "caution_keeps_quality_score"]
UL10 = ["dose_ul_partial_ceiling", "dose_ceiling_applied_once", "ul_exceedance_not_double_counted", "caution_keeps_quality_score"]

EXPECT = {
    # existing 35
    "202992": (G, SC, CO, NK, [VC, DN, EA], ["verification_registry_change"]),
    "298074": (G, SC, CO, NK, [VP, EA], ["verification_registry_change"]),
    "184058": (G, SC, CO, CA, UL10 + [VU, EA], ["safety_policy_change"]),
    "298053": (G, SC, CO, NK, [VP, EU], ["verification_registry_change"]),
    "219203": (G, SC, CO, NK, [VC, DN, EA], []),
    "294020": (G, SC, CO, NK, [VM, DN, EA], []),
    "241894": (G, SC, CO, NK, [VC, DN, EA], []),
    "173888": (M, SC, CO, NK, [VC, EU], []),
    "173918": (M, SC, CO, NK, [VC, EU], []),
    "178520": (M, SC, CO, NK, [EU, VU], ["safety_policy_change", "reference_data_correction"]),
    "328830": (M, SC, CO, NK, [VP, EU], ["verification_registry_change"]),
    "274081": (PB, SC, CO, NK, [VP, DN, EA], ["evidence_review_completed"]),
    "74124":  (O, SC, CO, NK, [VM, EU], []),
    "1650":   (PB, SC, CO, NK, [EG, VC, DN], ["evidence_review_completed"]),
    "178346": (PB, SC, CO, NK, [EG, VU, DN], ["evidence_review_completed"]),
    "327776": (O, SC, CO, NK, [VP, EA], ["verification_registry_change"]),
    "288740": (O, SC, CO, NK, [EG, VM], ["evidence_review_completed"]),
    "305203": (G, SC, CO, NK, [VC, DN, EA], []),
    "82300":  (G, SC, CO, NK, [VU, DN, EA], []),
    "302651": (G, SC, CO, NK, [VU, DN, EA], []),
    "255449": (G, SC, CO, NK, [VU, DN, EA], []),
    "183275": (G, SC, CO, NK, [VM, DN, EA], []),
    "306381": (SP, SC, CO, NK, ["dose_caffeine_below_ceiling", VC, EA], []),
    "2722":   (SP, SC, CO, NK, [VC, EA], []),
    "268690": (SP, SC, CO, NK, [VM, EA], []),
    "325587": (SP, SC, CO, NK, [VP, EA], ["verification_registry_change"]),
    "269425": (SP, SC, CO, NK, [VC, EA], []),
    "229913": (SP, SC, CO, NK, [VC, DN, EA], []),
    "184421": (FD, SC, CO, NK, [VM, DN, EA], []),
    "278343": (G, SC, CO, NK, [VM, DN, EA], []),
    "204739": (G, SC, CO, NK, [EG, VC, DN], ["evidence_review_completed"]),
    "232923": (G, SC, CO, CA, ["high_risk_active_zeroes_safety_hygiene", "caution_keeps_quality_score", "evidence_reviewed_zero_is_assessed", VM, DN], ["safety_policy_change"]),
    "211448": (G, SC, CO, NK, ["watchlist_excipient_not_blocking", VU, DN, EA], ["safety_policy_change"]),
    "274376": (SP, SC, CO, NK, [VC, EA], []),
    "294063": (G, SC, [CO, PA], CA, ["high_risk_active_zeroes_safety_hygiene", "caution_keeps_quality_score", "evidence_single_active_not_nothing_to_assess", VM, DN],
               ["safety_policy_change", "evidence_review_completed", "identity_resolution"]),
    # proposed additions
    "18924":  (M, SU, CO, BL, ["suppressed_hides_score_keeps_reason"], ["safety_policy_change"]),
    "220094": (SP, SU, CO, BL, ["suppressed_hides_score_keeps_reason"], ["safety_policy_change"]),
    "252358": (G, SU, CO, BL, ["suppressed_hides_score_keeps_reason", "safety_block_precedes_completeness"], ["safety_policy_change", "identity_resolution"]),
    "239458": (BC, SC, CO, NK, [EU, VU], []),
    "278523": (BC, SC, CO, CA, UL0 + [EU, VU], ["safety_policy_change"]),
    "24809":  (G, SC, CO, CA, UL0 + [EA, VC], ["safety_policy_change"]),
    "25539":  (G, SC, CO, CA, UL0 + [EA, VU], ["safety_policy_change"]),
    "256977": (M, SC, CO, CA, UL10 + [EU, VC], ["safety_policy_change"]),
    "308247": (SP, SC, CO, CA, ["dose_caffeine_zero_ceiling", "dose_ceiling_applied_once", "caution_keeps_quality_score", VC, EA], ["safety_policy_change"]),
    "239467": (O, SC, PA, NK, ["evidence_pending_marks_partial", "omega_carrier_mass_not_epa_dha", VU], ["evidence_review_completed", "identity_resolution"]),
    "212388": (O, SC, PA, NK, ["evidence_pending_marks_partial", VC], ["evidence_review_completed", "identity_resolution"]),
    "203390": (O, SC, CO, NK, [EA, VU], ["verification_registry_change"]),
    "178711": (M, SC, CO, NK, [EU, VU], ["verification_registry_change"]),
    "250851": (PB, SC, CO, NK, [EA, VP, DN], ["evidence_review_completed", "verification_registry_change"]),
    "202811": (G, SC, CO, NK, [EG, VU, DN], ["evidence_review_completed"]),
    "209389": (G, SC, CO, NK, ["evidence_reviewed_zero_is_assessed", VU, DN], ["evidence_review_completed"]),
    "269286": (G, SC, CO, NK, ["evidence_single_active_not_nothing_to_assess", EA, DN, VU], ["identity_resolution"]),
    "256962": (M, NS, PA, NK, ["not_scored_has_no_number"], ["identity_resolution"]),
}

# New entries: legacy required fields + notes. v3_shipped_* are null: not in the v3 baseline.
NEW = {
    "18924": ("blocked_verdict", "banned_excipient_pho_multi", "multi_or_prenatal", "blocked_short_circuit",
              ["banned_inactive_blocks", "multi_route_blocked"],
              "Partially hydrogenated oils (FDA revoked GRAS) in an inactive row block the product. Pairs with 211448, where a watchlist excipient only informs and deducts."),
    "220094": ("blocked_verdict", "banned_bvo_caffeinated_drink_mix", "sports_active", "blocked_short_circuit",
              ["banned_inactive_blocks", "caffeine_present_on_blocked_product"],
              "Brominated vegetable oil (FDA revoked authorization in 2024) blocks a caffeinated sports drink mix; the block replaces any Dose or caffeine scoring."),
    "252358": ("blocked_verdict", "non_routine_chelator_single", "generic", "blocked_short_circuit",
              ["non_banned_blocking_reason", "block_precedes_completeness_gate"],
              "Edetate disodium is blocked under NON_ROUTINE_CHELATOR, a blocking reason other than banned_ingredient; the block wins over the incomplete-data gate."),
    "239458": ("b_complex", "b_complex_within_ul", "generic", "b_complex_panel",
              ["b_complex_route", "authority_evidence_panel"],
              "B-complex with vitamin C inside every UL: the b_complex route with authority Evidence and no Dose ceiling."),
    "278523": ("b_complex", "b_complex_niacin_over_ul", "generic", "b_complex_panel",
              ["b_complex_route", "niacin_ul_zero_ceiling"],
              "B-100 complex whose niacin is about 286% of the 35 mg UL even at minimum directed use: Dose is set to 0 once and Safety/Hygiene does not deduct again."),
    "24809":  ("single_nutrient", "vitamin_d3_over_ul_zero", "generic", "single_nutrient",
              ["near_ul_dose", "ul_zero_ceiling_from_directed_maximum"],
              "Same 125 mcg D3 per softgel as 184058, but the directed maximum (2/day, 250% of UL) reaches the zero band; 184058's directed use stays at 125% (cap 10)."),
    "25539":  ("single_nutrient", "niacin_nicotinic_acid_over_ul", "generic", "single_nutrient",
              ["ul_zero_ceiling_from_directed_maximum"],
              "Nicotinic acid 500 mg against the 35 mg supplemental niacin UL: Dose 0 with CAUTION while the quality score stays visible."),
    "256977": ("multivitamin", "multi_niacin_partial_ceiling", "multi_or_prenatal", "multi_panel",
              ["ul_partial_ceiling_on_multi_route", "watchlist_excipient_present"],
              "Energy multivitamin at 114% of the niacin UL: the multi route caps Dose at 10 through the product-level ceiling."),
    "308247": ("sports_transparent", "preworkout_caffeine_daily_ceiling", "sports_active", "blend_per_component_or_not_scored",
              ["caffeine_daily_ceiling", "same_name_label_version_of_306381"],
              "A second DSLD version of the 306381 pre-workout: 600 mg caffeine/day at maximum directed use sets Dose to 0, while 306381 (300 mg/day) has no ceiling."),
    "239467": ("fish_oil", "omega_epa_dha_undisclosed_evidence_pending", "generic", "omega_dose",
              ["epa_dha_not_printed", "evidence_identity_material_unresolved"],
              "Fish oil 1000 mg with no EPA/DHA printed: carrier mass earns no Dose credit and Evidence is pending, so the assessment is partial."),
    "212388": ("fish_oil", "omega_dha_printed_evidence_pending", "generic", "omega_dose",
              ["evidence_identity_material_unresolved"],
              "DHA is printed, so Dose credit stands, while the Evidence review is pending and marks the assessment partial (contrast with 239467)."),
    "203390": ("fish_oil", "ordinary_omega_unverified", "generic", "omega_dose",
              ["ordinary_omega", "store_or_mid_brand_unverified"],
              "Ordinary triglyceride-unspecified fish oil with EPA/DHA printed and no verification on file: neutral Verification, assessed Evidence."),
    "178711": ("prenatal_multi", "store_brand_prenatal_unverified", "multi_or_prenatal", "multi_panel_prenatal",
              ["prenatal_route", "store_brand_no_certs"],
              "Store-brand once-daily prenatal: the prenatal panel with authority Evidence and neutral Verification."),
    "250851": ("probiotic", "single_strain_lgg_verified", "probiotic", "probiotic_cfu_adequacy",
              ["probiotic_evidence_components", "product_level_certification"],
              "Single-strain LGG probiotic with assessed strain-family Evidence and product-level certification."),
    "202811": ("herbal_unstandardized", "ginkgo_applicability_gap", "generic", "herbal_marker_dose",
              ["evidence_applicability_gap_botanical"],
              "Ginkgo extract whose reviewed research does not match this label's preparation or dose: shown as an applicability gap, never as no research."),
    "209389": ("herbal_unstandardized", "noni_no_qualifying_evidence", "generic", "herbal_marker_dose",
              ["evidence_reviewed_zero"],
              "Noni fruit powder: research was reviewed and none qualifies, a completed zero that differs from a pending review."),
    "269286": ("herbal_branded_extract", "saw_palmetto_prosterol_identity_unresolved", "generic", "herbal_marker_dose",
              ["branded_extract_read_as_blend_header", "unfinished_identity_partial"],
              "Prosterol (saw palmetto extract) 320 mg is read as a blend header (BLEND_GENERAL); the assessment is honestly partial, but see finding F2."),
    "256962": ("multivitamin", "adult_multi_completeness_gate", "multi_or_prenatal", "multi_panel",
              ["completeness_gate_not_scored"],
              "Adult men's multivitamin held by the completeness gate (strict scoring contract, identity readiness): no number until identity is ready."),
}

FINDINGS = {
    "evidence_single_active_not_nothing_to_assess": {
        "294063": "F1",
        "269286": "F2",
    },
}


# --------------------------------------------------------------------------
def display(score: float) -> int:
    return int(math.floor(float(score) + 0.5))


def tier_of(score: float, tiers: list) -> str:
    for band in tiers:
        if score >= band["min"]:
            return band["name"]
    return tiers[-1]["name"]


def tier_band(score, tiers):
    if score is None:
        return None
    names = [t["name"] for t in tiers]  # high -> low
    lo, hi = tier_of(display(max(0.0, score - 5)), tiers), tier_of(display(min(100.0, score + 5)), tiers)
    return [lo, hi] if names.index(lo) != names.index(hi) else [lo, lo]


def get(obj, path, default=None):
    cur = obj
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def check(prod, path, op, value):
    missing = object()
    got = get(prod, path, missing)
    if got is missing:
        return False, None
    if op == "eq":
        ok = got == value
    elif op == "ne":
        ok = got != value
    elif op == "in":
        ok = got in value
    elif op in ("le", "ge", "lt", "gt"):
        ok = isinstance(got, (int, float)) and not isinstance(got, bool) and {
            "le": got <= value, "ge": got >= value, "lt": got < value, "gt": got > value}[op]
    elif op == "is_null":
        ok = got is None
    elif op == "not_null":
        ok = got is not None
    elif op == "nonempty":
        ok = bool(got)
    elif op == "contains":
        ok = isinstance(got, list) and value in got
    elif op == "contains_text":
        ok = isinstance(got, str) and value in got
    elif op == "not_contains_text":
        ok = isinstance(got, str) and value.lower() not in got.lower()
    elif op == "eq_path":
        ok = got is not None and got == get(prod, value)
    elif op == "count_id_le":
        ok = isinstance(got, list) and sum(1 for e in got if e.get("id") == value[0]) <= value[1]
    else:
        raise ValueError(op)
    return ok, got


def load_products(root: Path, ids: set) -> dict:
    from stage_manifest import select_stage_files

    found = {}
    for fn in select_stage_files(root.glob("output_*_scored/scored"), "score", require_manifest=True):
        for prod in json.loads(fn.read_text()):
            pid = str(prod.get("dsld_id"))
            if pid in ids:
                if pid in found:
                    raise ValueError(f"Duplicate scored product ID: {pid}")
                found[pid] = prod
    return found


def build(doc: dict, products: dict, tiers: list) -> dict:
    out = copy.deepcopy(doc)
    existing = {c["dsld_id"] for c in out["canaries"]}
    for pid, (pc, sub, b5, route, edges, notes) in NEW.items():
        assert pid not in existing, pid
        prod = products[pid]
        out["canaries"].append({
            "dsld_id": pid, "brand_name": prod["brand_name"], "product_name": prod["product_name"],
            "primary_class": pc, "subclass": sub, "expected_b5_class": b5, "expected_dose_route_v4": route,
            "edge_cases": edges, "notes": notes, "v3_shipped_score": None, "v3_shipped_verdict": None,
        })
    for c in out["canaries"]:
        mod, qss, qas, pss, inv, extra = EXPECT[c["dsld_id"]]
        prod = products[c["dsld_id"]]
        c["expected_v4_module"] = mod
        c["expected_quality_score_status"] = qss
        c["expected_quality_assessment_status"] = qas
        c["expected_product_safety_status"] = pss
        c["expected_quality_tier_band"] = tier_band(prod.get("quality_score_v4_100"), tiers) if qss == SC else None
        c["expected_pillar_invariants"] = inv
        c["allowed_movement_reasons"] = DEFAULT_REASONS + [r for r in extra if r not in DEFAULT_REASONS]
    md = out["_metadata"]
    md["schema_version"] = "1.1.0"
    md["last_updated"] = "2026-10-19"
    if "b_complex" not in md["primary_classes"]:
        md["primary_classes"].append("b_complex")
    md["golden_set"] = {
        "purpose": "v4 golden set: each canary states expected route, statuses, a tier band and pillar invariants. The Coverage & Calibration dashboard raises a finding when a canary breaks one; a break is fixed at its owner or explained by an allowed movement reason, never by editing the expectation to the current score.",
        "reviewed_against": "Score stage run 20261019T070203540018Z (quality_score.json 1.29.1-dose-v41-omega-integration), main e6f2dd103.",
        "approval": "Approved by Sean 2026-10-19: D1 schema, D2 +/-5 tier band, D3 the 18 additions, D4 211448 class unchanged, D5 F1/F2 kept as failing expectations (scripts/audits/golden_set_v4_20261019/REVIEW.md).",
        "expectation_owners": EXPECTATION_OWNERS,
        "global_scored_invariants": GLOBAL_SCORED_INVARIANTS,
        "pillar_invariants": INVARIANTS,
        "check_ops": "eq, ne, in, le, ge, lt, gt, is_null, not_null, nonempty, contains (list), contains_text, not_contains_text (case-insensitive), eq_path (equals another path), count_id_le ([receipt entry id, max count]); paths are dotted keys into one scored product.",
        "movement_reasons": MOVEMENT_REASONS,
        "status_lists": "A status given as a list means policy allows any listed value (see the canary's review row).",
    }
    return out


def evaluate(proposed: dict, products: dict, tiers: list, core_ids: set) -> list:
    rows = []
    for c in proposed["canaries"]:
        pid = c["dsld_id"]
        prod = products.get(pid)
        res = {"dsld_id": pid, "in_core_catalog": pid in core_ids, "checks": []}
        if prod is None:
            res["checks"].append(("present", False, "missing from scored output"))
            rows.append(res)
            continue
        actual = {"expected_v4_module": prod.get("_v4_module"),
                  "expected_quality_score_status": prod.get("quality_score_status"),
                  "expected_quality_assessment_status": prod.get("quality_assessment_status"),
                  "expected_product_safety_status": prod.get("product_safety_status")}
        for field, got in actual.items():
            want = c[field]
            ok = got in want if isinstance(want, list) else got == want
            res["checks"].append((field, ok, got))
        band = c["expected_quality_tier_band"]
        tier = prod.get("quality_tier")
        if band is None:
            res["checks"].append(("expected_quality_tier_band", tier is None, tier))
        else:
            names = [t["name"] for t in tiers]
            ok = tier in names and names.index(band[1]) <= names.index(tier) <= names.index(band[0])
            res["checks"].append(("expected_quality_tier_band", ok, tier))
        if prod.get("quality_score_status") == SC:
            score = prod["quality_score_v4_100"]
            res["checks"].append(("tier_matches_display_score", tier_of(display(score), tiers) == tier, f"{score}->{tier}"))
            total = sum(p.get("score") or 0 for p in prod[P].values())
            res["checks"].append(("pillars_sum_to_score", abs(total - score) <= 0.15, f"{round(total, 2)} vs {score}"))
        for inv in c["expected_pillar_invariants"]:
            fails = []
            for path, op, value in proposed["_metadata"]["golden_set"]["pillar_invariants"][inv]["checks"]:
                ok, got = check(prod, path, op, value)
                if not ok:
                    fails.append(f"{path} {op} {value!r}: got {str(got)[:80]!r}")
            res["checks"].append((inv, not fails, "; ".join(fails)))
        rows.append(res)
    return rows


def render_tables(proposed: dict, products: dict, rows: list) -> str:
    res = {r["dsld_id"]: r for r in rows}
    abbrev = {"no_known_catalog_concern": "no_known", "suppressed_safety": "suppressed"}
    out = ["## Pillar invariants", "", "| id | rule | owner |", "|---|---|---|"]
    for k, v in {**{k: {**v, "owner": v["owner"]} for k, v in GLOBAL_SCORED_INVARIANTS.items()}, **INVARIANTS}.items():
        out.append(f"| `{k}` | {v['rule']} | {v['owner']} |")
    out += ["", "## Canary expectations and current result", "",
            "Status columns are expected values (a list means policy allows either). Current = tier and score on the reviewed run. "
            "Result = every check on that canary (statuses, band, global and pillar invariants).", "",
            "| # | dsld_id | product | route | score status | assessment | safety | tier band | current | invariants | extra movement reasons | result |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    new_ids = set(NEW)
    for n, c in enumerate(proposed["canaries"], 1):
        prod = products[c["dsld_id"]]
        r = res[c["dsld_id"]]
        fails = [name for name, ok, _ in r["checks"] if not ok]
        verdict = "PASS" if not fails else "FAIL: " + ", ".join(
            f"{x} ({FINDINGS.get(x, {}).get(c['dsld_id'], 'finding')})" for x in fails)
        qas = c["expected_quality_assessment_status"]
        band = c["expected_quality_tier_band"]
        extra = [x for x in c["allowed_movement_reasons"] if x not in DEFAULT_REASONS]
        name = f"{c['brand_name']} {c['product_name']}"[:60].replace("|", "/")
        out.append("| {} | {}{} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            n, c["dsld_id"], " (new)" if c["dsld_id"] in new_ids else "", name, c["expected_v4_module"],
            abbrev.get(c["expected_quality_score_status"], c["expected_quality_score_status"]),
            "/".join(qas) if isinstance(qas, list) else qas,
            abbrev.get(c["expected_product_safety_status"], c["expected_product_safety_status"]),
            "–".join(dict.fromkeys(band)) if band else "none",
            f"{prod.get('quality_tier')} {prod.get('quality_score_v4_100')}" if prod.get("quality_tier") else str(prod.get("verdict")),
            ", ".join(f"`{i}`" for i in c["expected_pillar_invariants"]), ", ".join(extra) or "—", verdict))
    return "\n".join(out) + "\n"


# Run only after branch claude/hungry-bell-fa1b07 (F2) is on main. 269286's approved expectations
# described the defect state (partial, unresolved identity, Poor). After F2 the label resolves to
# saw_palmetto. A raw -> scored replay on F2 code 0a70d9ce7 gives 57.4, Needs improvement, complete,
# Evidence evaluated_applicable 0.3, Dose 11.4 neutral, Verification unknown 6. The movement reason is
# identity_resolution, which is already allowed for this canary.
REANCHOR_AFTER_F2 = {
    "269286": {
        "expected_quality_assessment_status": CO,
        "expected_quality_tier_band": ["Poor", "Needs improvement"],  # +/-5 rule on 57.4
        "expected_pillar_invariants": ["evidence_single_active_not_nothing_to_assess", EA, DN, VU],
        "edge_cases": ["branded_extract_read_as_blend_header", "single_constituent_blend_row_resolved_f2"],
        "notes": "Prosterol (saw palmetto CO2 extract) 320 mg is filed by DSLD as a one-constituent blend. Before F2 the cleaner read it as a blend header (BLEND_GENERAL, partial, 31.0). F2 (claude/hungry-bell-fa1b07) resolves it to saw_palmetto, and these expectations pin the resolved behaviour.",
    },
}


def reanchor_after_f2() -> None:
    import data_batch
    doc = data_batch.load(CANARY_FILE)
    for c in doc["canaries"]:
        c.update(copy.deepcopy(REANCHOR_AFTER_F2.get(c["dsld_id"], {})))
    data_batch.save(CANARY_FILE, doc)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--products", type=Path, default=DEFAULT_PRODUCTS)
    ap.add_argument("--core-db", type=Path, default=DEFAULT_CORE_DB)
    ap.add_argument("--apply", action="store_true", help="write canary_products.json (only after Sean approves)")
    ap.add_argument("--reanchor-after-f2", action="store_true",
                    help="re-anchor 269286 once F2 (claude/hungry-bell-fa1b07) is merged; see REANCHOR_AFTER_F2")
    ap.add_argument("--evaluate-applied", action="store_true",
                    help="evaluate canary_products.json as it is, without rebuilding the proposal")
    args = ap.parse_args()
    if args.evaluate_applied:
        import data_batch
        doc = data_batch.load(CANARY_FILE)
        tiers = json.loads((REPO / CFG).read_text())["tiers"]
        products = load_products(args.products, {c["dsld_id"] for c in doc["canaries"]})
        core_ids = {str(r[0]) for r in sqlite3.connect(args.core_db).execute("select dsld_id from products_core")}
        rows = evaluate(doc, products, tiers, core_ids)
        failed = [(r["dsld_id"], n, g) for r in rows for n, ok, g in r["checks"] if not ok]
        print(f"applied canaries={len(rows)} checks={sum(len(r['checks']) for r in rows)} failed={len(failed)}")
        for f in failed:
            print("FAIL", *f)
        return 1 if failed else 0
    if args.reanchor_after_f2:
        reanchor_after_f2()
        print("re-anchored:", ", ".join(REANCHOR_AFTER_F2))
        return 0

    import data_batch
    doc = data_batch.load(CANARY_FILE)
    tiers = json.loads((REPO / CFG).read_text())["tiers"]
    ids = {c["dsld_id"] for c in doc["canaries"]} | set(NEW)
    products = load_products(args.products, ids)
    con = sqlite3.connect(args.core_db)
    core_ids = {str(r[0]) for r in con.execute("select dsld_id from products_core")}

    proposed = build(doc, products, tiers)
    rows = evaluate(proposed, products, tiers, core_ids)
    (HERE / "proposed_canaries.json").write_text(json.dumps(proposed, indent=2, ensure_ascii=False) + "\n")
    (HERE / "evaluation.json").write_text(json.dumps(rows, indent=2) + "\n")
    (HERE / "review_tables.md").write_text(render_tables(proposed, products, rows))
    failed = [(r["dsld_id"], name, got) for r in rows for name, ok, got in r["checks"] if not ok]
    print(f"canaries={len(proposed['canaries'])} checks={sum(len(r['checks']) for r in rows)} failed={len(failed)}"
          f" not_in_core={[r['dsld_id'] for r in rows if not r['in_core_catalog']]}")
    for f in failed:
        print("FAIL", *f)
    if args.apply:
        if proposed["_metadata"]["golden_set"]["approval"].startswith("PENDING"):
            print("refusing --apply: set golden_set.approval to Sean's recorded approval first")
            return 2
        data_batch.save(CANARY_FILE, proposed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
