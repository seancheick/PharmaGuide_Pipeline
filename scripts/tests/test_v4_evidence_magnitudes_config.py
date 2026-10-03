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
        "cap_total": 20.0, "cap_per_ingredient": 7.0,
        "enrollment_default_multiplier": 1.2,
        "primary_floor_strong": 14.0, "primary_floor_moderate": 11.0,
        "primary_floor_branded_strong": 18.0, "primary_floor_branded_moderate": 17.0,
        "nutrition_authority_floor": 10.0,
        # ONE owner for what a direction is worth; generic_evidence reads this rather than
        # hard-coding it, and its primary-floor path reads the same map. null = 0.0 since
        # 2026-09-18: evidence that did not show a benefit earns no affirmative credit.
        "effect_direction_multipliers": {"positive_strong": 1.0, "positive_weak": 0.85,
                                         "mixed": 0.6, "null": 0.0, "negative": 0.0},
        "enrollment_quality_bands": [[50.0, 0.6], [200.0, 0.8], [500.0, 1.0], [1000.0, 1.1]],
        "top_n_weights": [1.0, 0.7, 0.5, 0.3],
        "depth_bonus_bands": [[20.0, 0.25], [40.0, 0.5]],
    },
    "probiotic": {
        "cap_evidence": 20.0, "certainty_cap": 10.0, "applicability_cap": 6.0,
        "replication_cap": 4.0, "native_context_review_policy": "clinician_only",
        "alignment_weights": {"direct": 1.0, "partial": 0.75, "broad": 0.5,
                              "not_evaluable": 0.0, "none": 0.0},
        "generic_identity_weight": 0.5,
        "single_family_design_weights": {"rct": 1.0, "crossover_rct": 1.0, "cluster_rct": 1.0,
            "meta_analysis": 1.0, "systematic_review": 1.0, "guideline": 0.8,
            "observational": 0.5, "open_label": 0.4},
        "unspecified_human_design_weight": 4.0 / 6.0,
    },
    "multi_prenatal": {"cap_evidence": 20.0, "generic_cap_evidence": 20.0},
    "omega": {
        "cap_evidence": 20.0,
        "purpose_standards": {
            "omega_reviewed_weak": {"pillar_score": 10.4},
            "triglyceride_strong": {"pillar_score": 20.0},
            "prenatal_dha_intake_authority": {"pillar_score": 11.1},
            "prenatal_preterm_birth_outcome": {"score_eligible": False},
            "epa_predominant_depression": {"score_eligible": False},
            "high_dose_atrial_fibrillation_context": {"score_eligible": False,
                                                    "minimum_daily_epa_dha_mg": 1000},
        },
    },
}


def test_config_matches_reviewed_evidence_magnitudes():
    for mod, vals in EXPECTED.items():
        assert {key: value for key, value in EM[mod].items() if not key.startswith("_")} == {k: v for k, v in vals.items() if not k.startswith("_")}, f"evidence_magnitudes.{mod} drifted from reviewed values"


def test_runtime_constants_read_from_config_no_drift():
    assert generic_evidence.CAP_TOTAL == 20.0
    assert generic_evidence.PRIMARY_FLOOR_BRANDED_STRONG == 18.0
    # Below a study's dose the study does not apply: a gate, never a tunable gradient.
    assert not hasattr(generic_evidence, "SUB_CLINICAL_DOSE_GUARD_MULTIPLIER")
    assert "sub_clinical_dose_guard_multiplier" not in EM["generic"]
    # JSON lists reconstruct the original tuple-of-tuples / flat tuples
    assert generic_evidence.ENROLLMENT_QUALITY_BANDS == ((50.0, 0.6), (200.0, 0.8), (500.0, 1.0), (1000.0, 1.1))
    assert generic_evidence.TOP_N_WEIGHTS == (1.0, 0.7, 0.5, 0.3)
    assert generic_evidence.DEPTH_BONUS_BANDS == ((20.0, 0.25), (40.0, 0.5))
    assert probiotic_evidence.CAP_EVIDENCE == 20.0
    assert probiotic_evidence._EM["certainty_cap"] == 10.0
    assert probiotic_evidence._EM["applicability_cap"] == 6.0
    assert probiotic_evidence._EM["replication_cap"] == 4.0
    assert "cap_dose_applicability" not in EM["probiotic"]
    assert "dose_applicability_policy" not in EM["probiotic"]
    # Both lanes and both generic paths read the one config owner - no second copy anywhere.
    assert generic_evidence.EFFECT_DIRECTION_MULTIPLIERS == EXPECTED["generic"]["effect_direction_multipliers"]
    assert generic_evidence._EFFECT_FLOOR_MULTIPLIER is generic_evidence.EFFECT_DIRECTION_MULTIPLIERS
    assert probiotic_evidence.GENERIC_EFFECT_MULTIPLIERS is generic_evidence.EFFECT_DIRECTION_MULTIPLIERS
    assert multi_prenatal_evidence.CAP_EVIDENCE == multi_prenatal_evidence.GENERIC_CAP_EVIDENCE == 20.0
    assert omega_evidence.CAP_EVIDENCE == 20.0
