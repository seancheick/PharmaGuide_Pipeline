"""Signed G1 consolidation and source applicability regressions."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'data'


def rules():
    return {r['id']: r for r in json.loads((DATA / 'ingredient_interaction_rules.json').read_text())['interaction_rules']}


def test_omega_forms_share_monitor_payload_without_universal_cutoff():
    rows = rules()
    ids = ['RULE_INGREDIENT_OMEGA_3', 'RULE_INGREDIENT_FISH_OIL', 'RULE_IQM_DHA_BLEEDING', 'RULE_IQM_EPA_BLEEDING']
    for cls in ['anticoagulants', 'antiplatelets']:
        found = [next(x for x in rows[i]['drug_class_rules'] if x['drug_class_id'] == cls) for i in ids]
        for x in found:
            assert x['severity'] == 'monitor'
            assert x['min_effective_dose'] is None
            assert '3 g' not in x['alert_body']
        for key in ['alert_headline', 'alert_body', 'mechanism', 'action', 'informational_note', 'sources', 'profile_gate', 'direction', 'materiality']:
            assert all(x[key] == found[0][key] for x in found)
    pairs = json.loads((DATA / 'curated_interactions/curated_interactions_v1.json').read_text())['interactions']
    assert next(x for x in pairs if x['id'] == 'DSI_WAR_OMEGA3')['severity'] == 'Minor'


def test_calcium_iron_thyroid_payload_groups_and_preserves_spacing():
    found = [next(x for x in rules()[i]['drug_class_rules'] if x['drug_class_id'] == 'thyroid_medications') for i in ['RULE_IQM_CALCIUM', 'RULE_IQM_IRON_HYPERTENSION']]
    for key in ['alert_headline', 'alert_body', 'mechanism', 'action', 'informational_note', 'sources', 'profile_gate', 'direction', 'materiality']:
        assert found[0][key] == found[1][key]
    assert '4 hours' in found[0]['alert_body']
    assert found[0]['severity'] == 'caution'


def test_nicotinamide_not_given_nicotinic_acid_glucose_warning():
    rule = rules()['RULE_IQM_NIACIN_DIABETES']
    rows = [x for x in rule['condition_rules'] if x['condition_id'] == 'diabetes'] + [x for x in rule['drug_class_rules'] if x['drug_class_id'].startswith('hypoglycemics')]
    for x in rows:
        assert 'niacinamide' in x['profile_gate']['excludes']['nutrient_forms_any']
        assert 'nicotinic acid' in x['alert_body']


def test_chromium_does_not_invent_four_hour_interval():
    row = next(x for x in rules()['RULE_IQM_CHROMIUM_PICOLINATE_THYROID']['drug_class_rules'] if x['drug_class_id'] == 'thyroid_medications')
    assert '4 hours' not in row['action']
    assert 'picolinate' in row['alert_body']
    assert 'several hours' in row['action']


def test_b6_does_not_claim_proven_prolactin_suppression_or_gate():
    r = rules()['RULE_IQM_VITAMIN_B6_LACTATION']
    row = next(x for x in r['condition_rules'] if x['condition_id'] == 'lactation')
    assert 'do not trigger' not in row['alert_body']
    assert 'inconsistent' in r['pregnancy_lactation']['mechanism']
    assert 'dopaminergic' not in r['pregnancy_lactation']['mechanism']
    assert 'appropriate for anyone' not in json.dumps(r)


def test_green_tea_nadolol_scope_does_not_flag_other_beta_blockers():
    r = rules()['RULE_IQM_GREEN_TEA_HYPERTENSION']
    assert [x['drug_class_id'] for x in r['drug_class_rules']] == ['nadolol']
    row = r['drug_class_rules'][0]
    assert row['profile_gate']['requires']['drug_classes_any'] == ['nadolol']
    assert row['severity'] == 'avoid'
    classes = json.loads((DATA / 'drug_classes.json').read_text())['classes']
    assert classes['class:nadolol']['member_rxcuis'] == ['7226']
    assert 'nadolol' in [x['id'] for x in json.loads((DATA / 'clinical_risk_taxonomy.json').read_text())['drug_classes']]
    assert next(x for x in r['condition_rules'] if x['condition_id'] == 'hypertension')['severity'] == 'informational'


def test_known_niacinamide_suppressed_but_mixed_and_unknown_retained():
    from profile_gate_evaluator import evaluate_profile_gate
    r = rules()['RULE_IQM_NIACIN_DIABETES']
    row = next(x for x in r['condition_rules'] if x['condition_id'] == 'diabetes')
    for forms, expected in [(['niacinamide'], False), (['niacinamide', 'nicotinic acid'], True), ([], True)]:
        result = evaluate_profile_gate(row['profile_gate'], {'conditions': ['diabetes']}, {'nutrient_forms': forms}, base_severity=row['severity'])
        assert result.fires is expected


def test_nadolol_profile_gate_rejects_broad_beta_blocker_membership():
    from profile_gate_evaluator import evaluate_profile_gate
    row = rules()['RULE_IQM_GREEN_TEA_HYPERTENSION']['drug_class_rules'][0]
    for classes, expected in [(['nadolol', 'beta_blockers'], True), (['beta_blockers'], False), (['antihypertensives'], False)]:
        result = evaluate_profile_gate(row['profile_gate'], {'drug_classes': classes}, {}, base_severity=row['severity'])
        assert result.fires is expected


def test_niacin_unrelated_findings_keep_their_original_subjects():
    rule = rules()['RULE_IQM_NIACIN_DIABETES']
    rows = {x['condition_id']: x for x in rule['condition_rules']}
    assert 'hepatotoxicity' in rows['liver_disease']['mechanism']
    assert 'cardiovascular benefit' in rows['high_cholesterol']['mechanism']
    for ident in ['liver_disease', 'high_cholesterol']:
        assert rows[ident]['profile_gate']['excludes']['nutrient_forms_any'] == []
        assert 'blood glucose' not in rows[ident]['alert_body']


def test_chromium_thyroid_scope_keeps_unknown_and_mixed_forms():
    from enrich_supplements_v3 import SupplementEnricherV3
    enricher = SupplementEnricherV3()
    all_rules = rules()
    rule = all_rules['RULE_IQM_CHROMIUM_PICOLINATE_THYROID']
    glucose = all_rules['RULE_IQM_CHROMIUM_GLUCOSE']
    assert not any(x['drug_class_id'] == 'thyroid_medications' for x in glucose['drug_class_rules'])
    assert any(x['drug_class_id'].startswith('hypoglycemics') for x in glucose['drug_class_rules'])
    for forms, status, expected in [
        (['chromium picolinate'], 'mapped', True),
        (['chromium chloride'], 'mapped', False),
        (['chromium (unspecified)'], 'mapped', True),
        ([], 'unmapped', True),
        (['chromium chloride'], 'inferred', True),
        (['chromium chloride', 'chromium picolinate'], 'mapped', True),
    ]:
        row = {'form_match_status': status, 'matched_forms': [{'form_key': f} for f in forms]}
        assert enricher._interaction_rule_applies(rule, row) is expected
        assert enricher._interaction_rule_applies(glucose, row)
