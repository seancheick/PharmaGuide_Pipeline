"""Raw source preparation ownership; never copy blend totals to constituents."""
import copy
import pytest
from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from scoring_v4.scored_artifact import build_scored_artifact
from scoring_input_contract import get_scoring_ingredients

@pytest.fixture(scope='module')
def pipeline():
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()

def raw_row(name, amount, unit='Gram(s)', **kwargs):
    return dict(name=name, category='complex carbohydrate', ingredientGroup='Maltodextrin',
                quantity=[dict(quantity=amount, unit=unit, servingSizeOrder=1)],
                forms=[], nestedRows=[], **kwargs)

def run(pipeline, row):
    normalizer, enricher = pipeline
    label = dict(id='preparation-regression', fullName='Prebiotic', brandName='Test',
                 ingredientRows=[row], otherIngredients=[], servingSizes=[dict(quantity=1, unit='Scoop', order=1)])
    clean = normalizer.normalize_product(copy.deepcopy(label))
    enriched, _ = enricher.enrich_product(clean)
    return clean, enriched, build_scored_artifact(enriched)

def test_preticx_parent_preparation_retains_declared_amount(pipeline):
    row = raw_row('PreticX', 1.4)
    row['forms'] = [dict(name='Xylo-oligosaccharides', category='complex carbohydrate', ingredientGroup='Xylooligosaccharides')]
    clean, enriched, artifact = run(pipeline, row)
    parent = next(x for x in clean['activeIngredients'] if x['name'] == 'PreticX')
    assert parent['canonical_id'] == 'prebiotics'
    assert parent['quantity'] == 1.4
    assert parent['unit'] == 'Gram(s)'
    assert not enriched['proprietary_data']['has_proprietary_blends']
    scored = next(x for x in get_scoring_ingredients(enriched).rows if x['name'] == 'PreticX')
    assert scored['quantity'] == 1.4
    assert artifact['quality_pillars_v4']['transparency']['score'] == 15

def test_declared_inulin_preparation_preserves_botanical_source(pipeline):
    row = raw_row('Chicory', 8100, 'mg')
    row.update(category='botanical', ingredientGroup='chicory')
    row['forms'] = [dict(name='Inulin', category='fiber', ingredientGroup='Inulin'),
                    dict(name='Cichorium intybus', category='botanical', ingredientGroup='chicory')]
    clean, enriched, artifact = run(pipeline, row)
    active = clean['activeIngredients'][0]
    assert active['canonical_id'] == 'inulin'
    assert active['raw_source_text'] == 'Chicory'
    assert active['quantity'] == 8100
    assert any(x['name'] == 'Cichorium intybus' for x in active['forms'])
    assert any(x['canonical_id'] == 'inulin' for x in get_scoring_ingredients(enriched).rows)
    assert artifact['quality_score_status'] == 'scored'
    matches = enriched['evidence_data']['clinical_matches']
    assert any(x.get('id') == 'INGR_INULIN' and x.get('effect_direction') == 'mixed' for x in matches)
    assert artifact['quality_pillars_v4']['evidence']['score'] == 7.3

@pytest.mark.parametrize('forms', [[], [dict(name='Inulin', category='fiber', percent=20)],
                                   [dict(name='Inulin', category='fiber'),dict(name='Pectin', category='fiber')]])
def test_source_or_partial_mixture_is_not_isolated_inulin(pipeline, forms):
    row = raw_row('Chicory', 1000, 'mg');row.update(category='botanical', ingredientGroup='chicory', forms=forms)
    clean, _, _ = run(pipeline, row)
    assert clean['activeIngredients'][0]['canonical_id'] != 'inulin'

@pytest.mark.parametrize('name', ['Cranberry extract','Vaccinium macrocarpon Fruit Extract','standardized cranberry'])
def test_unspecified_cranberry_alias_does_not_invent_25_percent(pipeline, name):
    row = raw_row(name, 225, 'mg');row.update(category='botanical',ingredientGroup='cranberry',notes='standardized to contain 1% proanthocyanidins')
    _, enriched, _ = run(pipeline,row)
    assert all('25%' not in str(x.get('matched_form')) for x in get_scoring_ingredients(enriched).rows)

