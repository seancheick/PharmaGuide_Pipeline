"""Synergy dose floors compare against each threshold's NATIVE unit.

Regression: the "unit-aware" refactor forced the product amount to **mg**
before comparing to a cluster's ``min_effective_dose``, but the thresholds in
``synergy_cluster.json`` are authored in each nutrient's conventional unit
(methylcobalamin 500 **mcg**, vitamin d 1000 **IU**, probiotics 1e10 **CFU**).
Forcing mg mis-scaled every non-mg threshold, so ~19/58 clusters silently lost
their synergy bonus (under-credit).

Each threshold now carries its unit (default ``mg``; overrides in a shared
``min_effective_dose_units`` map) and the product amount is converted **to that
unit** before the comparison. Melatonin (0.5 mg, no override) still converts a
mcg-listed product to mg — preserving test_synergy_unit_aware.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_supplements_v3 import SupplementEnricherV3


def _enricher_with(clusters, units):
    e = SupplementEnricherV3()
    e.databases["synergy_cluster"] = {
        "synergy_clusters": clusters,
        "min_effective_dose_units": units,
    }
    return e


def _cluster(cid, ingredient, dose):
    return {
        "id": cid,
        "standard_name": cid,
        "ingredients": [ingredient],
        "canonical_ids": [ingredient],
        "min_effective_doses": {ingredient: dose},
        "allow_single_ingredient": True,
        "primary_ingredients": [ingredient],
    }


def _product(name, qty, unit):
    return {
        "name": "t",
        "activeIngredients": [
            {"name": name, "standardName": name, "quantity": qty, "unit": unit}
        ],
    }


def _meets(enricher, product):
    clusters = enricher._collect_synergy_data(product)
    return clusters[0]["matched_ingredients"][0]["meets_minimum"]


class TestMcgThresholdNoLongerMisScaled:
    """methylcobalamin floor = 500 mcg (was forced to mg → 0.5 ≥ 500 = False)."""

    def test_500_mcg_meets_500_mcg_floor(self):
        e = _enricher_with([_cluster("methyl", "methylcobalamin", 500)], {"methylcobalamin": "mcg"})
        assert _meets(e, _product("Methylcobalamin", 500, "mcg")) is True

    def test_300_mcg_does_not_meet_500_mcg_floor(self):
        e = _enricher_with([_cluster("methyl", "methylcobalamin", 500)], {"methylcobalamin": "mcg"})
        assert _meets(e, _product("Methylcobalamin", 300, "mcg")) is False

    def test_product_in_mg_converts_to_mcg(self):
        # 0.5 mg == 500 mcg → meets the 500 mcg floor
        e = _enricher_with([_cluster("methyl", "methylcobalamin", 500)], {"methylcobalamin": "mcg"})
        assert _meets(e, _product("Methylcobalamin", 0.5, "mg")) is True


class TestIuThreshold:
    def test_1000_iu_meets_1000_iu_floor(self):
        e = _enricher_with([_cluster("d", "vitamin d", 1000)], {"vitamin d": "iu"})
        assert _meets(e, _product("Vitamin D", 1000, "IU")) is True


class TestCfuThreshold:
    def test_1e10_cfu_meets_1e10_floor(self):
        e = _enricher_with([_cluster("pro", "probiotics", 10_000_000_000)], {"probiotics": "cfu"})
        assert _meets(e, _product("Probiotics", 10_000_000_000, "CFU")) is True


class TestMgDefaultPreserved:
    """No override → mg (the dominant convention); Codex's melatonin cases hold."""

    def test_melatonin_500_mcg_meets_half_mg(self):
        e = _enricher_with([_cluster("mel", "melatonin", 0.5)], {})
        assert _meets(e, _product("Melatonin", 500, "mcg")) is True

    def test_melatonin_300_mcg_does_not_meet_half_mg(self):
        e = _enricher_with([_cluster("mel", "melatonin", 0.5)], {})
        assert _meets(e, _product("Melatonin", 300, "mcg")) is False

    def test_mg_threshold_native(self):
        e = _enricher_with([_cluster("cur", "curcumin", 500)], {})
        assert _meets(e, _product("Curcumin", 500, "mg")) is True


