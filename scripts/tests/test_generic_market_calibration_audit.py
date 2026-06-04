import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
API_AUDIT_ROOT = SCRIPTS_ROOT / "api_audit"
for path in (SCRIPTS_ROOT, API_AUDIT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import generic_market_calibration_audit as audit  # noqa: E402


def test_quality_band_boundaries_are_market_readable():
    assert audit._quality_band(90) == "Excellent"
    assert audit._quality_band(70) == "Good"
    assert audit._quality_band(50) == "Fair"
    assert audit._quality_band(49.9) == "Poor"
    assert audit._quality_band(None) == "Not Scored"


def test_cohort_detection_uses_title_and_active_rows():
    product = {
        "product_name": "Premium Sleep Support",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"name": "Magnesium Glycinate", "canonical_id": "magnesium_glycinate"},
                {"name": "Melatonin", "canonical_id": "melatonin"},
            ]
        },
    }
    assert set(audit._cohorts_for(product)) >= {"magnesium", "melatonin"}


def test_why_not_higher_surfaces_binding_dimensions():
    module = {
        "dimensions": {
            "formulation": {"score": 12},
            "dose": {"score": 22},
            "evidence": {"score": 7},
            "transparency": {"score": 8},
        },
        "verification_bonus": {"score": 0},
        "manufacturer_trust": {"score": 1},
        "manufacturer_violations": {"score": 0},
    }
    reasons = audit._why_not_higher(module, 62, "moderate")
    assert "formulation: large headroom (12.0/30)" in reasons
    assert "evidence: large headroom (7.0/20)" in reasons
    assert "verification: low bonus (0.0/8)" in reasons
    assert "confidence: moderate" in reasons
