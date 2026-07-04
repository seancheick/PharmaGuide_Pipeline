#!/usr/bin/env python3
"""Formulation-magnitudes config hoist (2026-07-04) — drift + value guards.

PURE REFACTOR: the A1-A6 + B0 formulation point values, caps, and tier
thresholds moved from generic_formulation.py's hardcoded constants into
scoring_v4/config/quality_score.json (`formulation_magnitudes`). Empty-diff on a
real-product sample + targeted formulation tests verified score-neutrality at
hoist time.

These tests pin:
  (a) the config to the ORIGINAL values, so any future change is a deliberate
      recalibration rather than an accidental drift from the pre-hoist scores;
  (b) the module runtime constants to the config (single source, no divergence).
"""
import json
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.modules import generic_formulation as gf   # noqa: E402

CFG = json.loads((SCRIPTS_ROOT / "scoring_v4" / "config" / "quality_score.json").read_text())
FM = CFG["formulation_magnitudes"]

# The exact pre-hoist hardcoded values (the empty-diff baseline).
ORIGINAL = {
    "dimension_cap": 30.0, "presence_floor": 2.0,
    "a1_bio_score_cap": 15.0,
    "a2_premium_forms_cap": 4.0, "a2_premium_form_threshold": 12.0,
    "a2_premium_form_points_per_additional": 0.5,
    "a3_delivery_cap": 3.0, "a4_absorption_cap": 3.0,
    "a5_excellence_cap": 4.0, "a5a_organic": 1.0, "a5b_standardized_full": 1.0,
    "a5b_standardized_marker_only": 0.5, "a5d_non_gmo_project": 0.5, "a5e_natural": 1.0,
    "a6_single_ingredient_cap": 4.0, "a6_tier_floor_bio": 10.0,
    "a6_tier_solid_bio": 12.0, "a6_tier_elite_bio": 14.0,
    "a6_points_good": 1.0, "a6_points_solid": 3.0, "a6_points_elite": 4.0,
    "enzyme_cap": 2.0, "enzyme_points_per_named": 0.5,
    "premium_single_floor_solid": 22.0, "premium_single_floor_elite": 24.0,
    "standard_single_floor_validated_low_bio": 13.0,
    "b0_high_risk_penalty": 10.0, "b0_watchlist_penalty": 5.0, "b0_moderate_penalty": 10.0,
}
ORIGINAL_DELIVERY = {1: 3.0, 2: 2.0, 3: 1.0}
ORIGINAL_SYNERGY = {1: 1.0, 2: 0.75, 3: 0.5, 4: 0.25}


def test_config_scalars_match_original_values():
    for k, v in ORIGINAL.items():
        assert FM[k] == v, f"{k}: config {FM[k]} != original {v} (recalibration must be deliberate)"


def test_config_tier_dicts_match_original():
    assert {int(k): v for k, v in FM["a3_delivery_tier_points"].items()} == ORIGINAL_DELIVERY
    assert {int(k): v for k, v in FM["a5c_synergy_tier_points"].items()} == ORIGINAL_SYNERGY


def test_runtime_constants_read_from_config_no_drift():
    assert gf.CAP_BIO_SCORE == FM["a1_bio_score_cap"]
    assert gf.DIMENSION_CAP == FM["dimension_cap"]
    assert gf.A6_POINTS_ELITE == FM["a6_points_elite"]
    assert gf.B0_HIGH_RISK_PENALTY == FM["b0_high_risk_penalty"]
    assert gf.CAP_EXCELLENCE == FM["a5_excellence_cap"]
    assert gf.DELIVERY_TIER_POINTS == {int(k): v for k, v in FM["a3_delivery_tier_points"].items()}
    assert gf.A5C_SYNERGY_TIER_POINTS == {int(k): v for k, v in FM["a5c_synergy_tier_points"].items()}


def test_runtime_matches_original_end_to_end():
    # module constant resolves (via config) to the exact pre-hoist value
    assert gf.CAP_BIO_SCORE == 15.0
    assert gf.A6_TIER_ELITE_BIO == 14.0
    assert gf.B0_MODERATE_PENALTY == 10.0
    assert gf.DELIVERY_TIER_POINTS == {1: 3.0, 2: 2.0, 3: 1.0}
    assert gf.B0_CAP == gf.DIMENSION_CAP == 30.0