class TestUnconvertibleThresholds:
    def test_cross_dimensional_unit_does_not_false_positive_a_solo_cluster(self):
        e = _enricher_with([_cluster("pro", "probiotics", 100)], {"probiotics": "cfu"})
        assert e._collect_synergy_data(_product("Probiotics", 500, "mg")) == []

    def test_unsupported_unit_does_not_false_positive_a_solo_cluster(self):
        e = _enricher_with([_cluster("cur", "curcumin", 500)], {})
        assert e._collect_synergy_data(_product("Curcumin", 600, "spoon")) == []

    def test_multi_ingredient_cluster_keeps_unconvertible_match_but_marks_it_unevaluable(self):
        e = _enricher_with([{
            "id": "mixed",
            "standard_name": "mixed",
            "ingredients": ["curcumin", "probiotics"],
            "canonical_ids": ["curcumin", "probiotics"],
            "min_effective_doses": {"curcumin": 500, "probiotics": 100},
            "allow_single_ingredient": False,
            "primary_ingredients": ["curcumin", "probiotics"],
        }], {"probiotics": "cfu"})
        product = {
            "name": "t",
            "activeIngredients": [
                {"name": "Curcumin", "standardName": "Curcumin", "quantity": 500, "unit": "mg"},
                {"name": "Probiotics", "standardName": "Probiotics", "quantity": 500, "unit": "mg"},
            ],
        }

        clusters = e._collect_synergy_data(product)

        assert len(clusters) == 1
        assert clusters[0]["all_adequate"] is False
        matched = {row["cluster_ingredient"]: row for row in clusters[0]["matched_ingredients"]}
        assert matched["curcumin"]["meets_minimum"] is True
        assert matched["curcumin"]["dose_evaluable"] is True
        assert matched["probiotics"]["evaluated_quantity"] is None
        assert matched["probiotics"]["evaluated_unit"] is None
        assert matched["probiotics"]["dose_evaluable"] is False
        assert matched["probiotics"]["meets_minimum"] is False


@pytest.fixture(scope='module')
def canonical_synergy_enricher():
    return SupplementEnricherV3()


def _elderberry_source_product(pid, display='Elderberries'):
    """Retained source facts from293381/335161, reduced to relevant rows."""
    is_a = pid == '293381'
    rows = [
        ('Vitamin C', 'vitamin_c', 60 if is_a else 90, 'mg'),
        ('Zinc', 'zinc', 2.2 if is_a else 7.5, 'mg'),
        ('Black Elder Berry Extract', 'elderberry', 50, 'mg'),
        ('Vitamin A' if is_a else 'Vitamin D3', 'vitamin_a' if is_a else 'vitamin_d',
         600 if is_a else 30, 'mcg'),
    ]
    ingredients = [dict(name=name, standardName=display if canonical == 'elderberry' else name,
        canonical_id=canonical, canonical_source_db='ingredient_quality_map',
        quantity=qty, unit=unit, raw_source_path=f'ingredientRows[{i}]',
        raw_source_text=name, cleaner_row_role='active_scorable', source_section='active')
        for i, (name, canonical, qty, unit) in enumerate(rows)]
    return {'id': pid, 'fullName': 'Source qualified multivitamin fixture',
            'brandName': 'Source fixture', 'activeIngredients': ingredients, 'inactiveIngredients': []}


@pytest.mark.parametrize('pid', ['293381', '335161'])
@pytest.mark.parametrize('display', ['Elderberries', 'European Elder', 'Elderberry'])
def test_canonical_synergy_survives_source_display_spelling_at_enrichment_boundary(canonical_synergy_enricher, pid, display):
    enriched, _ = canonical_synergy_enricher.enrich_product(_elderberry_source_product(pid, display))
    clusters = {c['cluster_id']: c for c in enriched['formulation_data']['synergy_clusters']}
    for key, count in [('immune_defense', 4), ('respiratory_health_lung_support', 3)]:
        assert clusters[key]['match_count'] == count
        elder = next(r for r in clusters[key]['matched_ingredients'] if r['cluster_ingredient'] == 'elderberry')
        assert (elder['ingredient'], elder['quantity'], elder['unit']) == ('Black Elder Berry Extract', 50, 'mg')


@pytest.mark.parametrize('display', ['Elderberry', 'Elderberry extract', 'Elderberryish'])
def test_known_other_identity_cannot_match_generic_cluster_from_display(canonical_synergy_enricher, display):
    product = _elderberry_source_product('293381', display)
    row = product['activeIngredients'][2]
    row.update(name='Blueberry', raw_source_text='Blueberry', canonical_id='blueberry')
    clusters = canonical_synergy_enricher._collect_synergy_data(product)
    assert not any(m['cluster_ingredient'] == 'elderberry'
                   for c in clusters for m in c['matched_ingredients'])


