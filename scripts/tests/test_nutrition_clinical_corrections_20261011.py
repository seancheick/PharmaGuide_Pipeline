import json
from pathlib import Path
import pytest
from rda_ul_calculator import RDAULCalculator

DATA=Path(__file__).resolve().parents[1]/'data'

@pytest.mark.parametrize('sex',['male','female'])
@pytest.mark.parametrize('age',['19-30','31-50','51-70','71+'])
def test_adult_vanadium_established_ul_is_enforced(age,sex):
    calc=RDAULCalculator()
    above=calc.compute_nutrient_adequacy('Vanadium',1801,'mcg',age,sex)
    boundary=calc.compute_nutrient_adequacy('Vanadium',1800,'mcg',age,sex)
    assert above.ul == 1800
    assert above.ul_status == 'established'
    assert above.over_ul
    assert not boundary.over_ul

@pytest.mark.parametrize('age,sex',[('14-18','male'),('14-18','female'),('19-30','pregnancy'),('19-30','lactation')])
def test_vanadium_unknown_lifestage_ul_is_not_adult_limit(age,sex):
    result=RDAULCalculator().compute_nutrient_adequacy('Vanadium',1801,'mcg',age,sex)
    assert result.ul is None
    assert result.ul_status == 'not_determined'
    assert any('food' in warning and 'No UL' in warning for warning in result.warnings)
    assert not result.over_ul

def test_folic_acid_note_distinguishes_physiology_from_label_conversion():
    entry=json.loads((DATA/'unit_conversions.json').read_text())['vitamin_conversions']['folate_folic_acid']
    assert '0.6 mcg' in entry['notes']
    assert '0.5 mcg' in entry['notes']
    assert entry['conversions']['mcg_to_mcg_dfe'] == 1.7

@pytest.mark.parametrize('nutrient',['Chromium','Manganese','Biotin','Choline','Vitamin K','Pantothenic Acid','Potassium','Sodium','Chloride','Fluoride','Alpha-Linolenic Acid'])
def test_formal_adequate_intakes_are_not_mislabelled_rdas(nutrient):
    result=RDAULCalculator().compute_nutrient_adequacy(nutrient,1,'mg')
    assert result.rda_ai_source == 'ai'


def test_non_dri_dose_anchor_does_not_claim_an_rda():
    result=RDAULCalculator().compute_nutrient_adequacy('Coenzyme Q10',100,'mg')
    assert result.rda_ai_source == 'unknown'
    assert not any('of RDA' in note for note in result.notes)
    assert result.rda_ai == 30


def test_formal_rda_control_remains_rda():
    result=RDAULCalculator().compute_nutrient_adequacy('Zinc',11,'mg')
    assert result.rda_ai_source == 'rda'
    assert result.pct_rda == 100


@pytest.mark.parametrize('nutrient,expected', [('Zinc','established'), ('Vitamin K','not_determined')])
def test_other_native_ul_status_controls_remain_unchanged(nutrient,expected):
    result=RDAULCalculator().compute_nutrient_adequacy(nutrient,1,'mg','19-30','male')
    assert result.ul_status == expected
    assert not any('vanadium' in warning.lower() for warning in result.warnings)


@pytest.mark.parametrize('nutrient,amount,reference',[('Vitamin E',15,15),('Hyaluronic Acid',120,120)])
def test_unqualified_optimal_ranges_are_not_presented_as_clinical_recommendations(nutrient,amount,reference):
    result=RDAULCalculator().compute_nutrient_adequacy(nutrient,amount,'mg')
    assert result.optimal_min is None
    assert result.optimal_max is None
    assert result.rda_ai == reference
    assert result.pct_rda == 100


def test_hyaluronate_trial_dose_is_not_claimed_as_a_universal_minimum():
    rows=json.loads((DATA/'rda_optimal_uls.json').read_text())['nutrient_recommendations']
    ha=next(row for row in rows if row['id']=='hyaluronic_acid')
    assert 'lower bound of the clinically effective dose' not in ha['notes']
    assert '60 and 120 mg/day' in ha['notes']
    assert '1.8 MDa' in ha['notes']
    vitamin_e=next(row for row in rows if row['id']=='vitamin_e')
    assert 'Smokers may need higher intake' not in vitamin_e['special_considerations']
