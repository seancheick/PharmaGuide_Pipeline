"""Exact archived-label hierarchy/material regressions; never inferred masses."""
import copy
import json
from pathlib import Path

import pytest

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from normalization import extract_enzyme_activity
from scoring_v4.scored_artifact import build_scored_artifact
from build_final_db import build_detail_blob

FIXTURES = Path(__file__).parent / 'fixtures'

def raw_label(pid):
    return json.loads((FIXTURES / f'residual_source_{pid}_raw.json').read_text())

@pytest.fixture(scope='module')
def assessments():
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    result = {}
    for pid in ['275412', '182990']:
        cleaned = normalizer.normalize_product(raw_label(pid))
        enriched, _ = enricher.enrich_product(cleaned)
        scored = build_scored_artifact(enriched)
        result[pid] = cleaned, enriched, scored, build_detail_blob(enriched, scored)
    return result

def test_archived_raw_enzyme_groups_keep_their_actual_parent(assessments):
    cleaned, enriched, scored, _ = assessments['275412']
    rows = {x['raw_source_path']: x for x in cleaned['activeIngredients']}
    for index, count in [(13, 7), (14, 12), (15, 1)]:
        group = rows[f'ingredientRows[{index}]']
        assert group['parent_source_path'] == 'ingredientRows[12]'
        assert group['parentBlend'] == 'RAW Enzyme Blend'
        assert group['quantity'] == 0 and group['unit'] == 'NP'
        members = [x for x in rows.values() if x.get('parent_source_path') == group['raw_source_path']]
        assert len(members) == count
    assert rows['ingredientRows[12]']['quantity'] == 620
    for index in [16, 17, 18]:
        assert rows[f'ingredientRows[{index}]'].get('parent_source_path') != 'ingredientRows[12]'
    [activator] = [x for x in cleaned['display_ingredients'] if x['raw_source_path'] == 'ingredientRows[19]']
    assert activator.get('parent_source_path') != 'ingredientRows[12]'
    assert rows['ingredientRows[16]']['quantity'] == 31
    blends = [b for b in enriched['proprietary_data']['blends'] if b.get('source_row_ref') == 'ingredientRows[12]']
    assert len(blends) == 1 and blends[0]['disclosure_level'] == 'partial'
    evidence = scored['_v4_module_breakdown']['dimensions']['transparency']['metadata']['B5_blend_evidence']
    assert any(x.get('source_row_ref') == 'ingredientRows[12]' and x['computed_blend_penalty_magnitude'] > 0 for x in evidence)

def test_all_printed_digestive_activity_values_survive_without_mass_allocation(assessments):
    cleaned, _, _, _ = assessments['275412']
    rows = {x['raw_source_path']: x for x in cleaned['activeIngredients']}
    children = [rows[f'ingredientRows[{group}].nestedRows[{j}]'] for group,n in [(13,7),(14,12),(15,1)] for j in range(n)]
    assert len(children) == 20
    assert all(x.get('activity_quantity', 0) and x.get('activity_unit') for x in children)
    assert all(x['quantity'] == 0 and x['unit'] == 'NP' for x in children)
    assert rows['ingredientRows[17]']['activity_quantity'] == 67
    assert rows['ingredientRows[18]']['activity_quantity'] == 5

