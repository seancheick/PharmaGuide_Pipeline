#!/usr/bin/env python3
"""Category-magnitudes config hoist (2026-07-04) — drift + value guards.

PURE REFACTOR (final config-hoist batch): category-router dimension caps +
generic public caps/floors, and the category-adapter magnitudes
(b_complex / immune / joint / sleep / safety_hygiene) moved into
scoring_v4/config/quality_score.json (`category_magnitudes.<module>`). Also
hoists the generic_formulation DIETARY_SUGAR_* bands (missed in the pilot) into
the existing formulation_magnitudes block. Empty diff (1128 entrypoint×product
pairs) verified neutral.

Pins config to pre-hoist values + runtime parity; canonical-ID sets, regex form
patterns and the retired affine constants stay in code.
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
    "multi_prenatal": {"dimension_caps": [["formulation", 14], ["dose", 25], ["evidence", 20], ["transparency", 15]]},
    # 1.3.0 omega rubric: transparency 15 -> 13 when the unreachable oxidation
    # component was retired (Verification owns independently tested oxidation).
    "omega": {"dimension_caps": [["formulation", 25], ["dose", 25], ["evidence", 20], ["transparency", 13]]},
    # 1.20.0: optional prebiotics do not increase probiotic Formulation.
    "probiotic": {"dimension_caps": [["formulation", 15], ["dose", 25], ["evidence", 20], ["transparency", 15]]},
    "b_complex": {"formulation_cap": 23.0, "dose_cap": 25.0, "evidence_cap": 20.0},
    # 1.21.1 (authored as 1.13.1 + 1.13.2): the high-variability botanical stack penalty moved out of
    # immune_support.py literals (pure refactor, values unchanged).
    # Then the Dose bands, above-band fraction, daily-use points, Dose cap
    # and high-zinc / high-vitamin-D thresholds followed (pure refactor).
    "immune_support": {"evidence_cap": 17.0,
                       "high_variability_botanical_stack_min_count": 3,
                       "high_variability_botanical_stack_penalty": 3.0,
                       "dose_cap": 22.0,
                       "dose_bands": {
                           "vitamin_c_mg": {"low": 100.0, "high": 1000.0, "points": 3.0},
                           "vitamin_d_mcg": {"low": 15.0, "high": 50.0, "points": 3.0},
                           "zinc_mg": {"low": 8.0, "high": 25.0, "points": 3.0},
                           "copper_mg": {"low": 0.5, "high": 2.0, "points": 1.5},
                           "selenium_mcg": {"low": 45.0, "high": 200.0, "points": 1.5},
                           "beta_glucan_mg": {"low": 100.0, "high": 250.0, "points": 3.0},
                           "quercetin_mg": {"low": 250.0, "high": 1000.0, "points": 2.5},
                           "elderberry_mg": {"low": 100.0, "high": 600.0, "points": 2.5},
                       },
                       "dose_above_band_fraction": 0.5,
                       "daily_use_discipline_points": 2.0,
                       "high_zinc_threshold_mg": 40.0,
                       "high_vitamin_d_threshold_mcg": 100.0},
    "joint_support": {"evidence_cap": 14.0,
                      "target_dose_mg": {"glucosamine": 1500.0, "chondroitin": 1200.0, "msm": 1500.0,
                                         "uc_ii": 40.0, "hyaluronic_acid": 120.0}},
    "safety_hygiene": {"cap": 4.0},
}
SUGAR = {
    "dietary_sugar_low_added_penalty": 1.0, "dietary_sugar_sugar_alcohol_penalty": 1.0,
    "dietary_sugar_high_glycemic_or_syrup_penalty": 2.0,
    "dietary_sugar_moderate_penalty": 3.0, "dietary_sugar_high_penalty": 4.0, "dietary_sugar_cap": 4.0,
}


def test_category_config_matches_pre_hoist_values():
    for mod, vals in ORIGINAL.items():
        assert CM[mod] == vals, f"category_magnitudes.{mod} drifted from pre-hoist values"


def test_sugar_bands_config_matches_pre_hoist_values():
    for k, v in SUGAR.items():
        assert FM[k] == v, f"formulation_magnitudes.{k} drifted"


def test_runtime_constants_read_from_config_no_drift():
    assert generic.DIMENSION_CAPS == (("formulation", 30), ("dose", 25), ("evidence", 20), ("transparency", 10))
    assert generic.MANUFACTURER_TRUST_CAP == 5
    assert generic.MANUFACTURER_VIOLATIONS_FLOOR == -25
    assert multi_prenatal.DIMENSION_CAPS == (("formulation", 14), ("dose", 25), ("evidence", 20), ("transparency", 15))
    assert omega.DIMENSION_CAPS == (("formulation", 25), ("dose", 25), ("evidence", 20), ("transparency", 13))
    assert probiotic.DIMENSION_CAPS == (("formulation", 15), ("dose", 25), ("evidence", 20), ("transparency", 15))
    assert b_complex.FORMULATION_CAP == 23.0 and b_complex.B7_CAP == 3.0
    assert immune_support.IMMUNE_EVIDENCE_CAP == 17.0
    assert immune_support.HIGH_VARIABILITY_BOTANICAL_STACK_MIN_COUNT == 3
    assert immune_support.HIGH_VARIABILITY_BOTANICAL_STACK_PENALTY == 3.0
    assert immune_support.IMMUNE_DOSE_CAP == 22.0
    assert immune_support.IMMUNE_DOSE_BANDS == ORIGINAL["immune_support"]["dose_bands"]
    assert immune_support.IMMUNE_DOSE_ABOVE_BAND_FRACTION == 0.5
    assert immune_support.IMMUNE_DAILY_USE_DISCIPLINE_POINTS == 2.0
    assert immune_support.HIGH_ZINC_THRESHOLD_MG == 40.0
    assert immune_support.HIGH_VITAMIN_D_THRESHOLD_MCG == 100.0
    assert joint_support.JOINT_SUPPORT_EVIDENCE_CAP == 14.0
    assert joint_support.JOINT_TARGET_DOSE_MG == ORIGINAL["joint_support"]["target_dose_mg"]
    assert safety_hygiene.SAFETY_HYGIENE_CAP == 4.0
    # sugar bands (formulation_magnitudes)
    assert generic_formulation.DIETARY_SUGAR_MODERATE_PENALTY == 3.0
    assert generic_formulation.DIETARY_SUGAR_CAP == 4.0
