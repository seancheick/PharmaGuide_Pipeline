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
    if canonical is None:
        # An unmapped member's label taxonomy cannot turn the whole blend
        # mass into its own scored preparation or Dose benchmark subject.
        assert row is None
        assert (child['quantity'], child['unit']) == (0, 'NP')
        return
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


@pytest.fixture(scope='module')
def raw_pipeline():
    import logging
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def test_exact_meratrim_flower_head_source_resolves_without_allocating_blend(raw_pipeline):
    import json
    from pathlib import Path
    from scoring_input_contract import get_scoring_ingredients
    from scoring_v4.scored_artifact import build_scored_artifact

    raw = json.loads((Path(__file__).parent / 'fixtures/raw_meratrim_328797.json').read_text())
    normalizer, enricher = raw_pipeline
    cleaned = normalizer.normalize_product(raw)
    source = next(r for r in cleaned['activeIngredients']
                  if r['raw_source_path'] == 'ingredientRows[0].nestedRows[0]')
    assert source['canonical_id'] == 'sphaeranthus_indicus'
    assert source['canonical_source_db'] == 'botanical_ingredients'
    assert (source['quantity'], source['unit']) == (0, 'NP')
    enriched, _ = enricher.enrich_product(cleaned)
    source_rows = enriched['ingredient_quality_data']['ingredients']
    parent = next(r for r in source_rows if r['raw_source_path'] == 'ingredientRows[0]')
    child = next(r for r in source_rows if r['raw_source_path'] == source['raw_source_path'])
    assert (parent['quantity'], parent['unit']) == (400, 'mg')
    assert (child['quantity'], child['unit']) == (0, 'NP')
    projections = [r for r in get_scoring_ingredients(enriched, strict=True).rows
                   if r.get('canonical_id') == 'sphaeranthus_indicus']
    assert projections
    assert all(is_lent_blend_mass(r) and not has_usable_individual_dose(r) for r in projections)
    scored = build_scored_artifact(enriched)
    assert scored['quality_pillars_v4']['evidence']['score'] == 0
    assessment = scored['_v4_module_breakdown']['dimensions']['dose']['metadata']['botanical_dose']
    assert assessment['benchmark'] == 'unresolved'
    assert assessment['assessment_status'] == 'complete'
    assert assessment['reason_code'] == 'amount_not_declared'
    assert 'dose_benchmark_identity_unresolved' not in scored['assessment_readiness']['release_assessment']['blockers']
    from build_final_db import build_detail_blob
    blob = build_detail_blob(enriched, scored)
    public_parent = next(r for r in blob['ingredients']
                         if r['raw_source_path'] == 'ingredientRows[0]')
    assert public_parent['quantity'] == 400
    child_labels = [r for r in blob['display_ingredients']
                    if r.get('raw_source_path', '').startswith('ingredientRows[0].nestedRows[')]
    assert len(child_labels) == 2
    assert all(r['exact_dose_text'] == '' for r in child_labels)
    assert not any(r.get('canonical_id') == 'sphaeranthus_indicus' and r.get('quantity') == 400
                   for r in blob['ingredients'])


@pytest.mark.parametrize('label', ['Indian Sphaeranthus', 'Sphaeranthus',
                                  'Sphaeranthus amaranthoides flower head extract'])
def test_exact_flower_head_alias_does_not_identify_genus_or_another_species(raw_pipeline, label):
    normalizer, _ = raw_pipeline
    name, _, _ = normalizer._enhanced_ingredient_mapping(label, [])
    assert name != 'Sphaeranthus indicus'
