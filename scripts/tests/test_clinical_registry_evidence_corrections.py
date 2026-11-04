"""Clinical source identity, integrity and applicability regressions."""
import json
from pathlib import Path
import pytest

DATA = Path(__file__).resolve().parents[1] / 'data'

def records(file, key):
    return {r['id']: r for r in json.loads((DATA / file).read_text())[key]}

def backed():
    return records('backed_clinical_studies.json', 'backed_clinical_studies')

def test_retracted_lutein_source_cannot_be_described_as_affirmative_evidence():
    row = backed()['INGR_LUTEIN']
    ref = next(x for x in row['references_structured'] if x['pmid'] == '41573009')
    assert ref['retracted'] is True
    assert '42211211' in json.dumps(row)
    assert row['study_type'] == row['evidence_level'] == 'reference'
    assert row['total_enrollment'] == 48  # Retained combination-study sample, not isolated-lutein evidence.
    assert all(c['scoring_eligible'] is False and c['review_status'] == 'rejected_source'
               for c in row['study_contexts'])
    assert not {'cardiovascular', 'digestive_health'} & set(row['endpoint_relevance_tags'])
    assert '28661438' in json.dumps(row)

def test_branded_evidence_does_not_borrow_wrong_material_studies():
    rows = backed()
    assert '31221944' not in {r['pmid'] for r in rows['BRAND_ASTAREAL']['references_structured']}
    assert 'later follow-up' not in rows['BRAND_THERACURMIN']['notable_studies']
    assert 'mosaicplasty' in rows['BRAND_THERACURMIN']['notable_studies']
    assert 'general curcumin review' in rows['BRAND_LIFE_EXTENSION_SUPER_BIOCURCUMIN']['notable_studies']
    assert 'not the finished Life Extension product' in rows['BRAND_LIFE_EXTENSION_SUPER_BIOCURCUMIN']['notable_studies']
    assert rows['BRAND_WELLMUNE']['study_type'] == 'reference'
    assert 'Yestimun' in rows['BRAND_WELLMUNE']['notes']
    assert rows['BRAND_SEAKELP']['study_type'] == 'reference'

@pytest.mark.parametrize('id,expected', [('BRAND_MITOQ',20),('BRAND_COGNIZIN',100),('BRAND_CURCUMIN_C3',45),('BRAND_SENSORIL',None),('BRAND_BCM95',None),('BRAND_CIRCADIN',None),('BRAND_AFFRON',None)])
def test_enrollment_has_explicit_cited_cohort_basis(id,expected):
    assert backed()[id]['total_enrollment'] == expected

def test_strain_35624_keeps_historical_alias_and_corrects_canonical_taxonomy():
    r = records('clinically_relevant_strains.json','clinically_relevant_strains')['STRAIN_INFANTIS_35624']
    assert r['standard_name'] == 'Bifidobacterium longum subsp. longum 35624'
    assert any('infantis' in x.lower() for x in r['aliases'])

def literature():
    return {r['canonical_id']:r for r in json.loads((DATA/'literature_evidence_records.json').read_text())['literature_evidence_records']}

def test_literature_does_not_promote_animal_or_narrative_sources_to_human_trials():
    r=literature()['lycopene']
    assert r['scoring_eligible'] is False
    assert all(s.get('scoring_eligible') is False for s in r['qualifying_human_studies'])
    assert r['studied_dose_exposure']['values'] == []

def test_areds2_primary_null_and_subgroup_are_distinct():
    r=literature()['zeaxanthin']
    assert r['qualifying_human_studies'][0]['effect_direction'] == 'null'
    assert 'subgroup' in r['qualifying_human_studies'][1]['primary_endpoint'].lower()
    assert r['qualifying_human_studies'][1]['scoring_eligible'] is False

def test_literature_population_dose_and_enrollment_match_cited_trials():
    rows=literature()
    assert next(s for s in rows['l_leucine']['qualifying_human_studies'] if s['pmid']=='24284442')['sample_size']==40
    assert 'universal' in rows['l_leucine']['applicability_decision']
    s=rows['tmg_betaine']['qualifying_human_studies'][0]
    assert s['dose']=='>= 4 g/day'
    assert s['duration']=='6–24 weeks'
    assert 4000 in rows['tmg_betaine']['studied_dose_exposure']['values']


