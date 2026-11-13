"""An established nutritional role earns full Evidence (Sean, 2026-11-13).

Essential-nutrient panels already reach the Evidence ceiling through nutrition
authority coverage, while a single essential nutrient stopped at 10/18 raw
(11.1/20). Full credit applies only when every purpose-owning ingredient has an
established nutritional role; a mixed formula keeps the existing floor, so adding
a vitamin never lifts another ingredient's Evidence by its presence.
"""
from __future__ import annotations

from scoring_v4.modules.generic_evidence import NUTRITION_AUTHORITY_FLOOR, score_evidence
from scoring_v4.quality_score_config import config
from test_v4_generic_evidence_p133 import _ingredient, _product

FULL = config()["evidence_subscale"]["archetype_reference"]["generic_single_molecule"]


def _score(*rows):
    return score_evidence(_product(ingredients=list(rows), matches=[]), apply_primary_floor=True)


def test_single_essential_nutrient_earns_full_evidence():
    payload = _score(_ingredient(name="Vitamin D3", standard_name="Vitamin D",
                                 canonical_id="vitamin_d", quantity=25, unit="mcg"))
    assert payload["metadata"]["nutrition_authority_canonical"] == "vitamin_d"
    assert payload["components"]["primary_evidence_floor"] == FULL == 18.0
    assert payload["score"] == FULL


def test_all_essential_pair_earns_full_evidence():
    payload = _score(
        _ingredient(name="Vitamin K1", canonical_id="vitamin_k1", quantity=100, unit="mcg"),
        _ingredient(name="Vitamin K2", canonical_id="vitamin_k2", quantity=100, unit="mcg"),
    )
    assert payload["metadata"]["nutrition_authority_floor_applied"] is True
    assert payload["score"] == FULL


def test_mixed_formula_keeps_existing_floor():
    payload = _score(
        _ingredient(name="Magnesium", canonical_id="magnesium", quantity=300, unit="mg"),
        _ingredient(name="Ashwagandha", canonical_id="ashwagandha", quantity=300, unit="mg"),
    )
    assert payload["metadata"]["nutrition_authority_canonical"] == "magnesium"
    assert payload["components"]["primary_evidence_floor"] == NUTRITION_AUTHORITY_FLOOR == 10.0
    assert payload["score"] == NUTRITION_AUTHORITY_FLOOR


def test_full_floor_converts_to_full_pillar():
    from scoring_v4.quality_score import _pillar_evidence

    cfg = config()
    pillar = _pillar_evidence({"score": FULL, "metadata": {}}, cfg["pillars"]["evidence"]["weight"],
                              "generic_single_molecule", cfg)
    assert pillar["score"] == 20.0