def test_explicit_xos_child_dose_does_not_inherit_preticx_total(pipeline):
    row=raw_row('PreticX Prebiotic Fiber',1.4)
    row['nestedRows']=[raw_row('Xylo-oligosaccharides',1.0)]
    row['nestedRows'][0]['ingredientGroup']='Xylooligosaccharides'
    clean,enriched,_=run(pipeline,row)
    children=[x for x in clean['activeIngredients'] if x['name']=='Xylo-oligosaccharides']
    assert children and children[0]['quantity']==1.0
    assert all(x.get('quantity')!=1.4 for x in children)

def test_true_mixture_keeps_undisclosed_member_amounts(pipeline):
    row=raw_row('Proprietary Prebiotic Blend',1.4)
    row['nestedRows']=[dict(name='Inulin',category='fiber',ingredientGroup='Inulin',quantity=[],forms=[]),dict(name='Pectin',category='fiber',ingredientGroup='Pectin',quantity=[],forms=[])]
    clean,enriched,_=run(pipeline,row)
    assert enriched['proprietary_data']['has_proprietary_blends']
    assert all(x.get('quantity',0)==0 for x in clean['activeIngredients'] if x['name'] in {'Inulin','Pectin'})

@pytest.mark.parametrize('name', ['whole cranberry powder','cranberry juice concentrate'])
def test_cranberry_preparations_remain_distinct(pipeline,name):
    row=raw_row(name,225,'mg');row.update(category='botanical',ingredientGroup='cranberry')
    _,enriched,_=run(pipeline,row)
    rows=get_scoring_ingredients(enriched).rows
    assert rows and any(name==x.get('matched_form') for x in rows)

def test_explicit_25_percent_cranberry_notes_select_specific_form(pipeline):
    row=raw_row('Cranberry extract',225,'mg');row.update(category='botanical',ingredientGroup='cranberry',notes='standardized to contain 25% proanthocyanidins')
    _,enriched,_=run(pipeline,row)
    assert any(x.get('matched_form')=='cranberry extract (25% proanthocyanidins)' for x in get_scoring_ingredients(enriched).rows)


def test_reviewed_cranberry_unit_correction_is_exact_label_only(pipeline):
    n,_=pipeline
    row=raw_row("Cranberry Fruit Extract",1.2,"mg")
    for ident,unit in [("294036","Gram(s)"),("different-label","mg")]:
        corrected=n._apply_label_corrections([copy.deepcopy(row)],ident)
        assert corrected[0]["quantity"][0]["unit"]==unit
        assert corrected[0]["quantity"][0]["quantity"]==1.2


@pytest.mark.parametrize("form", [dict(name="Vitamin C",category="fiber"),dict(name="Inulin",category="fiber",prefix="contains"),dict(name="Inulin",category="fiber",notes="20%"),dict(name="Inulin",category="fiber",quantity=[dict(quantity=20,unit="mg")])])
def test_partial_or_mistyped_source_form_cannot_own_whole_source_mass(pipeline,form):
    row=raw_row("Chicory",1000,"mg");row.update(category="botanical",ingredientGroup="chicory",forms=[form])
    clean,_,_=run(pipeline,row)
    assert clean["activeIngredients"][0]["canonical_id"]=="chicory_root"


@pytest.mark.parametrize("field", ["name", "description"])
def test_partial_source_wording_cannot_become_whole_preparation(pipeline, field):
    row = raw_row("Chicory", 1000, "mg")
    row.update(category="botanical", ingredientGroup="chicory", forms=[dict(name="Inulin", category="fiber")])
    row[field] = "Chicory extract standardized to contain 20% inulin"
    clean, _, _ = run(pipeline, row)
    assert clean["activeIngredients"][0]["canonical_id"] != "inulin"


def test_reviewed_unit_correction_rejects_changed_quantity(pipeline):
    normalizer, _ = pipeline
    row = raw_row("Cranberry Fruit Extract", 2.4, "mg")
    corrected = normalizer._apply_label_corrections([copy.deepcopy(row)], "294036")
    assert corrected[0]["quantity"][0]["unit"] == "mg"


def test_value_and_unit_correction_only_rewrites_matching_serving_column(pipeline):
    normalizer, _ = pipeline
    row = raw_row("SelenoExcell ", 640, "mg")
    row["quantity"] += [dict(quantity=200, unit="mg", servingSizeOrder=2), dict(quantity=7, unit="mg", servingSizeOrder=3)]
    corrected = normalizer._apply_label_corrections([copy.deepcopy(row)], "302650")
    assert [(q["quantity"], q["unit"]) for q in corrected[0]["quantity"]] == [(200, "mcg"), (200, "mg"), (7, "mg")]


