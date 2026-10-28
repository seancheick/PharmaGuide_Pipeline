"""Contracts for the keyed serving-frequency before/after audit."""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from audits.serving_frequency_audit import _threshold_key  # noqa: E402


THRESHOLD = {
    "basis": "per_day",
    "comparator": ">",
    "threshold_value": 200.0,
    "threshold_unit": "mg",
}


def test_threshold_key_distinguishes_separate_label_rows() -> None:
    """Two same-canonical rows must not overwrite different evaluations."""
    first = _threshold_key(
        "82369",
        "RULE_INGREDIENT_CAFFEINE",
        "caffeine",
        "pregnancy",
        THRESHOLD,
        ingredient_row_id="ingredientRows[1].nestedRows[0]",
    )
    second = _threshold_key(
        "82369",
        "RULE_INGREDIENT_CAFFEINE",
        "caffeine",
        "pregnancy",
        THRESHOLD,
        ingredient_row_id="ingredientRows[2]",
    )

    assert first != second


def test_threshold_key_is_stable_when_rule_arrays_reorder() -> None:
    """The key uses semantic rule terms, never a list index."""
    kwargs = {
        "dsld_id": "82369",
        "rule_id": "RULE_INGREDIENT_CAFFEINE",
        "ingredient": "caffeine",
        "condition": "pregnancy",
        "threshold": dict(THRESHOLD),
        "ingredient_row_id": "ingredientRows[2]",
    }

    assert _threshold_key(**kwargs) == _threshold_key(**kwargs)


def _ranged_facts_record(notes='1-2 scoops'):
    return {'servingSizes': [{'order': 1, 'minQuantity': 5.55, 'maxQuantity': 11.1,
        'unit': 'Gram(s)', 'notes': notes, 'minDailyServings': 1, 'maxDailyServings': 1}],
        'activeIngredients': [{'raw_taxonomy': {'quantityVariants': [
            {'serving_size_order': 1, 'serving_size_quantity': size,
             'serving_size_unit': 'Gram(s)', 'selected_for_analysis': selected}
            for size, selected in [(5.55, False), (11.1, True)]]}}]}


def test_explicit_same_audience_scoop_range_preserves_minimum_intake():
    from serving_frequency import resolve_facts_panel_serving_basis
    basis = resolve_facts_panel_serving_basis(_ranged_facts_record())
    assert basis['min_servings_per_day'] == 0.5
    assert basis['max_servings_per_day'] == 1


def test_audience_or_unsubstantiated_serving_range_keeps_selected_adult_column():
    from serving_frequency import resolve_facts_panel_serving_basis
    for notes in ['1-2 scoops for children and adults', '1 scoop', '1-3 scoops']:
        basis = resolve_facts_panel_serving_basis(_ranged_facts_record(notes))
        assert basis['min_servings_per_day'] == 1
    record = _ranged_facts_record()
    record['activeIngredients'][0]['raw_taxonomy']['quantityVariants'].pop(0)
    assert resolve_facts_panel_serving_basis(record)['min_servings_per_day'] == 1


def test_ranged_intake_does_not_borrow_another_audience_or_panel_basis():
    from serving_frequency import resolve_facts_panel_serving_basis
    for key, values in [('serving_size_order', [1, 2]),
                        ('daily_value_target_group', ['children', 'adults'])]:
        record = _ranged_facts_record()
        variants = record['activeIngredients'][0]['raw_taxonomy']['quantityVariants']
        for variant, value in zip(variants, values):
            variant[key] = value
        assert resolve_facts_panel_serving_basis(record)['min_servings_per_day'] == 1


def test_secondary_dosage_frequency_keeps_real_pantethine_label_range():
    from dosage_normalizer import DosageNormalizer
    from serving_frequency import resolve_daily_serving_range
    # Structured label regimen from Thorne Pantethine182289:250mg per capsule,
    # two to three occasions daily. Per-serving conversion remains250mg.
    product = {'id': '182289', 'servingSizes': [
        {'minQuantity': 1, 'maxQuantity': 1, 'unit': 'Capsule(s)',
         'minDailyServings': 2, 'maxDailyServings': 3}],
        'activeIngredients': [{'name': 'Pantethine', 'quantity': 250, 'unit': 'mg'}]}
    result = DosageNormalizer().normalize_product_dosages(product)
    assert result.success
    basis = result.serving_basis
    assert (basis.servings_per_day_min, basis.servings_per_day_max) == resolve_daily_serving_range(product)[:2]
    assert (basis.servings_per_day_min, basis.servings_per_day_max, basis.servings_per_day_used) == (2, 3, 2)
    row = result.normalized_ingredients[0]
    assert (row.normalized_amount, row.normalized_unit) == (250, 'mg')
    assert (row.per_day_min, row.per_day_max) == (500, 750)
    assert row.conversion_evidence['success'] is True


def test_secondary_dosage_selects_the_canonical_adult_facts_column():
    from dosage_normalizer import DosageNormalizer
    from serving_frequency import select_canonical_serving
    product = {'servingSizes': [
        {'quantity': 1, 'unit': 'Capsule(s)', 'minDailyServings': 1, 'maxDailyServings': 1},
        {'quantity': 2, 'unit': 'Capsule(s)', 'minDailyServings': 3, 'maxDailyServings': 2}]}
    selected = select_canonical_serving(product['servingSizes'])
    basis = DosageNormalizer()._extract_serving_basis(product)
    assert basis.quantity == selected['quantity'] == 2
    assert (basis.servings_per_day_min, basis.servings_per_day_max) == (2, 3)


def test_secondary_dosage_preserves_fractional_frequency_and_default_uncertainty():
    from dosage_normalizer import DosageNormalizer
    from serving_frequency import resolve_daily_serving_range
    normalizer = DosageNormalizer()
    directed = {'servingSizes': [{'quantity': 1, 'unit': 'Capsule(s)'}],
                'serving_basis': {'min_servings_per_day': 0.5, 'max_servings_per_day': 0.5,
                                  'servings_per_day_source': 'directions'}}
    defaulted = {'servingSizes': [{'quantity': 1, 'unit': 'Capsule(s)',
                                  'minDailyServings': 1, 'maxDailyServings': 1,
                                  'dailyServingsSource': 'default'}]}
    for product in (directed, defaulted):
        low, high, was_defaulted = resolve_daily_serving_range(product)
        basis = normalizer._extract_serving_basis(product)
        assert (basis.servings_per_day_min, basis.servings_per_day_max) == (low, high)
        assert ('default' in ' '.join(basis.notes).lower()) == was_defaulted
        if was_defaulted:
            assert basis.confidence != 'high'
