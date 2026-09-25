"""Every label form state has one outcome, end to end (normalize -> enrich ->
score -> curation queue):

1. no form on the label        -> scored at the IQM unspecified policy, not queued
2. a named form IQM lacks      -> held, queued as disclosed_form_unmapped
3. an unknown active           -> cleaner's unmapped-active output, held
4. a known excipient           -> other-ingredients route, never queued
5. a named IQM form            -> that form's bio_score
6. a form the pipeline dropped -> held, queued as pipeline_form_loss; distinct
                                  from label nondisclosure (1)
"""
import copy
import json
import logging
from pathlib import Path

import pytest

BASE = json.loads((Path(__file__).parent / 'fixtures' / 'form_association_318107_raw.json').read_text())
IQM = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'ingredient_quality_map.json').read_text())


def _row(order, name, group, category, forms=()):
    return {
        'order': order, 'ingredientId': 990000 + order, 'description': '', 'notes': '',
        'quantity': [{'servingSizeOrder': 1, 'servingSizeQuantity': 1, 'operator': '=', 'quantity': 100,
                      'unit': 'mg', 'dailyValueTargetGroup': [], 'servingSizeUnit': 'Capsule(s)'}],
        'nestedRows': [], 'name': name, 'category': category, 'ingredientGroup': group, 'uniiCode': None,
        'alternateNames': [],
        'forms': [{'order': i + 1, 'ingredientId': 980000 + order * 10 + i, 'prefix': None, 'percent': None,
                   'name': form, 'category': category, 'ingredientGroup': group, 'uniiCode': None}
                  for i, form in enumerate(forms)],
    }


def _label(pid, rows, others=()):
    raw = copy.deepcopy(BASE)
    raw.update({
        'id': pid, 'fullName': f'Form State {pid}', 'brandName': 'Probe Labs', 'statements': [], 'claims': [],
        'servingSizes': [{'order': 1, 'minQuantity': 1, 'maxQuantity': 1, 'minDailyServings': 1,
                          'maxDailyServings': 1, 'unit': 'Capsule(s)', 'notes': '', 'inSFB': True}],
        'physicalState': {'langualCode': 'E0159', 'langualCodeDescription': 'Capsule'},
        'productType': {'langualCode': 'A1302', 'langualCodeDescription': 'Vitamin'},
        'ingredientRows': rows,
        'otheringredients': {'text': None, 'ingredients': [
            {'order': i + 1, 'ingredientId': 970000 + i, 'name': name, 'category': 'other',
             'ingredientGroup': name, 'uniiCode': None, 'alternateNames': [], 'forms': []}
            for i, name in enumerate(others)]},
    })
    return raw


VITAMIN_C = ('Vitamin C', 'Vitamin C', 'vitamin')


@pytest.fixture(scope='module')
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def _run(pipeline, raw):
    from score_supplements_v4 import score_product_v4
    normalizer, enricher = pipeline
    enricher._form_fallback_details = []
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    readiness = score_product_v4(enriched)['v4_breakdown']['assessment_readiness']
    rows = {r['name']: r for r in enriched['ingredient_quality_data']['ingredients']}
    queue = [(f['gap_type'], f['unmapped_form_text'], f['dsld_id']) for f in enricher._form_fallback_details]
    return enriched, readiness, rows, queue


def _unspecified(parent):
    from scoring_reference_resolver import unknown_form_quality
    return unknown_form_quality(IQM[parent])['bio_score']


def test_no_form_on_the_label_scores_at_the_unspecified_policy_and_is_not_queued(pipeline):
    raw = _label(1, [_row(1, *VITAMIN_C), _row(2, 'Magnesium', 'Magnesium', 'mineral', ['Magnesium Citrate'])],
                 ['Magnesium Stearate'])
    enriched, readiness, rows, queue = _run(pipeline, raw)
    assert rows['Vitamin C']['form_match_status'] == 'n/a'
    assert rows['Vitamin C']['bio_score'] == _unspecified('vitamin_c')
    assert readiness['is_live_ready'] is True and readiness['identity']['blocking_contract_findings'] == []
    assert queue == []

    # 5. a named IQM form scores that form's bio_score
    magnesium = rows['Magnesium']
    assert (magnesium['form_id'], magnesium['form_match_status']) == ('magnesium citrate', 'mapped')
    assert magnesium['bio_score'] == IQM['magnesium']['forms']['magnesium citrate']['bio_score']

    # 4. a known excipient takes the other-ingredients route
    stearate = enriched['inactiveIngredients'][0]
    assert (stearate['canonical_source_db'], stearate['mapped']) == ('other_ingredients', True)
    assert 'Magnesium Stearate' not in pipeline[0].unmapped_details


