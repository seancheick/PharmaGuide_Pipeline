#!/usr/bin/env python3
"""Dose-magnitudes config hoist (2026-07-04) — drift + value guards.

PURE REFACTOR: the dose-dimension caps, windows, thresholds and penalties across
the six score_dose modules moved from hardcoded constants into
scoring_v4/config/quality_score.json (`dose_magnitudes.<module>`). Empty-diff on
a real-product sample (564 module×product pairs) verified score-neutrality.

Pins (a) the config to the pre-hoist values (drift → deliberate recalibration),
and (b) each module's runtime constants to the config (single source).
"""
import json
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.modules import (   # noqa: E402
    generic_dose, multi_prenatal_dose, probiotic_dose,
    omega_dose, sports_dose, fiber_digestive_dose,
)

CFG = json.loads((SCRIPTS_ROOT / "scoring_v4" / "config" / "quality_score.json").read_text())
DM = CFG["dose_magnitudes"]
DOSE_CEILING = CFG["dose_safety_ceiling"]

ORIGINAL = {
    "generic": {
        # 1.21.0: the multi-form bonus and its two thresholds are retired
        # (IQM bio_score owns form quality); exact equality keeps them out.
        "cap_supplemental_window": 22.0, "dimension_cap": 25.0,
        # Dose V4.1 (§2.4): the per-nutrient UL band key is retired.
        "window_rda_threshold": 25.0,
        "window_overdose_credit": 11.0, "window_high_source_pct": 20.0, "window_full_adequacy_pct": 100.0,
        # 1.26.0 (V4.1 Step 4): the 16/12 no-reference credits are replaced by
        # the one dose_subscale.unbenchmarked_neutral_public owner.
    },
    "multi_prenatal": {
        # 1.26.0: panel breadth is count-based and retired; the prenatal
        # complement scores DHA only (the reviewed prenatal anchor).
        "dimension_cap": 25.0, "cap_rda_ai_coverage": 15.0,
        "cap_critical_nutrient_coverage": 5.0, "cap_prenatal_complement_support": 1.0,
        "prenatal_dha_full_mg": 200.0, "prenatal_dha_partial_mg": 100.0,
        "targeted_multi_selected_anchors": 5,
        "critical_min_pct_rda": {"folate": 50.0, "iron": 50.0, "iodine": 50.0,
                                 "vitamin_d": 50.0, "vitamin_b12": 50.0, "choline": 25.0},
    },
    "probiotic": {
        # 2026-09-04: remove invented allocations / clinical support from Dose.
        # 1.26.0: per-strain disclosure moves to Transparency, and a total CFU or
        # a strain mass is a recorded label limit with no floor credit.
        "cap_dose": 25.0, "cap_cfu_adequacy": 15.0,
        "v3_cfu_adequacy_cap": 5.0,
        "tier_points": {"low": 0.0, "adequate": 1.0, "good": 2.0, "excellent": 3.0},
        "dose_applicability_policy": {"credit": {"EXACT_TESTED_DOSE": 1.0,
            "WITHIN_TESTED_RANGE": 0.0, "NEAR_TESTED_RANGE": 0.0,
            "OUTSIDE_TESTED_RANGE": 0.0, "DOSE_UNKNOWN": 0.0}},
    },
    "omega": {"cap_dose": 25.0},
    "sports": {"dimension_cap": 25.0},
    "fiber_digestive": {"dimension_cap": 25.0},
}


def test_config_matches_pre_hoist_values():
    for mod, vals in ORIGINAL.items():
        values = {k: v for k, v in DM[mod].items()
                  if not k.startswith("_") and k != "contribution_policy_targets"}  # _doc strings are not magnitudes
        assert values == vals, f"dose_magnitudes.{mod} drifted from pinned values"


def test_contribution_policy_targets_are_pinned():
    # Dose V4.1 section 3.1 (Sean, 2026-10-17): 20% of the FDA Daily Value.
    targets = DM["generic"]["contribution_policy_targets"]
    assert {k: v["target_mg"] for k, v in targets.items() if not k.startswith("_")} == {
        "magnesium": 84.0, "calcium": 260.0}


def test_dose_safety_ceiling_has_one_config_owner():
    assert {k: v for k, v in DOSE_CEILING.items() if not k.startswith("_") and k != "caffeine"} == {
        "exceeds_above_pct": 100.0,
        "zero_at_pct": 150.0,
        "partial_ceiling_public": 10.0,
    }
    assert "dose_safety_policy" not in CFG
    # Dose V4.1 D3: caffeine is the one approved non-UL upper reference.
    caffeine = DOSE_CEILING["caffeine"]
    assert (caffeine["exceeds_above_mg_day"], caffeine["zero_at_mg_day"]) == (400.0, 600.0)
    serialized_nested_blocks = json.dumps({
        "dose_magnitudes": DM,
        "category_magnitudes": CFG["category_magnitudes"],
    })
    assert "b7_ul_pct_threshold" not in serialized_nested_blocks
    assert "b7_per_flag_penalty" not in serialized_nested_blocks
    assert '"b7_cap"' not in serialized_nested_blocks


def test_runtime_constants_read_from_config_no_drift():
    assert generic_dose.CAP_SUPPLEMENTAL_WINDOW == DM["generic"]["cap_supplemental_window"] == 22.0
    for module in (generic_dose, multi_prenatal_dose):
        assert not hasattr(module, "B7_CAP") and not hasattr(module, "B7_UL_PCT_THRESHOLD")
    assert multi_prenatal_dose.DIMENSION_CAP == DM["multi_prenatal"]["dimension_cap"] == 25.0
    assert multi_prenatal_dose.CRITICAL_MIN_PCT_RDA == DM["multi_prenatal"]["critical_min_pct_rda"]
    assert not hasattr(multi_prenatal_dose, "PANEL_BREADTH_FULL_COUNT")
    assert not hasattr(generic_dose, "NO_REFERENCE_INDIVIDUAL_DOSE_CREDIT")
    assert not hasattr(probiotic_dose, "AGGREGATE_CFU_LOW_NAMED_STRAIN_TOTAL_FLOOR")
    assert CFG["dose_subscale"]["unbenchmarked_neutral_public"] == 11.4
    assert probiotic_dose.TIER_POINTS == DM["probiotic"]["tier_points"]
    assert "support_level_caps" not in DM["probiotic"]
    assert probiotic_dose.CAP_CFU_ADEQUACY == 15.0
    assert omega_dose.CAP_DOSE == 25.0
    assert sports_dose.DIMENSION_CAP == 25.0
    assert fiber_digestive_dose.DIMENSION_CAP == 25.0