def test_generic_canonical_fallback_does_not_transfer_form_specific_cluster():
    e = _enricher_with([{
        'id': 'form_specific', 'standard_name': 'Form specific fixture',
        'ingredients': ['magnesium glycinate'], 'canonical_ids': ['magnesium'],
        'min_effective_doses': {'magnesium glycinate': 100},
        'allow_single_ingredient': True, 'primary_ingredients': ['magnesium glycinate'],
    }], {})
    product = _product('Magnesium Oxide', 200, 'mg')
    product['activeIngredients'][0].update(canonical_id='magnesium', canonical_source_db='ingredient_quality_map')
    assert e._collect_synergy_data(product) == []


def test_canonical_synergy_keeps_strict_nonfunctional_source_excluded(canonical_synergy_enricher):
    import copy
    product = _elderberry_source_product('293381')
    rows = copy.deepcopy(product['activeIngredients'])
    for row in rows:
        row.update(mapped=True, mapped_identity=True, scoreable_identity=True,
                   identity_disposition='clean', score_eligible_by_cleaner=True,
                   role_classification='active_scorable', dose_class='therapeutic_mass')
    rows[2].update(scoreable_identity=False, score_eligible_by_cleaner=False,
                   cleaner_row_role='inactive_excipient', source_section='inactive',
                   role_classification='recognized_non_scorable')
    product['activeIngredients'][2].update(
        cleaner_row_role='inactive_excipient', source_section='inactive',
        score_eligible_by_cleaner=False)
    product['ingredient_quality_data'] = {
        'ingredients': rows, 'ingredients_scorable': [r for i, r in enumerate(rows) if i != 2]}
    clusters = canonical_synergy_enricher._collect_synergy_data(product)
    assert not any(m['cluster_ingredient'] == 'elderberry'
                   for c in clusters for m in c['matched_ingredients'])


def test_legacy_synergy_without_canonical_identity_keeps_existing_match(canonical_synergy_enricher):
    product = _elderberry_source_product('293381', 'Elderberry')
    for row in product['activeIngredients']:
        row.pop('canonical_id')
        row.pop('canonical_source_db')
    clusters = canonical_synergy_enricher._collect_synergy_data(product)
    assert any(m['cluster_ingredient'] == 'elderberry'
               for c in clusters for m in c['matched_ingredients'])


def test_prepared_alcar_alias_keeps_existing_source_match_at_enrichment_boundary(canonical_synergy_enricher):
    product = {'id': '294029', 'fullName': 'ALCAR source fixture', 'activeIngredients': [
        {'name': 'Vitamin B6', 'standardName': 'Vitamin B6 (Pyridoxine)',
         'canonical_id': 'vitamin_b6_pyridoxine', 'canonical_source_db': 'ingredient_quality_map',
         'quantity': 6.7, 'unit': 'mg', 'raw_source_path': 'ingredientRows[0]',
         'raw_source_text': 'Vitamin B6', 'cleaner_row_role': 'active_scorable'},
        {'name': 'Acetyl-L-Carnitine', 'standardName': 'L-Carnitine',
         'canonical_id': 'l_carnitine', 'canonical_source_db': 'ingredient_quality_map',
         'quantity': 500, 'unit': 'mg', 'raw_source_path': 'ingredientRows[1]',
         'raw_source_text': 'Acetyl-L-Carnitine', 'cleaner_row_role': 'active_scorable'},
    ]}
    enriched, _ = canonical_synergy_enricher.enrich_product(product)
    cluster = next((c for c in enriched['formulation_data']['synergy_clusters']
                    if c['cluster_id'] == 'nerve_health_neuropathy_support'), None)
    assert cluster is not None
    alcar = next(m for m in cluster['matched_ingredients'] if m['ingredient'] == 'Acetyl-L-Carnitine')
    assert alcar['cluster_ingredient'] == 'acetyl-l-carnitine'
    assert alcar['min_effective_dose'] == 500
    assert alcar['meets_minimum'] is True


