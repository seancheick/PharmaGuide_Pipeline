"""V4 Phase 5 — Safety Hygiene Rebalance (+10 -> +4).

Hygiene keeps ONLY the two non-overlapping clean-safety components:
  +2 no banned/high-risk/watchlist signal
  +2 no recalled signal
It drops the three components already penalised elsewhere, so a product is not
double-penalised by hygiene AND the dedicated penalty:
  - overdose       -> B7 penalty owns it
  - harmful additive -> B1 penalty owns it
  - manufacturer violation -> manufacturer_violations penalty owns it

Exit gate: clean products get modest credit (+4); weak products can't inflate
from "no known issue"; products with a real safety signal still get 0.
"""
from __future__ import annotations

from scoring_v4.modules.safety_hygiene import (  # noqa: E402
    SAFETY_HYGIENE_CAP,
    score_safety_hygiene_base,
)


def _clean_product(**extra) -> dict:
    product = {
        "dsld_id": "TEST1",
        "product_name": "Clean Single Nutrient",
        "ingredient_quality_data": {
            "ingredients_scorable": [{"canonical_id": "magnesium", "name": "Magnesium",
                                      "quantity": 200, "unit": "mg", "mapped": True}],
        },
        "rda_ul_data": {"adequacy_results": [], "safety_flags": []},
        "contaminant_data": {"banned_substances": {"substances": []},
                             "harmful_additives": {"additives": []}},
        "manufacturer_data": {"violations": {"total_deduction_applied": 0.0, "violations": []}},
    }
    product.update(extra)
    return product


def test_cap_is_four():
    assert SAFETY_HYGIENE_CAP == 4.0


def test_clean_product_gets_four_from_two_components():
    out = score_safety_hygiene_base(_clean_product()).to_dict()
    assert out["score"] == 4.0
    assert out["max"] == 4.0
    assert out["components"] == {
        "no_banned_high_risk_or_watchlist_match": 2.0,
        "no_recalled_match": 2.0,
    }
    # Removed components must NOT be credited anymore.
    assert "no_b7_overdose" not in out["components"]
    assert "no_harmful_additive" not in out["components"]
    assert "no_manufacturer_violation" not in out["components"]


def test_overdose_does_not_zero_hygiene_no_double_penalty():
    # B7 owns overdose; hygiene must still credit the clean banned/recalled axes.
    p = _clean_product(rda_ul_data={"adequacy_results": [], "safety_flags": [{"pct_ul": 160.0}]})
    out = score_safety_hygiene_base(p).to_dict()
    assert out["score"] == 4.0
    assert out["metadata"].get("hard_cleanliness_failure") is not True


def test_harmful_additive_does_not_zero_hygiene_no_double_penalty():
    # B1 owns harmful additives.
    p = _clean_product(contaminant_data={"banned_substances": {"substances": []},
                                         "harmful_additives": {"additives": [{"severity_level": "high"}]}})
    assert score_safety_hygiene_base(p).to_dict()["score"] == 4.0


def test_manufacturer_violation_does_not_zero_hygiene_no_double_penalty():
    # manufacturer_violations penalty owns this; hygiene must not also zero out.
    p = _clean_product(manufacturer_data={"violations": {"total_deduction_applied": -10.0,
                                                         "violations": [{"severity_level": "high"}]}})
    out = score_safety_hygiene_base(p).to_dict()
    assert out["score"] == 4.0
    assert "manufacturer_violation_present" not in out["failed_components"]


def test_banned_signal_zeros_hygiene_hard_failure():
    p = _clean_product(contaminant_data={
        "banned_substances": {"substances": [{"name": "X", "status": "banned", "match_type": "exact"}]},
        "harmful_additives": {"additives": []}})
    out = score_safety_hygiene_base(p).to_dict()
    assert out["score"] == 0.0
    assert out["metadata"]["hard_cleanliness_failure"] is True
    assert "banned_high_risk_or_watchlist_match_present" in out["failed_components"]


def test_recalled_signal_zeros_hygiene_hard_failure():
    p = _clean_product(contaminant_data={
        "banned_substances": {"substances": [{"name": "X", "status": "recalled", "match_type": "exact"}]},
        "harmful_additives": {"additives": []}})
    out = score_safety_hygiene_base(p).to_dict()
    assert out["score"] == 0.0
    assert out["metadata"]["hard_cleanliness_failure"] is True
    assert "recalled_match_present" in out["failed_components"]
