"""An established nutritional role earns full Evidence (Sean, 2026-11-13).

Essential-nutrient panels already reach the Evidence ceiling through nutrition
authority coverage, while a single essential nutrient stopped at 10/18 raw
(11.1/20). Full credit applies only when every purpose-owning ingredient has an
established nutritional role; a mixed formula keeps the existing floor, so adding
a vitamin never lifts another ingredient's Evidence by its presence.
"""
from __future__ import annotations

import pytest

from scoring_v4.modules.generic_evidence import NUTRITION_AUTHORITY_FLOOR, score_evidence
from scoring_v4.quality_score_config import config
from test_v4_generic_evidence_p133 import _ingredient, _product

FULL = config()["evidence_subscale"]["archetype_reference"]["generic_single_molecule"]


@pytest.mark.parametrize('fallback', [False, True])
def test_authority_purpose_rows_derive_once_per_scope_and_isolate_mutations(monkeypatch, fallback):
    import evidence_resolver
    from scoring_input_contract import scoring_input_scope
    from scoring_v4.modules.generic_evidence import _purpose_owner_rows
    from test_evidence_resolver import _eaa_product

    product = _eaa_product()
    calls = []
    original = evidence_resolver.evidence_prominent_row_keys

    def counted(*args, **kwargs):
        calls.append(1)
        return set() if fallback else original(*args, **kwargs)

    monkeypatch.setattr(evidence_resolver, 'evidence_prominent_row_keys', counted)
    with scoring_input_scope(product):
        rows = _purpose_owner_rows(product)
        rows[0]['name'] = 'Changed only in caller'
        assert _purpose_owner_rows(product)[0]['name'] == 'L-Leucine'
    assert len(calls) == 1
    assert product['activeIngredients'][0]['name'] == 'L-Leucine'


def test_full_authority_cannot_transfer_between_same_canonical_preparations():
    from copy import deepcopy
    from test_evidence_resolver import _eaa_product
    from evidence_resolver import evidence_prominent_row_keys
    from scoring_v4.modules.generic_evidence import nutrition_authority_floor_value

    product = _eaa_product()
    row = deepcopy(product['activeIngredients'][0])
    row.update(name='DL-Leucine', raw_source_text='DL-Leucine', raw_source_path='ingredientRows[1]')
    for rows in [product['activeIngredients'], product['ingredient_quality_data']['ingredients'],
                 product['ingredient_quality_data']['ingredients_scorable']]:
        rows.append(row)
    assert ('ingredientRows[1]', 'l_leucine') in evidence_prominent_row_keys(product)
    assert nutrition_authority_floor_value(product, 'l_leucine') == NUTRITION_AUTHORITY_FLOOR
    from assessment_readiness import _current_nutrition_authority_receipt
    payload = score_evidence(product, apply_primary_floor=True, owner_scoped=True)
    assert payload['score'] == NUTRITION_AUTHORITY_FLOOR
    assert payload['metadata']['nutrition_authority_canonical'] == 'l_leucine'
    assert _current_nutrition_authority_receipt(product, payload)
    product['activeIngredients'][0]['raw_source_text'] = 'DL-Leucine'
    assert not _current_nutrition_authority_receipt(product, payload)


def test_undosed_nutritional_blend_members_keep_full_role_authority():
    from test_evidence_prominence_ownership import _row
    from scoring_v4.modules.generic_evidence import nutrition_authority_floor_value

    product = _product(product_name='Zinc Blend', ingredients=[
        _row('Zinc Blend', 'zinc_blend', 300, path='ingredientRows[0]',
             is_proprietary_blend=True, cleaner_row_role='blend_header_total'),
        _row('Zinc', 'zinc', None, unit=None, path='ingredientRows[0].nestedRows[0]',
             cleaner_row_role='nested_display_only', score_eligible_by_cleaner=False,
             isNestedIngredient=True, parentBlend='Zinc Blend'),
        _row('Magnesium', 'magnesium', 100, path='ingredientRows[1]'),
    ], matches=[])
    product['product_name'] = 'Zinc Blend + Magnesium'
    product['ingredient_quality_data']['ingredients_scorable'] = [
        product['ingredient_quality_data']['ingredients'][-1]]
    assert nutrition_authority_floor_value(product, 'zinc') == FULL
    from assessment_readiness import _current_nutrition_authority_receipt
    from scoring_v4.modules.generic_evidence import nutrition_authority_references
    payload = score_evidence(product, apply_primary_floor=True, owner_scoped=True)
    assert payload['score'] == FULL
    canonical = payload['metadata']['nutrition_authority_canonical']
    assert nutrition_authority_references(product, canonical)
    assert _current_nutrition_authority_receipt(product, payload)


def _score(*rows):
    return score_evidence(_product(ingredients=list(rows), matches=[]), apply_primary_floor=True)


def test_single_essential_nutrient_earns_full_evidence():
    payload = _score(_ingredient(name="Vitamin D3", standard_name="Vitamin D",
                                 canonical_id="vitamin_d", quantity=25, unit="mcg"))
    assert payload["metadata"]["nutrition_authority_canonical"] == "vitamin_d"
    assert payload["components"]["primary_evidence_floor"] == FULL == 20.0
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
    the full role value (20). The receipt must read the capped score, not demand
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


def test_stale_uncapped_receipt_fails_after_immune_routing():
    """A breakdown scored before the immune route (no cap applied, score equal to
    the floor) is not a valid receipt for the current immune-routed product."""
    from assessment_readiness import _current_nutrition_authority_receipt
    from test_evidence_resolver import _eaa_product

    product = _eaa_product('l_lysine', 'L-Lysine', 'l-lysine base', quantity=1000)
    product['supplement_type'] = {'type': 'single_nutrient'}
    stale = score_evidence(product, apply_primary_floor=True, owner_scoped=True)
    assert stale['score'] == FULL
    product['primary_type'] = 'immune_support'
    assert _current_nutrition_authority_receipt(product, stale) is False


def test_full_nutrition_floor_explains_its_established_role():
    from scoring_v4.quality_score import _pillar_evidence

    payload = _score(_ingredient(name="Vitamin D3", standard_name="Vitamin D",
                                 canonical_id="vitamin_d", quantity=25, unit="mcg"))
    pillar = _pillar_evidence(payload, 20.0, "generic_single_molecule", config())
    assert pillar["reason"].startswith("Established nutritional role")