def test_cross_namespace_preparation_keeps_existing_lexical_scope(canonical_synergy_enricher):
    product = {'id': '182627', 'fullName': 'Green tea source fixture', 'activeIngredients': [
        {'name': 'decaffeinated Green Tea extract', 'standardName': 'Green Tea',
         'canonical_id': 'green_tea', 'canonical_source_db': 'standardized_botanicals',
         'quantity': 325, 'unit': 'mg'},
        {'name': 'Chromium', 'standardName': 'Chromium', 'canonical_id': 'chromium',
         'canonical_source_db': 'ingredient_quality_map', 'quantity': 500, 'unit': 'mcg'},
    ]}
    cluster = next((c for c in canonical_synergy_enricher._collect_synergy_data(product)
                    if c['cluster_id'] == 'fat_metabolism'), None)
    assert cluster is not None
    tea = next(m for m in cluster['matched_ingredients'] if m['cluster_ingredient'] == 'green tea extract')
    assert tea['quantity'] == 325
    assert tea['min_effective_dose'] == 400
    assert tea['meets_minimum'] is False


def test_generic_canonical_does_not_establish_branded_preparation():
    e = _enricher_with([{
        'id': 'branded_fixture', 'standard_name': 'Branded fixture',
        'ingredients': ['carnipure'], 'canonical_ids': ['l_carnitine'],
        'min_effective_doses': {}, 'allow_single_ingredient': True,
        'primary_ingredients': ['carnipure'],
    }], {})
    product = _product('L-Carnitine', 500, 'mg')
    product['activeIngredients'][0].update(canonical_id='l_carnitine', canonical_source_db='ingredient_quality_map')
    assert e._collect_synergy_data(product) == []


def test_existing_coq10_lexical_alias_keeps_scope_and_resolves_curated_threshold():
    e = _enricher_with([{
        'id': 'coq_alias', 'standard_name': 'CoQ10 alias fixture',
        'ingredients': ['coq10', 'coenzyme q10', 'vitamin c'], 'canonical_ids': ['coq10', 'vitamin_c'],
        'min_effective_doses': {'coq10': 100}, 'allow_single_ingredient': True,
        'primary_ingredients': ['coq10', 'coenzyme q10'],
    }], {})
    product = _product('Kaneka Ubiquinol', 25, 'mg')
    product['activeIngredients'][0].update(standardName='Coenzyme Q10', canonical_id='coq10', canonical_source_db='ingredient_quality_map')
    product['activeIngredients'].append({'name': 'Vitamin C', 'standardName': 'Vitamin C',
        'canonical_id': 'vitamin_c', 'canonical_source_db': 'ingredient_quality_map', 'quantity': 100, 'unit': 'mg'})
    member = e._collect_synergy_data(product)[0]['matched_ingredients'][0]
    assert member['cluster_ingredient'] == 'coenzyme q10'
    assert member['quantity'] == 25
    assert member['min_effective_dose'] == 100
    assert member['meets_minimum'] is False


@pytest.mark.parametrize('name', ['N-Acetyl-L-Cysteine', 'N-Acetyl Cysteine'])
def test_nac_does_not_borrow_cysteine_identity_or_zero_minimum(name):
    e = _enricher_with([{
        'id': 'nac_alias', 'standard_name': 'NAC alias fixture',
        'ingredients': ['cysteine', 'nac', 'n-acetyl cysteine', 'vitamin c'],
        'canonical_ids': ['l_cysteine', 'nac', 'vitamin_c'], 'min_effective_doses': {'nac': 600},
        'allow_single_ingredient': True, 'primary_ingredients': ['cysteine', 'nac', 'n-acetyl cysteine'],
    }], {})
    product = _product(name, 100, 'mg')
    product['activeIngredients'][0].update(canonical_id='nac', canonical_source_db='ingredient_quality_map')
    product['activeIngredients'].append({'name': 'Vitamin C', 'standardName': 'Vitamin C',
        'canonical_id': 'vitamin_c', 'canonical_source_db': 'ingredient_quality_map', 'quantity': 100, 'unit': 'mg'})
    member = next(m for m in e._collect_synergy_data(product)[0]['matched_ingredients']
                  if m['ingredient'] == name)
    assert member['cluster_ingredient'] != 'cysteine'
    assert member['min_effective_dose'] == 600
    assert member['meets_minimum'] is False


