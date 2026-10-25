"""Prepared serving totals cannot inherit powder-only beta-carotene scope."""
import pytest
from enrich_supplements_v3 import SupplementEnricherV3

@pytest.fixture(scope='module')
def enricher():
    return SupplementEnricherV3()

def _row(quantity, form='Natural Beta-Carotene', variants=True):
    return {'name':'Vitamin A','standardName':'Vitamin A','canonical_id':'vitamin_a','canonical_source_db':'ingredient_quality_map','quantity':quantity,'unit':'mcg RAE','dailyValue':380,'forms':[{'name':form}], 'quantityVariants': ([{'quantity':3000,'unit':'mcg RAE','serving_size_order':1,'serving_size_quantity':360,'serving_size_unit':'Gram(s)'},{'quantity':3417,'unit':'mcg RAE','serving_size_order':1,'serving_size_quantity':360,'serving_size_unit':'Gram(s)'}] if variants else [])}

def _assess(e,row,directions='Mix four scoops with water or milk.'):
    return e._collect_rda_ul_data({'activeIngredients':[row],'inactiveIngredients':[],'statements':[{'type':'Suggested/Recommended/Usage/Directions','notes':directions}]},min_servings_per_day=1,max_servings_per_day=2)

def test_prepared_larger_total_does_not_clear_unknown_contribution_as_beta(enricher):
    out=_assess(enricher,_row(3417));row=out['analyzed_ingredients'][0]
    assert row['converted_quantity']==3417
    assert row['ul_assessment_status']=='indeterminate'
    assert row['skip_ul_reason']=='mixed_vitamin_a_preformed_fraction_unknown'
    assert row['ul_for_default_profile'] is None
    assert not out['has_over_ul'] and not out['safety_flags']
    assert row['warnings']

@pytest.mark.parametrize('quantity,variants,directions',[(3417,False,'Mix with water or milk.'),(3417,True,'Swallow with water.')])
def test_pure_beta_and_unrelated_variant_contexts_keep_no_ul(enricher,quantity,variants,directions):
    row=_assess(enricher,_row(quantity,variants=variants),directions)['analyzed_ingredients'][0]
    assert row['skip_ul_reason']=='beta_carotene_no_established_ul'
    assert row['ul_assessment_status']=='not_applicable'

def test_retinyl_variant_still_gets_actual_preformed_ul(enricher):
    out=_assess(enricher,_row(3417,form='Retinyl Palmitate'))
    assert out['has_over_ul']


def test_different_serving_quantity_is_not_a_preparation_scope_mismatch(enricher):
    row=_row(3417)
    row['quantityVariants'][0]['serving_size_quantity']=180
    out=_assess(enricher,row)
    assert out['analyzed_ingredients'][0]['skip_ul_reason']=='beta_carotene_no_established_ul'


def test_shared_serving_order_with_omitted_quantity_keeps_prepared_scope_unknown(enricher):
    row=_row(3417)
    for variant in row['quantityVariants']:
        variant.pop('serving_size_quantity')
    assert _assess(enricher,row)['analyzed_ingredients'][0]['ul_assessment_status']=='indeterminate'


def test_powder_total_does_not_prove_all_activity_is_added_beta_carotene(enricher):
    # Batch9 exact Bulk panels identify an added source, not every source's
    # share of the powder activity. Selecting water must not invent zero retinol.
    row = _assess(enricher, _row(3000))['analyzed_ingredients'][0]
    assert row['converted_quantity'] == 3000
    assert row['skip_ul_reason'] == 'mixed_vitamin_a_preformed_fraction_unknown'
    assert row['ul_assessment_status'] == 'indeterminate'
