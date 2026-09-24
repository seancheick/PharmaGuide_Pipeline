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