@pytest.mark.parametrize('form,expected', [('potassium chloride', False), ('potassium citrate', True), ('potassium (unspecified)', False)])
def test_preparation_cluster_consumes_exact_source_owned_form(form, expected):
    e = _enricher_with([{
        'id': 'citrate_fixture', 'standard_name': 'Citrate fixture',
        'ingredients': ['potassium citrate', 'vitamin c'], 'canonical_ids': ['potassium', 'vitamin_c'],
        'min_effective_doses': {},
    }], {})
    potassium = {'name': 'Potassium', 'standardName': 'Potassium', 'canonical_id': 'potassium',
                 'canonical_source_db': 'ingredient_quality_map', 'raw_source_text': 'Potassium',
                 'raw_source_path': 'ingredientRows[0]', 'quantity': 50, 'unit': 'mg'}
    vitamin_c = {'name': 'Vitamin C', 'standardName': 'Vitamin C', 'canonical_id': 'vitamin_c',
                 'canonical_source_db': 'ingredient_quality_map', 'raw_source_text': 'Vitamin C',
                 'raw_source_path': 'ingredientRows[1]', 'quantity': 100, 'unit': 'mg'}
    quality = [{**r, 'matched_form': form if i == 0 else 'ascorbic acid',
                'form_id': form if i == 0 else 'ascorbic acid', 'mapped': True,
                'mapped_identity': True, 'scoreable_identity': True, 'identity_disposition': 'clean',
                'source_section': 'active', 'cleaner_row_role': 'active_scorable',
                'score_eligible_by_cleaner': True, 'role_classification': 'active_scorable',
                'dose_class': 'therapeutic_mass'} for i, r in enumerate([potassium, vitamin_c])]
    product = {'activeIngredients': [potassium, vitamin_c],
               'ingredient_quality_data': {'ingredients': quality, 'ingredients_scorable': quality}}
    clusters = e._collect_synergy_data(product)
    assert bool(clusters) is expected
    if clusters:
        member = next(m for m in clusters[0]['matched_ingredients'] if m['cluster_ingredient'] == 'potassium citrate')
        assert (member['quantity'], member['unit']) == (50, 'mg')


@pytest.mark.parametrize('term,canonical,source_name,other_threshold', [
    ('acetyl-l-carnitine', 'l_carnitine', 'Acetyl-L-Carnitine', 'levocarnitine'),
    ('magnesium glycinate', 'magnesium', 'Magnesium Glycinate', 'magnesium oxide'),
])
def test_alias_threshold_cannot_cross_specific_preparation_scope(term, canonical, source_name, other_threshold):
    e = _enricher_with([{
        'id': 'scope_fixture', 'standard_name': 'Scope fixture', 'ingredients': [term],
        'canonical_ids': [canonical], 'min_effective_doses': {other_threshold: 1000},
        'allow_single_ingredient': True, 'primary_ingredients': [term],
    }], {})
    product = _product(source_name, 500, 'mg')
    product['activeIngredients'][0].update(canonical_id=canonical, canonical_source_db='ingredient_quality_map')
    member = e._collect_synergy_data(product)[0]['matched_ingredients'][0]
    assert member['min_effective_dose'] == 0
    assert member['min_effective_dose_unit'] is None


def test_prepared_magnesium_scope_is_not_proved_by_parent_display_at_enrichment_boundary():
    e = _enricher_with([{
        'id': 'glycinate_fixture', 'standard_name': 'Glycinate fixture',
        'ingredients': ['magnesium glycinate'], 'canonical_ids': ['magnesium'],
        'min_effective_doses': {'magnesium glycinate': 100},
        'allow_single_ingredient': True, 'primary_ingredients': ['magnesium glycinate'],
    }], {})
    product = {'id': 'prepared_mg_fixture', 'fullName': 'Magnesium fixture', 'activeIngredients': [{
        'name': 'Magnesium', 'standardName': 'Magnesium', 'quantity': 200, 'unit': 'mg',
        'canonical_id': 'magnesium', 'canonical_source_db': 'ingredient_quality_map',
        'raw_source_path': 'ingredientRows[0]', 'raw_source_text': 'Magnesium',
        'forms': [{'name': 'Magnesium Oxide'}], 'cleaner_row_role': 'active_scorable',
    }]}
    enriched, _ = e.enrich_product(product)
    quality = enriched['ingredient_quality_data']['ingredients_scorable']
    assert quality[0]['matched_form'] == 'magnesium oxide'
    assert enriched['formulation_data']['synergy_clusters'] == []
