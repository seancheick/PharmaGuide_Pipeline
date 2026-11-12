"""Source-supported safety regressions from the October clinical audit."""
import functools
import json
import re
from pathlib import Path

import pytest

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
    # Dr. Pham 2026-11-12 (section 2): avoid generally; contraindicated only with an exact source.
    assert ssri['severity'] == 'avoid'

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

def test_cbd_immunosuppressant_text_names_the_everolimus_label_finding():
    """EPIDIOLEX 7.2 measures everolimus (about 2.5-fold) and names sirolimus and tacrolimus; it does not say
    CBD affects immune function. Everolimus (RxCUI 141704) reaches the sub-rule through its class."""
    row = next(x for x in _rules()['RULE_BANNED_CBD_INTERACTIONS']['drug_class_rules']
               if x['drug_class_id'] == 'immunosuppressants')
    for drug in ('everolimus', 'sirolimus', 'tacrolimus'):
        assert drug in row['mechanism'] and drug in row['action'] and drug in row['informational_note'], drug
    assert '2.5-fold' in row['mechanism']
    assert 'immune function' not in row['informational_note']
    # Everolimus is also used for tuberous sclerosis and cancer, so the copy is not transplant-only.
    assert 'transplant' not in (row['alert_headline'] + row['alert_body']).lower()
    assert row['severity'] == 'caution'
    assert any('8bf27097-4870-43fb-94f0-f3d0871d1eec' in url for url in row['sources'])
    classes = json.loads((DATA / 'drug_classes.json').read_text())['classes']
    assert '141704' in classes['class:immunosuppressants']['member_rxcuis']

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


# Dr. Pham review 2026-11-11 (scripts/audits/clinical_review_20261111), batch 2: label-backed corrections.
PARNATE = 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b72d8187-dfcc-4ea0-b5e9-c0be95b69a27'
UK_ACETYLCYSTEINE_SMPC = 'https://www.medicines.org.uk/emc/product/2488/smpc'
REVIEW_FILE = 'audits/clinical_review_20261111/DR_PHAM_REVIEW_20261111.md'
STATIN_LABELS = {  # each marketed statin's own gemfibrozil instruction, read 2026-11-11
    'simvastatin': '8f55d5de-5a4f-4a39-8c84-c53976dd6af9', 'rosuvastatin': '325a5d0e-9a72-4015-9fcd-1655fb504cee',
    'atorvastatin': 'a60cc18b-0631-4cf0-b021-9f52224ece65', 'pravastatin': '42ccbca7-fa52-4df9-8f1a-ea7da7312883',
    'lovastatin': 'df7ddf4f-d569-431e-81f1-9129d7043150', 'fluvastatin': '726ea2db-f1b0-4b73-a515-02157db88a42',
    'pitavastatin': '44dcbf97-99ec-427c-ba50-207e0069d6d2',
}


def _pairs():
    out = {}
    for name in ('curated_interactions_v1.json', 'med_med_pairs_v1.json', 'batch_critical_2026_05.json'):
        for row in json.loads((DATA / 'curated_interactions' / name).read_text())['interactions']:
            assert row['id'] not in out, row['id']
            out[row['id']] = row
    return out


def _pair_text(row):
    return ' '.join(row.get(k) or '' for k in ('mechanism', 'management', 'evidence_notes')).lower()


def _same_rule():
    return next(r for r in _rules()['RULE_IQM_SAME']['drug_class_rules'] if r['drug_class_id'] == 'maois')


@functools.lru_cache(maxsize=1)
def _verify_context():
    import sys
    sys.path.insert(0, str(DATA.parent / 'api_audit'))
    import verify_interactions as vi

    def load(name):
        return json.loads((DATA / name).read_text(encoding='utf-8'))

    index = vi.build_iqm_cui_index(
        load('ingredient_quality_map.json'), botanicals=load('botanical_ingredients.json'),
        banned_recalled=load('banned_recalled_ingredients.json'),
        harmful_additives=load('harmful_additives.json'), other_ingredients=load('other_ingredients.json'))
    return vi, vi.VerifyContext(iqm_cui_index=index, drug_classes=load('drug_classes.json'))


def _verified(pair_id, row=None):
    """The pair as verify_interactions.py emits it for the build (evidence tier and canonical ids recomputed)."""
    vi, ctx = _verify_context()
    return vi.verify_entry(dict(row or _pairs()[pair_id]), ctx, vi.VerificationReport())


def test_same_evidence_tier_after_verification_matches_what_each_record_supports():
    # verify_interactions.py recomputes evidence_level before the build, so test its output.
    tiers = {}
    for pair_id in ('DSI_TRANYLCYPROMINE_SAME', 'DSI_MAOI_SAME'):
        normalized = _verified(pair_id)
        assert normalized['agent2_canonical_id'] == 'same', pair_id
        tiers[pair_id] = normalized['evidence_level']
    assert tiers == {'DSI_TRANYLCYPROMINE_SAME': 'established', 'DSI_MAOI_SAME': 'moderate'}
    assert _same_rule()['evidence_level'] == tiers['DSI_MAOI_SAME']


def test_statin_gemfibrozil_is_split_by_statin_label():
    pairs = _pairs()
    simva = pairs['DDI_SIMVASTATIN_GEMFIBROZIL']
    assert (simva['agent1_id'], simva['agent2_id'], simva['severity']) == ('36567', '4719', 'Contraindicated')
    assert any(STATIN_LABELS['simvastatin'] in u for u in simva['source_urls'])
    cls = pairs['DDI_STATIN_GEMFIBROZIL']
    assert cls['agent1_id'] == 'class:statins' and cls['severity'] == 'Major'
    for statin, setid in STATIN_LABELS.items():
        assert any(setid in u for u in cls['source_urls']), statin
    text = _pair_text(cls)
    # The old advice contradicted the pravastatin label ("avoid") and chose a drug for the user.
    assert 'use pravastatin' not in text and 'fenofibrate' not in text
    assert all('fda-drug-safety-communication' not in u for u in cls['source_urls']), 'the FDA page is 404'


def test_ciprofloxacin_theophylline_is_avoid_with_label_management_only():
    row = _pairs()['DDI_THEOPHYLLINE_CIPRO']
    assert row['severity'] == 'Major'
    text = _pair_text(row)
    assert '30–50%' not in text and '30-50%' not in text, 'the label gives no fixed dose cut'
    assert 'azithromycin' not in text
    assert 'theophylline level' in text
    # Medicines carry no route, so drops are flagged too, with the scope stated rather than silently excluded.
    assert 'eye or ear drops' in text


def test_nac_nitroglycerin_warns_about_hypotension_from_the_acetylcysteine_label():
    row = _pairs()['DSI_NITROGLYCERIN_NAC']
    assert (row['agent1_id'], row['agent2_id'], row['agent2_canonical_id']) == ('4917', 'C0001047', 'nac')
    assert row['severity'] == 'Moderate'
    assert UK_ACETYLCYSTEINE_SMPC in row['source_urls'] and '9120179' in row['source_pmids']
    text = _pair_text(row)
    assert 'low blood pressure' in text and 'headache' in text
    assert 'isosorbide' not in text, 'no source was read for other nitrates'
    # The SmPC: if both are required, patients should be monitored for hypotension.
    assert 'blood pressure should be checked' in row['management']


def test_an_exact_pair_that_hides_a_class_pair_is_never_the_weaker_warning():
    # The app shows only the exact pair when both match the same two agents
    # (stack_interaction_checker.dart), so the exact pair must not be weaker.
    classes = json.loads((DATA / 'drug_classes.json').read_text())['classes']
    rank = {'Minor': 1, 'Moderate': 2, 'Major': 3, 'Contraindicated': 4}

    def members(agent):
        agent = str(agent)
        if agent.startswith('class:'):
            return set(map(str, classes[agent]['member_rxcuis']))
        return {agent}

    rows = list(_pairs().values()) + json.loads(
        (DATA / 'curated_interactions' / 'batch_critical_2026_05.json').read_text())['interactions']
    exact = {frozenset((str(r['agent1_id']), str(r['agent2_id']))): r for r in rows
             if not str(r['agent1_id']).startswith('class:') and not str(r['agent2_id']).startswith('class:')}
    overlaps = []
    for row in rows:
        if not (str(row['agent1_id']).startswith('class:') or str(row['agent2_id']).startswith('class:')):
            continue
        for a in members(row['agent1_id']):
            for b in members(row['agent2_id']):
                hit = exact.get(frozenset((a, b)))
                if hit:
                    overlaps.append((row['id'], hit['id']))
                    assert rank[hit['severity']] >= rank[row['severity']], (row['id'], hit['id'])
    assert ('DDI_STATIN_GEMFIBROZIL', 'DDI_SIMVASTATIN_GEMFIBROZIL') in overlaps


