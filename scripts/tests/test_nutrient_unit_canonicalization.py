"""One owner for nutrient unit spellings (normalization.py), ported for v4.1.

Enriched rows spell activity units without spaces (mcgdfe, mgne) while
reference data spells them with spaces; analyte-qualified mass (mg
alpha-tocopherol, mg AT) is plain mg for vitamin E only.
"""
import pytest

from normalization import analyte_unit_parent, canonicalize_nutrient_unit


@pytest.mark.parametrize('unit, expected', [
    ('mcgdfe', 'mcg dfe'), ('mcg DFE', 'mcg dfe'), ('mgNE', 'mg ne'), ('mcg RAE', 'mcg rae'),
    ('mg alpha-tocopherol', 'mg'), ('mg AT', 'mg'), ('mg', 'mg'), ('mcg', 'mcg'),
])
def test_activity_and_analyte_units_have_one_canonical_spelling(unit, expected):
    assert canonicalize_nutrient_unit(unit) == expected


def test_analyte_mass_belongs_to_its_own_nutrient():
    assert analyte_unit_parent('mg alpha-tocopherol') == 'vitamin_e'
    assert analyte_unit_parent('mg') is None


def test_the_enricher_threshold_units_use_the_same_owner():
    from enrich_supplements_v3 import SupplementEnricherV3
    enricher = SupplementEnricherV3.__new__(SupplementEnricherV3)
    assert enricher._normalize_threshold_unit('mcgDFE') == 'mcg dfe'
    assert enricher._normalize_threshold_unit('mg NE') == 'mg ne'


def test_mixed_natural_and_synthetic_vitamin_e_is_only_an_upper_bound():
    from unit_converter import convert_nutrient
    mixed = convert_nutrient('Vitamin E', 100, 'IU', 'mg', 'Vitamin E (as d-alpha tocopherol and dl-alpha tocopheryl acetate)')
    natural = convert_nutrient('Vitamin E', 100, 'IU', 'mg', 'Vitamin E (as d-alpha tocopherol)')
    assert natural.confidence == 'high'
    assert mixed.confidence == 'medium' and mixed.converted_value == natural.converted_value
