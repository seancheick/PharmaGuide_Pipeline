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
