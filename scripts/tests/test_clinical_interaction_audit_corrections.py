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
    for name in ('curated_interactions_v1.json', 'med_med_pairs_v1.json'):
        for row in json.loads((DATA / 'curated_interactions' / name).read_text())['interactions']:
            out[row['id']] = row
    return out


def _pair_text(row):
    return ' '.join(row.get(k) or '' for k in ('mechanism', 'management', 'evidence_notes')).lower()


def _same_rule():
    return next(r for r in _rules()['RULE_IQM_SAME']['drug_class_rules'] if r['drug_class_id'] == 'maois')


def test_same_contraindication_is_exact_for_tranylcypromine_and_inferred_for_other_maois():
    pairs = _pairs()
    exact = pairs['DSI_TRANYLCYPROMINE_SAME']
    assert (exact['agent1_id'], exact['agent2_id'], exact['severity']) == ('10734', 'C0036002', 'Contraindicated')
    assert PARNATE in exact['source_urls']
    # No MAOI warning is lowered while ask 1 is pending, and the exported text says the scope is inferred.
    cls = pairs['DSI_MAOI_SAME']
    assert cls['severity'] == 'Contraindicated'
    assert 'class inference' in cls['mechanism'].lower()
    # The profile rule keeps its published avoid for the MAOI class: a contraindicated profile rule is
    # hidden from people without a matching profile until G4, which would drop SAMe's conditional note.
    rule = _same_rule()
    assert rule['severity'] == 'avoid' and rule['informational_note']
    copy = ' '.join(rule[k] for k in ('action', 'alert_headline', 'alert_body')).lower()
    assert 'tranylcypromine' in copy and 'unless cleared' not in copy
    assert 'class inference' in rule['mechanism'].lower()
    assert rule['clinical_review']['file'] == REVIEW_FILE and 'ask 1' in rule['clinical_review']['notes']


def _verified(pair_id):
    """The pair as verify_interactions.py emits it for the build (evidence tier and canonical ids recomputed)."""
    import sys
    sys.path.insert(0, str(DATA.parent / 'api_audit'))
    import verify_interactions as vi

    def load(name):
        return json.loads((DATA / name).read_text(encoding='utf-8'))

    index = vi.build_iqm_cui_index(
        load('ingredient_quality_map.json'), botanicals=load('botanical_ingredients.json'),
        banned_recalled=load('banned_recalled_ingredients.json'),
        harmful_additives=load('harmful_additives.json'), other_ingredients=load('other_ingredients.json'))
    ctx = vi.VerifyContext(iqm_cui_index=index, drug_classes=load('drug_classes.json'))
    return vi.verify_entry(dict(_pairs()[pair_id]), ctx, vi.VerificationReport())


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
    ('DSI_WAR_GINGER', 'RULE_IQM_GINGER_BLEEDING', 'anticoagulants', 'caution', False),
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
        assert sub['clinical_review']['file'] == REVIEW_FILE, rule_id
        if drug_class != 'anticoagulants':
            continue
        fires = {
            name: pge.evaluate_profile_gate(sub['profile_gate'], profile, {}, base_severity=severity).fires
            for name, profile in (('warfarin', warfarin), ('unknown', unknown_blood_thinner), ('doac', apixaban))
        }
        # Warfarin-specific evidence never reaches a DOAC user; an unknown blood thinner still gets it.
        assert fires == {'warfarin': True, 'unknown': True, 'doac': not warfarin_only}, rule_id


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
