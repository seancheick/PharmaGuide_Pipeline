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