def test_nac_nitroglycerin_keeps_its_nac_canonical_id_through_verification():
    # verify_interactions.py replaces an authored supplement canonical id with the
    # ingredient-map lookup by CUI, so NAC's map entry must carry C0001047.
    normalized = _verified('DSI_NITROGLYCERIN_NAC')
    assert normalized is not None
    assert normalized['agent2_canonical_id'] == 'nac'


# Batch 3a of Dr. Pham's 2026-11-11 review: anticoagulant scope (rows A2, A4-A10).
WARFARIN_LABEL = 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=ab98f729-31b4-2b6d-e053-2995a90afed7'
UK_WARFARIN = 'https://www.medicines.org.uk/emc/product/14333/smpc'
LOVAZA = 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=21cfa4ce-0b05-47ed-b268-339eb1b83b75'
APP_SEVERITY = {'Contraindicated': 'contraindicated', 'Major': 'avoid', 'Moderate': 'caution', 'Minor': 'monitor'}
ANTICOAGULANT_ROWS = (
    # pair, rule, sub-rule class, reviewed severity, warfarin-specific evidence
    ('DSI_WAR_SJW', 'RULE_INGREDIENT_ST_JOHNS_WORT', 'anticoagulants', 'avoid', True),
    ('DSI_WAR_COQ10', 'RULE_IQM_COQ10_HEART_DISEASE_STATINS', 'anticoagulants', 'monitor', True),
    ('DSI_WAR_GINKGO', 'RULE_IQM_GINKGO_HYPERTENSION', 'anticoagulants', 'caution', False),
    ('DSI_WAR_GARLIC', 'RULE_INGREDIENT_GARLIC', 'anticoagulants', 'caution', False),
    ('DSI_WAR_GLUCOSAMINE', 'RULE_INGREDIENT_GLUCOSAMINE', 'anticoagulants', 'caution', True),
    ('DSI_WAR_CRANBERRY', 'RULE_INGREDIENT_CRANBERRY', 'anticoagulants', 'caution', True),
    ('DSI_WAR_GINGER', 'RULE_IQM_GINGER_BLEEDING', 'anticoagulants', 'caution', True),
    ('DSI_NSAID_FISHOIL', 'RULE_INGREDIENT_FISH_OIL', 'nsaids', 'monitor', False),
)


def _sub(rule_id, drug_class):
    return next(r for r in _rules()[rule_id]['drug_class_rules'] if r['drug_class_id'] == drug_class)


def _rule_text(sub):
    return ' '.join(sub.get(k) or '' for k in (
        'mechanism', 'action', 'alert_headline', 'alert_body', 'informational_note')).lower()


def test_anticoagulant_pairs_and_rules_agree_on_the_reviewed_severity_and_scope():
    import profile_gate_evaluator as pge

    pairs = _pairs()
    warfarin = {'drug_classes': ['anticoagulants', 'vitamin_k_antagonists']}
    unknown_blood_thinner = {'drug_classes': ['anticoagulants']}
    apixaban = {'drug_classes': ['anticoagulants', 'doacs']}
    for pair_id, rule_id, drug_class, severity, warfarin_only in ANTICOAGULANT_ROWS:
        pair, sub = pairs[pair_id], _sub(rule_id, drug_class)
        assert APP_SEVERITY[pair['severity']] == severity, pair_id
        assert sub['severity'] == severity, rule_id
        # Minor pairs sit in the background lane (pipeline label, not exported); the rest never do.
        assert (pair.get('display_layer') == 'background') == (pair['severity'] == 'Minor'), pair_id
        # Reviewed 2026-11-11; rows refined by the signed answers of 2026-11-12 cite that file instead.
        assert sub['clinical_review']['file'] in (REVIEW_FILE, ANSWERS_FILE), rule_id
        if drug_class != 'anticoagulants':
            continue
        fires = {
            name: bool(_anticoagulant_hits(rule_id, profile))
            for name, profile in (('warfarin', warfarin), ('unknown', unknown_blood_thinner), ('doac', apixaban))
        }
        # Warfarin-specific evidence never reaches a DOAC user; an unknown blood thinner still gets it.
        assert fires == {'warfarin': True, 'unknown': True, 'doac': not warfarin_only}, rule_id


WARFARIN_ONLY_RULES = tuple(rule for _, rule, cls, _, only in ANTICOAGULANT_ROWS if only and cls == 'anticoagulants')


def _anticoagulant_hits(rule_id, drug_classes):
    """The rule's blood-thinner sub-rules whose gate fires for a profile, by drug class id."""
    import profile_gate_evaluator as pge

    profile = {'drug_classes': sorted(drug_classes['drug_classes'])}
    return [
        sub['drug_class_id'] for sub in _rules()[rule_id]['drug_class_rules']
        if sub['drug_class_id'] in ('anticoagulants', 'vitamin_k_antagonists')
        and pge.evaluate_profile_gate(sub['profile_gate'], profile, {}, base_severity=sub['severity']).fires
    ]


def test_warfarin_only_findings_follow_an_identified_warfarin_and_fall_back_only_when_unidentified():
    # Profiles as the app builds them: each entered medicine adds the classes it is a member of
    # (drug_classes.json); "Blood thinners" is the only user-selectable blood-thinner class.
    warfarin, apixaban = {'anticoagulants', 'vitamin_k_antagonists'}, {'anticoagulants', 'doacs'}
    profiles = {
        'warfarin': warfarin,
        'warfarin and apixaban': warfarin | apixaban,  # a DOAC elsewhere must not veto the warfarin finding
        'apixaban': apixaban,
        'blood thinner not identified': {'anticoagulants'},
    }
    expected = {
        'warfarin': ['vitamin_k_antagonists'],
        'warfarin and apixaban': ['vitamin_k_antagonists'],
        'apixaban': [],
        'blood thinner not identified': ['anticoagulants'],
    }
    for rule_id in WARFARIN_ONLY_RULES:
        hits = {name: _anticoagulant_hits(rule_id, {'drug_classes': p}) for name, p in profiles.items()}
        assert hits == expected, rule_id
        # The identified and fallback sub-rules carry one decision and one text.
        vka, fallback = (_sub(rule_id, cls) for cls in ('vitamin_k_antagonists', 'anticoagulants'))
        strip = lambda s: {k: v for k, v in s.items() if k not in ('drug_class_id', 'profile_gate')}  # noqa: E731
        assert strip(vka) == strip(fallback), rule_id
    assert set(WARFARIN_ONLY_RULES) == {
        'RULE_INGREDIENT_ST_JOHNS_WORT', 'RULE_INGREDIENT_GLUCOSAMINE', 'RULE_INGREDIENT_CRANBERRY',
        'RULE_IQM_COQ10_HEART_DISEASE_STATINS', 'RULE_IQM_GINGER_BLEEDING'}