def test_natural_trace_matrix_is_source_material_without_fabricated_elements(assessments):
    cleaned, enriched, scored, blob = assessments['182990']
    rows = {x['raw_source_path']: x for x in cleaned['activeIngredients']}
    matrix = rows['ingredientRows[5]']
    assert matrix['cleaner_row_role'] == 'source_descriptor'
    assert matrix['dose_class'] == 'source_material_mass'
    assert matrix['quantity'] == 700 and matrix['unit'] == 'mg'
    assert [rows[f'ingredientRows[{i}]']['quantity'] for i in range(5)] == [50,150,245,6,50]
    assert len(rows) == 6  # Typical ranges are not seven new measured doses.
    assert not any(b.get('source_row_ref') == 'ingredientRows[5]' for b in enriched['proprietary_data']['blends'])
    assert blob['proprietary_blend_detail']['has_proprietary_blends'] is False
    blockers = scored['assessment_readiness']['release_assessment']['blockers']
    assert 'clinical_applicability_unreviewed:INGR_CALCIUM' in blockers
    # INGR_MAGNESIUM_GENERIC now has a reviewed applicability scope (Dr. Pham,
    # 2026-10-28: blood pressure), so it is no longer an unreviewed blocker.
    assert not any('INGR_MAGNESIUM_GENERIC' in blocker for blocker in blockers)
    text = json.dumps(enriched, ensure_ascii=False)
    assert '0.7 - 0.9 mg' in text and '1.0 - 1.2 mg' in text

@pytest.mark.parametrize('text,value,unit', [('1,248 HCU',1248,'HCU'),('65 PGU',65,'PGU'),('50 endo-PGU',50,'ENDO-PGU'),('840 XU',840,'XU'),('5 SOD Units',5,'SOD')])
def test_exact_archived_assay_units_are_native_activity_only(text,value,unit):
    assert extract_enzyme_activity(text) == (value, unit)
    assert extract_enzyme_activity('', value, unit) == (value, unit)
    assert extract_enzyme_activity(text + '/g') == (None,None)

def test_picograms_are_not_pectinase_activity():
    assert extract_enzyme_activity('65 pg') == (None,None)
    assert extract_enzyme_activity('',65,'pg') == (None,None)

def test_consumer_display_uses_the_same_native_activity_owner(assessments):
    _, _, _, blob = assessments['275412']
    rows = {x['raw_source_path']: x for x in blob['display_ingredients']}
    for group,n in [(13,7),(14,12),(15,1)]:
        for j in range(n):
            assert rows[f'ingredientRows[{group}].nestedRows[{j}]']['exact_dose_text'].strip('— ')
    assert rows['ingredientRows[14].nestedRows[5]']['exact_dose_text'] == '1,248 HCU'
    assert rows['ingredientRows[14].nestedRows[9]']['exact_dose_text'] == '65 PGU'
    assert rows['ingredientRows[14].nestedRows[11]']['exact_dose_text'] == '840 XU'
    assert rows['ingredientRows[18]']['exact_dose_text'].startswith('5 SOD')

@pytest.mark.parametrize('change', ['missing_group','member_changed','parent_amount','duplicate_group','parent_mismatch'])
def test_reviewed_hierarchy_fails_closed_on_source_changes(change):
    raw = raw_label('275412')
    if change == 'missing_group':
        raw['ingredientRows'].pop(14)
    elif change == 'member_changed':
        raw['ingredientRows'][13]['nestedRows'][0]['name'] = 'Unknown Enzyme'
    elif change == 'parent_amount':
        raw['ingredientRows'][12]['quantity'][0]['quantity'] = 621
    elif change == 'duplicate_group':
        raw['ingredientRows'].append(copy.deepcopy(raw['ingredientRows'][13]))
        raw['ingredientRows'][-1]['raw_source_path'] = 'ingredientRows[13]'
    else:
        raw['ingredientRows'][12]['name'] = 'Different Formula'
    with pytest.raises(ValueError, match='Reviewed serving source changed|hierarchy|source path|note attribution'):
        EnhancedDSLDNormalizer().normalize_product(raw)

def test_unreviewed_product_cannot_borrow_hierarchy_correction():
    raw = raw_label('275412');raw['id'] = '999999'
    rows = EnhancedDSLDNormalizer().normalize_product(raw)['activeIngredients']
    [group] = [x for x in rows if x['raw_source_path'] == 'ingredientRows[13]']
    assert group.get('parent_source_path') is None