def test_american_ginseng_source_is_an_acute_glucose_challenge_not_a_daily_minimum():
    row = literature()['american_ginseng']
    study, = row['qualifying_human_studies']
    assert study['pmid'] == '10761967'
    assert study['sample_size'] == 19
    assert row['studied_dose_exposure'] == {
        'values': [3000], 'unit': 'mg', 'basis': 'acute_challenge',
    }
    assert 'glucose challenge' in study['dose']
    assert 'daily minimum' in row['applicability_decision']
    assert 'standardized' not in row['material_form'].lower()


def test_touchi_source_retains_tea_preparation_three_month_course_and_before_meal_use():
    row = literature()['touchi_extract']
    study, = row['qualifying_human_studies']
    assert study['pmid'] == '11481402'
    assert study['sample_size'] == 36
    assert study['duration'] == '3 months'
    assert 'before each of three meals' in study['dose']
    assert 'Houji-tea' in row['material_form']
    assert 'fasting' in study['primary_endpoint']
    assert 'minimum' in row['applicability_decision']


def test_mct_source_reports_36_participants_and_a_discrete_12_g_regimen():
    row = literature()['mct_oil']
    study = next(study for study in row['qualifying_human_studies']
                 if study['pmid'] == '41443401')
    assert study['sample_size'] == 36
    assert study['dose'] == '12 g MCT'
    assert row['studied_dose_exposure']['values'] == [12000]
    assert 'working memory' in study['primary_endpoint']
    assert 'minimum' in row['applicability_decision']


def test_phosphatidic_acid_source_keeps_parametric_null_and_magnitude_inference_distinct():
    row = literature()['phosphatidic_acid']
    study, = row['qualifying_human_studies']
    assert study['pmid'] == '23035701'
    assert 'no significant between-group differences' in study['outcome']
    assert 'magnitude-based' in study['outcome']
    assert 'statistically significant increases' not in study['outcome']
    assert 'minimum' in row['applicability_decision']
    assert 'without investigator supervision' in row['population_context']
    assert 'weekly training-log review and feedback' in row['population_context']
    assert 'supervised progressive training' not in row['population_context']


def test_lysine_review_does_not_invent_a_positive_one_gram_threshold():
    row = literature()['l_lysine']
    study = next(study for study in row['qualifying_human_studies']
                 if study['pmid'] == '26252373')
    assert study['effect_direction'] == 'null'
    assert 'no evidence of efficacy for lysine' in study['primary_endpoint']
    assert 'no established 1 g/day threshold' in row['applicability_decision']

def strains():
    return records('clinically_relevant_strains.json','clinically_relevant_strains')

def context(rows, rid, cid):
    return next(c for c in rows[rid]['study_contexts'] if c['context_id']==cid)

def test_probiotic_source_units_and_randomized_population_are_honest():
    rows=strains()
    c=context(rows,'STRAIN_RHAMNOSUS_R0011','r0011_chronic_rhinosinusitis_19201289')
    assert c['dose']['values']==[]
    assert 'active cells' in c['dose']['duration_note']
    c=context(rows,'STRAIN_INFANTIS_BI26','bi26_underweight_infants_growth_42137872')
    assert c['dose']['dose_basis']=='nominal_assigned_arm'
    c=context(rows,'STRAIN_BREVE_M16V','m16v_synbiotic_formula_csection_39915586')
    assert c['sample_size']==224
    assert '54.8%' in c['population']['description']
    assert 'intact' in ' '.join(c['limitations'])

def test_probiotic_outcomes_do_not_borrow_combination_or_erase_secondary_signals():
    rows=strains()
    c=context(rows,'STRAIN_BREVE_M16V','m16v_neonatal_jaundice_adjunct_41994268')
    assert all(o['direction']!='positive' for o in c['outcomes'] if o['name'] in {'hospital_stay_duration','transcutaneous_bilirubin_decline'})
    c=context(rows,'STRAIN_LONGUM_1714','b1714_low_mood_42060410')
    assert 'vitality' in ' '.join(c['limitations'])
    c=context(rows,'STRAIN_ACIDOPHILUS_LAFTI_L10','lafti_l10_elite_athletes_urti_27363733')
    assert any(o['name']=='cd4_cd8_ratio' and o['direction']=='positive' and o['kind']=='surrogate' for o in c['outcomes'])

