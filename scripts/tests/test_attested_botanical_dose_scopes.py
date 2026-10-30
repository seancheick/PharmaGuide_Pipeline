"""Sean's dated attestation preserves each prior-approved physical preparation."""
import json
from copy import deepcopy
from pathlib import Path
import pytest

GROUPS={
 'panax_root_extract_unspecified':['312543','312544','312545','312546','312547','327872','332892'],
 'panax_root_extract_3pct':['1628','1630','18276','63928','74798','74799'],
 'panax_root_extract_2pct':['239074'], 'panax_root_extract_4to1':['3752'],
 'panax_root_extract_7pct':['259593'],'panax_root_extract_1pct':['269748'],
 'panax_root_extract_12pct':['278018'],
 'american_ginseng_rhizome_extract_unspecified':['310646','310647','310648','310649'],
 'american_ginseng_rhizome_extract_4to1':['329914'],
 'american_ginseng_leaf_extract':['312858'],'panax_mixed_stem_root_extract':['239741'],
 'red_panax_leaf_stem_extract':['241914'],
 'black_maca_root_powder':['329925','329926','329927','329928'],
 'red_maca_root_powder':['330068','330069'],
}
CASES=[(owner,pid) for owner,ids in GROUPS.items() for pid in ids]

@pytest.fixture(scope='module')
def products():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    n,e=EnhancedDSLDNormalizer(),SupplementEnricherV3()
    return {pid:e.enrich_product(n.normalize_product(json.loads((Path(__file__).parent/'fixtures'/f'raw_attested_dose_{pid}.json').read_text())))[0] for _,pid in CASES}

def pair(product,pid):
    from scoring_input_contract import _route_scoring_rows
    from dose_assessment import _source_dose_row
    rows=[r for r in _route_scoring_rows(product) if r.get('canonical_id') in {'ginseng','maca'}]
    row=next(r for r in rows if 'panax ginseng' in str(r.get('raw_source_text')).lower()) if pid=='239074' else rows[0]
    return row,_source_dose_row(product,row)

@pytest.mark.parametrize('owner,pid',CASES)
def test_attested_exact_original_preparation_completes_only_dose(products,owner,pid):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    from evidence_resolver import _load_literature_evidence
    from dose_assessment import _dose_source_preparation_matches,verified_reference_citations
    from clinical_applicability import assess_clinical_source_review
    p=products[pid];row,source=pair(p,pid);before=deepcopy(p)
    record=_load_literature_evidence()[owner]
    assert _dose_source_preparation_matches(p,row,record)
    assert _botanical_benchmark(row,product=p)=='absent'
    assert verified_reference_citations(record)
    assert not assess_clinical_source_review(record)['is_complete']
    assert record['reference_semantics']['review_date']=='2026-10-29'
    assert "original review date was not supplied" in record['notes']
    assert source['quantity']==row['quantity']
    assert p==before

@pytest.mark.parametrize('owner,pid',CASES)
@pytest.mark.parametrize('change',['missing_source','wrong_part','foreign_row','missing_scope'])
def test_attested_scope_cannot_borrow_physical_source_facts(products,owner,pid,change):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    p=deepcopy(products[pid]);row,source=pair(p,pid)
    if change=='missing_source': p['activeIngredients']=[]
    elif change=='foreign_row': row['raw_source_path']='ingredientRows[998]'
    elif change=='wrong_part':
        source['plantPart']='flower';source['notes']='PlantPart: flower';source['forms']=[];source['raw_taxonomy']['forms']=[]
    else:
        source['notes']='';source['plantPart']=None;source['genus']=None;source['species']=None;source['raw_taxonomy']['forms']=[]
    assert _botanical_benchmark(row,product=p)=='unresolved'

@pytest.mark.parametrize('owner,pid',CASES)
def test_other_attested_material_groups_are_not_equated(products,owner,pid):
    from dose_assessment import _dose_source_preparation_matches
    from evidence_resolver import _load_literature_evidence
    p=products[pid];row,_=pair(p,pid);records=_load_literature_evidence()
    for other in GROUPS:
        if other!=owner:
            assert not _dose_source_preparation_matches(p,row,records[other]),(owner,other,pid)

@pytest.mark.parametrize('owner,pid',CASES)
def test_contradictory_typed_part_cannot_borrow_retained_source_notes(products,owner,pid):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    p=deepcopy(products[pid]);row,source=pair(p,pid);source['plantPart']='flower'
    assert _botanical_benchmark(row,product=p)=='unresolved'

@pytest.mark.parametrize('pid',['312543','310646'])
@pytest.mark.parametrize('percent',['8%','15%'])
def test_unspecified_assay_scope_rejects_any_new_declared_assay(products,pid,percent):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    p=deepcopy(products[pid]);row,source=pair(p,pid)
    source['notes']=(source.get('notes') or '')+'; standardized to '+percent+' ginsenosides'
    assert _botanical_benchmark(row,product=p)=='unresolved'

@pytest.mark.parametrize('pid',['312543','310646'])
def test_explicitly_negated_assay_does_not_claim_standardization(products,pid):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    p=deepcopy(products[pid]);row,source=pair(p,pid)
    source['notes']=(source.get('notes') or '')+'; not standardized to 8% ginsenosides'
    assert _botanical_benchmark(row,product=p)=='absent'

@pytest.mark.parametrize('pid',['329925','330068'])
@pytest.mark.parametrize('processing',['gelatinized','spray-dried'])
def test_colored_powder_scope_does_not_transfer_to_other_processing(products,pid,processing):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    p=deepcopy(products[pid]);row,source=pair(p,pid)
    source['notes']+='; '+processing
    assert _botanical_benchmark(row,product=p)=='unresolved'

@pytest.mark.parametrize('pid',['312543','310646'])
@pytest.mark.parametrize('ratio',['8:1','20:1'])
def test_undeclared_der_scope_rejects_any_new_original_ratio(products,pid,ratio):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    p=deepcopy(products[pid]);row,source=pair(p,pid)
    source['notes']=(source.get('notes') or '')+'; DER '+ratio
    assert _botanical_benchmark(row,product=p)=='unresolved'

@pytest.mark.parametrize('pid',['312543','310646'])
def test_negated_ratio_does_not_establish_extraction_ratio(products,pid):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    p=deepcopy(products[pid]);row,source=pair(p,pid)
    source['notes']=(source.get('notes') or '')+'; not a 20:1 extract'
    assert _botanical_benchmark(row,product=p)=='absent'
