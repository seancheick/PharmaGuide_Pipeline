"""Quantity disclosure has one owner, scoring_input_contract.dose_disclosure_status(row):
it selects the amount, checks the unit, reads blend membership and returns
'disclosed' | 'not_disclosed_blend' | 'missing'. The export's dose_status and
display label and both v4 Transparency modules read it directly.

Disclosure is a label fact: a printed enzyme activity (45,000 HUT) is disclosed
even though Dose cannot use it as a mass exposure. Real record 232243 (digestive
enzymes in HUT, FIP, CU, USP ...): Transparency used to count 2 of its 11 active
rows as dose-disclosed while the export showed all 11 amounts.
"""
import json
import math
from pathlib import Path

import pytest

from scoring_input_contract import dose_disclosure_status


@pytest.mark.parametrize('row,expected', [
    ({'quantity': 500, 'unit': 'mg'}, 'disclosed'),
    ({'quantity': 45000, 'unit': 'HUT'}, 'disclosed'),
    ({'quantity': 18, 'unit': 'mg NE', 'isNestedIngredient': True}, 'disclosed'),
    ({'quantity': '2.5', 'unit': 'Gram(s)', 'unit_normalized': 'g'}, 'disclosed'),
    ({'quantity': None, 'has_dose': True}, 'disclosed'),                      # strain-side CFU
    ({'quantity': 0, 'unit': 'NP', 'isNestedIngredient': True}, 'not_disclosed_blend'),
    ({'quantity': 0, 'unit': 'NP', 'proprietaryBlend': True}, 'not_disclosed_blend'),
    ({'quantity': 0, 'unit': 'NP', 'parent_blend': 'Energy Blend'}, 'not_disclosed_blend'),
    ({'quantity': 0, 'unit': 'NP', 'cleaner_row_role': 'nested_display_only'}, 'not_disclosed_blend'),
    ({'quantity': 5, 'unit': 'NP'}, 'missing'),
    ({'quantity': None, 'unit': None}, 'missing'),
    ({'quantity': math.nan, 'unit': 'mg'}, 'missing'),
])
def test_owner(row, expected):
    assert dose_disclosure_status(row) == expected


def test_export_and_transparency_read_the_owner_only():
    from build_final_db import _compute_dose_status
    for row in ({'quantity': 45000, 'unit': 'HUT'}, {'quantity': 0, 'unit': 'NP', 'isNestedIngredient': True}):
        assert _compute_dose_status(row) == dose_disclosure_status(row)
    modules = Path(__file__).resolve().parents[1] / 'scoring_v4' / 'modules'
    for name in ('generic_transparency', 'multi_prenatal_transparency'):
        text = (modules / f'{name}.py').read_text()
        assert 'dose_disclosure_status(row)' in text and 'has_dose' not in text, name


def test_real_enzyme_label_rows_are_all_disclosed():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'dose_disclosure_232243_raw.json').read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    scored = build_scored_artifact(enriched)
    disclosure = scored['_v4_module_breakdown']['dimensions']['transparency']['metadata']['complete_active_disclosure']
    assert disclosure['complete_row_count'] == disclosure['active_row_count'] == 11


def _printed_zero(unit='mcg'):
    return {'name': 'Vitamin D', 'canonical_id': 'vitamin_d', 'quantity': 0,
            'unit': unit, 'raw_source_path': 'ingredientRows[1]',
            'raw_taxonomy': {'quantityVariants': [{
                'quantity': 0, 'unit': unit, 'operator': '=',
                'quantity_parsed': True, 'selected_for_analysis': True,
            }]}}


@pytest.mark.parametrize('unit', ['mcg', 'g', 'Gram(s)'])
def test_exact_printed_zero_is_disclosed_without_becoming_a_positive_dose(unit):
    from scoring_input_contract import _positive_quantity, has_source_printed_amount
    row = _printed_zero(unit)
    assert dose_disclosure_status(row) == 'disclosed'
    assert _positive_quantity(row) is None
    assert has_source_printed_amount(row) is False
    assert _positive_quantity(row, allow_zero=True) == 0
    assert has_source_printed_amount(row, allow_zero=True) is True


