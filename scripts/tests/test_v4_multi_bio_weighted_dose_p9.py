"""Multi/prenatal dose coverage is not weighted by form bio_score.

Phase 9 multiplied each nutrient's RDA/AI coverage by ``0.75 + bio_score / 60``.
bio_score is an ordinal IQM form rating, not a measured absorption fraction, and
the same rating already drives Formulation panel form quality; an unknown form
received 1.0 and could out-dose a known one. Since quality_score 1.7.0 Dose
scores the disclosed amount only. Genuine underdosing and upper-limit handling
are unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scoring_v4.modules.multi_prenatal_dose import B7_UL_PCT_THRESHOLD, score_dose  # noqa: E402

_NUTRIENTS = ["Magnesium", "Vitamin B12", "Folate", "Zinc", "Vitamin B6"]
_CANONICALS = ["magnesium", "vitamin_b12", "folate", "zinc", "vitamin_b6"]


def _adeq(n, pct_rda=100.0, pct_ul=None):
    return {"nutrient": n, "pct_rda": pct_rda, "pct_ul": pct_ul, "scoring_eligible": True}


def _ing(canonical, bio):
    row = {"name": canonical.replace("_", " ").title(), "canonical_id": canonical,
           "mapped": True, "quantity": 10, "unit": "mg"}
    if bio is not None:
        row["bio_score"] = bio
    return row


def _product(bio, adequacy=None, safety_flags=None):
    ingredients = [_ing(canonical, bio) for canonical in _CANONICALS]
    return {"status": "active", "product_name": "Multi", "supplement_type": {"type": "multivitamin"},
            "ingredient_quality_data": {"total_active": len(ingredients),
                                        "ingredients_scorable": ingredients},
            "rda_ul_data": {"adequacy_results": adequacy or [_adeq(n) for n in _NUTRIENTS],
                            "safety_flags": safety_flags or []}}


@pytest.mark.parametrize("bio", [0, 6, 12, 15, None])
def test_adequate_coverage_credit_is_independent_of_form_rating(bio):
    payload = score_dose(_product(bio))

    assert set(payload["metadata"]["coverage_nutrient_scores"].values()) == {1.0}
    assert payload["components"]["rda_ai_coverage"] == 15.0


def test_unknown_form_cannot_out_dose_a_rated_form():
    low = score_dose(_product(6))["components"]["rda_ai_coverage"]
    unknown = score_dose(_product(None))["components"]["rda_ai_coverage"]

    assert low == unknown


@pytest.mark.parametrize("bio", [6, 15])
def test_genuine_underdose_keeps_its_dose_response(bio):
    payload = score_dose(_product(bio, adequacy=[_adeq(n, pct_rda=20.0) for n in _NUTRIENTS]))

    assert set(payload["metadata"]["coverage_nutrient_scores"].values()) == {0.4}
    assert payload["components"]["rda_ai_coverage"] == 6.0


def test_upper_limit_violation_keeps_zero_credit_and_dose_safety_penalty():
    adequacy = [_adeq(n) for n in _NUTRIENTS]
    adequacy[3] = _adeq("Zinc", pct_rda=100.0, pct_ul=B7_UL_PCT_THRESHOLD)
    flags = [{"nutrient": "Zinc", "pct_ul": B7_UL_PCT_THRESHOLD, "severity": "high", "ul_gate_eligible": True}]

    payload = score_dose(_product(15, adequacy=adequacy, safety_flags=flags))

    assert payload["metadata"]["coverage_nutrient_scores"]["zinc"] == 0.0
    assert payload["penalties"]["B7_dose_safety"] < 0
