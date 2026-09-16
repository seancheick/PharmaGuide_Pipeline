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
    "omega": {"dimension_caps": ROUTER_DC},
    "probiotic": {"dimension_caps": [["formulation", 16], ["dose", 25], ["evidence", 20], ["transparency", 15]]},
    "b_complex": {"formulation_cap": 23.0, "dose_cap": 25.0, "evidence_cap": 20.0},
    "immune_support": {"formulation_bonus_cap": 12.0, "evidence_cap": 17.0},
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
    assert omega.DIMENSION_CAPS == (("formulation", 25), ("dose", 25), ("evidence", 20), ("transparency", 15))
    assert probiotic.DIMENSION_CAPS == (("formulation", 16), ("dose", 25), ("evidence", 20), ("transparency", 15))
    assert b_complex.FORMULATION_CAP == 23.0 and b_complex.B7_CAP == 3.0
    assert immune_support.IMMUNE_FORMULATION_BONUS_CAP == 12.0
    assert joint_support.JOINT_SUPPORT_EVIDENCE_CAP == 14.0
    assert joint_support.JOINT_TARGET_DOSE_MG == ORIGINAL["joint_support"]["target_dose_mg"]
    assert safety_hygiene.SAFETY_HYGIENE_CAP == 4.0
    # sugar bands (formulation_magnitudes)
    assert generic_formulation.DIETARY_SUGAR_MODERATE_PENALTY == 3.0
    assert generic_formulation.DIETARY_SUGAR_CAP == 4.0