@pytest.mark.parametrize('change', [
    'np', 'unspecified', 'unparsed', 'missing_parsed', 'missing_source',
    'unselected', 'multiple_selected', 'ambiguous', 'qualified_bound',
    'boolean', 'quantity_mismatch',
])
def test_zero_defaults_and_unresolved_quantities_do_not_prove_disclosure(change):
    row = _printed_zero()
    variant = row['raw_taxonomy']['quantityVariants'][0]
    if change in {'np', 'unspecified'}:
        row['unit'] = variant['unit'] = change
    elif change == 'unparsed':
        variant['quantity_parsed'] = False
    elif change == 'missing_parsed':
        variant.pop('quantity_parsed')
    elif change == 'missing_source':
        row.pop('raw_source_path')
    elif change == 'unselected':
        variant['selected_for_analysis'] = False
    elif change == 'multiple_selected':
        row['raw_taxonomy']['quantityVariants'].append({**variant, 'quantity': 10})
    elif change == 'ambiguous':
        row['quantity_operator'] = 'ambiguous'
    elif change == 'qualified_bound':
        variant['operator'] = '<'
    elif change == 'boolean':
        row['quantity'] = variant['quantity'] = False
    elif change == 'quantity_mismatch':
        variant['quantity'] = 10
    assert dose_disclosure_status(row) == 'missing'


def test_printed_zero_survives_clean_enrich_artifact_as_disclosure_only():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_input_contract import get_scoring_ingredients
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = {'id': 'ZERO-DISCLOSURE', 'fullName': 'Vitamin C', 'ingredientRows': [
        {'name': 'Vitamin C', 'category': 'vitamin', 'ingredientGroup': 'Vitamin C',
         'quantity': [{'quantity': 100, 'unit': 'mg', 'operator': '='}]},
        {'name': 'Vitamin D', 'category': 'vitamin', 'ingredientGroup': 'Vitamin D',
         'quantity': [{'quantity': 0, 'unit': 'mcg', 'operator': '='}]},
    ]}
    product, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    zero = next(r for r in product['ingredient_quality_data']['ingredients']
                if r.get('canonical_id') == 'vitamin_d')
    assert dose_disclosure_status(zero) == 'disclosed'
    assert zero['scoreable_identity'] is False
    assert [r['canonical_id'] for r in get_scoring_ingredients(product, strict=True).rows] == ['vitamin_c']
    artifact = build_scored_artifact(product)
    disclosure = artifact['_v4_module_breakdown']['dimensions']['transparency']['metadata']['complete_active_disclosure']
    assert disclosure['qualifies'] is True
    assert disclosure['declared_active_count'] == disclosure['active_row_count'] == 1


@pytest.mark.parametrize('unit', ['unknown', 'n/a', 'none', '—', 'packet'])
def test_zero_pseudo_units_are_not_disclosed_measurements(unit):
    row = {'quantity': 0, 'unit': unit, 'raw_source_path': 'ingredientRows[0]',
        'raw_taxonomy': {'quantityVariants': [{'quantity': 0, 'unit': unit,
            'quantity_parsed': True, 'selected_for_analysis': True}]}}
    assert dose_disclosure_status(row) == 'missing'


@pytest.mark.parametrize('unit', ['IU', 'mg NE', 'DU'])
def test_exact_zero_disclosure_keeps_non_mass_units(unit):
    row = {'quantity': 0, 'unit': unit, 'raw_source_path': 'ingredientRows[0]',
        'raw_taxonomy': {'quantityVariants': [{'quantity': 0, 'unit': unit,
            'quantity_parsed': True, 'selected_for_analysis': True}]}}
    assert dose_disclosure_status(row) == 'disclosed'


def test_typed_printed_enzyme_activity_is_disclosed_even_when_mass_is_np():
    row = {'name': 'Protease', 'quantity': 0, 'unit': 'NP',
           'activity_quantity': 75000, 'activity_unit': 'HUT',
           'isNestedIngredient': True}
    assert dose_disclosure_status(row) == 'disclosed'
    assert row['quantity'] == 0 and row['unit'] == 'NP'
