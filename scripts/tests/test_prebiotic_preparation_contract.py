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