def test_a_named_form_iqm_lacks_is_held_and_queued(pipeline):
    raw = _label(2, [_row(1, *VITAMIN_C, forms=['Ascorbyl Zqxate'])])
    _, readiness, rows, queue = _run(pipeline, raw)
    row = rows['Vitamin C']
    assert (row['canonical_id'], row['form_id'], row['bio_score']) == ('vitamin_c', None, None)
    assert row['form_match_status'] == 'unmapped'
    assert readiness['is_live_ready'] is False
    assert readiness['identity']['blocking_contract_findings'] == ['disclosed_form_unmapped']
    assert queue == [('disclosed_form_unmapped', 'Ascorbyl Zqxate', '2')]


def test_an_unknown_active_goes_to_the_cleaners_unmapped_active_output(pipeline):
    raw = _label(3, [_row(1, *VITAMIN_C), _row(2, 'Zqxolide', 'Zqxolide', 'non-nutrient/non-botanical')])
    _, readiness, rows, queue = _run(pipeline, raw)
    assert rows['Zqxolide']['role_classification'] == 'active_unmapped'
    assert pipeline[0].unmapped_details['Zqxolide']['is_active'] is True
    assert readiness['is_live_ready'] is False
    assert queue == []


def test_a_form_the_pipeline_dropped_is_held_and_not_mistaken_for_nondisclosure(pipeline, monkeypatch):
    # Simulate a match path that never consults the cleaner's forms: the row
    # reads the parent's unspecified value, exactly like a label with no form.
    _, enricher = pipeline
    real = enricher._match_quality_map

    def ignores_cleaned_forms(ing_name, std_name, quality_map, _form_extraction_attempt=False,
                              cleaned_forms=None, **kwargs):
        return real(ing_name, std_name, quality_map, _form_extraction_attempt,
                    cleaned_forms if _form_extraction_attempt else None, **kwargs)

    monkeypatch.setattr(enricher, '_match_quality_map', ignores_cleaned_forms)
    enricher._match_quality_cache.clear()
    try:
        _, readiness, rows, queue = _run(pipeline, _label(4, [_row(1, *VITAMIN_C, forms=['Ascorbic Acid'])]))
    finally:
        enricher._match_quality_cache.clear()
    row = rows['Vitamin C']
    assert row['form_match_status'] == 'lost' and row['lost_forms'] == ['Ascorbic Acid']
    assert readiness['is_live_ready'] is False
    assert readiness['identity']['blocking_contract_findings'] == ['pipeline_form_loss']
    assert queue == [('pipeline_form_loss', 'Ascorbic Acid', '4')]


def test_descriptor_and_curated_unspecified_tokens_are_not_losses(pipeline):
    # "Sodium Borate" is an IQM alias of boron's unspecified form; "Kelp" is
    # iodine's source. Neither names a form the row dropped.
    _, enricher = pipeline
    assert enricher._dropped_label_forms('Boron', 'boron', [{'name': 'Sodium Borate', 'ingredientGroup': 'Boron'}]) == []
    assert enricher._dropped_label_forms('Iodine', 'iodine', [{'name': 'Kelp', 'category': 'botanical',
                                                               'ingredientGroup': 'Kelp'}]) == []


def test_the_queue_report_ranks_by_held_products_and_names_them(pipeline):
    _, enricher = pipeline
    enricher._form_fallback_details = []
    for pid in (21, 22):
        pipeline_raw = _label(pid, [_row(1, *VITAMIN_C, forms=['Ascorbyl Zqxate'])])
        enricher.enrich_product(pipeline[0].normalize_product(pipeline_raw))
    entry = enricher._form_curation_report()['form_fallbacks'][0]
    assert (entry['canonical_id'], entry['unmapped_form_text'], entry['gap_type']) == (
        'vitamin_c', 'Ascorbyl Zqxate', 'disclosed_form_unmapped')
    assert (entry['affected_product_count'], entry['dsld_ids'], entry['brands']) == (2, ['21', '22'], ['Probe Labs'])
    assert entry['examples'][0]['raw_source_text']


def test_the_redundant_match_time_tracker_is_gone():
    from enrich_supplements_v3 import SupplementEnricherV3
    assert not hasattr(SupplementEnricherV3, '_track_unmapped_form')


def test_a_label_naming_a_different_identity_is_held_for_identity_verification(pipeline):
    # Eleuthero (Eleutherococcus senticosus) is filed as a form of Panax
    # ginseng; it must not take ginseng's scoring.
    _, readiness, rows, queue = _run(pipeline, _label(5, [_row(1, 'Siberian Ginseng', 'Eleuthero', 'botanical')]))
    row = rows['Siberian Ginseng']
    assert (row['form_match_status'], row['bio_score']) == ('needs_identity_verification', None)
    assert readiness['identity']['blocking_contract_findings'] == ['needs_identity_verification']
    assert queue == [('needs_identity_verification', 'siberian ginseng (eleuthero)', '5')]