def test_ginger_blood_thinner_findings_carry_the_warfarin_evidence_and_scope():
    # A9 is ginger + warfarin: the cohort studied warfarin users and the crossover healthy men, and no
    # retained source covers another blood thinner. The ginger-extract rule is the same subject; it
    # cited the NCCIH ginger page, which never mentions bleeding (read 2026-11-11).
    reviewed = _sub('RULE_IQM_GINGER_BLEEDING', 'anticoagulants')
    for rule_id in ('RULE_IQM_GINGER_BLEEDING', 'RULE_OTHER_GINGER_EXTRACT_BLEEDING'):
        hits = {
            name: _anticoagulant_hits(rule_id, {'drug_classes': p}) for name, p in (
                ('warfarin', {'anticoagulants', 'vitamin_k_antagonists'}),
                ('apixaban', {'anticoagulants', 'doacs'}),
                ('blood thinner not identified', {'anticoagulants'}),
            )
        }
        assert hits == {
            'warfarin': ['vitamin_k_antagonists'], 'apixaban': [],
            'blood thinner not identified': ['anticoagulants'],
        }, rule_id
        for cls in ('vitamin_k_antagonists', 'anticoagulants'):
            sub = _sub(rule_id, cls)
            text = _rule_text(sub)
            assert 'warfarin' in sub['action'].lower() and 'warfarin' in sub['alert_body'].lower(), (rule_id, cls)
            assert 'blood thinner' not in text and 'anticoagulant activity' not in text, (rule_id, cls)
            assert set(sub['sources']) == {
                'https://pubmed.ncbi.nlm.nih.gov/17723077/', 'https://pubmed.ncbi.nlm.nih.gov/15801937/'}, rule_id
            for key in ('severity', 'evidence_level', 'mechanism', 'action', 'alert_headline', 'alert_body'):
                assert sub[key] == reviewed[key], (rule_id, cls, key)


def test_betrixaban_is_a_doac_and_leaves_the_unidentified_fallback():
    """BEVYXXA: betrixaban is an oral factor Xa inhibitor (ATC B01AF, inside the doacs class's ATC scope) and a
    P-gp substrate, so it reads as a DOAC: no warfarin INR text, and St. John's wort still shows avoid. The
    injected direct thrombin inhibitors are ATC B01AE but not oral; since Q7 (signed 2026-11-12) they are an
    identified injected subgroup outside the warfarin fallback."""
    classes = json.loads((DATA / 'drug_classes.json').read_text())['classes']

    def profile(rxcui):
        return {cid.removeprefix('class:') for cid, c in classes.items()
                if not cid.startswith('_') and rxcui in c.get('member_rxcuis', [])}

    betrixaban = profile('1927851')
    assert {'anticoagulants', 'doacs'} <= betrixaban and 'vitamin_k_antagonists' not in betrixaban
    import profile_gate_evaluator as pge

    for rule_id in WARFARIN_ONLY_RULES:
        assert _anticoagulant_hits(rule_id, {'drug_classes': betrixaban}) == [], rule_id
    sjw_doac = _sub('RULE_INGREDIENT_ST_JOHNS_WORT', 'doacs')
    assert sjw_doac['severity'] == 'avoid'
    assert pge.evaluate_profile_gate(sjw_doac['profile_gate'], {'drug_classes': sorted(betrixaban)}, {},
                                     base_severity='avoid').fires
    for name, rxcui in (('argatroban', '15202'), ('bivalirudin', '60819'), ('desirudin', '114934'),
                        ('lepirudin', '237057')):
        assert profile(rxcui) == {'anticoagulants', 'injectable_anticoagulants'}, name


# --- Signed answers 2026-11-12, batch 2: anticoagulants (Q3, Q7, section 2, Part B 3D) -------------------------------

ANSWERS_FILE = 'audits/clinical_review_20261111/DR_PHAM_ANSWERS_20261112.md'
SINTHROME = 'https://www.medicines.org.uk/emc/product/2058/smpc'
MARCUMAR = 'https://www.fachinfo.de/pdf/003056'
LIXIANA = 'https://www.medicines.org.uk/emc/product/6905/smpc'
INJECTED = {  # RxNorm ingredient RxCUIs, verified on RxNav 2026-11-12
    'argatroban': '15202', 'bivalirudin': '60819', 'desirudin': '114934', 'lepirudin': '237057',
    'heparin': '5224', 'enoxaparin': '67108', 'dalteparin': '67109', 'tinzaparin': '69646', 'fondaparinux': '321208',
}
GLUCOSAMINE_Q3 = (
    'Do not start glucosamine while taking warfarin unless your anticoagulation clinician has specifically agreed and '
    'arranged appropriate INR monitoring. Tell them before stopping or changing glucosamine. Some warfarin labels '
    'advise against this combination.'
)
CONSUMER_FIELDS = ('action', 'alert_headline', 'alert_body', 'informational_note')
FALLBACK_RULES = ('RULE_INGREDIENT_ST_JOHNS_WORT', 'RULE_INGREDIENT_GLUCOSAMINE', 'RULE_INGREDIENT_CRANBERRY',
                  'RULE_IQM_COQ10_HEART_DISEASE_STATINS', 'RULE_IQM_GINGER_BLEEDING',
                  'RULE_OTHER_GINGER_EXTRACT_BLEEDING')


def _classes():
    return json.loads((DATA / 'drug_classes.json').read_text())['classes']


def _profile_of(*rxcuis):
    """Profile-gate ids an entered regimen produces: every class each medicine is a member of."""
    return {cid.removeprefix('class:') for cid, c in _classes().items()
            if any(r in c.get('member_rxcuis', []) for r in rxcuis)}


def _firing_subs(profile):
    import profile_gate_evaluator as pge

    for rule in _rules().values():
        for sub in rule.get('drug_class_rules', []):
            if pge.evaluate_profile_gate(sub['profile_gate'], {'drug_classes': sorted(profile)}, {},
                                         base_severity=sub['severity']).fires:
                yield rule['id'], sub


def test_injected_anticoagulants_are_an_identified_subgroup_outside_the_warfarin_fallback():
    """Q7: injected thrombin inhibitors get their own subgroup and leave the unidentified-warfarin fallback; Part B
    3D: heparins and fondaparinux join the anticoagulants without receiving warfarin text."""
    classes = _classes()
    injected = classes['class:injectable_anticoagulants']
    assert dict(zip(injected['member_names'], injected['member_rxcuis'])) == INJECTED
    assert set(INJECTED.values()) <= set(classes['class:anticoagulants']['member_rxcuis'])
    for cid in ('class:doacs', 'class:vitamin_k_antagonists'):
        assert not set(INJECTED.values()) & set(classes[cid]['member_rxcuis']), cid
    taxonomy = json.loads((DATA / 'clinical_risk_taxonomy.json').read_text())
    assert 'injectable_anticoagulants' in {c['id'] for c in taxonomy['drug_classes']}
    for name, rxcui in INJECTED.items():
        profile = _profile_of(rxcui)
        assert profile == {'anticoagulants', 'injectable_anticoagulants'}, name
        for rule_id in (*WARFARIN_ONLY_RULES, 'RULE_OTHER_GINGER_EXTRACT_BLEEDING'):
            assert _anticoagulant_hits(rule_id, {'drug_classes': profile}) == [], (name, rule_id)
        # No St. John's wort finding is inherited from warfarin or the oral DOACs.
        assert not [s for rid, s in _firing_subs(profile) if rid == 'RULE_INGREDIENT_ST_JOHNS_WORT'
                    and s['drug_class_id'] != 'antidepressants_ssri_snri'], name


def test_a_warfarin_type_medicine_keeps_its_findings_next_to_another_anticoagulant():
    """Section 2: one entered medicine cannot suppress a valid finding for another in the same regimen."""
    warfarin, apixaban, enoxaparin, acenocoumarol = '11289', '1364430', '67108', '154'
    for regimen in ((warfarin, enoxaparin), (warfarin, apixaban), (acenocoumarol, enoxaparin),
                    (warfarin, apixaban, enoxaparin)):
        profile = _profile_of(*regimen)
        for rule_id in (*WARFARIN_ONLY_RULES, 'RULE_OTHER_GINGER_EXTRACT_BLEEDING'):
            assert _anticoagulant_hits(rule_id, {'drug_classes': profile}) == ['vitamin_k_antagonists'], (
                regimen, rule_id)
        sjw = sorted(s['drug_class_id'] for rid, s in _firing_subs(profile) if rid == 'RULE_INGREDIENT_ST_JOHNS_WORT'
                     and s['drug_class_id'] in ('anticoagulants', 'vitamin_k_antagonists', 'doacs'))
        assert sjw == sorted(['vitamin_k_antagonists', *(['doacs'] if apixaban in regimen else [])]), regimen


WARFARIN_QUALIFIER = re.compile(
    r"if you take warfarin|warfarin users?\b|in (?:a |people taking )?warfarin|with warfarin|warfarin-type|"
    r"vitamin K antagonist|warfarin-treated", re.I)


