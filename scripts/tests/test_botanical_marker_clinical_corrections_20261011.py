import json
from pathlib import Path
import pytest
from enrich_supplements_v3 import SupplementEnricherV3

@pytest.fixture
def enricher():
    e=SupplementEnricherV3.__new__(SupplementEnricherV3)
    p=Path(__file__).resolve().parents[1]/'data'/'botanical_marker_contributions.json'
    e.databases={'botanical_marker_contributions':json.loads(p.read_text())}
    return e

@pytest.mark.parametrize('text',[
 'Broccoli sprout standardized to 10% glucoraphanin',
 'Broccoli sprout standardized to 10% glucoraphanin with myrosinase',
])
def test_precursor_does_not_become_measured_sulforaphane(enricher,text):
    marker=enricher._compute_delivers_markers({'canonical_id':'broccoli_sprout','quantity':100,'unit_normalized':'mg','name':text})[0]
    assert marker['estimated_dose_mg'] is None
    assert marker['confidence_scale'] == 0

@pytest.mark.parametrize('text',[
 'Broccoli sprout standardized to 10% glucoraphanin and 2% sulforaphane',
 'Broccoli sprout sulforaphane 2%; glucoraphanin 10%',
])
def test_percentage_belongs_to_named_marker(enricher,text):
    marker=enricher._compute_delivers_markers({'canonical_id':'broccoli_sprout','quantity':100,'unit_normalized':'mg','name':text})[0]
    assert marker['estimated_dose_mg'] == 2
    assert marker['confidence_scale'] == 1

def test_total_curcuminoids_are_not_measured_chemical_curcumin(enricher):
    marker=enricher._compute_delivers_markers({'canonical_id':'turmeric','quantity':400,'unit_normalized':'mg','name':'Turmeric standardized to 95% total curcuminoids'})[0]
    assert marker['estimated_dose_mg'] is None
    assert marker['confidence_scale'] == 0
    control=enricher._compute_delivers_markers({'canonical_id':'turmeric','quantity':400,'unit_normalized':'mg','name':'Turmeric standardized to 95% curcumin'})[0]
    assert control['estimated_dose_mg'] == 380

@pytest.mark.parametrize('canonical,other,marker',[
 ('marigold','zeaxanthin','lutein'),
 ('cayenne_pepper','total capsaicinoids','capsaicin'),
 ('green_tea_extract','polyphenols','EGCG'),
])
def test_other_fraction_is_not_the_target_fraction(enricher,canonical,other,marker):
    row={'canonical_id':canonical,'quantity':100,'unit_normalized':'mg','name':f'Extract standardized to 20% {other}'}
    result=enricher._compute_delivers_markers(row)[0]
    assert result['estimated_dose_mg'] is None
    assert result['confidence_scale'] == 0
    row['name']=f'Extract standardized to 20% {marker}'
    result=enricher._compute_delivers_markers(row)[0]
    assert result['estimated_dose_mg'] == 20


@pytest.mark.parametrize('percentage,expected', [(50, 100), (0.5, 1)])
def test_knotweed_hold_preserves_declared_composition_and_safety_exposure(enricher, percentage, expected):
    ing = {'canonical_id': 'japanese_knotweed', 'quantity': 200, 'unit_normalized': 'mg',
           'name': f'Japanese Knotweed standardized to {percentage}% trans-resveratrol'}
    marker = enricher._compute_delivers_markers(ing)[0]
    assert marker['scoring_eligible'] is False
    assert marker['declared_standardization_pct'] == percentage
    assert marker['estimated_dose_mg'] == expected
    assert marker['estimation_method'] == 'standardization_pct'
    ing['delivers_markers'] = [marker]
    derived = enricher._derived_marker_interaction_rows(ing)
    assert derived[0]['canonical_id'] == 'resveratrol'
    assert derived[0]['quantity'] == expected


def test_knotweed_hold_does_not_turn_undisclosed_amount_into_zero(enricher):
    marker = enricher._compute_delivers_markers({'canonical_id': 'japanese_knotweed',
        'name': 'Japanese Knotweed standardized to 50% resveratrol'})[0]
    assert marker['estimated_dose_mg'] is None
    assert marker['scoring_eligible'] is False
    control = enricher._compute_delivers_markers({'canonical_id': 'grape', 'quantity': 200,
        'unit_normalized': 'mg', 'name': 'Grape standardized to 5% trans-resveratrol'})[0]
    assert control['estimated_dose_mg'] == 10
    assert control.get('scoring_eligible') is not False


