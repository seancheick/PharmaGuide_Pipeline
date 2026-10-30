"""Four independently verified Laminaria japonica extract rows keep one source identity."""
from copy import deepcopy
import json
from pathlib import Path

import pytest


@pytest.fixture(scope='module')
def owners():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


@pytest.mark.parametrize('pid', ['252562','255054','255055','255057'])
def test_exact_whole_grass_extract_has_same_species_owner_before_and_after_enrichment(owners, pid):
    from scoring_input_contract import _source_tree_rows, _route_scoring_rows
    from dose_assessment import _source_dose_row
    normalizer, enricher = owners
    raw = json.loads((Path(__file__).parent / f'fixtures/raw_kelp_{pid}.json').read_text())
    cleaned = normalizer.normalize_product(raw)
    source = cleaned['activeIngredients'][0]
    assert source['canonical_id'] == 'kombu'
    assert source['canonical_source_db'] == 'botanical_ingredients'
    assert source['raw_source_text'] == raw['ingredientRows'][0]['name']
    assert source['quantity'] == 500 and source['unit'] == 'mg'
    assert 'Laminaria japonica' in source['notes']
    assert 'whole grass' in source['notes']
    enriched, errors = enricher.enrich_product(cleaned)
    assert not errors
    physical = _source_tree_rows(enriched)[0]
    routed = _route_scoring_rows(enriched)[0]
    assert physical['canonical_id'] == routed['canonical_id'] == 'kombu'
    assert _source_dose_row(enriched, routed) is physical
    quality = enriched['ingredient_quality_data']['ingredients'][0]
    assert quality['canonical_id_before'] == quality['canonical_id_after'] == 'kombu'
    assert quality['identity_disposition'] == 'taxonomy_only'
    foreign = deepcopy(routed)
    foreign['canonical_id'] = 'kelp_powder'
    assert _source_dose_row(enriched, foreign) is None


@pytest.mark.parametrize('name, expected', [('Ascophyllum nodosum powder','kelp_powder'),('Laminaria digitata powder','laminaria_digitata')])
def test_distinct_powder_species_does_not_borrow_kombu_extract_identity(owners, name, expected):
    normalizer, _ = owners
    raw = json.loads((Path(__file__).parent / 'fixtures/raw_kelp_252562.json').read_text())
    raw['id'] = 'unreviewed-kelp-powder'
    row = raw['ingredientRows'][0]
    row.update(name=name, ingredientGroup=name, category='botanical', notes='', forms=[])
    result = normalizer.normalize_product(raw)['activeIngredients'][0]
    assert result['canonical_id'] == expected
    assert result['canonical_id'] != 'kombu'