def _warfarin_only_sentences(text):
    """Consumer sentences that address the reader as a warfarin user: an INR sentence not qualified to warfarin,
    or one that speaks of "your warfarin"."""
    return [s for s in re.split(r'(?<=[.;])\s+', text or '')
            if re.search(r'\byour warfarin\b', s, re.I) or ('INR' in s and not WARFARIN_QUALIFIER.search(s))]


@pytest.mark.parametrize('rxcui', ['1364430', '1114195', '1037042', '1599538', *INJECTED.values()])
def test_no_warfarin_instruction_reaches_a_doac_or_injected_anticoagulant_user_unqualified(rxcui):
    """Section 2 and Q7: no INR instructions for DOAC or injected-anticoagulant users; Part B 3D: adding the heparins
    must not widen warfarin-specific instructions. Every rule and pair such a user can reach is checked."""
    profile = _profile_of(rxcui)
    for rule_id, sub in _firing_subs(profile):
        for field in CONSUMER_FIELDS:
            assert not _warfarin_only_sentences(sub.get(field)), (rxcui, rule_id, sub['drug_class_id'], field)
    reachable = {rxcui, *(f'class:{c}' for c in profile)}
    for pair in _pairs().values():
        if pair['agent1_id'] in reachable:
            assert not _warfarin_only_sentences(pair['management']), (rxcui, pair['id'])


def test_warfarin_only_sentence_check_catches_the_reviewed_failures():
    """The check above is not vacuous: the sentences it was written against fail it."""
    for text in ('Tell your warfarin prescriber about changes in vitamin D supplementation.',
                 'INR may need to be checked more frequently and warfarin dose adjusted.',
                 'Monitor INR more frequently when starting or stopping CBD.'):
        assert _warfarin_only_sentences(text), text
    assert not _warfarin_only_sentences('If you take warfarin, ask about INR checks when you start it.')


def test_warfarin_type_findings_name_one_warfarin_type_term():
    """Review of batch 2: "a similar blood thinner" read as any blood thinner (a DOAC user who picked only "Blood
    thinners" would follow an INR instruction). The VKA and fallback copy qualifies the class as warfarin-type, the
    vocabulary's own term (ginger says "medicine", since its copy never claims other blood thinners)."""
    for rule_id in FALLBACK_RULES:
        for cls in ('vitamin_k_antagonists', 'anticoagulants'):
            sub = _sub(rule_id, cls)
            for vague in ('similar blood thinner', 'similar medicine'):
                assert vague not in _rule_text(sub), (rule_id, cls, vague)
            assert 'warfarin-type' in sub['action'], (rule_id, cls)


def test_st_johns_wort_with_vkas_cites_each_label_and_marks_the_class_inference():
    """Q7 and section 2: strong avoidance for warfarin, acenocoumarol and phenprocoumon, each with its own source;
    other VKAs keep it as a stated precautionary class inference."""
    pairs = _pairs()
    for pair_id, rxcui, source in (('DSI_ACENOCOUMAROL_SJW', '154', SINTHROME),
                                   ('DSI_PHENPROCOUMON_SJW', '8150', MARCUMAR)):
        pair = pairs[pair_id]
        assert (pair['agent1_id'], pair['agent2_canonical_id'], pair['severity']) == (rxcui, 'st_johns_wort', 'Major')
        assert pair['source_urls'][0] == source and pair['applies_to'] == 'specific_drug'
        assert 'stopping' in pair['management'] and 'INR' in pair['management']
        assert ANSWERS_FILE in pair['verification']['notes'] and 'Dr. Pham' not in pair['verification']['method']
    for cls in ('vitamin_k_antagonists', 'anticoagulants'):
        sub = _sub('RULE_INGREDIENT_ST_JOHNS_WORT', cls)
        assert sub['severity'] == 'avoid' and {SINTHROME, MARCUMAR} <= set(sub['sources'])
        assert 'acenocoumarol' in sub['mechanism'] and 'phenprocoumon' in sub['mechanism']
        assert 'precautionary class inference' in sub['mechanism']
        assert 'warfarin' in sub['alert_body'] and 'stopping' in sub['action']


def test_st_johns_wort_with_doacs_records_each_label_and_the_edoxaban_policy():
    """Section 2: apixaban, rivaroxaban, dabigatran labels support avoiding; edoxaban's UK label says caution, so
    avoid is PharmaGuide precautionary policy, recorded in its own evidence record."""
    pairs = _pairs()
    doac = pairs['DSI_DOAC_SJW']
    notes = doac['evidence_notes']
    for label in ('ELIQUIS', 'rivaroxaban', 'PRADAXA', 'SAVAYSA', 'Lixiana'):
        assert label in notes, label
    assert 'does not name' in notes and LIXIANA in doac['source_urls']
    edoxaban = pairs['DSI_EDOXABAN_SJW']
    assert (edoxaban['agent1_id'], edoxaban['severity'], edoxaban['applies_to']) == ('1599538', 'Major', 'specific_drug')
    assert LIXIANA in edoxaban['source_urls'] and 'precautionary policy' in edoxaban['evidence_notes']
    assert 'caution' in edoxaban['evidence_notes']
    sub = _sub('RULE_INGREDIENT_ST_JOHNS_WORT', 'doacs')
    assert LIXIANA in sub['sources'] and 'precautionary policy' in sub['mechanism']
    for text in (_pair_text(doac), _pair_text(edoxaban), _rule_text(sub)):
        assert 'inr' not in text


def test_glucosamine_with_warfarin_type_medicines_uses_the_signed_q3_action():
    """Q3: caution kept, with a firm do-not-start-without-agreement action; Q7: acenocoumarol and phenprocoumon
    labels support the precaution; no invented recheck interval; not a contraindication."""
    pairs = _pairs()
    # Q3's action, followed by the existing bleeding-report instruction (not softened).
    assert pairs['DSI_WAR_GLUCOSAMINE']['management'] == (
        GLUCOSAMINE_Q3 + ' This includes glucosamine-chondroitin products. Report unusual bruising or bleeding.')
    assert pairs['DSI_WAR_GLUCOSAMINE']['severity'] == 'Moderate'
    for pair_id, rxcui, source in (('DSI_ACENOCOUMAROL_GLUCOSAMINE', '154', SINTHROME),
                                   ('DSI_PHENPROCOUMON_GLUCOSAMINE', '8150', MARCUMAR)):
        pair = pairs[pair_id]
        assert (pair['agent1_id'], pair['agent2_canonical_id'], pair['severity']) == (rxcui, 'glucosamine', 'Moderate')
        assert pair['source_urls'][0] == source and pair['management'].startswith('Do not start glucosamine')
    for cls in ('vitamin_k_antagonists', 'anticoagulants'):
        sub = _sub('RULE_INGREDIENT_GLUCOSAMINE', cls)
        assert sub['severity'] == 'caution'
        assert sub['action'].startswith('Do not start glucosamine') and 'Some warfarin labels' in sub['action']
        assert {SINTHROME, MARCUMAR} <= set(sub['sources']) and 'inference' in sub['mechanism']
        text = _rule_text(sub)
        assert 'contraindicat' not in text and 'weeks' not in text and 'stop warfarin' not in text


def test_warfarin_findings_extended_to_other_vkas_say_they_are_an_inference():
    """Q7: CoQ10, cranberry and ginger evidence stays warfarin-specific; the VKA extension is stated as inference in
    every duplicated owner, both ginger records included."""
    for rule_id in ('RULE_IQM_COQ10_HEART_DISEASE_STATINS', 'RULE_INGREDIENT_CRANBERRY', 'RULE_IQM_GINGER_BLEEDING',
                    'RULE_OTHER_GINGER_EXTRACT_BLEEDING'):
        for cls in ('vitamin_k_antagonists', 'anticoagulants'):
            sub = _sub(rule_id, cls)
            assert 'warfarin' in sub['mechanism'] and 'inference' in sub['mechanism'], (rule_id, cls)
            assert 'inferred' in sub['action'], (rule_id, cls)
            assert sub['clinical_review']['file'] == ANSWERS_FILE, (rule_id, cls)


