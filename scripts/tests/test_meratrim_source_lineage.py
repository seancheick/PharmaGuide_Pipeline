"""Container mass and minted botanical labels never become verified child doses."""
from __future__ import annotations

import pytest

from scoring_input_contract import (
    _derive_blend_header_anchor_from_nested_child,
    is_lent_blend_mass,
)
from scoring_v4.modules.generic_helpers import has_usable_individual_dose


def _parent_and_child(canonical=None):
    parent = {
        'name': 'Meratrim Proprietary Blend', 'canonical_id': 'BLEND_GENERAL',
        'raw_source_path': 'ingredientRows[0]', 'cleaner_row_role': 'blend_header_total',
        'quantity': 400, 'unit': 'mg', 'raw_taxonomy': {'category': 'blend'},
    }
    child = {
        'name': 'Indian Sphaeranthus Flower Head Extract',
        'canonical_id': canonical,
        'canonical_source_db': 'botanical_ingredients' if canonical else 'unmapped',
        'raw_source_path': 'ingredientRows[0].nestedRows[0]',
        'quantity': 0, 'unit': 'NP',
        'raw_taxonomy': {'category': 'botanical', 'ingredientGroup': 'Indian sphaeranthus'},
    }
    return parent, child


@pytest.mark.parametrize('canonical,kind', [
    (None, 'label_taxonomy_anchor'),
    ('sphaeranthus_indicus', 'verified_ingredient'),
])
def test_blend_projection_preserves_actual_child_identity_provenance(canonical, kind):
    parent, child = _parent_and_child(canonical)
    row = _derive_blend_header_anchor_from_nested_child({}, parent, [child])
    assert row['clean_identity_id'] == canonical
    assert row['identity_kind'] == kind
    assert row['dose_value'] == parent['quantity'] == 400
    assert (child['quantity'], child['unit']) == (0, 'NP')
    assert is_lent_blend_mass(row)
    assert not has_usable_individual_dose(row)
    assert row['raw_source_path'] == parent['raw_source_path']
    assert row['linked_rows'] == [parent['raw_source_path'], child['raw_source_path']]


def test_disclosed_child_never_inherits_the_blend_total():
    parent, child = _parent_and_child('sphaeranthus_indicus')
    child.update(quantity=75, unit='mg')
    assert _derive_blend_header_anchor_from_nested_child({}, parent, [child]) is None
    assert child['quantity'] == 75


def test_child_without_parent_lineage_cannot_borrow_the_total():
    parent, child = _parent_and_child('sphaeranthus_indicus')
    child['raw_source_path'] = 'ingredientRows[1]'
    assert _derive_blend_header_anchor_from_nested_child({}, parent, [child]) is None
