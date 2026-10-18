"""Source-supported delivery and therapeutic-dose corrections, with unknowns retained."""
import json
from pathlib import Path
import pytest
from scoring_v4.modules import collagen_profile, botanical_profile

DATA=Path(__file__).resolve().parents[1]/'data'
def rows(file,key):
    return {r['id']:r for r in json.loads((DATA/file).read_text())[key]}

@pytest.mark.parametrize('id',['l_theanine','valerian_root','biocell_collagen','phosphatidylserine','reishi_mushroom_extract','saffron','passionflower','sage'])
def test_trial_exposures_are_not_unverified_safety_ceilings(id):
    row=rows('rda_therapeutic_dosing.json','therapeutic_dosing')[id]
    assert row['upper_limit'] is None
    assert 'not established' in row['upper_limit_notes'].lower()

def test_biocell_daily_dose_counts_both_administrations():
    row=rows('rda_therapeutic_dosing.json','therapeutic_dosing')['biocell_collagen']
    assert row['typical_dosing_range'] == '1000-2000'
    assert row['reference_semantics']['curve'] == 'completed_no_benchmark_neutral'
    assert '500 mg validated for skin' not in row['upper_limit_notes']

@pytest.mark.parametrize('id',['curcumin_absorption','magnesium_nervous_system','joint_inflammation','eye_health','bone_health','thyroid_support','urinary_tract_health','kidney_health_support','omega3_niacin_lipid'])
def test_broad_match_groups_do_not_claim_an_existing_scoring_bonus_or_proven_combination(id):
    row=rows('synergy_cluster.json','synergy_clusters')[id]
    assert 'synergy bonus' not in row['note'].lower()
    assert row['evidence_tier']==4
    assert 'not establish' in row['evidence_note'].lower() or 'not demonstrated' in row['evidence_note'].lower()

def test_synergy_sources_represent_actual_design_and_result():
    r=rows('synergy_cluster.json','synergy_clusters')
    assert 'observational' in r['magnesium_nervous_system']['sources'][0]['label'].lower()
    assert 'primary' in r['eye_health']['evidence_note'].lower()
    assert 'Alzheimer' in r['kidney_health_support']['evidence_note']
    assert 'not a systematic review' in r['omega3_niacin_lipid']['evidence_note']

def test_study_preparation_does_not_become_generic_botanical_dose():
    r=rows('rda_therapeutic_dosing.json','therapeutic_dosing')
    for id in ['valerian_root','phosphatidylserine','reishi_mushroom_extract','passionflower','sage','saffron']:
        assert r[id]['typical_dosing_range'] == ''
        assert r[id]['reference_semantics']['curve'] == 'completed_no_benchmark_neutral'
    assert r['l_theanine']['typical_dosing_range']=='100.6'
    assert 'Suntheanine' in r['l_theanine']['upper_limit_notes']