def test_coq10_warfarin_copy_does_not_call_the_effect_mild_and_records_the_bleeding_signal():
    pair = _pairs()['DSI_WAR_COQ10']
    assert '17723077' in pair['source_pmids'] and 'self-reported bleeding' in _pair_text(pair)
    for cls in ('anticoagulants', 'vitamin_k_antagonists'):
        sub = _sub('RULE_IQM_COQ10_HEART_DISEASE_STATINS', cls)
        assert 'mild' not in _rule_text(sub), cls
        assert 'self-reported bleeding' in sub['mechanism'] and 'does not establish' in sub['mechanism']


def test_reviewed_anticoagulant_records_drop_unsupported_floors_and_instructions():
    import re

    pairs = _pairs()
    for rule_id in ('RULE_INGREDIENT_GARLIC', 'RULE_IQM_GINKGO_HYPERTENSION'):
        for drug_class in ('anticoagulants', 'antiplatelets'):
            sub = _sub(rule_id, drug_class)
            assert sub.get('min_effective_dose') is None, (rule_id, drug_class)
            assert sub['materiality'] == 'presence'
            assert '600' not in _rule_text(sub) and '120 mg' not in _rule_text(sub)
    # A rule-level dose tier replaces the sub-rule severity in the enricher, so none may remain
    # on a reviewed (rule, class): garlic's > 1200 mg avoid / otherwise monitor tier had no source.
    for pair_id, rule_id, drug_class, _, _ in ANTICOAGULANT_ROWS:
        tiers = [t for t in _rules()[rule_id].get('dose_thresholds') or []
                 if t.get('scope') == 'drug_class' and t.get('target_id') == drug_class]
        assert not tiers, (rule_id, drug_class)
    assert 'do not combine' not in _rule_text(_sub('RULE_IQM_GINKGO_HYPERTENSION', 'anticoagulants'))
    glucosamine = _rule_text(_sub('RULE_INGREDIENT_GLUCOSAMINE', 'anticoagulants'))
    assert '2-4 weeks' not in glucosamine and '2–4 weeks' not in glucosamine
    assert 'with food' not in _rule_text(_sub('RULE_INGREDIENT_FISH_OIL', 'nsaids'))
    assert 'with food' not in _pair_text(pairs['DSI_NSAID_FISHOIL'])
    cranberry = _rule_text(_sub('RULE_INGREDIENT_CRANBERRY', 'anticoagulants'))
    assert '1 l' not in cranberry and 'increase warfarin levels' not in cranberry
    assert 'small amounts' not in _pair_text(pairs['DSI_WAR_CRANBERRY'])
    assert not re.search(r'\bsafe\b', _pair_text(pairs['DSI_WAR_GARLIC']))
    assert 'other vitamin-k antagonists' not in _rule_text(_sub('RULE_INGREDIENT_ST_JOHNS_WORT', 'anticoagulants'))
    assert 'mild antiplatelet' not in _rule_text(_sub('RULE_IQM_GINGER_BLEEDING', 'anticoagulants'))


def test_reviewed_anticoagulant_records_cite_the_sources_that_support_them():
    pairs = _pairs()
    sjw = _sub('RULE_INGREDIENT_ST_JOHNS_WORT', 'anticoagulants')
    assert UK_WARFARIN in pairs['DSI_WAR_SJW']['source_urls'] and UK_WARFARIN in sjw['sources']
    for pair_id in ('DSI_WAR_COQ10', 'DSI_WAR_GINKGO', 'DSI_WAR_GARLIC'):
        assert WARFARIN_LABEL in pairs[pair_id]['source_urls'], pair_id
    cranberry = pairs['DSI_WAR_CRANBERRY']
    assert {'18516070', '19553405'} <= set(cranberry['source_pmids'])
    assert UK_WARFARIN in cranberry['source_urls'] and not any('mhra.gov.uk' in u for u in cranberry['source_urls'])
    assert 'avoid cranberry products' in cranberry['evidence_notes'].lower(), 'the UK instruction is recorded'
    ginger_rule = _sub('RULE_IQM_GINGER_BLEEDING', 'anticoagulants')
    for urls in (pairs['DSI_WAR_GINGER']['source_urls'], ginger_rule['sources']):
        assert not any('nccih.nih.gov/health/ginger' in u for u in urls), 'NCCIH ginger never mentions bleeding'
    assert {'17723077', '15801937'} <= set(pairs['DSI_WAR_GINGER']['source_pmids'])
    glucosamine = pairs['DSI_WAR_GLUCOSAMINE']
    assert '18363538' in glucosamine['source_pmids'] and UK_WARFARIN in glucosamine['source_urls']
    # The glucosamine-chondroitin teaching case (PMC3743701) is kept: Dr. Pham counts those reports.
    assert any('23946031' in u for u in _sub('RULE_INGREDIENT_GLUCOSAMINE', 'anticoagulants')['sources'])
    fish_oil = pairs['DSI_NSAID_FISHOIL']
    assert LOVAZA in fish_oil['source_urls'] and LOVAZA in _sub('RULE_INGREDIENT_FISH_OIL', 'nsaids')['sources']
    assert 'extrapolation' in _pair_text(fish_oil) and 'icosapent ethyl' in _pair_text(fish_oil)


def test_anticoagulant_rule_evidence_matches_the_verified_pair_tier():
    # One interaction, one evidence tier: the rule states what verify_interactions.py derives for its pair.
    tiers = {}
    for pair_id, rule_id, drug_class, _, _ in ANTICOAGULANT_ROWS:
        tiers[pair_id] = _verified(pair_id)['evidence_level']
        assert _sub(rule_id, drug_class)['evidence_level'] == tiers[pair_id], (pair_id, rule_id)
    # The warfarin label's CoQ10 line is an example ("may"), with mixed clinical data: not established.
    assert tiers['DSI_WAR_COQ10'] == 'probable'


def test_sibling_floor_removals_are_not_attributed_to_the_clinical_review():
    # Dr. Pham decided the anticoagulant rows; removing the same unsupported floor from the
    # antiplatelet siblings is the agent's correction and must not carry her review record.
    for rule_id in ('RULE_INGREDIENT_GARLIC', 'RULE_IQM_GINKGO_HYPERTENSION'):
        assert 'clinical_review' in _sub(rule_id, 'anticoagulants')
        assert 'clinical_review' not in _sub(rule_id, 'antiplatelets'), rule_id


def test_garlic_with_a_blood_thinner_is_caution_at_every_amount():
    # The production path: the enricher's interaction profile for a garlic product.
    from enrich_supplements_v3 import SupplementEnricherV3

    enricher = SupplementEnricherV3()

    def severity(quantity):
        row = {'name': 'Garlic Extract', 'raw_source_text': 'Garlic Extract', 'standard_name': 'Garlic',
               'canonical_id': 'garlic', 'raw_source_path': 'ingredientRows[0]', 'quantity': quantity, 'unit': 'mg'}
        product = {'dsld_id': 'TEST_GARLIC', 'product_name': 'Garlic', 'ingredient_quality_data': {
            'ingredients_scorable': [row], 'ingredients': [row], 'ingredients_skipped': []}}
        profile = enricher._collect_interaction_profile(product)
        [alert] = [a for a in profile['ingredient_alerts'] if a['rule_id'] == 'RULE_INGREDIENT_GARLIC']
        return next(h['severity'] for h in alert['drug_class_hits'] if h['drug_class_id'] == 'anticoagulants')

    assert {q: severity(q) for q in (300.0, 1500.0, None)} == {300.0: 'caution', 1500.0: 'caution', None: 'caution'}


# Batch 3b part 2 of Dr. Pham's 2026-11-11 review: licorice (A14, F4) and levodopa + iron (F2).
EMA_LICORICE = (
    'https://www.ema.europa.eu/en/documents/herbal-monograph/final-european-union-herbal-monograph-'
    'glycyrrhiza-glabra-l-glycyrrhiza-inflata-bat-glycyrrhiza-uralensis-fisch-radix-revision-1_en.pdf'
)
LANOXIN = 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=d91e3646-4c63-4512-ab22-db39c085c4dc'
SINEMET = 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=9b17b028-964a-473c-823d-81423535bd66'
INBRIJA = 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=077c0f39-a3a2-4b2b-a184-09131889dcfb'
LICORICE_RULES = ('RULE_IQM_LICORICE_HYPERTENSION', 'RULE_BOTANICAL_LICORICE_ROOT')


