"""Source-grounded identity and warning regressions from the clinical audit."""
import json
from pathlib import Path
import pytest

DATA = Path(__file__).resolve().parents[1] / 'data' / 'banned_recalled_ingredients.json'

def entries():
    return {row['id']: row for row in json.loads(DATA.read_text())['ingredients']}

def test_butylene_glycol_is_not_a_specific_14_butanediol_alias():
    row = entries()['BANNED_14_BUTANEDIOL']
    assert 'butylene glycol' not in row['aliases']
    assert '1,4-butylene glycol' in row['aliases']
    assert row['clinical_risk_enum'] == 'critical'

def test_ssri_class_is_not_an_exact_fluoxetine_alias():
    row = entries()['SPIKE_FLUOXETINE']
    assert 'SSRI antidepressant' not in row['aliases']
    assert 'fluoxetine' in row['aliases']

def test_metformin_warning_retains_principal_risk_and_context():
    row = entries()['ADULTERANT_METFORMIN']
    assert 'lactic acidosis' in row['safety_warning'].lower()
    assert 'low blood sugar with other diabetes drugs' in row['safety_warning'].lower()
    assert 'stop the supplement' in row['safety_warning'].lower()
    assert 'does not apply to prescribed metformin' in row['safety_warning'].lower()
    assert row['clinical_risk_enum'] == 'critical'

def test_hidden_dexamethasone_requires_supervised_discontinuation():
    row = entries()['SPIKE_DEXAMETHASONE']
    assert 'abrupt stopping after prolonged use' in row['safety_warning'].lower()
    assert 'suppress adrenal function' in row['safety_warning'].lower()
    assert 'consult a clinician immediately for safe discontinuation' in row['safety_warning'].lower()
    assert 'before stopping' in row['safety_warning_one_liner'].lower()
    assert row['clinical_risk_enum'] == 'critical'

def test_rimonabant_suspension_and_withdrawal_are_distinct():
    row = entries()['ADULTERANT_RIMONABANT']
    assert '2009' in row['reason']
    assert any(ref.get('url') == 'https://www.ema.europa.eu/en/medicines/human/EPAR/acomplia' for ref in row['references_structured'])

def matcher():
    from enrich_supplements_v3 import SupplementEnricherV3
    e=SupplementEnricherV3.__new__(SupplementEnricherV3)
    e.databases={'banned_recalled_ingredients':json.loads(DATA.read_text()),'banned_match_allowlist':{'allowlist':[],'denylist':[]}}
    for key in ['_safe_token_alias_cache','_low_precision_token_alias_cache','_regex_pattern_cache','_token_bounded_pattern_cache','_short_acronym_alias_cache','_hyphen_space_pattern_cache']:
        setattr(e,key,{})
    return e


def test_analogue_names_do_not_also_claim_the_parent_drug():
    e=matcher()
    cases=[('amino tadalafil','SPIKE_AMINOTADALAFIL','SPIKE_TADALAFIL'),('chloro-tadalafil','SPIKE_CHLOROPRETADALAFIL','SPIKE_TADALAFIL'),('propoxyphenyl sildenafil','SPIKE_PROPOXYPHENYLSILDENAFIL','SPIKE_SILDENAFIL')]
    for name,analogue,parent in cases:
        result=e._check_banned_substances([{'name':name,'standardName':name}])
        ids={r['banned_id'] for r in result['substances']}
        assert analogue in ids
        assert parent not in ids
    result=e._check_banned_substances([{'name':n,'standardName':n} for n in ['amino tadalafil','tadalafil']])
    ids={r['banned_id'] for r in result['substances']}
    assert {'SPIKE_AMINOTADALAFIL','SPIKE_TADALAFIL'} <= ids


def test_analogue_copy_does_not_invent_comparative_activity_or_detection_intent():
    for key in ['SPIKE_AMINOTADALAFIL','SPIKE_CHLOROPRETADALAFIL','SPIKE_PROPOXYPHENYLSILDENAFIL','RECALLED_DEEP']:
        row=entries()[key]
        text=' '.join(row.get(k,'') for k in ['reason','safety_warning','safety_warning_one_liner']).lower()
        assert 'evad' not in text
        assert 'equivalent' not in text
        assert row['clinical_risk_enum'] == 'critical'