def _approved_marker_source(monkeypatch, study):
    import clinical_applicability
    from test_evidence_resolver import _approved_test_source
    source = _approved_test_source({**study, "ingredient": "Resveratrol"}, name="Resveratrol")
    current = clinical_applicability.reviewed_entries()
    monkeypatch.setattr(clinical_applicability, "reviewed_entries", lambda: {**current, source["id"]: source})
    return source


def test_eligible_marker_study_cannot_override_relationship_hold(monkeypatch):
    from scoring_v4.modules.generic_evidence import score_evidence
    import clinical_applicability
    e = SupplementEnricherV3()
    study = {'id': 'INGR_RESVERATROL', 'standard_name': 'Resveratrol',
             'aliases': ['resveratrol'], 'study_type': 'rct_single',
             'evidence_level': 'ingredient-human', 'effect_direction': 'positive_strong',
             'total_enrollment': 100, 'scoring_eligible': True,
             'references_structured': [{'pmid': '28661438'}]}
    study = _approved_marker_source(monkeypatch, study)
    e.databases['backed_clinical_studies'] = {'backed_clinical_studies': [study]}
    # Inspect the production payload before applicability filtering; the study's
    # own eligibility must not overwrite the separately held relationship.
    monkeypatch.setattr(clinical_applicability, 'filter_clinical_matches', lambda p, m: (m, []))
    row = {'name': 'Japanese Knotweed', 'standard_name': 'Japanese Knotweed',
           'canonical_id': 'japanese_knotweed', 'quantity': 200, 'unit': 'mg',
           'unit_normalized': 'mg', 'raw_source_text': 'Japanese Knotweed 50% resveratrol',
           'mapped': True, 'scoreable_identity': True, 'bio_score': 10}
    row['delivers_markers'] = e._compute_delivers_markers(row)
    product = {'name': 'Knotweed source review', 'activeIngredients': [row],
               'ingredient_quality_data': {'ingredients': [row], 'ingredients_scorable': [row]}}
    result = e._collect_evidence_data(product, product['ingredient_quality_data'])
    marker_matches = [m for m in result['clinical_matches'] if m.get('marker_via_ingredient')]
    assert marker_matches and all(m.get('scoring_eligible') is False for m in marker_matches)
    product['evidence_data'] = result
    assert score_evidence(product, apply_primary_floor=True)['score'] == 0
    direct = dict(row, name='Resveratrol', standard_name='Resveratrol', canonical_id='resveratrol',
                  raw_source_text='Resveratrol', delivers_markers=[])
    control = dict(product, activeIngredients=[direct], ingredient_quality_data={
        'ingredients': [direct], 'ingredients_scorable': [direct]},
        evidence_data={'clinical_matches': [study]})
    assert score_evidence(control, apply_primary_floor=True)['score'] > 0

@pytest.mark.parametrize('held_first', [True, False])
def test_held_marker_cannot_consume_independent_eligible_source(monkeypatch, held_first):
    import clinical_applicability
    from scoring_v4.modules.generic_evidence import score_evidence
    e = SupplementEnricherV3()
    study = {'id': 'INGR_RESVERATROL', 'standard_name': 'Resveratrol',
             'aliases': ['resveratrol'], 'study_type': 'rct_single',
             'evidence_level': 'ingredient-human', 'effect_direction': 'positive_strong',
             'total_enrollment': 100, 'scoring_eligible': True,
             'references_structured': [{'pmid': '28661438'}]}
    study = _approved_marker_source(monkeypatch, study)
    e.databases['backed_clinical_studies'] = {'backed_clinical_studies': [study]}
    monkeypatch.setattr(clinical_applicability, 'filter_clinical_matches', lambda p, m: (m, []))
    rows = []
    for canonical, name in [('japanese_knotweed', 'Japanese Knotweed'), ('grape', 'Grape')]:
        row = {'canonical_id': canonical, 'name': name, 'standard_name': name,
               'raw_source_text': name + ' standardized to 50% resveratrol',
               'quantity': 200, 'unit': 'mg', 'unit_normalized': 'mg',
               'mapped': True, 'scoreable_identity': True, 'bio_score': 10}
        row['delivers_markers'] = e._compute_delivers_markers(row)
        rows.append(row)
    if not held_first:
        rows.reverse()
    product = {'name': 'Independent source control', 'activeIngredients': rows,
               'ingredient_quality_data': {'ingredients': rows, 'ingredients_scorable': rows}}
    product['evidence_data'] = e._collect_evidence_data(product, product['ingredient_quality_data'])
    eligible = [m for m in product['evidence_data']['clinical_matches']
                if m.get('scoring_eligible') is not False]
    assert len(eligible) == 1 and eligible[0]['marker_via_ingredient'] == 'grape'
    assert score_evidence(product, apply_primary_floor=True)['score'] > 0