def _licorice_alerts(canonical_id, source_db):
    """The enricher's licorice alerts for a one-row product: {rule_id: {drug_class_id: severity}}."""
    from enrich_supplements_v3 import SupplementEnricherV3

    row = {'name': canonical_id, 'raw_source_text': canonical_id, 'standard_name': canonical_id,
           'canonical_id': canonical_id, 'canonical_source_db': source_db,
           'raw_source_path': 'ingredientRows[0]', 'quantity': None, 'unit': None}
    product = {'dsld_id': 'TEST_LICORICE', 'product_name': 't', 'ingredient_quality_data': {
        'ingredients_scorable': [row], 'ingredients': [row], 'ingredients_skipped': []}}
    alerts = SupplementEnricherV3()._collect_interaction_profile(product)['ingredient_alerts']
    return {a['rule_id']: {h['drug_class_id']: h['severity'] for h in a['drug_class_hits']}
            for a in alerts if a['rule_id'] in LICORICE_RULES}


def test_licorice_with_blood_pressure_medicine_is_avoid_unless_verified_dgl():
    import profile_gate_evaluator as pge

    pair = _pairs()['DSI_ANTIHYP_LICORICE']
    assert APP_SEVERITY[pair['severity']] == 'avoid'
    iqm, botanical = (_sub(rule_id, 'antihypertensives') for rule_id in LICORICE_RULES)
    # A licorice_root label meets both rules (its IQM twin), so both carry one decision and one text.
    assert iqm == botanical
    assert iqm['severity'] == 'avoid' and iqm['materiality'] == 'presence'
    assert iqm['evidence_level'] == _verified('DSI_ANTIHYP_LICORICE')['evidence_level']
    assert EMA_LICORICE in iqm['sources']
    assert iqm['clinical_review']['file'] == REVIEW_FILE
    text = _rule_text(iqm)
    assert 'dgl' in text and 'does not say' in text, 'unknown preparation is not assumed to be DGL'
    assert 'does not apply to dgl' not in text and 'is unaffected' not in text
    assert 'discontinue' not in text and 'monitor blood pressure and review' not in text
    import re
    assert not re.search(r'\bsafe\b', text)
    assert pge.evaluate_profile_gate(iqm['profile_gate'], {'drug_classes': ['antihypertensives']}, {},
                                     base_severity='avoid').fires


def test_licorice_with_cardiac_glycosides_is_avoid_from_the_ema_monograph():
    import profile_gate_evaluator as pge

    pair = _pairs()['DSI_CARDIACGLYC_LICORICE']
    assert (pair['type'], pair['agent1_id'], pair['agent2_id'], pair['severity']) == (
        'Med-Sup', 'class:cardiac_glycosides', 'C0086555', 'Major')
    assert {EMA_LICORICE, LANOXIN} <= set(pair['source_urls'])
    assert '28660884' in pair['source_pmids']
    sub = _sub('RULE_IQM_LICORICE_HYPERTENSION', 'cardiac_glycosides')
    assert sub['severity'] == 'avoid' and sub['materiality'] == 'presence'
    assert sub.get('min_effective_dose') is None
    assert {EMA_LICORICE, LANOXIN} <= set(sub['sources'])
    assert sub['clinical_review']['file'] == REVIEW_FILE
    assert sub['evidence_level'] == _verified('DSI_CARDIACGLYC_LICORICE')['evidence_level']
    # No glycyrrhizin floor: no tier, amount or "small amounts" reassurance for this pair.
    rule = _rules()['RULE_IQM_LICORICE_HYPERTENSION']
    assert not [t for t in rule.get('dose_thresholds') or [] if t.get('target_id') == 'cardiac_glycosides']
    for text in (_rule_text(sub), _pair_text(pair)):
        assert ' mg' not in text and 'small amount' not in text
        assert 'dgl' in text and 'does not say' in text
    assert pge.evaluate_profile_gate(sub['profile_gate'], {'drug_classes': ['cardiac_glycosides']}, {},
                                     base_severity='avoid').fires


def test_glycyrrhizin_licorice_identities_reach_both_warnings_and_verified_dgl_does_not():
    from identity.interaction import interaction_subject_ids

    assert interaction_subject_ids('chinese_licorice') == ['chinese_licorice', 'licorice']
    for canonical_id, source_db in (('licorice', 'ingredient_quality_map'),
                                    ('licorice_root', 'botanical_ingredients'),
                                    ('chinese_licorice', 'botanical_ingredients')):
        hits = _licorice_alerts(canonical_id, source_db)['RULE_IQM_LICORICE_HYPERTENSION']
        assert hits['antihypertensives'] == 'avoid' and hits['cardiac_glycosides'] == 'avoid', canonical_id
    assert _licorice_alerts('dgl_deglycyrrhizinated_licorice', 'botanical_ingredients') == {}
    # A bare species name is not a DGL claim: only labels that state the preparation route to DGL.
    botanicals = json.loads((DATA / 'botanical_ingredients.json').read_text())['botanical_ingredients']
    dgl = next(b for b in botanicals if b['id'] == 'dgl_deglycyrrhizinated_licorice')
    assert 'glycyrrhiza glabra' not in {a.lower() for a in dgl['aliases']}


def test_levodopa_iron_is_caution_from_the_carbidopa_levodopa_label():
    import re

    pair = _pairs()['DSI_LEVODOPA_IRON']
    assert (pair['type'], pair['agent1_id'], pair['agent2_id'], pair['severity']) == (
        'Med-Sup', '6375', 'C0302583', 'Moderate')
    assert SINEMET in pair['source_urls']
    # Levodopa's ingredient RxCUI also reaches inhaled levodopa, so its own label (section 7.3) is cited too.
    assert INBRIJA in pair['source_urls']
    text = _pair_text(pair)
    assert 'chelate' in text and 'inbrija' in text
    # The labels name iron salts, including multivitamins that contain them; covering every iron form is ours.
    assert 'says this applies to iron supplements' not in text
    assert 'labels name iron salts' in text and 'as a precaution' in text
    # The label gives no spacing interval, so the record states none.
    assert not re.search(r'\b(\d+|one|two|three|four|six)\s*(hours?|hrs?|h)\b', text)
    normalized = _verified('DSI_LEVODOPA_IRON')
    assert normalized['agent2_canonical_id'] == 'iron'
    assert normalized['evidence_level'] == 'established'


def test_curated_supplement_canonical_ids_are_the_ones_verification_ships():
    """verify_interactions.py derives a supplement side's canonical id from its CUI and ignores the
    stored one, so a stored id that differs misstates which products the pair reaches."""
    from identity.interaction import normalize_interaction_canonical_id as norm

    def ids(row, stored):
        out = []
        for side in ('agent1', 'agent2'):
            value = row.get(f'{side}_canonical_id')
            if stored and value is None and str(row[f'{side}_id']).startswith('ref:'):
                value = str(row[f'{side}_id']).removeprefix('ref:')  # the verifier's reference fallback
            out.append(norm(value) or '')
        return sorted(out)

    drifted = {}
    for pair_id, row in _pairs().items():
        shipped = _verified(pair_id, row)
        if shipped is not None and ids(row, True) != ids(shipped, False):
            drifted[pair_id] = (ids(row, True), ids(shipped, False))
    assert drifted == {}


def test_enricher_user_alerts_honor_the_profile_gate():
    """The enricher's user-alert path must apply each hit's profile_gate.
    A DOAC user (anticoagulants + doacs) must not get the warfarin-only
    fallback row; a warfarin user gets the VKA row (CodeRabbit on #448)."""
    import sys
    sys.path.insert(0, str(DATA.parent))
    from enrich_supplements_v3 import SupplementEnricherV3
    owner = SupplementEnricherV3.__new__(SupplementEnricherV3)
    owner.unit_converter = None
    owner.databases = {name: json.loads((DATA / (name + '.json')).read_text()) for name in ('clinical_risk_taxonomy', 'ingredient_quality_map', 'botanical_ingredients', 'other_ingredients')}
    rule = _rules()['RULE_INGREDIENT_GLUCOSAMINE']
    owner.databases['ingredient_interaction_rules'] = {'interaction_rules': [rule]}
    canonical = rule['subject_ref']['canonical_id']
    ingredient = {'name': canonical, 'canonical_id': canonical, 'canonical_source_db': rule['subject_ref']['db'], 'quantity': 100, 'unit': 'mg'}
    product = {'ingredient_quality_data': {'ingredients': [ingredient]}, 'servingSizes': [{'minDailyServings': 1, 'maxDailyServings': 1}]}

    def alerts(drug_classes):
        profile = owner._collect_interaction_profile(product, user_profile={'drug_classes': drug_classes})
        return [a['drug_class_id'] for a in profile['user_condition_alerts']['alerts'] if a['type'] == 'drug_class']

    assert alerts(['anticoagulants', 'doacs']) == []
    assert alerts(['anticoagulants', 'vitamin_k_antagonists']) == ['vitamin_k_antagonists']
    assert alerts(['anticoagulants']) == ['anticoagulants']