def test_source_scope_is_not_reversed_or_categorical_absence():
    rows=entries()
    assert 'synthetic pyrrolidone' not in rows['BANNED_SUNIFIRAM']['reason']
    assert 'piperazine' in rows['BANNED_SUNIFIRAM']['reason']
    assert 'no completed human trials' not in rows['PEPTIDE_BPC157']['reason'].lower()
    assert 'only in animal' not in rows['PEPTIDE_BPC157']['safety_warning'].lower()
    assert 'two' in rows['PEPTIDE_BPC157']['reason'].lower()
    assert 'there are no human data' not in rows['SARM_CARDARINE']['reason'].lower()
    assert '12-week' in rows['SARM_CARDARINE']['reason'].lower()
    assert 'group 1 for methylmercury' not in rows['HM_MERCURY']['reason'].lower()
    assert 'methylmercury compounds as group 2b' in rows['HM_MERCURY']['reason'].lower()
    assert 'oral-cavity tumors in rats' in rows['HM_CHROMIUM_HEXAVALENT']['reason'].lower()
    assert 'small-intestine tumors in mice' in rows['HM_CHROMIUM_HEXAVALENT']['reason'].lower()
    assert 'at all times' in rows['BANNED_HIGENAMINE']['reason'].lower()
    assert rows['SPIKE_METHOCARBAMOL']['references_structured'][0]['date']=='2026-02-26'


def test_orange_b_current_revocation_is_not_a_new_cancer_finding():
    row = entries()['BANNED_ADD_ORANGE_B']
    assert row['regulatory_date'] == '2026-09-08'
    assert 'abandoned' in row['reason']
    assert 'Potential carcinogen' not in row['reason']
    assert 'FDA-approved only' not in row['safety_warning']


def test_class_rows_do_not_use_single_member_unii_or_unrelated_aliases():
    rows = entries()
    assert not rows['BANNED_ADD_PHTHALATES']['external_ids'].get('unii')
    assert 'plasticizers' not in rows['BANNED_ADD_PHTHALATES']['aliases']
    assert not rows['BANNED_ADD_SYNTHETIC_ESTROGENS']['external_ids'].get('unii')
    assert 'synthetic hormone' not in rows['BANNED_ADD_SYNTHETIC_ESTROGENS']['aliases']


def test_delta8_reports_are_attributed_to_the_correct_surveillance_system():
    reason = entries()['BANNED_DELTA8_THC']['reason']
    assert '104' in reason and '2,362' in reason
    assert 'over 2,000 adverse event reports' not in reason


def test_dhea_does_not_attribute_leflunomide_livertox_to_dhea():
    row = entries()['BANNED_DHEA']
    assert 'LiverTox lists DHEA' not in row['reason']
    assert all(ref.get('title') != 'LiverTox: DHEA' for ref in row['references_structured'])


@pytest.mark.parametrize('key', ['BANNED_METHYLDIAZINOL', 'BANNED_DIMETHANDROSTENOL', 'BANNED_NORETHANDRIOL'])
def test_steroid_warnings_preserve_supervised_discontinuation(key):
    row = entries()[key]
    assert 'immediately' in row['safety_warning'].lower()
    assert 'withdrawal' in row['safety_warning'].lower()
    assert 'before stopping' in row['safety_warning_one_liner'].lower()
    assert 'stop using' not in row['safety_warning_one_liner'].lower()


@pytest.mark.parametrize('name,wrong_id', [
    ('laxogenin', 'ADD_5A_HYDROXY_LAXOGENIN'),
    ('3,3-diiodothyronine', 'ADD_DIIODOTHYRONINE_T2'),
    ('stool softener', 'ADD_DOCUSATE_SODIUM'),
    ('docusate calcium', 'ADD_DOCUSATE_SODIUM'),
    ('flour improver', 'BANNED_ADD_POTASSIUM_BROMATE'),
    ('dough conditioner', 'BANNED_ADD_POTASSIUM_BROMATE'),
    ('phytocannabinoids', 'BANNED_CBD_US'),
    ('Hemp Aerial Parts Extract', 'BANNED_CBD_US'),
])
def test_generic_roles_other_chemicals_and_hemp_do_not_become_specific_banned_identity(name, wrong_id):
    result = matcher()._check_banned_substances([{'name': name, 'standardName': name}])
    assert wrong_id not in {r['banned_id'] for r in result['substances']}


def test_laxogenin_derivative_copy_is_synthetic_and_dod_scope():
    row = entries()['ADD_5A_HYDROXY_LAXOGENIN']
    assert 'synthetic' in row['reason'].lower()
    assert 'steroidal plant compound' not in row['safety_warning'].lower()
    assert 'wada prohibited class' not in row['reason'].lower()


def test_cannabis_exception_is_not_product_hemp_percentage():
    row = entries()['WADA_CANNABIS']
    wada = next(j for j in row['jurisdictions'] if j['jurisdiction_code'] == 'WADA')
    assert '0.3%' not in wada['source']['citation']
    assert 'cannabidiol' in wada['source']['citation'].lower()


