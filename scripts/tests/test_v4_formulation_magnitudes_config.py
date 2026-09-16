#!/usr/bin/env python3
"""Canonical generic-Formulation config ownership guards."""

import json
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.modules import generic_formulation as gf  # noqa: E402

CFG = json.loads(
    (SCRIPTS_ROOT / "scoring_v4" / "config" / "quality_score.json").read_text()
)
FM = CFG["formulation_magnitudes"]

CANONICAL = {
    "dimension_cap": 30.0,
    "presence_floor": 2.0,
    "a1_bio_score_cap": 15.0,
    "a3_delivery_cap": 3.0,
    "a4_absorption_cap": 3.0,
    "a5b_standardized_full": 1.0,
    "a5b_standardized_marker_only": 0.5,
    "b0_high_risk_penalty": 10.0,
    "b0_watchlist_penalty": 5.0,
    "b0_moderate_penalty": 10.0,
}

RETIRED = {
    "a2_premium_forms_cap",
    "a2_premium_form_threshold",
    "a2_premium_form_points_per_additional",
    "a5_excellence_cap",
    "a5a_organic",
    "a5c_synergy_tier_points",
    "a5d_non_gmo_project",
    "a5e_natural",
    "a6_single_ingredient_cap",
    "a6_tier_floor_bio",
    "a6_tier_solid_bio",
    "a6_tier_elite_bio",
    "a6_points_good",
    "a6_points_solid",
    "a6_points_elite",
    "enzyme_cap",
    "enzyme_points_per_named",
    "premium_single_floor_solid",
    "premium_single_floor_elite",
    "standard_single_floor_validated_low_bio",
}


def test_config_contains_only_current_generic_formulation_magnitudes() -> None:
    for key, value in CANONICAL.items():
        assert FM[key] == value
    assert RETIRED.isdisjoint(FM)


def test_delivery_tiers_are_config_owned() -> None:
    assert {int(k): v for k, v in FM["a3_delivery_tier_points"].items()} == {
        1: 3.0,
        2: 2.0,
        3: 1.0,
    }


def test_runtime_constants_read_the_canonical_config() -> None:
    assert gf.CAP_BIO_SCORE == FM["a1_bio_score_cap"] == 15.0
    assert gf.DIMENSION_CAP == FM["dimension_cap"] == 30.0
    assert gf.B0_HIGH_RISK_PENALTY == FM["b0_high_risk_penalty"] == 10.0
    assert gf.DELIVERY_TIER_POINTS == {1: 3.0, 2: 2.0, 3: 1.0}
    assert gf.B0_CAP == gf.DIMENSION_CAP
