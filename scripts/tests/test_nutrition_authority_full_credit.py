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


def test_capped_amino_acid_role_keeps_a_valid_readiness_receipt():
    """An immune-routed L-lysine label: the immune Evidence cap (17) sits below
    the full role value (18). The receipt must read the capped score, not demand
    score == floor, or a finished product is marked unready."""
    from assessment_readiness import _current_nutrition_authority_receipt
    from test_evidence_resolver import _eaa_product

    product = _eaa_product('l_lysine', 'L-Lysine', 'l-lysine base', quantity=1000)
    product['supplement_type'] = {'type': 'single_nutrient'}
    product['primary_type'] = 'immune_support'
    payload = score_evidence(product, apply_primary_floor=True, owner_scoped=True)
    assert payload['metadata']['immune_support_evidence_cap_applied'] is True
    assert payload['metadata']['primary_evidence_floor'] == FULL
    assert payload['score'] == payload['metadata']['immune_support_evidence_cap'] < FULL
    assert _current_nutrition_authority_receipt(product, payload) is True
