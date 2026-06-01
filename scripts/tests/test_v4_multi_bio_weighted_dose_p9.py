"""Phase 9 — bioavailability-weighted multivitamin dose coverage.

"Adequate on paper" (100% RDA) is not adequate in vivo: magnesium oxide is poorly
absorbed vs glycinate. So each nutrient's dose-coverage credit is scaled by its
form bio_score, so a cheap-form multi cannot out-dose a premium-form one purely on
panel breadth (the multi-inflation that let a basic multi tie a premium one).
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scoring_v4.modules.multi_prenatal_dose import score_dose, _bio_weight  # noqa: E402

_NUTRIENTS = ["Magnesium", "Vitamin B12", "Folate", "Zinc", "Vitamin B6"]


def _adeq(n):
    return {"nutrient": n, "pct_rda": 100.0, "pct_ul": None, "scoring_eligible": True}


def _ing(canonical, bio):
    return {"name": canonical.replace("_", " ").title(), "canonical_id": canonical,
            "mapped": True, "bio_score": bio, "quantity": 10, "unit": "mg"}


def _product(ingredients):
    return {"status": "active", "product_name": "Multi", "supplement_type": {"type": "multivitamin"},
            "ingredient_quality_data": {"total_active": len(ingredients),
                                        "ingredients_scorable": ingredients},
            "rda_ul_data": {"adequacy_results": [_adeq(n) for n in _NUTRIENTS], "safety_flags": []}}


def test_bio_weight_curve():
    assert _bio_weight(15.0) == 1.0           # premium form, full credit
    assert _bio_weight(None) == 1.0           # unknown -> neutral, never penalized
    assert _bio_weight(0.0) == 0.5            # floored
    assert _bio_weight(7.5) == 0.75           # mid


def test_premium_forms_out_cover_cheap_forms_at_same_rda():
    cheap = _product([
        _ing("magnesium", 5), _ing("vitamin_b12", 5), _ing("folate", 5),
        _ing("zinc", 5), _ing("vitamin_b6", 6),
    ])
    premium = _product([
        _ing("magnesium", 14), _ing("vitamin_b12", 14), _ing("folate", 14),
        _ing("zinc", 13), _ing("vitamin_b6", 13),
    ])
    cheap_cov = score_dose(cheap)["components"]["rda_ai_coverage"]
    prem_cov = score_dose(premium)["components"]["rda_ai_coverage"]
    # same 100% RDA across the panel, but premium forms are more bioavailable
    assert prem_cov > cheap_cov
    # and the gap is material (not a rounding wash)
    assert prem_cov - cheap_cov >= 3.0
