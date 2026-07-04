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

DM = json.loads((SCRIPTS_ROOT / "scoring_v4" / "config" / "quality_score.json").read_text())["dose_magnitudes"]

ORIGINAL = {
    "generic": {
        "cap_supplemental_window": 22.0, "cap_multi_form_bonus": 3.0, "dimension_cap": 25.0,
        "window_rda_threshold": 25.0, "window_ul_partial_band": 100.0, "b7_ul_pct_threshold": 150.0,
        "window_overdose_credit": 11.0, "no_reference_individual_dose_credit": 16.0,
        "no_reference_product_evidence_credit": 12.0, "multi_form_premium_bio_threshold": 12.0,
        "multi_form_min_group_count": 2, "b7_per_flag_penalty": 2.0, "b7_cap": 3.0,
    },
    "multi_prenatal": {
        "dimension_cap": 25.0, "cap_rda_ai_coverage": 15.0, "cap_panel_breadth": 3.0,
        "cap_critical_nutrient_coverage": 5.0, "cap_prenatal_complement_support": 2.0,
        "b7_ul_pct_threshold": 150.0, "b7_per_flag_penalty": 2.0, "b7_cap": 3.0,
        "panel_breadth_full_count": 18, "prenatal_dha_full_mg": 200.0, "prenatal_dha_partial_mg": 100.0,
        "targeted_multi_selected_anchors": 5,
        "critical_min_pct_rda": {"folate": 50.0, "iron": 50.0, "iodine": 50.0,
                                 "vitamin_d": 50.0, "vitamin_b12": 50.0, "choline": 25.0},
    },
    "probiotic": {
        "cap_dose": 25.0, "cap_per_strain_cfu_disclosure": 10.0, "cap_cfu_adequacy": 15.0,
        "cap_aggregate_cfu_proxy_adequacy": 11.0, "aggregate_cfu_low_tier_presence_floor": 2.0,
        "aggregate_cfu_low_named_strain_total_floor": 4.0, "cap_direct_strain_mass_floor": 5.0,
        "v3_cfu_adequacy_cap": 5.0,
        "tier_points": {"low": 0.0, "adequate": 1.0, "good": 2.0, "excellent": 3.0},
        "support_level_caps": {"high": 1.0, "moderate": 0.75, "weak": 0.5},
    },
    "omega": {"cap_dose": 25.0},
    "sports": {"dimension_cap": 25.0},
    "fiber_digestive": {"dimension_cap": 25.0},
}


def test_config_matches_pre_hoist_values():
    for mod, vals in ORIGINAL.items():
        assert DM[mod] == vals, f"dose_magnitudes.{mod} drifted from pre-hoist values"


def test_runtime_constants_read_from_config_no_drift():
    assert generic_dose.CAP_SUPPLEMENTAL_WINDOW == DM["generic"]["cap_supplemental_window"] == 22.0
    assert generic_dose.B7_CAP == DM["generic"]["b7_cap"] == 3.0
    assert generic_dose.MULTI_FORM_MIN_GROUP_COUNT == DM["generic"]["multi_form_min_group_count"] == 2
    assert multi_prenatal_dose.DIMENSION_CAP == DM["multi_prenatal"]["dimension_cap"] == 25.0
    assert multi_prenatal_dose.CRITICAL_MIN_PCT_RDA == DM["multi_prenatal"]["critical_min_pct_rda"]
    assert multi_prenatal_dose.PANEL_BREADTH_FULL_COUNT == 18
    assert probiotic_dose.TIER_POINTS == DM["probiotic"]["tier_points"]
    assert probiotic_dose.SUPPORT_LEVEL_CAPS == DM["probiotic"]["support_level_caps"]
    assert probiotic_dose.CAP_CFU_ADEQUACY == 15.0
    assert omega_dose.CAP_DOSE == 25.0
    assert sports_dose.DIMENSION_CAP == 25.0
    assert fiber_digestive_dose.DIMENSION_CAP == 25.0
