#!/usr/bin/env python3
"""Formulation-variant magnitudes config hoist (2026-07-04) — drift + value guards.

PURE REFACTOR: category-specific formulation/profile caps, form-quality points,
standardization tiers and botanical dose-band credits across the variant
score_formulation / botanical / collagen modules moved into
scoring_v4/config/quality_score.json (`formulation_variant_magnitudes.<module>`).
Empty diff (846 entrypoint×product pairs) verified neutral.

Pins config to pre-hoist values + runtime parity; canonical-ID sets stay in code.
"""
import json
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.modules import (   # noqa: E402
    multi_prenatal_formulation, omega_formulation, probiotic_formulation,
    sports_formulation, fiber_digestive_formulation, botanical_profile, collagen_profile,
)

FVM = json.loads((SCRIPTS_ROOT / "scoring_v4" / "config" / "quality_score.json").read_text())["formulation_variant_magnitudes"]

ORIGINAL = {
    "multi_prenatal": {
        "cap_formulation": 25.0, "formulation_presence_floor": 2.0, "cap_panel_form_quality": 12.0,
        "cap_premium_form_diversity": 4.0, "cap_key_form_support": 5.0, "cap_panel_disclosure_structure": 2.0,
        "cap_dosage_form_suitability": 2.0, "panel_form_smoothing_factor": 0.7, "panel_form_neutral_floor": 9.0,
        "bio_score_max": 15.0, "premium_form_threshold": 12.0, "premium_points_per_additional": 0.5,
        "gummy_formulation_penalty": 3.0,
    },
    "omega": {"cap_formulation": 25.0, "data_limited_form_floor": 19.0, "data_limited_form_min_epa_dha_mg": 750.0},
    "probiotic": {"cap_formulation": 25.0},
    "sports": {"dimension_cap": 30.0},
    "fiber_digestive": {"dimension_cap": 30.0},
    "botanical": {
        "botanical_formulation_cap": 15.0, "standardization_tier_full": 4.0, "standardization_tier_near": 3.0,
        "standardization_tier_half": 2.0, "standardization_tier_disclosed": 1.0,
        "botanical_dose_within": 21.0, "botanical_dose_near": 16.0, "botanical_dose_above": 12.0,
        "botanical_dose_below": 12.0, "botanical_dose_disclosed_no_ref": 12.0, "botanical_dose_blend_total": 10.0,
        "botanical_dose_primary_no_dose": 5.0, "botanical_dose_no_active": 0.0,
    },
    "collagen": {"collagen_formulation_cap": 15.0},
}


def test_config_matches_pre_hoist_values():
    for mod, vals in ORIGINAL.items():
        assert FVM[mod] == vals, f"formulation_variant_magnitudes.{mod} drifted from pre-hoist values"


def test_runtime_constants_read_from_config_no_drift():
    assert multi_prenatal_formulation.CAP_FORMULATION == 25.0
    assert multi_prenatal_formulation.GUMMY_FORMULATION_PENALTY == 3.0
    assert multi_prenatal_formulation.PANEL_FORM_SMOOTHING_FACTOR == 0.7
    assert omega_formulation.DATA_LIMITED_FORM_MIN_EPA_DHA_MG == 750.0
    assert probiotic_formulation.CAP_FORMULATION == 25.0
    assert sports_formulation.DIMENSION_CAP == 30.0
    assert fiber_digestive_formulation.DIMENSION_CAP == 30.0
    assert botanical_profile.BOTANICAL_FORMULATION_CAP == 15.0
    assert botanical_profile.STANDARDIZATION_TIER_FULL == 4.0
    assert botanical_profile.BOTANICAL_DOSE_WITHIN == 21.0
    assert botanical_profile.BOTANICAL_DOSE_NO_ACTIVE == 0.0
    assert collagen_profile.COLLAGEN_FORMULATION_CAP == 15.0
