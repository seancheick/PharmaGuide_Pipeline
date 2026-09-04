#!/usr/bin/env python3
"""Evidence-magnitudes config hoist (2026-07-04) — drift + value guards.

Original hoist: evidence-dimension caps, primary-evidence floors, enrollment/depth
bands and effect-direction multipliers across the four score_evidence modules
moved into scoring_v4/config/quality_score.json (`evidence_magnitudes.<module>`).
Pins reviewed values and each module's runtime constants to the config. The
probiotic /8 allocation now requires reviewed dose applicability; marketing
indication alignment is metadata only, not a scoring component.
"""
import json
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.modules import (   # noqa: E402
    generic_evidence, probiotic_evidence, multi_prenatal_evidence, omega_evidence,
)

EM = json.loads((SCRIPTS_ROOT / "scoring_v4" / "config" / "quality_score.json").read_text())["evidence_magnitudes"]

EXPECTED = {
    "generic": {
        "cap_total": 20.0, "cap_per_ingredient": 7.0, "supra_clinical_multiple": 3.0,
        "sub_clinical_dose_guard_multiplier": 0.25, "enrollment_default_multiplier": 1.2,
        "primary_floor_strong": 14.0, "primary_floor_moderate": 11.0,
        "primary_floor_branded_strong": 18.0, "primary_floor_branded_moderate": 17.0,
        "nutrition_authority_floor": 10.0, "primary_mass_fraction": 0.5,
        "enrollment_quality_bands": [[50.0, 0.6], [200.0, 0.8], [500.0, 1.0], [1000.0, 1.1]],
        "top_n_weights": [1.0, 0.7, 0.5, 0.3],
        "depth_bonus_bands": [[20.0, 0.25], [40.0, 0.5]],
    },
    "probiotic": {
        "cap_evidence": 20.0, "cap_strain_clinical": 12.0, "cap_dose_applicability": 8.0,
        "effect_direction_multipliers": {"positive_strong": 1.0, "positive_weak": 0.85,
                                         "mixed": 0.6, "null": 0.25, "negative": 0.0},
        "native_strain_evidence_points": {"strong": 8.0, "high": 8.0, "moderate": 6.0,
                                          "medium": 6.0, "weak": 3.0, "low": 3.0, "limited": 3.0},
        "native_strain_evidence_weights": [1.0, 0.7, 0.5, 0.3],
    },
    "multi_prenatal": {"cap_evidence": 20.0, "generic_cap_evidence": 20.0},
    "omega": {"cap_evidence": 20.0},
}


def test_config_matches_reviewed_evidence_magnitudes():
    for mod, vals in EXPECTED.items():
        assert EM[mod] == vals, f"evidence_magnitudes.{mod} drifted from reviewed values"


def test_runtime_constants_read_from_config_no_drift():
    assert generic_evidence.CAP_TOTAL == 20.0
    assert generic_evidence.PRIMARY_FLOOR_BRANDED_STRONG == 18.0
    assert generic_evidence.SUB_CLINICAL_DOSE_GUARD_MULTIPLIER == 0.25
    # JSON lists reconstruct the original tuple-of-tuples / flat tuples
    assert generic_evidence.ENROLLMENT_QUALITY_BANDS == ((50.0, 0.6), (200.0, 0.8), (500.0, 1.0), (1000.0, 1.1))
    assert generic_evidence.TOP_N_WEIGHTS == (1.0, 0.7, 0.5, 0.3)
    assert generic_evidence.DEPTH_BONUS_BANDS == ((20.0, 0.25), (40.0, 0.5))
    assert probiotic_evidence.CAP_STRAIN_CLINICAL == EM["probiotic"]["cap_strain_clinical"] == 12.0
    assert probiotic_evidence.CAP_DOSE_APPLICABILITY == EM["probiotic"]["cap_dose_applicability"] == 8.0
    assert probiotic_evidence.EFFECT_DIRECTION_MULTIPLIERS == EXPECTED["probiotic"]["effect_direction_multipliers"]
    assert probiotic_evidence.NATIVE_STRAIN_EVIDENCE_POINTS == EXPECTED["probiotic"]["native_strain_evidence_points"]
    assert probiotic_evidence.NATIVE_STRAIN_EVIDENCE_WEIGHTS == (1.0, 0.7, 0.5, 0.3)
    assert multi_prenatal_evidence.CAP_EVIDENCE == multi_prenatal_evidence.GENERIC_CAP_EVIDENCE == 20.0
    assert omega_evidence.CAP_EVIDENCE == 20.0
