#!/usr/bin/env python3
"""Transparency-magnitudes config hoist (2026-07-04) — drift + value guards.

PURE REFACTOR: disclosure bases, blend (B5) coefficients/multipliers, allergen
(B2)/label (B3) points and the disease-claim (B6) penalty across the four
score_transparency modules moved into
scoring_v4/config/quality_score.json (`transparency_magnitudes.<module>`).
Empty score_transparency diff (376 module×product pairs) verified neutral.

Pins config to pre-hoist values + runtime parity. Regex keyword patterns and the
generic-override category set stay in code.
"""
import json
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scoring_v4.modules import (   # noqa: E402
    generic_transparency, multi_prenatal_transparency,
    probiotic_transparency, omega_transparency,
)

TM = json.loads((SCRIPTS_ROOT / "scoring_v4" / "config" / "quality_score.json").read_text())["transparency_magnitudes"]

ORIGINAL = {
    "generic": {
        "dimension_cap": 10.0, "clear_disclosure_base": 6.0, "complete_active_disclosure_bonus": 3.0,
        "b2_cap": 2.0, "b2_severity_points": {"high": 2.0, "moderate": 1.5, "low": 1.0},
        "b3_cap": 4.0, "b3_allergen_free": 2.0, "b3_gluten_free": 1.0, "b3_vegan_or_vegetarian": 1.0,
        "b5_base": {"full": 0.0, "partial": 1.0, "none": 2.0},
        "b5_prop_coef": {"full": 0.0, "partial": 3.0, "none": 5.0},
        "b5_cap": 10.0, "b5_count_denom_min": 8,
        "b5_class_multipliers": {"probiotic": 0.4, "multi_or_prenatal": 1.3, "sports_active": 1.5, "generic": 1.0},
        "b5_trivial_micro_blend_hidden_mass_mg": 1.0, "b5_trivial_micro_blend_max_impact": 0.01,
        "b6_disease_claim_penalty": 5.0,
    },
    "multi_prenatal": {
        "dimension_cap": 15.0, "cap_panel_identity_disclosure": 4.0,
        "cap_panel_individual_dose_disclosure": 7.0,
        "adjunct_blend_panel_disclosure_threshold": 0.9, "adjunct_blend_b5_cap": 2.0,
    },
    "probiotic": {
        "dimension_cap": 15.0, "cap_strain_identities": 8.0,
        "cap_per_strain_cfu": 7.0, "cap_aggregate_cfu_disclosure_proxy": 4.0,
    },
    "omega": {
        "cap_transparency": 15.0, "data_limited_transparency_floor": 12.0,
        "data_limited_transparency_min_epa_dha_mg": 750.0,
    },
}


def test_config_matches_pre_hoist_values():
    for mod, vals in ORIGINAL.items():
        assert TM[mod] == vals, f"transparency_magnitudes.{mod} drifted from pre-hoist values"


def test_runtime_constants_read_from_config_no_drift():
    assert generic_transparency.DIMENSION_CAP == 10.0
    assert generic_transparency.B2_SEVERITY_POINTS == {"high": 2.0, "moderate": 1.5, "low": 1.0}
    assert generic_transparency.B5_BASE == {"full": 0.0, "partial": 1.0, "none": 2.0}
    assert generic_transparency.B5_PROP_COEF == {"full": 0.0, "partial": 3.0, "none": 5.0}
    assert generic_transparency.B5_CLASS_MULTIPLIERS == TM["generic"]["b5_class_multipliers"]
    assert generic_transparency.B5_COUNT_DENOM_MIN == 8
    assert generic_transparency.B6_DISEASE_CLAIM_PENALTY == 5.0
    assert multi_prenatal_transparency.CAP_PANEL_INDIVIDUAL_DOSE_DISCLOSURE == 7.0
    assert multi_prenatal_transparency.ADJUNCT_BLEND_PANEL_DISCLOSURE_THRESHOLD == 0.9
    assert probiotic_transparency.CAP_STRAIN_IDENTITIES == 8.0
    assert omega_transparency.DATA_LIMITED_TRANSPARENCY_MIN_EPA_DHA_MG == 750.0