def test_trace_material_disposition_is_exact_quantity_edition_only():
    raw = raw_label('182990');raw['ingredientRows'][5]['quantity'][0]['quantity'] = 701
    rows = EnhancedDSLDNormalizer().normalize_product(raw)['activeIngredients']
    [matrix] = [x for x in rows if x['raw_source_path'] == 'ingredientRows[5]']
    assert matrix['quantity'] == 701 and matrix['cleaner_row_role'] != 'source_descriptor'

def test_shared_owner_preserves_existing_hdu_display_support():
    assert EnhancedDSLDNormalizer._activity_dose_from_notes('(10,000 HDU)') == '10,000 HDU'
    assert extract_enzyme_activity('10,000 HDU') == (10000, 'HDU')

def test_corrected_display_hierarchy_depth_matches_parent_links(assessments):
    _, _, _, blob = assessments['275412']
    rows = {x['raw_source_path']: x for x in blob['display_ingredients']}
    for group,n in [(13,7),(14,12),(15,1)]:
        row = rows[f'ingredientRows[{group}]']
        assert row['parent_source_path'] == 'ingredientRows[12]'
        assert row['parent_label'] == 'RAW Enzyme Blend' and row['nested_depth'] == 1
        for i in range(n):
            child = rows[f'ingredientRows[{group}].nestedRows[{i}]']
            assert child['nested_depth'] == 2 and child['parent_source_path'] == row['raw_source_path']

def test_probiotic_total_belongs_to_separate_blend_not_each_species(assessments):
    _, enriched, _, _ = assessments['275412']
    data = enriched['probiotic_data']
    assert data['total_cfu'] == 500_000_000
    assert data['cfu_raw_source_path'] == 'ingredientRows[16]'
    [header] = [x for x in data['probiotic_blends'] if x.get('raw_source_path') == 'ingredientRows[16]']
    assert header['cfu_data']['cfu_count'] == 500_000_000
    children = [x for x in data['probiotic_blends'] if x.get('raw_source_path') in {'ingredientRows[16].nestedRows[0]','ingredientRows[16].nestedRows[1]'}]
    assert all(not x['cfu_data']['has_cfu'] for x in children)
    assert not any(x.get('raw_source_path') == 'ingredientRows[12]' and x['cfu_data'].get('has_cfu') for x in data['probiotic_blends'])


@pytest.mark.parametrize('change', ['count', 'parent_mass', 'species'])
def test_reviewed_cfu_attribution_is_atomic_and_exact(change):
    normalizer = EnhancedDSLDNormalizer()
    rows = raw_label('275412')['ingredientRows']
    normalizer._stamp_raw_source_paths(rows, 'ingredientRows')
    if change == 'count':
        rows[16]['nestedRows'][0]['notes'] = 'Total Cultures 600,000,000 CFU'
    elif change == 'parent_mass':
        rows[16]['quantity'][0]['quantity'] = 32
    else:
        rows[16]['nestedRows'][1]['name'] = 'Another culture'
    before = copy.deepcopy(rows)
    with pytest.raises(ValueError, match='note attribution'):
        normalizer._apply_label_corrections(rows, '275412')
    assert rows == before


def test_trace_material_correction_does_not_transfer_to_another_physical_row():
    raw = raw_label('182990')
    raw['ingredientRows'].append(copy.deepcopy(raw['ingredientRows'][5]))
    rows = raw['ingredientRows']
    normalizer = EnhancedDSLDNormalizer()
    normalizer._stamp_raw_source_paths(rows, 'ingredientRows')
    normalizer._apply_label_corrections(rows, '182990')
    assert rows[5]['_label_scoring_disposition'] == 'source_descriptor'
    assert rows[6].get('_label_scoring_disposition') is None


def test_reviewed_hierarchy_and_note_corrections_are_idempotent():
    normalizer = EnhancedDSLDNormalizer()
    rows = raw_label('275412')['ingredientRows']
    normalizer._stamp_raw_source_paths(rows, 'ingredientRows')
    normalizer._apply_label_corrections(rows, '275412')
    first = copy.deepcopy(rows)
    normalizer._apply_label_corrections(rows, '275412')
    assert rows == first