def test_unrelated_botanical_companion_is_not_preparation_source(pipeline):
    row = raw_row("Chicory", 1000, "mg")
    row.update(category="botanical", ingredientGroup="chicory", forms=[dict(name="Inulin", category="fiber"), dict(name="Senna", category="botanical")])
    clean, _, _ = run(pipeline, row)
    assert clean["activeIngredients"][0]["canonical_id"] != "inulin"


@pytest.mark.parametrize("qualification", [dict(percent=20), dict(notes="20% of row"), dict(quantity=[dict(quantity=20, unit="mg")])])
def test_partial_source_descriptor_cannot_establish_whole_preparation(pipeline, qualification):
    row = raw_row("Chicory", 1000, "mg")
    source = dict(name="Cichorium intybus", category="botanical", **qualification)
    row.update(category="botanical", ingredientGroup="chicory", forms=[dict(name="Inulin", category="fiber"), source])
    clean, _, _ = run(pipeline, row)
    assert clean["activeIngredients"][0]["canonical_id"] != "inulin"


@pytest.mark.parametrize("marker", ["Proanthocyanidin", "Proanthocyanidins"])
def test_declared_cranberry_marker_is_not_an_unknown_or_25_percent_form(pipeline, marker):
    row = raw_row("Cranberry fruit extract", 25, "mg")
    row.update(category="botanical", ingredientGroup="cranberry", forms=[dict(name=marker, percent=1, category="non-nutrient/non-botanical", ingredientGroup="Proanthocyanidins (unspecified)")])
    _, enriched, artifact = run(pipeline, row)
    assert artifact["quality_score_status"] == "scored"
    rows = get_scoring_ingredients(enriched).rows
    assert not any("25%" in str(x.get("matched_form")) for x in rows)


def test_xos_identity_notes_do_not_claim_universal_low_dose_efficacy():
    """Identity copy must preserve trial/preparation limits, not invent a benchmark."""
    import json
    from pathlib import Path
    data = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'ingredient_quality_map.json').read_text())
    notes = data['prebiotics']['forms']['xylooligosaccharides (XOS)']['notes']
    assert 'Effective at lower doses compared to other prebiotics.' not in notes
    assert 'PMID 24513849' in notes and 'PMID 26300782' in notes
    assert '70%' in notes and '2015' in notes
    assert 'not establish' in notes and 'PreticX' in notes
    assert 'universal minimum effective dose' in notes


def test_gos_notes_bound_bimuno_preparation_and_outcomes():
    """Generic GOS must not inherit an unconditional branded efficacy claim."""
    import json
    from pathlib import Path
    data = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'ingredient_quality_map.json').read_text())
    notes = data['prebiotics']['forms']['galactooligosaccharides (GOS)']['notes']
    assert 'Well-tolerated and effective.' not in notes
    assert 'PMID 30109908' in notes and 'PMID 26218845' in notes
    assert '1.37 g' in notes and '48%' in notes
    assert 'no significant' in notes and 'not a universal' in notes


def test_phage_notes_do_not_transfer_combination_or_surrogate_benefits():
    """No pathogenic-infection or phage-alone efficacy from microbial changes."""
    import json
    from pathlib import Path
    data = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'ingredient_quality_map.json').read_text())
    notes = data['bacteriophages']['forms']['bacteriophage blend']['notes']
    assert 'without disturbing beneficial flora' not in notes
    assert 'Targets specific gut pathogens' not in notes
    assert 'PMID 30897686' in notes and 'PMID 32824480' in notes
    assert 'no phage-only arm' in notes and 'no significant between-group' in notes
    assert 'same trial' in notes and 'not active phage mass' in notes


def test_prebiotic_copy_preserves_active_fiber_basis_and_specific_response():
    from pathlib import Path
    import json
    iqm = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'ingredient_quality_map.json').read_text())
    assert '3 g/day of beta-glucan soluble fiber' in iqm['oat_bran']['description']
    assert 'FDA-approved heart health claim at 3g/day' not in iqm['oat_bran']['description']
    fos = iqm['prebiotics']['forms']['fructooligosaccharides (FOS)']
    assert 'PMID 16569219' in fos['notes']
    assert 'Lactobacillus counts did not significantly change' in fos['notes']
    assert 'preferentially feeding Bifidobacterium and Lactobacillus' not in fos['notes']
