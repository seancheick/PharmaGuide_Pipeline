#!/usr/bin/env python3
"""Formulation-variant configuration contract and runtime parity guards."""
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
    # 1.7.0: premium-form diversity and key-form name credit removed (IQM owns form quality).
    # 1.26.0 (V4.1 Step 4): panel disclosure structure and the panel neutral floor
    # retired; an unrated row keeps the shared formulation_magnitudes neutral.
    "multi_prenatal": {
        "cap_formulation": 12.0, "formulation_presence_floor": 2.0, "cap_panel_form_quality": 12.0,
        "bio_score_max": 15.0,
    },
    "omega": {"cap_formulation": 25.0},
    # 1.20.0: optional prebiotics no longer manufacture probiotic form quality.
    # 1.26.0: total-potency and identity disclosure move to Transparency; the
    # shared IQM rating and delivery tier own probiotic form quality.
    "probiotic": {"cap_formulation": 15.0},
    # 1.26.0: route bases, disclosure, focus and practicality retired; source
    # quality is the one Formulation owner on both routes.
    "sports": {"dimension_cap": 30.0},
    "fiber_digestive": {"dimension_cap": 30.0},
    # 1.26.0: identity is a neutral baseline; plant part, amount, brand and the
    # disclosed-marker tier earn nothing here; unsupported Dose bands are retired.
    "botanical": {
        "botanical_formulation_cap": 15.0, "botanical_identity_neutral": 7.2, "botanical_extract": 1.6,
        "standardization_tier_full": 3.2, "standardization_tier_near": 2.4, "standardization_tier_half": 1.6,
        "botanical_dose_no_active": 0.0,
    },
    "collagen": {"collagen_formulation_cap": 15.0, "collagen_identity_neutral": 4.8, "collagen_hydrolyzed": 3.2},
}


def test_config_matches_reviewed_values():
    for mod, vals in ORIGINAL.items():
        assert FVM[mod] == vals, f"formulation_variant_magnitudes.{mod} retained magnitudes drifted"
    for retired in ("botanical_dose_within", "botanical_dose_near", "botanical_dose_above", "botanical_dose_band_scale"):
        assert retired not in FVM["botanical"]


def test_runtime_constants_read_from_config_no_drift():
    assert multi_prenatal_formulation.CAP_FORMULATION == 12.0
    assert not hasattr(multi_prenatal_formulation, "PANEL_FORM_NEUTRAL_FLOOR")
    assert omega_formulation.CAP_FORMULATION == 25.0
    assert probiotic_formulation.CAP_FORMULATION == 15.0
    assert sports_formulation.DIMENSION_CAP == 30.0
    assert fiber_digestive_formulation.DIMENSION_CAP == 30.0
    assert botanical_profile.BOTANICAL_FORMULATION_CAP == 15.0
    assert botanical_profile.STANDARDIZATION_TIER_FULL == 3.2
    assert botanical_profile.BOTANICAL_IDENTITY_NEUTRAL == 7.2
    assert collagen_profile.COLLAGEN_IDENTITY_NEUTRAL == 4.8
    for retired in ("BOTANICAL_DOSE_WITHIN", "BOTANICAL_DOSE_NEAR", "BOTANICAL_DOSE_ABOVE", "BOTANICAL_DOSE_BAND_SCALE"):
        assert not hasattr(botanical_profile, retired)
    assert botanical_profile.BOTANICAL_DOSE_NO_ACTIVE == 0.0
    assert collagen_profile.COLLAGEN_FORMULATION_CAP == 15.0
