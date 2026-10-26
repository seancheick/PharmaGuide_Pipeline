"""Exact-source closeout cases; unknown label quantities remain unknown."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from enhanced_normalizer import EnhancedDSLDNormalizer
from serving_frequency import resolve_daily_serving_range


@pytest.fixture(scope='module')
def sources():
    return json.loads((Path(__file__).parent / 'fixtures' / 'returned_review_completion_raw.json').read_text())


@pytest.fixture(scope='module')
def products(sources):
    n = EnhancedDSLDNormalizer()
    return {pid: n.normalize_product(deepcopy(raw)) for pid, raw in sources.items()}


@pytest.mark.parametrize('pid', ['25583','29049','29054','43662','43947','63330','63463','63475','78327','268493'])
def test_no_printed_daily_maximum_remains_a_default_basis(products, sources, pid):
    assert resolve_daily_serving_range(products[pid]) == (1, 1, True)
    if pid != '268493':
        assert products[pid]['statements'] == sources[pid]['statements']
    else:
        # Carry the already-reviewed coconut/allergen correction forward.
        assert any('Contains Tree Nuts' in x.get('notes','') for x in products[pid]['statements'])


@pytest.mark.parametrize('pid,amount', [('43662',325),('43947',550),('63330',325),('63463',550),('63475',325)])
def test_foodstate_source_preserves_root_without_inventing_nitrate(products, pid, amount):
    row = next(r for r in products[pid]['activeIngredients'] if 'FoodState' in r['name'] and 'Beet' in r['name'])
    assert row['name'].endswith('Beet Root')
    assert row['plantPart'] == 'root'
    assert row['quantity'] == amount
    assert row.get('unit') == 'mg'


def test_exact_steroid_name_restored_without_clearing_existing_ban(products):
    row = next(r for r in products['33361']['activeIngredients'] if r['raw_source_path'] == 'ingredientRows[0]')
    assert '17β' in row['raw_source_text']
    assert row['quantity'] == 7.5
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    enriched, _ = SupplementEnricherV3().enrich_product(deepcopy(products['33361']))
    assert build_scored_artifact(enriched)['verdict'] == 'BLOCKED'


def test_professional_bulk_b12_barcode_does_not_become_a_serving(products, sources):
    p = products['254413']
    assert p['upcSku'] == 'X001FYWVWV'
    assert p['statements'] == sources['254413']['statements']
    assert resolve_daily_serving_range(p)[2] is True
    assert not any(r.get('quantity') == 50000 for r in p['activeIngredients'])


def test_hemp_seed_and_efa_note_follow_printed_label(products):
    rows = products['259374']['activeIngredients']
    hemp = next(r for r in rows if 'hemp' in r['name'].lower())
    assert hemp['plantPart'] == 'seed' and hemp['quantity'] == 30
    efa = next(r for r in products['259374']['display_ingredients']
               if r.get('raw_source_path') == 'ingredientRows[6].nestedRows[0]')
    assert efa['exact_dose_text'] == '1.7 g'
    assert '2,000' not in efa.get('raw_source_text','')



def test_zero_sodium_unit_repair_changes_no_exposure(products):
    row = next(r for r in products['306350']['display_ingredients']
               if r.get('raw_source_path') == 'ingredientRows[3]')
    assert row['exact_dose_text'] == '0 mg'



def test_waterex_source_is_already_correct(products):
    rows = products['312713']['activeIngredients']
    row = next(r for r in rows if r.get('canonical_id') == 'corn_silk')
    assert row['quantity'] == 6.25 and 'Powder' in row['name']
    uva = next(r for r in rows if 'uva' in r['name'].lower())
    assert '3:1' in json.dumps(uva)


def test_adrenal_herb_parts_are_literal_and_amounts_remain_undisclosed(products):
    rows = products['315586']['activeIngredients']
    expected = {'Astragalus':'root','Wood Betony':'herb','Ginkgo':'leaf','Eleuthero':'root',
                'Gotu Kola':'herb','Rhodiola':'root','Licorice':'root','Lavender':'flower',
                'Spearmint':'leaf','Passionflower':'leaf'}
    for name, part in expected.items():
        row = next(r for r in rows if r.get('name','').startswith(name))
        assert row['plantPart'] == part
        assert row['quantity'] == 0 and row['unit'] == 'NP'


def test_eaa_has_one_total_and_preserves_source_linked_undosed_children(products):
    p = products['330806']
    rows = {r['raw_source_path']: r for r in p['display_ingredients']}
    assert rows['ingredientRows[0]']['children'] == ['Proprietary Blend']
    wrapper = rows['ingredientRows[1]']
    assert wrapper['parent_source_path'] == 'ingredientRows[0]'
    assert len(wrapper['children']) == 9
    assert wrapper['exact_dose_text'] == ''
    for index in range(9):
        row = rows[f'ingredientRows[1].nestedRows[{index}]']
        assert row['parent_source_path'] == 'ingredientRows[1]' and row['nested_depth'] == 2
        assert row['exact_dose_text'] == ''
    active = [r for r in p['activeIngredients'] if r.get('raw_source_path','').startswith('ingredientRows[1].')]
    assert len(active) == 9
    assert all(r['quantity'] == 0 and not r['score_eligible_by_cleaner'] for r in active)


def test_mixed_grape_source_cannot_become_seed_only(products):
    rows = {r['raw_source_path']: r for r in products['330882']['activeIngredients']}
    mixed, seed = rows['ingredientRows[2]'], rows['ingredientRows[5]']
    assert (mixed['canonical_id'], mixed['canonical_source_db']) == ('grape', 'botanical_ingredients')
    assert mixed['quantity'] == 210
    assert set(mixed['plantPart'].split(' and ')) == {'seed','skin'}
    assert len(mixed['forms']) == 2
    assert seed['canonical_id'] == 'grape_seed_extract' and seed['quantity'] == 125


@pytest.mark.parametrize('pid', ['254413','25583','268493','29049','29054','33361','43662','43947',
                                '63330','63463','63475','78327','259374','306350','315586','330806'])
def test_reviewed_sources_fail_closed_when_panel_or_statements_change(sources, pid):
    raw = deepcopy(sources[pid])
    raw['statements'].append({'type':'Warning','notes':'Changed source edition'})
    with pytest.raises(ValueError, match='Reviewed|correction'):
        EnhancedDSLDNormalizer().normalize_product(raw)

@pytest.mark.parametrize('pid', ['33361','43662','43947','63330','63463','63475','259374'])
def test_reviewed_literal_correction_exports_without_assigning_quality_identity(products, pid):
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    from build_final_db import build_detail_blob
    enriched, _ = SupplementEnricherV3().enrich_product(deepcopy(products[pid]))
    scored = build_scored_artifact(deepcopy(enriched))
    blob = build_detail_blob(enriched, scored)
    assert scored['quality_score_v4_100'] is None
    assert blob['row_ledger']
    if pid == '33361':
        assert scored['verdict'] == 'BLOCKED'

def test_mixed_grape_parts_survive_enrichment_and_export(products):
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    from build_final_db import build_detail_blob
    enriched, _ = SupplementEnricherV3().enrich_product(deepcopy(products['330882']))
    mixed = next(r for r in enriched['ingredient_quality_data']['ingredients']
                 if r.get('raw_source_path') == 'ingredientRows[2]')
    assert mixed['canonical_id'] == 'grape'
    assert mixed.get('bio_score') is None
    blob = build_detail_blob(enriched, build_scored_artifact(deepcopy(enriched)))
    mixed = next(r for r in blob['ingredients'] if r.get('raw_source_path') == 'ingredientRows[2]')
    assert mixed['canonical_id'] == 'grape'
    assert 'Skin' in mixed['source_label_form'] and 'Seed' in mixed['source_label_form']

def test_default_daily_explanation_does_not_deny_printed_qualitative_directions(products):
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    enriched, _ = SupplementEnricherV3().enrich_product(deepcopy(products['268493']))
    scored = build_scored_artifact(enriched)
    text = json.dumps(scored['quality_pillars_v4']['dose'])
    assert 'no daily directions' not in text
    assert 'no daily amount' in text
    assert scored['quality_pillars_v4']['dose']['score'] == 2.4
