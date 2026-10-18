#!/usr/bin/env python3
"""Category magnitude value guards and runtime parity.

Surviving formulation, evidence and compatibility budgets remain pinned.
Approved retired Dose windows must stay absent; source-reference semantics
are validated separately from these numerical magnitudes.
"""
import json
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.modules import (   # noqa: E402
    generic, multi_prenatal, omega, probiotic, b_complex,
    immune_support, joint_support, sleep_support, safety_hygiene, generic_formulation,
)

CFG = json.loads((SCRIPTS_ROOT / "scoring_v4" / "config" / "quality_score.json").read_text())
CM = CFG["category_magnitudes"]
FM = CFG["formulation_magnitudes"]

ROUTER_DC = [["formulation", 25], ["dose", 25], ["evidence", 20], ["transparency", 15]]
ORIGINAL = {
    "generic": {
        "dimension_caps": [["formulation", 30], ["dose", 25], ["evidence", 20], ["transparency", 10]],
        "manufacturer_trust_cap": 5, "manufacturer_violations_floor": -25,
        "botanical_raw_floor": 40.0,
    },
    # 1.7.0: multi/prenatal Formulation is IQM panel form quality 12 + disclosure 2.
    # 1.26.0 (V4.1 Step 4): Formulation caps follow the retained form-quality
    # component (multi panel 12, B-complex 8); disclosure and count credits are retired.
    "multi_prenatal": {"dimension_caps": [["formulation", 12], ["dose", 25], ["evidence", 20], ["transparency", 15]]},
    # 1.21.3: the cap is the 5 + 3 + 3 live disclosure components; oxidation
    # remains Verification-owned and contributes no Transparency points.
    "omega": {"dimension_caps": [["formulation", 25], ["dose", 25], ["evidence", 20], ["transparency", 11]]},
    # 1.20.0: optional prebiotics do not increase probiotic Formulation.
    "probiotic": {"dimension_caps": [["formulation", 15], ["dose", 25], ["evidence", 20], ["transparency", 15]]},
    "b_complex": {"formulation_cap": 8.0, "dose_cap": 25.0, "evidence_cap": 20.0},
    # 1.21.1 (authored as 1.13.1 + 1.13.2): the high-variability botanical stack penalty moved out of
    # immune_support.py literals (pure refactor, values unchanged).
    # Approved Dose retirement removes amount windows and above-band cuts;
    # compatibility component budgets and diagnostic thresholds stay unchanged.
    "immune_support": {"evidence_cap": 17.0,
                       "high_variability_botanical_stack_min_count": 3,
                       "high_variability_botanical_stack_penalty": 3.0,
                       "dose_cap": 22.0,
                       "dose_bands": {
                           "vitamin_c_mg": {"points": 3.0},
                           "vitamin_d_mcg": {"points": 3.0},
                           "zinc_mg": {"points": 3.0},
                           "copper_mg": {"points": 1.5},
                           "selenium_mcg": {"points": 1.5},
                           "beta_glucan_mg": {"points": 3.0},
                           "quercetin_mg": {"points": 2.5},
                           "elderberry_mg": {"points": 2.5},
                       },
                       "daily_use_discipline_points": 2.0,
                       "high_zinc_threshold_mg": 40.0,
                       "high_vitamin_d_threshold_mcg": 100.0},
    "joint_support": {"evidence_cap": 14.0},
    "safety_hygiene": {"cap": 4.0},
}
SUGAR = {
    "dietary_sugar_low_added_penalty": 1.0, "dietary_sugar_sugar_alcohol_penalty": 1.0,
    "dietary_sugar_high_glycemic_or_syrup_penalty": 2.0,
    "dietary_sugar_moderate_penalty": 3.0, "dietary_sugar_high_penalty": 4.0, "dietary_sugar_cap": 4.0,
}


def test_category_config_matches_pre_hoist_values():
    for mod, vals in ORIGINAL.items():
        magnitudes = {key: value for key, value in CM[mod].items() if key != "reference_semantics"}
        assert magnitudes == vals, f"category_magnitudes.{mod} retained magnitudes drifted"
    assert "dose_above_band_fraction" not in CM["immune_support"]
    assert all(set(band) == {"points"} for band in CM["immune_support"]["dose_bands"].values())
    assert "target_dose_mg" not in CM["joint_support"]
    assert "sleep_support" not in CM


def test_sugar_bands_config_matches_pre_hoist_values():
    for k, v in SUGAR.items():
        assert FM[k] == v, f"formulation_magnitudes.{k} drifted"


def test_runtime_constants_read_from_config_no_drift():
    assert generic.DIMENSION_CAPS == (("formulation", 30), ("dose", 25), ("evidence", 20), ("transparency", 10))
    assert generic.MANUFACTURER_TRUST_CAP == 5
    assert generic.MANUFACTURER_VIOLATIONS_FLOOR == -25
    assert multi_prenatal.DIMENSION_CAPS == (("formulation", 12), ("dose", 25), ("evidence", 20), ("transparency", 15))
    assert omega.DIMENSION_CAPS == (("formulation", 25), ("dose", 25), ("evidence", 20), ("transparency", 11))
    assert probiotic.DIMENSION_CAPS == (("formulation", 15), ("dose", 25), ("evidence", 20), ("transparency", 15))
    assert b_complex.FORMULATION_CAP == 8.0 and not hasattr(b_complex, "B7_CAP")
    assert immune_support.IMMUNE_EVIDENCE_CAP == 17.0
    assert immune_support.HIGH_VARIABILITY_BOTANICAL_STACK_MIN_COUNT == 3
    assert immune_support.HIGH_VARIABILITY_BOTANICAL_STACK_PENALTY == 3.0
    assert immune_support.IMMUNE_DOSE_CAP == 22.0
    assert immune_support.IMMUNE_DOSE_BANDS == ORIGINAL["immune_support"]["dose_bands"]
    assert not hasattr(immune_support, "IMMUNE_DOSE_ABOVE_BAND_FRACTION")
    assert immune_support.IMMUNE_DAILY_USE_DISCIPLINE_POINTS == 2.0
    assert immune_support.HIGH_ZINC_THRESHOLD_MG == 40.0
    assert immune_support.HIGH_VITAMIN_D_THRESHOLD_MCG == 100.0
    assert joint_support.JOINT_SUPPORT_EVIDENCE_CAP == 14.0
    assert not hasattr(joint_support, "JOINT_TARGET_DOSE_MG")
    assert safety_hygiene.SAFETY_HYGIENE_CAP == 4.0
    # sugar bands (formulation_magnitudes)
    assert generic_formulation.DIETARY_SUGAR_MODERATE_PENALTY == 3.0
    assert generic_formulation.DIETARY_SUGAR_CAP == 4.0