def test_probiotic_review_retains_combination_research_without_isolated_credit():
    for id in ['STRAIN_JENSENII_LBV116','STRAIN_GASSERI_LBV150N','STRAIN_CRISPATUS_LBV88','STRAIN_CASEI_HA108']:
        r=strains()[id]
        assert r['evidence_level']=='none'
        assert 'combination' in r['literature_review']['note'].lower()


def test_bifidum_summary_cannot_transfer_strain_viability_or_combination_results():
    from evidence_resolver import clinical_record_sources_eligible
    row = backed()['INGR_BIFIDOBACTERIUM_BIFIDUM']
    assert not clinical_record_sources_eligible(row)
    assert row['study_type'] == 'reference'
    assert 'effect_direction' not in row
    assert 'published_studies_count' not in row
    refs = {str(r.get('pmid')): r for r in row['references_structured']}
    assert {'21418261', '32277872', '32300799', '31342226'} <= refs.keys()
    assert 'non-viable' in refs['32277872']['note']
    assert 'combination' in refs['32300799']['note']
    assert 'L. plantarum CCFM8610' in refs['31342226']['note']
    assert 'not a species-specific participant total' in row['notes']
    assert 'not a B. bifidum-only RCT' in row['notable_studies']


def test_ginger_citations_keep_pregnancy_and_chemotherapy_outcomes_distinct():
    row = backed()['INGR_GINGER']
    assert row['primary_outcome'] == 'Digestive Health'
    assert row['endpoint_relevance_tags'] == ['digestive_health']
    assert 'concomitant 5-HT3' in row['notable_studies']
    assert 'PMID 21818642 is a randomized trial' in row['notable_studies']
    assert 'vitamin B6' in row['notable_studies']
    assert 'do not support' in row['notable_studies']


def test_turmeric_citations_distinguish_oa_symptoms_from_biomarkers():
    row = backed()['INGR_TURMERIC']
    assert row['primary_outcome'] == 'Joint & Bone Health'
    assert row['endpoint_relevance_tags'] == ['joint_pain']
    assert 'PMID 38576215 is an umbrella review' in row['notable_studies']
    assert 'PMID 40615851 reviews inflammatory biomarkers' in row['notable_studies']
    assert 'no significant effects' in row['notable_studies']
    assert 'equivalence between generic turmeric powder' in row['notes']


def test_glycine_rat_mechanism_is_not_human_clinical_efficacy():
    from evidence_resolver import clinical_record_sources_eligible
    row = backed()['INGR_GLYCINE']
    refs = {r['pmid']: r for r in row['references_structured']}
    assert refs['25533534']['scoring_eligible'] is False
    assert {'22529837', '25533534', '37851316'} <= refs.keys()
    assert 'rats' in row['notable_studies']
    assert row['endpoint_relevance_tags'] == ['sleep']
    assert not clinical_record_sources_eligible(row)


def test_same_conflicting_depression_reviews_do_not_establish_joint_or_adjunct_credit():
    from evidence_resolver import clinical_record_sources_eligible
    row = backed()['INGR_SAME']
    assert not clinical_record_sources_eligible(row)
    assert row['health_goals_supported'] == []
    assert 'primary_outcome' not in row  # no misleading legacy display category
    assert 'neither establishes a stronger adjunctive benefit' in row['notes']
    assert {r['pmid'] for r in row['references_structured']} == {'38423354', '38199136'}
    assert row['effect_direction'] == 'positive_strong'  # retained historical grade, explicitly held


def test_niacin_keeps_wrong_topic_identifiers_as_excluded_history_not_clinical_depth():
    row = backed()['INGR_VITAMIN_B3_NIACIN']
    assert row['primary_outcome'] == 'Cardiovascular/Heart Health'
    assert row['endpoint_relevance_tags'] == ['cardiovascular']
    assert all(k not in row for k in ('total_enrollment', 'published_studies_count', 'registry_completed_trials_count'))
    assert all(n in row['notable_studies'] for n in ('NCT01411436', 'NCT00619541', 'NCT02961829'))
    assert 'Excluded from niacin lipid-efficacy support' in row['notable_studies']
    refs = {r['pmid']:r for r in row['references_structured']}
    assert set(refs) == {'11498460','15642562','9732910','25141367'}
    assert 'not standalone niacin efficacy' in refs['25141367']['note']