@pytest.mark.parametrize('key', ['HM_ARSENIC', 'HM_CADMIUM', 'HM_LEAD', 'HM_MERCURY'])
def test_metals_have_no_unsourced_universal_fda_daily_ban(key):
    row = entries()[key]
    federal = [j for j in row['jurisdictions'] if j['jurisdiction_code'] == 'US']
    assert all('FDA limit:' not in j['source']['citation'] for j in federal)
    assert all(j['status'] != 'banned' for j in row['jurisdictions'] if j['jurisdiction_code'] in {'IARC', 'WHO', 'USP'})
    assert row['clinical_risk_enum'] in {'high', 'critical'}


def test_lead_safe_harbor_is_not_a_maximum_intake():
    row = entries()['HM_LEAD']
    assert 'maximum daily intake' not in row['reason'].lower()
    ref = row['references_structured'][0]
    assert 'MADL' in ref['title'] and 'NSRL' in ref['title'] and '15' in ref['title']


def test_talc_current_reference_matches_group_2a():
    ref = entries()['BANNED_ADD_TALC']['references_structured'][1]
    assert '136' in ref['title']
    assert 'carcinogenicity_2b' not in ref['supports_claims']


def test_eu_additive_transition_dates_do_not_invent_earlier_bans():
    titanium = entries()['BANNED_ADD_TITANIUM_DIOXIDE']
    assert 'minimum durability' in titanium['reason']
    propyl = entries()['BANNED_ADD_PROPYLPARABEN']
    assert propyl['jurisdictions'][0]['effective_date'] == '2008-08-15'
    assert 'eur-lex' in propyl['references_structured'][0]['url']


def test_bitter_orange_events_are_not_attributed_as_proven_single_ingredient_causation():
    row = entries()['BANNED_BITTER_ORANGE']
    assert 'unclear' in row['reason'].lower()
    assert 'has caused' not in row['reason'].lower()
    assert 'routinely exceed' not in row['reason'].lower()


def test_ginkgo_review_title_and_label_limit_do_not_imply_bad_purity():
    row = entries()['CONTAM_GINKGOLIC_ACID']
    assert 'Multifaceted' in row['references_structured'][0]['title']
    assert 'alone' in row['reason'].lower()
    assert 'suggests an under-purified' not in row['safety_warning'].lower()


def test_recalled_collagen_retains_both_fish_and_egg_allergen_hazards():
    row=entries()['RECALLED_DIVIDED_SUNSET_COLLAGEN_PEPTIDES']
    for field in ['reason','safety_warning','safety_warning_one_liner']:
        assert 'fish' in row[field].lower() and 'egg' in row[field].lower()
    assert 'parenthetical' in row['reason'].lower()
    assert row['match_mode']=='historical'


def test_mybladder_exact_lot_and_source_specific_infection_scope():
    row=entries()['RECALLED_PURITY_PRODUCTS_MY_BLADDER']
    assert row['recall_scope']['lots']==['030425176']
    assert '1303' in row['reason']
    assert 'treatment-resistant' not in row['reason']
    assert 'company' in row['reason'].lower()


@pytest.mark.parametrize('key,date',[('RECALLED_RHEUMACARE_CAPSULES','2025-12-22'),('RECALLED_SILINTAN','2025-10-20'),('RECALLED_GREEN_LUMBER','2025-08-28')])
def test_recall_initiation_is_distinct_from_publication(key,date):
    row=entries()[key]
    assert row['regulatory_date']==date
    assert 'initiation' in row['regulatory_date_label'].lower()
    assert row['recall_scope']['lots']


@pytest.mark.parametrize('key',['RECALLED_OXYELITE_PRO','RECALLED_RHEUMACARE_CAPSULES','RECALLED_MR7_SUPER_700000'])
def test_product_recall_does_not_claim_permanent_ban_or_state_statute(key):
    row=entries()[key]
    assert all(j['status']=='recalled' and j['source']['type']=='fda_recall' for j in row['jurisdictions'])
    assert row['status']=='recalled'


def test_modern_warrior_warning_retains_tianeptine():
    row=entries()['RECALLED_MODERN_WARRIOR']
    assert 'tianeptine' in row['safety_warning'].lower()
    assert '2022' in str(row['recall_scope']) and '2025' in str(row['recall_scope'])


def test_rosabella_complete_lots_and_live_it_up_stickpacks_preserve_historical_policy():
    row=entries()['RECALLED_ROSABELLA_MORINGA']
    assert len(row['recall_scope']['lots'])==52
    assert any('5100048' in lot and '11/2027' in lot for lot in row['recall_scope']['lots'])
    assert row['match_mode']=='historical'
    live=entries()['RECALLED_LIVE_IT_UP_SUPER_GREENS']
    assert 'stick' in str(live['recall_scope']).lower()
    assert live['match_mode']=='historical'


