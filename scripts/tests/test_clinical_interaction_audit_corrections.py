"""Source-supported safety regressions from the October clinical audit."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'data'

def _rules():
    return {r['id']: r for r in json.loads((DATA / 'ingredient_interaction_rules.json').read_text())['interaction_rules']}

def test_5htp_ssri_gate_accepts_actual_medication_class():
    rule = _rules()['RULE_IQM_5HTP_SEROTONIN']
    ssri = next(r for r in rule['drug_class_rules'] if r['drug_class_id'] == 'antidepressants_ssri_snri')
    classes = json.loads((DATA / 'drug_classes.json').read_text())['classes']
    assert 'class:ssris' in classes
    assert 'ssris' in ssri['profile_gate']['requires']['drug_classes_any']
    assert 'antidepressants_ssri_snri' in ssri['profile_gate']['requires']['drug_classes_any']
    assert ssri['severity'] == 'contraindicated'

def test_pea_does_not_direct_unsupervised_maoi_discontinuation():
    row = _rules()['RULE_IQM_PHENYLETHYLAMINE']['drug_class_rules'][0]
    assert 'Discontinue MAOI' not in row['action']
    assert 'prescrib' in row['action'].lower()
    assert 'Do not combine' in row['action']
    assert row['severity'] == 'contraindicated'

# Studied efficacy doses do not establish a safe-below interaction boundary.
FLOOR_RULES = (
    'RULE_IQM_ALPHA_LIPOIC_ACID_DIABETES', 'RULE_IQM_BERBERINE_DIABETES',
    'RULE_IQM_BITTER_MELON_DIABETES', 'RULE_IQM_CINNAMON_GLUCOSE',
    'RULE_IQM_FENUGREEK_DIABETES', 'RULE_IQM_GLUCOMANNAN_DIABETES',
    'RULE_IQM_GINGER_BLEEDING', 'RULE_IQM_GREEN_TEA_HYPERTENSION',
    'RULE_IQM_HAWTHORN_HYPERTENSION', 'RULE_IQM_L_ARGININE_HYPERTENSION',
    'RULE_IQM_PSYLLIUM_DIABETES', 'RULE_INGREDIENT_ST_JOHNS_WORT',
    'RULE_INGREDIENT_GLUCOSAMINE', 'RULE_IQM_TRIBULUS_METABOLIC',
    'RULE_IQM_L_THEANINE_ANTIHYPERTENSIVES',
)

def test_source_studied_doses_do_not_suppress_precautionary_interactions():
    for ident in FLOOR_RULES:
        rule = _rules()[ident]
        for row in rule.get('condition_rules', []) + rule.get('drug_class_rules', []):
            if row.get('direction') == 'harmful':
                assert row.get('min_effective_dose') is None, (ident, row)
                # Null numeric floors preserve the existing severity and profile scope.

def test_sjw_serotonergic_gate_accepts_actual_ssri_class():
    rule = _rules()['RULE_INGREDIENT_ST_JOHNS_WORT']
    ssri = next(r for r in rule['drug_class_rules'] if r['drug_class_id'] == 'antidepressants_ssri_snri')
    assert 'ssris' in ssri['profile_gate']['requires']['drug_classes_any']
    assert ssri['severity'] == 'contraindicated'

CURATED_FLOOR_IDS = (
    'DSI_DM_CINNAMON', 'DSI_WAR_GARLIC', 'DSI_OC_SOY', 'DSI_WAR_TURMERIC',
    'DSI_WAR_GINGER', 'DSI_ANTIHYP_COQ10', 'DSI_METFORMIN_ALA',
    'DSI_DM_BITTERMELON', 'DSI_DM_FENUGREEK', 'DSI_NSAID_GARLIC',
    'DSI_SEDATIVES_VALERIAN', 'DSI_SEDATIVES_PASSIONFLOWER',
    'DSI_ANTIHYP_MAGNESIUM', 'DSI_ANTIHYP_ASHWAGANDHA', 'DSI_ANTICOAG_TURMERIC',
)
def _curated():
    return {r['id']: r for r in json.loads((DATA / 'curated_interactions' / 'curated_interactions_v1.json').read_text())['interactions']}

def test_curated_study_doses_do_not_disable_precaution_below_a_cutoff():
    for ident in CURATED_FLOOR_IDS:
        row = _curated()[ident]
        assert row.get('dose_threshold') is None, ident
        assert row['materiality'] == 'presence'

def test_immunosuppressant_sjw_monitoring_uses_drug_levels_not_inr():
    row = _curated()['DSI_IMMUNO_SJW']
    assert 'INR' not in row['management']
    assert 'prescriber' in row['management'].lower()
    assert row['severity'] == 'Contraindicated'

def test_melatonin_source_studies_administered_melatonin():
    assert '10668847' in _curated()['DSI_SSRI_MELATONIN']['source_pmids']

def test_cbd_copy_does_not_invent_an_epidiolex_anticoagulant_warning():
    row = _curated()['DSI_ANTICOAG_CBD']
    assert 'carries this interaction warning' not in row['mechanism']
    assert 'warfarin' in row['mechanism'].lower()
    assert 'case report' in row['mechanism'].lower()
    assert 'INR' in row['management']

def test_sjw_statin_clinical_endpoint_is_not_labelled_pk():
    row = _curated()['DSI_STATINS_SJW']
    assert 'up to 50%' not in row['mechanism']
    assert 'LDL' in row['mechanism']

ADDITIONAL_UNSUPPORTED_FLOOR_RULES = (
    'RULE_INGREDIENT_ALOE_VERA', 'RULE_IQM_VANADIUM_DIABETES',
    'RULE_IQM_VITAMIN_E_PREGNANCY_EXCESS', 'RULE_IQM_TURMERIC_LIVER',
    'RULE_INGREDIENT_OMEGA_3', 'RULE_INGREDIENT_FISH_OIL',
    'RULE_INGREDIENT_CURCUMIN', 'RULE_INGREDIENT_VITAMIN_D',
    'RULE_INGREDIENT_FLAXSEED', 'RULE_IQM_GUARANA',
    'RULE_IQM_DHA_BLEEDING', 'RULE_IQM_EPA_BLEEDING',
    'RULE_IQM_FORSKOLIN_ANTIHYPERTENSIVES', 'RULE_IQM_L_CARNITINE_DIABETES',
    'RULE_BOTAN_WHITE_MULBERRY_DIABETES', 'RULE_IQM_BROMELAIN',
)
def test_additional_clinical_dose_floors_require_actual_interaction_boundaries():
    for ident in ADDITIONAL_UNSUPPORTED_FLOOR_RULES:
        rule = _rules()[ident]
        for row in rule.get('condition_rules', []) + rule.get('drug_class_rules', []):
            if row.get('direction') == 'harmful':
                assert row.get('min_effective_dose') is None, ident

def test_niacin_glucose_floor_is_distinct_from_supported_statin_label_cutoff():
    rule = _rules()['RULE_IQM_NIACIN_DIABETES']
    assert rule['condition_rules'][0].get('min_effective_dose') is None
    assert rule['drug_class_rules'][2]['min_effective_dose']['value'] == 1000

def test_consumer_copy_preserves_the_actual_transplant_hazard():
    rows = _rules()
    probiotic = rows['RULE_IQM_PROBIOTICS_IMMUNOCOMPROMISED']['drug_class_rules'][0]
    assert 'infection' in probiotic['alert_body'].lower()
    assert 'immune-modulating' not in probiotic['alert_body']
    for ident in ('RULE_BOTAN_SCHISANDRA_BERRY_CYP3A4', 'RULE_IQM_SILYMARIN_LIVER', 'RULE_BANNED_CBD_INTERACTIONS'):
        row = next(x for x in rows[ident]['drug_class_rules'] if x['drug_class_id'] == 'immunosuppressants')
        assert 'immune-modulating' not in row['alert_body']
        assert 'drug' in row['alert_body'].lower()

def test_potassium_bp_warning_is_about_potassium_retention():
    row = _rules()['RULE_IQM_POTASSIUM_HYPERTENSION']['drug_class_rules'][0]
    assert 'potassium' in row['alert_body'].lower()
    assert 'ACE' in row['alert_body']
    assert 'counter antihypertensive' not in row['alert_body']

def test_chromium_valence_and_caffeine_lithium_source_copy():
    rows = _rules()
    assert 'Divalent chromium' not in rows['RULE_IQM_CHROMIUM_GLUCOSE']['drug_class_rules'][2]['mechanism']
    row = rows['RULE_INGREDIENT_CAFFEINE']['drug_class_rules'][0]
    assert not row['alert_body'].endswith('c...')
    assert any('32949106' in x for x in row['sources'])

def test_oral_aloe_pregnancy_lactation_excludes_topical_only():
    row = _rules()['RULE_INGREDIENT_ALOE_VERA']['pregnancy_lactation']
    assert 'topical_only' in row['profile_gate']['excludes']['product_forms_any']

def test_caffeine_population_copy_distinguishes_breastfeeding_guidance():
    row = _rules()['RULE_INGREDIENT_CAFFEINE']['pregnancy_lactation']
    assert '300' in row['alert_body']
    assert '200' in row['alert_body']
    assert 'preterm' in row['alert_body'].lower()

def test_model_specific_evidence_is_not_presented_as_proven_human_harm():
    rows = _rules()
    assert 'rat' in rows['RULE_BANNED_BITTER_ORANGE_HYPERTENSION']['condition_rules'][0]['mechanism'].lower()
    assert 'fish' in rows['RULE_INGREDIENT_REISHI__AUTOIMMUNE']['condition_rules'][0]['mechanism'].lower()
    assert 'theoretical' in rows['RULE_BANNED_ADD_HORDENINE']['drug_class_rules'][0]['mechanism'].lower()
    assert rows['RULE_BANNED_ADD_HORDENINE']['drug_class_rules'][0]['evidence_level'] != 'established'

def test_folate_mthfr_copy_retains_folic_acid_neural_tube_guidance():
    row = _rules()['RULE_IQM_FOLATE_TTC']['condition_rules'][0]
    assert 'folic acid' in row['action'].lower()
    assert 'preferred' not in row['action'].lower()

def test_chamomile_case_was_bleeding_not_thrombosis():
    row = _rules()['RULE_INGREDIENT_CHAMOMILE']['condition_rules'][0]
    assert 'thrombo' not in row['mechanism'].lower()

def test_nccih_explicit_pregnancy_avoidance_is_not_hidden_as_no_data():
    for ident in ('RULE_IQM_ASHWAGANDHA', 'RULE_INGREDIENT_PASSIONFLOWER__SEDATIVES'):
        row = _rules()[ident]['pregnancy_lactation']
        assert row['pregnancy_category'] == 'avoid'
        assert 'https://www.nccih.nih.gov/health/' in ' '.join(row['sources'])
        assert 'pregnant' in row['profile_gate']['requires']['profile_flags_any']

def test_profile_hazard_copy_is_complete_and_glucosamine_does_not_invent_platelet_activity():
    rows = _rules()
    assert not rows['RULE_IQM_GOLDENSEAL_PREGNANCY']['drug_class_rules'][1]['alert_body'].endswith('...')
    assert not rows['RULE_IQM_YOHIMBE_PREGNANCY']['drug_class_rules'][1]['alert_body'].endswith('...')
    assert 'mild antiplatelet' not in rows['RULE_INGREDIENT_GLUCOSAMINE']['drug_class_rules'][1]['alert_body']

def test_willow_monograph_restrictions_are_retained_in_pregnancy_copy():
    row = _rules()['RULE_IQM_WHITE_WILLOW_BARK_BLEEDING']['pregnancy_lactation']
    assert row['pregnancy_category'] == 'avoid'
    assert 'third trimester' in row['alert_body'].lower()
    assert row['lactation_category'] == 'avoid'

def test_resveratrol_cell_effect_is_not_a_proven_human_150mg_boundary():
    row = _rules()['RULE_IQM_RESVERATROL_BLEEDING']['condition_rules'][0]
    assert 'clinically meaningful antiplatelet effects have been documented' not in row['mechanism']
    assert 'laboratory' in row['mechanism'].lower()

def test_unsupported_study_dose_tier_does_not_suppress_real_label_warning():
    import sys
    sys.path.insert(0, str(DATA.parent))
    from enrich_supplements_v3 import SupplementEnricherV3
    owner=SupplementEnricherV3.__new__(SupplementEnricherV3)
    owner.unit_converter=None
    owner.databases={name:json.loads((DATA/(name+'.json')).read_text()) for name in ('clinical_risk_taxonomy','ingredient_quality_map','botanical_ingredients','other_ingredients')}
    # Frozen real labels 277679 (100 mg x3/day ALA) and182713 (400 mg/day curcumin).
    for rule_id,canonical,amount,servings,target in [('RULE_IQM_ALPHA_LIPOIC_ACID_DIABETES','alpha_lipoic_acid',100,3,'diabetes'),('RULE_INGREDIENT_CURCUMIN','curcumin',400,1,'anticoagulants')]:
        rule=_rules()[rule_id]
        owner.databases['ingredient_interaction_rules']={'interaction_rules':[rule]}
        ingredient={'name':canonical,'canonical_id':canonical,'canonical_source_db':'ingredient_quality_map','quantity':amount,'unit':'mg'}
        profile=owner._collect_interaction_profile({'ingredient_quality_data':{'ingredients':[ingredient]},'servingSizes':[{'minDailyServings':servings,'maxDailyServings':servings}]},user_profile=None)
        hits=[hit for alert in profile['ingredient_alerts'] for hit in alert.get('condition_hits',[])+alert.get('drug_class_hits',[]) if hit.get('condition_id',hit.get('drug_class_id'))==target]
        assert hits
        assert all((hit.get('dose_decision') or {}).get('consumer_disposition')!='suppress' for hit in hits), rule_id


def test_psyllium_lithium_sources_and_advice_match_actual_medicine():
    rule = _rules()['RULE_IQM_PSYLLIUM_DIABETES']
    row = next(r for r in rule['drug_class_rules'] if r['drug_class_id'] == 'lithium')
    assert row['severity'] == 'monitor'
    assert row['profile_gate']['requires']['drug_classes_any'] == ['lithium']
    assert 'https://pubmed.ncbi.nlm.nih.gov/1968148/' in row['sources']
    assert any('LithicarbFCtab.pdf' in s for s in row['sources'])
    assert all(s not in row['sources'] for s in ['https://pubmed.ncbi.nlm.nih.gov/9737361/', 'https://pubmed.ncbi.nlm.nih.gov/8636317/'])
    text = ' '.join(row.get(k, '') for k in ['mechanism', 'action', 'alert_body', 'informational_note']).lower()
    assert 'thyroid' not in text
    assert 'levothyroxine' not in text
    assert 'at least 2 hours' not in text
    assert 'lithium' in row['alert_body'].lower()
    assert 'monitor' in row['action'].lower()
    assert row['alert_headline'] == 'May lower lithium levels'