def test_enricher_user_alert_gates_derive_flags_from_conditions():
    """A checked condition supplies the profile flag the taxonomy derives from it
    (surgery_scheduled, pregnant, breastfeeding, trying_to_conceive), so a gate
    requiring that flag still fires. A user-selectable flag is never derived:
    "immunocompromised" alone does not mean "severely immunocompromised"
    (CodeRabbit on #448)."""
    import sys
    sys.path.insert(0, str(DATA.parent))
    from enrich_supplements_v3 import SupplementEnricherV3
    owner = SupplementEnricherV3.__new__(SupplementEnricherV3)
    owner.unit_converter = None
    owner.databases = {name: json.loads((DATA / (name + '.json')).read_text()) for name in ('clinical_risk_taxonomy', 'ingredient_quality_map', 'botanical_ingredients', 'other_ingredients')}

    def alerts(rule_id, conditions, flags=None):
        rule = _rules()[rule_id]
        owner.databases['ingredient_interaction_rules'] = {'interaction_rules': [rule]}
        canonical = rule['subject_ref']['canonical_id']
        ingredient = {'name': canonical, 'canonical_id': canonical, 'canonical_source_db': rule['subject_ref']['db'], 'quantity': 100, 'unit': 'mg'}
        product = {'ingredient_quality_data': {'ingredients': [ingredient]}, 'servingSizes': [{'minDailyServings': 1, 'maxDailyServings': 1}]}
        user_profile = {'conditions': conditions, **({'profile_flags': flags} if flags else {})}
        profile = owner._collect_interaction_profile(product, user_profile=user_profile)
        return sorted({a['condition_id'] for a in profile['user_condition_alerts']['alerts'] if a['type'] == 'condition'})

    assert alerts('RULE_INGREDIENT_GARLIC', ['surgery_scheduled']) == ['surgery_scheduled']
    assert alerts('RULE_INGREDIENT_ST_JOHNS_WORT', ['lactation']) == ['lactation']
    assert alerts('RULE_IQM_PROBIOTICS_IMMUNOCOMPROMISED', ['immunocompromised']) == []
    assert alerts('RULE_IQM_PROBIOTICS_IMMUNOCOMPROMISED', ['immunocompromised'], ['severely_immunocompromised']) == ['immunocompromised']


FLUOROQUINOLONE_ZINC_SPACING = {
    # pair id: (RxCUI, label interval). Dr. Pham, A12 (2026-11-11); each label read 2026-11-11.
    'DSI_ZINC_CIPROFLOXACIN': ('2551', 'at least 2 hours before or 6 hours after'),
    'DSI_ZINC_LEVOFLOXACIN': ('82122', 'at least 2 hours before or 2 hours after'),
    'DSI_ZINC_MOXIFLOXACIN': ('139462', 'at least 4 hours before or 8 hours after'),
}


def test_zinc_fluoroquinolone_spacing_follows_each_antibiotic_label():
    """A12: caution with drug-specific spacing; direction matters and injected forms are not affected."""
    pairs = _pairs()
    for pair_id, (rxcui, interval) in FLUOROQUINOLONE_ZINC_SPACING.items():
        pair = pairs[pair_id]
        assert (pair['agent1_id'], pair['agent2_canonical_id'], pair['severity']) == (rxcui, 'zinc', 'Moderate'), pair_id
        assert interval in pair['management'], pair_id
        assert 'injected' in pair['management'].lower(), pair_id
        others = [i for _, i in FLUOROQUINOLONE_ZINC_SPACING.values() if i != interval]
        assert not any(i in pair['management'] for i in others), pair_id
    fallback = pairs['DSI_ZINC_FLUOROQUINOLONE']
    assert fallback['severity'] == 'Moderate'
    assert 'differs by drug' in fallback['management']
    assert not any(i in fallback['management'] for _, i in FLUOROQUINOLONE_ZINC_SPACING.values())


def test_calcium_ciprofloxacin_separates_supplements_from_calcium_in_a_meal():
    """A13: caution with the label's spacing; dairy or fortified juice alone differs from those foods in a meal."""
    pair = _pairs()['DSI_CALCIUM_CIPROFLOXACIN']
    text = pair['management'].lower()
    assert pair['severity'] == 'Moderate'
    assert 'at least 2 hours before or 6 hours after' in text
    assert 'calcium-fortified juice' in text and 'on their own' in text and 'meal' in text
    assert 'injected' in text


# Dr. Pham's signed answers, 2026-11-12 (DR_PHAM_ANSWERS_20261112.md Part A), batch 1: serotonergic harmonization.
ANSWERS_FILE = 'audits/clinical_review_20261111/DR_PHAM_ANSWERS_20261112.md'
NARDIL = 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=513a41d0-37d4-4355-8a6d-a2c643bce6fa'
EMSAM = 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b891bd9f-fdb8-4862-89c5-ecdd700398a3'
HEALTH_CANADA_5HTP = 'https://webprod.hc-sc.gc.ca/nhpid-bdipsn/atReq?atid=5htp&lang=eng'
ZOLOFT = 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=fda754f6-d0f3-4dce-a17a-927d64f912f7'
RASAGILINE_LABEL = 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=68cef20f-10c0-475e-af95-b7799355c7e9'
XADAGO = 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=c4d65f28-983f-42b4-bb23-023ae0fe81b2'
SAME_ACTION = "Do not add SAMe while taking an MAOI without your prescriber's approval."


def test_same_with_maois_is_avoid_by_class_and_contraindicated_only_where_a_label_supports_it():
    """Q1: tranylcypromine names SAM-e; phenelzine through its serotonergic-agent category; other MAOIs avoid."""
    pairs = _pairs()
    exact = pairs['DSI_TRANYLCYPROMINE_SAME']
    assert (exact['agent1_id'], exact['severity']) == ('10734', 'Contraindicated') and PARNATE in exact['source_urls']
    phenelzine = pairs['DSI_PHENELZINE_SAME']
    assert (phenelzine['agent1_id'], phenelzine['agent2_id'], phenelzine['severity']) == ('8123', 'C0036002', 'Contraindicated')
    assert NARDIL in phenelzine['source_urls'] and phenelzine['applies_to'] == 'specific_drug'
    text = _pair_text(phenelzine)
    # The label prohibits serotonergic agents as a category and does not name SAMe; the record says so.
    assert 'does not name samE'.lower() in text and 'interpretation' in text
    # The class pair now matches the class profile rule: one avoid, no Contraindicated/avoid split.
    cls, rule = pairs['DSI_MAOI_SAME'], _same_rule()
    assert cls['severity'] == 'Major' and APP_SEVERITY[cls['severity']] == rule['severity'] == 'avoid'
    for copy in (cls['management'], rule['action']):
        assert SAME_ACTION in copy
        assert 'Do not stop or switch' in copy
    assert 'Do not combine SAMe with an MAOI' not in cls['management']
    # The consumer-facing fields name the exact contraindications, not only the mechanism.
    rule_copy = ' '.join(rule[k] for k in ('action', 'alert_headline', 'alert_body')).lower()
    assert 'tranylcypromine' in rule_copy and 'phenelzine' in rule_copy and 'emsam' in rule_copy
    # EMSAM is not told apart by this class record; the record says why without claiming the app cannot match it.
    assert 'cannot be told apart' not in cls['evidence_notes'] and 'keyed on the MAOI class' in cls['evidence_notes']
    assert 'unless cleared' not in rule_copy and rule['informational_note']
    # Exported text says where the class-wide scope is an inference.
    assert 'class inference' in cls['mechanism'].lower() and 'class inference' in rule['mechanism'].lower()
    # The pending-question wording is gone from every record.
    for blob in (json.dumps(cls), json.dumps(rule), json.dumps(phenelzine)):
        assert 'ask 1' not in blob and 'pending' not in blob.lower()
    assert rule['clinical_review'] == {**rule['clinical_review'], 'reviewer': 'Dr. Pham', 'reviewed_at': '2026-11-12',
                                       'file': ANSWERS_FILE}
    assert phenelzine['verification']['notes'].count(ANSWERS_FILE) == 1


