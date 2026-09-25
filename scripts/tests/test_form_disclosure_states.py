"""Every label form state has one outcome, end to end (normalize -> enrich ->
score -> curation queue):

1. no form on the label        -> scored at the IQM unspecified policy, not queued
2. a named form IQM lacks      -> held, queued as disclosed_form_unmapped
3. an unknown active           -> cleaner's unmapped-active output, held
4. a known excipient           -> other-ingredients route, never queued
5. a named IQM form            -> that form's bio_score
6. a form the pipeline dropped -> held, queued as pipeline_form_loss; distinct
                                  from label nondisclosure (1)

A held row always reads form_match_status 'unmapped' (the only three values are
mapped, unmapped and n/a); why it is held is curation-report data (gap_type),
not a product field.
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
    assert (row['form_match_status'], row['unmapped_forms'], row['bio_score']) == ('unmapped', ['Ascorbic Acid'], None)
    assert 'lost_forms' not in row
    assert readiness['is_live_ready'] is False
    assert readiness['identity']['blocking_contract_findings'] == ['disclosed_form_unmapped']
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


def test_a_label_naming_a_different_identity_is_held_as_unmapped(pipeline):
    # D-tyrosine (the (2R) enantiomer) is filed under L-tyrosine as a
    # wrong_stereoisomer; it must not take L-tyrosine's scoring.
    _, readiness, rows, queue = _run(pipeline, _label(5, [_row(1, 'D-Tyrosine', 'Tyrosine', 'amino acid')]))
    row = rows['D-Tyrosine']
    assert (row['form_match_status'], row['unmapped_forms'], row['bio_score']) == ('unmapped', ['d-tyrosine'], None)
    assert readiness['identity']['blocking_contract_findings'] == ['disclosed_form_unmapped']
    assert queue == [('identity_mismatch', 'd-tyrosine', '5')]


def test_form_match_status_keeps_three_values(pipeline):
    raws = [_label(6, [_row(1, *VITAMIN_C), _row(2, 'Magnesium', 'Magnesium', 'mineral', ['Magnesium Citrate'])]),
            _label(7, [_row(1, *VITAMIN_C, forms=['Ascorbyl Zqxate'])]),
            _label(8, [_row(1, 'D-Tyrosine', 'Tyrosine', 'amino acid')])]
    statuses = {row['form_match_status'] for raw in raws for row in _run(pipeline, raw)[2].values()}
    assert statuses == {'mapped', 'unmapped', 'n/a'}


def _iron(form, mg=10):
    row = _row(2, 'Iron', 'Iron', 'mineral', [form])
    row['quantity'][0]['quantity'] = mg
    return row


def _pillars(pipeline, raw):
    from score_supplements_v4 import score_product_v4
    normalizer, enricher = pipeline
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    result = score_product_v4(enriched)
    return result['quality_score_status'], {k: v.get('score') for k, v in (result['quality_pillars_v4'] or {}).items()}


def test_a_form_that_delivers_none_of_its_nutrient_earns_no_dose_or_evidence(pipeline):
    # IQM parent_relationship not_a_nutrient_source: iron oxide supplies no
    # iron. A label listing it beside vitamin C scores Dose and Evidence
    # exactly as vitamin C alone; iron bisglycinate still earns iron's Dose.
    _, c_only = _pillars(pipeline, _label(46, [_row(1, *VITAMIN_C)]))
    _, with_oxide = _pillars(pipeline, _label(47, [_row(1, *VITAMIN_C), _iron('Iron Oxide')]))
    _, with_glycinate = _pillars(pipeline, _label(48, [_row(1, *VITAMIN_C), _iron('Ferrous Bisglycinate')]))
    assert (with_oxide['dose'], with_oxide['evidence']) == (c_only['dose'], c_only['evidence'])
    assert with_glycinate['dose'] != c_only['dose']


def test_a_form_that_delivers_nothing_keeps_its_own_formulation_only(pipeline):
    # Formulation reads iron oxide's own low bio_score; Dose and Evidence
    # give nothing as iron (bisglycinate, for contrast, earns both).
    _, oxide = _pillars(pipeline, _label(49, [_iron('Iron Oxide')]))
    _, glycinate = _pillars(pipeline, _label(50, [_iron('Ferrous Bisglycinate')]))
    assert (oxide['dose'], oxide['evidence']) == (0.0, 0.0)
    assert 0 < oxide['formulation'] < glycinate['formulation']
    assert glycinate['dose'] > 0 and glycinate['evidence'] > 0


def test_delivery_is_derived_from_parent_relationship_alone():
    from scoring_reference_resolver import delivers_parent_nutrient
    assert delivers_parent_nutrient('iron', ['iron oxide']) is False
    assert delivers_parent_nutrient('vitamin_e', ['oxidized vitamin E']) is False
    assert delivers_parent_nutrient('vitamin_d', ['vitamin D analogs (non-functional)']) is False
    assert delivers_parent_nutrient('iron', ['iron oxide', 'iron bisglycinate']) is True
    assert delivers_parent_nutrient('iron', [None]) is True


def test_an_omega3_total_reads_its_disclosed_ethyl_ester(pipeline):
    # 302644 Doctor's Best Calamari DHA: "Total Omega-3 Fatty Acids" as
    # "Omega-3 Fatty Acids Ethyl Ester". The generic-omega-3 path once
    # dropped the form; the printed spelling is now an IQM alias of the form.
    from score_supplements_v4 import score_product_v4
    normalizer, enricher = pipeline
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'form_association_302644_raw.json').read_text())
    enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
    row = next(r for r in enriched['ingredient_quality_data']['ingredients'] if r['name'] == 'Total Omega-3 Fatty Acids')
    assert (row['canonical_id'], row['form_id'], row['form_match_status']) == ('fish_oil', 'ethyl ester', 'mapped')
    assert score_product_v4(enriched)['quality_score_status'] == 'scored'


@pytest.mark.parametrize('label', ['Siberian Ginseng', 'Eleuthero Root Extract', 'Eleutherococcus senticosus root Extract'])
def test_eleuthero_is_its_own_identity_not_panax_ginseng(pipeline, label):
    _, enricher = pipeline
    match = enricher._match_quality_map(label, label, enricher.databases['ingredient_quality_map'])
    assert (match['canonical_id'], match['form_id']) == ('siberian_ginseng', 'eleuthero (Eleutherococcus senticosus)')


@pytest.mark.parametrize('label', ['CurcuWIN Turmeric root extract', 'CurcuWIN Turmeric extract'])
def test_curcuwin_reads_its_own_form(pipeline, label):
    _, enricher = pipeline
    match = enricher._match_quality_map(label, label, enricher.databases['ingredient_quality_map'],
                                        cleaned_forms=[{'name': 'Curcuminoids'}], cleaner_canonical_id='turmeric')
    assert (match['canonical_id'], match['form_id']) == ('curcumin', 'curcuwin')


def test_epa_under_an_omega3_total_is_a_component_not_a_form(pipeline):
    # IQM fish_oil relationships: contains epa, dha. "Omega-3 Fatty Acids"
    # with an EPA line is read as fish oil with a component, not an EPA form.
    _, enricher = pipeline
    form_data = {'raw_form_text': 'Eicosapentaenoic Acid', 'dsld_category': 'fatty acid',
                 'dsld_ingredient_group': 'EPA (Eicosapentaenoic Acid)'}
    assert enricher._form_token_context(form_data, {'fish oil'}, 'fish_oil', 'Omega-3 Fatty Acids') == 'component'
    assert enricher._form_token_context(form_data, {'vitamin c'}, 'vitamin_c', 'Vitamin C') is None
