"""Quantity disclosure has one owner, scoring_input_contract.dose_disclosure_status,
read by the export's dose_status and by v4 Transparency.

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


@pytest.mark.parametrize('quantity,unit,member,expected', [
    (500, 'mg', False, 'disclosed'),
    (45000, 'HUT', False, 'disclosed'),
    (18, 'mg NE', True, 'disclosed'),
    ('2.5', 'g', False, 'disclosed'),
    (0, 'NP', True, 'not_disclosed_blend'),
    (0, 'mg', True, 'not_disclosed_blend'),
    (5, 'NP', False, 'missing'),
    (None, None, False, 'missing'),
    (math.nan, 'mg', False, 'missing'),
    ('abc', 'mg', True, 'not_disclosed_blend'),
])
def test_owner(quantity, unit, member, expected):
    assert dose_disclosure_status(quantity, unit, member) == expected


def test_export_reads_the_owner():
    from build_final_db import _compute_dose_status
    rows = [{'quantity': 45000, 'unit': 'HUT'}, {'quantity': 0, 'unit': 'NP', 'isNestedIngredient': True},
            {'quantity': 0, 'unit': 'NP', 'proprietaryBlend': True}, {'quantity': 0, 'unit': 'mg'}]
    for row in rows:
        member = bool(row.get('isNestedIngredient') or row.get('proprietaryBlend'))
        assert _compute_dose_status(row) == dose_disclosure_status(row['quantity'], row['unit'], member)


def test_transparency_counts_activity_units_as_disclosed():
    from scoring_v4.modules.generic_helpers import has_disclosed_amount, has_usable_individual_dose
    enzyme = {'quantity': 45000, 'unit': 'HUT'}
    assert has_disclosed_amount(enzyme) and not has_usable_individual_dose(enzyme)
    assert not has_disclosed_amount({'quantity': 0, 'unit': 'NP'})
    assert has_disclosed_amount({'quantity': None, 'has_dose': True})


def test_real_enzyme_label_rows_are_all_disclosed():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'dose_disclosure_232243_raw.json').read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    scored = build_scored_artifact(enriched)
    disclosure = scored['_v4_module_breakdown']['dimensions']['transparency']['metadata']['complete_active_disclosure']
    assert disclosure['complete_row_count'] == disclosure['active_row_count'] == 11