def test_5htp_with_ssris_and_snris_is_contraindicated_on_both_surfaces_from_the_health_canada_monograph():
    """Section 2: DSI_SSRI_5HTP was Major while the SSRI/SNRI rule was contraindicated."""
    pairs = _pairs()
    pair = pairs['DSI_SSRI_5HTP']
    rule = _sub('RULE_IQM_5HTP_SEROTONIN', 'antidepressants_ssri_snri')
    assert pair['agent1_id'] == 'class:antidepressants_ssri_snri'
    assert APP_SEVERITY[pair['severity']] == rule['severity'] == 'contraindicated'
    for sources in (pair['source_urls'], rule['sources']):
        assert HEALTH_CANADA_5HTP in sources
    # The source's jurisdiction and scope are recorded with the evidence.
    assert 'Health Canada' in pair['evidence_notes'] and 'jurisdiction' in pair['evidence_notes'].lower()
    assert 'antidepressants' in pair['evidence_notes']
    # Widening the pair from SSRIs to SSRIs and SNRIs drops no SSRI user.
    classes = json.loads((DATA / 'drug_classes.json').read_text())['classes']
    assert set(classes['class:ssris']['member_rxcuis']) <= set(classes[pair['agent1_id']]['member_rxcuis'])
    assert _verified('DSI_SSRI_5HTP')['evidence_level'] == rule['evidence_level']
    # No self-managed washout on any 5-HTP antidepressant record.
    maoi_rule = _sub('RULE_IQM_5HTP_SEROTONIN', 'maois')
    for copy in (rule['action'], maoi_rule['action'], pair['management'], pairs['DSI_MAOI_5HTP']['management']):
        assert 'observe a washout' not in copy and 'Allow appropriate washout' not in copy
        assert 'prescriber' in copy
    maoi_pair = pairs['DSI_MAOI_5HTP']
    assert HEALTH_CANADA_5HTP in maoi_pair['source_urls']
    assert 'universally contraindicated' not in maoi_pair.get('evidence_notes', '')
    # Contraindicated on both MAOI records, and both tell the user not to combine (no review-and-proceed wording).
    assert APP_SEVERITY[maoi_pair['severity']] == maoi_rule['severity'] == 'contraindicated'
    for copy in (maoi_pair['management'], maoi_rule['action']):
        assert copy.startswith('Do not take 5-HTP with an MAOI') or copy.startswith('Do not combine 5-HTP with MAOIs')
        assert 'without the prescriber reviewing' not in copy
    # Oral selegiline (Parkinson's disease) inherits the antidepressant contraindication only by class.
    assert 'oral selegiline' in maoi_pair['evidence_notes'] and 'class inference' in maoi_pair['evidence_notes']


def test_st_johns_wort_with_ssris_and_snris_is_avoid_on_both_surfaces_without_a_washout():
    """Section 2: avoid generally; no SSRI/SNRI label checked contraindicates it; no universal washout."""
    pair = _pairs()['DSI_SSRI_SJW']
    rule = _sub('RULE_INGREDIENT_ST_JOHNS_WORT', 'antidepressants_ssri_snri')
    assert pair['agent1_id'] == 'class:antidepressants_ssri_snri'
    assert APP_SEVERITY[pair['severity']] == rule['severity'] == 'avoid'
    assert ZOLOFT in pair['source_urls'] and ZOLOFT in rule['sources']
    assert _verified('DSI_SSRI_SJW')['evidence_level'] == rule['evidence_level']
    consumer = (pair['mechanism'] + ' ' + pair['management']).lower()
    for copy in (consumer, _rule_text(rule)):
        assert 'emergency' in copy and 'serotonin syndrome' in copy
        assert 'half-lives' not in copy and '14 days' not in copy and 'washout' not in copy
    assert 'Do not combine' not in rule['alert_headline']
    # The alert body alone also conveys how serious serotonin syndrome can be.
    assert 'life-threatening' in rule['alert_body']
    assert rule['clinical_review']['file'] == ANSWERS_FILE


def test_rasagiline_and_safinamide_get_their_label_st_johns_wort_contraindication_and_no_other_maoi_rule():
    """Part B 3D: exact coverage from each label; no blanket MAO-B membership in the MAOI class."""
    pairs = _pairs()
    classes = json.loads((DATA / 'drug_classes.json').read_text())['classes']
    for pair_id, rxcui, label in (('DSI_RASAGILINE_SJW', '134748', RASAGILINE_LABEL),
                                  ('DSI_SAFINAMIDE_SJW', '1922448', XADAGO)):
        pair = pairs[pair_id]
        assert (pair['agent1_id'], pair['agent2_canonical_id'], pair['severity']) == (rxcui, 'st_johns_wort', 'Contraindicated')
        assert label in pair['source_urls'] and pair['applies_to'] == 'specific_drug'
        assert _verified(pair_id)['evidence_level'] == 'established'
        assert not [cid for cid, c in classes.items() if rxcui in c['member_rxcuis']], pair_id
def test_batch8_unknown_kidney_function_requires_review_without_blanket_avoid():
    for ident in ('RULE_IQM_MAGNESIUM_HYPERTENSION', 'RULE_IQM_POTASSIUM_HYPERTENSION'):
        row = next(r for r in _rules()[ident]['condition_rules'] if r['condition_id'] == 'kidney_disease')
        assert row['severity'] == 'caution'
        assert 'before' in row['action'].lower()
        assert row['profile_gate']['dose'] is None
        assert row.get('min_effective_dose') is None
        assert row['direction'] == 'harmful'
    potassium = _rules()['RULE_IQM_POTASSIUM_HYPERTENSION']
    assert next(r for r in potassium['drug_class_rules'] if r['drug_class_id'] == 'potassium_sparing_diuretics')['severity'] == 'avoid'


def test_batch8_unproven_zinc_and_theanine_interactions_are_neutral_information():
    for ident, target in [('RULE_IQM_ZINC', 'thyroid_medications'), ('RULE_IQM_L_THEANINE_ANTIHYPERTENSIVES', 'antihypertensives')]:
        row = next(r for r in _rules()[ident]['drug_class_rules'] if r['drug_class_id'] == target)
        assert (row['severity'], row['direction'], row['evidence_level']) == ('informational', 'neutral', 'theoretical')
        assert row['profile_gate']['dose'] is None
        assert row.get('min_effective_dose') is None
    # The established antibiotic interaction is a different concern.
    assert next(r for r in _rules()['RULE_IQM_ZINC']['drug_class_rules'] if r['drug_class_id'] == 'fluoroquinolones')['severity'] == 'caution'


def test_batch8_vitamin_d_does_not_claim_class_wide_bleeding_or_a_dose_boundary():
    rule = _rules()['RULE_INGREDIENT_VITAMIN_D']
    rows = [r for r in rule['drug_class_rules'] if r['drug_class_id'] != 'thiazide_diuretics']
    assert len(rows) == 1
    row = rows[0]
    assert row['drug_class_id'] == 'vitamin_k_antagonists'
    assert row['severity'] == 'informational' and row['direction'] == 'neutral'
    assert 'warfarin' in row['alert_body'].lower() and 'deficiency' in row['alert_body'].lower()
    text = json.dumps(row).lower()
    for wrong in ('8983860', '10,000', 'mild antiplatelet', 'shared metabolic pathways'):
        assert wrong not in text
    assert row['profile_gate']['dose'] is None
    assert row['profile_gate']['requires']['drug_classes_any'] == ['vitamin_k_antagonists']