def test_contaminated_glp1_general_guidance_is_not_a_named_recall_or_all_injection():
    row=entries()['BANNED_CONTAMINATED_GLP1']
    assert row['regulatory_date'] is None
    assert 'oral' in row['reason'].lower()
    assert all(j['status']=='clinical_advisory' and j['source']['type']=='fda_advisory' for j in row['jurisdictions'])
    assert 'Class II Recalls' not in row['references_structured'][1]['title']
    assert row['clinical_risk_enum']=='critical'


def test_fluoride_scientific_source_is_not_a_statutory_ban():
    row=entries()['BANNED_PEDIATRIC_FLUORIDE']
    assert row['regulatory_date']=='2025-05-13'
    assert 'three' in row['jurisdictions'][0]['source']['citation']
    assert all(j['status']!='banned' and j['source']['type']!='state_statute' for j in row['jurisdictions'])
    assert row['status']=='watchlist'


def test_titan_warning_is_warning_letter_not_recall():
    row=entries()['RECALLED_TITAN_SARMS_LLC']
    assert 'recalled' not in row['safety_warning'].lower()
    assert 'research' in row['recall_scope']['note'].lower()


def test_ykarine_event_does_not_prove_an_individual_stroke_mechanism():
    row=entries()['RECALLED_GE_LABS_YKARINE']
    assert 'erythrocytosis' not in row['reason'].lower()
    assert 'advisory' in row['recall_scope']['note'].lower()
    assert 'scheduleiii' in row['reason'].lower().replace(' ','')


def test_nasal_recall_contamination_is_formulation_specific():
    row=entries()['RECALLED_REBOOST_CLEARLIFE_NASAL_SPRAY']
    assert 'may' in row['reason'].lower()
    assert 'company' in row['reason'].lower()
    assert row['recall_scope']['lots']


def test_metal_fragment_source_is_canadian_specific_recall():
    row=entries()['BANNED_METAL_FIBERS']
    assert row['jurisdictions'][0]['jurisdiction_code']=='CA'
    assert row['jurisdictions'][0]['status']=='recalled'
    assert 'accumulation' not in row['safety_warning'].lower()
    assert row['clinical_risk_enum']=='critical'


def test_garcinia_australian_warning_is_not_a_blanket_ban():
    row=entries()['RISK_GARCINIA_CAMBOGIA']
    assert next(j for j in row['jurisdictions'] if j['jurisdiction_code']=='AU')['status']=='restricted'
    assert row['clinical_risk_enum']=='high'


@pytest.mark.parametrize('key',['HIGH_RISK_CHAPARRAL','HIGH_RISK_GERMANDER','HIGH_RISK_PENNYROYAL','RISK_BITTER_ORANGE','RISK_KAVA','RISK_YOHIMBE'])
def test_high_risk_advisory_is_not_a_contradictory_legal_ban(key):
    row=entries()[key]
    j=row['jurisdictions'][0]
    assert j['status']=='under_review'
    assert row['status']=='high_risk'


def test_foreign_jurisdiction_names_do_not_apply_as_us_bans():
    rows=entries()
    for key in ['HIGH_RISK_PENNYROYAL','HIGH_RISK_GERMANDER','RISK_KAVA']:
        for j in rows[key]['jurisdictions']:
            if j.get('name') in ['UK','Germany','France','Switzerland']:
                assert j['jurisdiction_code'] == {'UK':'GB','Germany':'DE','France':'FR','Switzerland':'CH'}[j['name']]
                assert j['status']=='under_review'


def test_lobeline_cessation_review_is_the_actual_review_and_scoped_outcome():
    row=entries()['RISK_LOBELIA']
    ref=row['references_structured'][1]
    assert '22336780' in ref['url']
    assert '24373424' not in str(ref)
    assert 'any indication' not in row['reason'].lower()
    assert 'long-term' in ref['evidence_summary'].lower()


def test_hydroxy_laxogenin_acetate_does_not_inherit_free_compound_identity():
    e = matcher()
    key = 'ADD_5A_HYDROXY_LAXOGENIN'
    for name in ['5a-hydroxy laxogenin acetate', '5-alpha hydroxy laxogenin acetate']:
        result = e._check_banned_substances([{'name': name, 'standardName': name}])
        assert key not in {row['banned_id'] for row in result['substances']}
    for name in ['5a-hydroxy laxogenin', '5-alpha hydroxy laxogenin']:
        result = e._check_banned_substances([{'name': name, 'standardName': name}])
        assert key in {row['banned_id'] for row in result['substances']}
    row = entries()[key]
    assert row['external_ids']['unii'] == '844KE20WT5'
    assert row['clinical_risk_enum'] == 'high'
    assert 'not' in row['notes'].lower() and 'safety' in row['notes'].lower()
