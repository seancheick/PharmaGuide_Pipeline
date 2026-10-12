"""Source-grounded pairwise corrections; thresholds never imply unverified safety.

Per-entry live-content receipts: presence_warning_audit_20261012 in the clinical audit.
"""
import json
from pathlib import Path

import pytest

from build_interaction_db import build_interaction_row
from api_audit.verify_interactions import normalize_severity

DATA = Path(__file__).resolve().parents[1] / 'data'
PAIRS = {
    row['id']: row
    for name in ('curated_interactions_v1.json', 'med_med_pairs_v1.json', 'batch_critical_2026_05.json')
    for row in json.loads((DATA / 'curated_interactions' / name).read_text())['interactions']
}
UNSUPPORTED_FLOORS = (
    'DSI_ANTICOAG_HORSE_CHESTNUT', 'DSI_ANTIHYP_VITD',
    'DSI_ANTIPSYCH_MELATONIN', 'DSI_BENZO_MELATONIN',
    'DSI_DM_ASHWAGANDHA', 'DSI_DM_GYMNEMA', 'DSI_FISHOIL_GINKGO',
    'DSI_FISHOIL_VITE', 'DSI_MELATONIN_VALERIAN', 'DSI_NSAID_FISHOIL',
    'DSI_NSAID_GINKGO', 'DSI_SEDATIVES_ASHWAGANDHA', 'DSI_SSRI_GINKGO',
    'DSI_DM_CHROMIUM', 'SSI_ZINC_COPPER',
)


@pytest.mark.parametrize('rule_id', UNSUPPORTED_FLOORS)
def test_studied_doses_and_unrelated_upper_limits_do_not_hide_pairwise_reviews(rule_id):
    pair = PAIRS[rule_id]
    assert pair['materiality'] == 'presence'
    assert pair.get('dose_threshold') is None
    row = build_interaction_row(pair, rxcui_to_class={}, build_time='2026-10-12', interaction_db_version='audit')
    assert row['dose_dependent'] == 0
    assert row['dose_threshold_json'] is None
    assert row['management'] and row['severity']  # uncertainty does not silently remove the review


def test_opioid_warning_matches_opioids_instead_of_nonopioid_sleep_medicines():
    classes = json.loads((DATA / 'drug_classes.json').read_text())['classes']
    assert PAIRS['DDI_BENZO_OPIOID']['agent2_id'] == 'class:opioids'
    members = set(classes['class:opioids']['member_rxcuis'])
    assert {'7052', '4337', '7804', '5489', '2670', '6813', '1819', '10689'} <= members
    assert not members & {'6711', '39993', '1490468', '3289', '7533', '28863', '7242', '7309'}
    assert 'opioid use disorder' in PAIRS['DDI_BENZO_OPIOID']['management'].lower()


def test_statins_are_scoped_by_the_existing_membership_owner():
    classes = json.loads((DATA / 'drug_classes.json').read_text())['classes']
    flucon = PAIRS['DDI_FLUCONAZOLE_STATINS']['agent2_id']
    sjw = PAIRS['DSI_STATINS_SJW']['agent1_id']
    assert flucon == 'class:fluconazole_sensitive_statins'
    assert sjw == 'class:cyp3a4_metabolized_statins'
    assert set(classes[flucon]['member_rxcuis']) == {'83367', '36567', '6472', '41127'}
    assert set(classes[sjw]['member_rxcuis']) == {'83367', '36567', '6472'}
    assert '42463' not in classes[flucon]['member_rxcuis']  # pravastatin
    assert '301542' not in classes[sjw]['member_rxcuis']  # rosuvastatin


def test_cautionary_triptan_label_is_not_a_contraindication():
    pair = PAIRS['DDI_SSRI_TRIPTAN']
    assert normalize_severity(pair['severity']) == 'caution'
    assert pair['materiality'] == 'presence'
    assert '29482205' in pair['source_pmids']
    assert 'emergency' in pair['management'].lower()


def test_melatonin_antipsychotic_pair_uses_the_medicine_actually_studied():
    pair = PAIRS['DSI_ANTIPSYCH_MELATONIN']
    assert pair['agent1_id'] == '10502'  # live RxNorm IN: thioridazine
    assert pair['agent1_name'] == 'Thioridazine'
    assert pair['materiality'] == 'presence'


def test_unsafe_replacement_medication_and_patient_self_adjustment_are_removed():
    assert 'use morphine' not in PAIRS['DDI_MAOI_MEPERIDINE']['management'].lower()
    assert 'amoxicillin' not in PAIRS['DDI_MTX_TRIMETHOPRIM']['management'].lower()
    assert 'initiate leucovorin' not in PAIRS['DDI_MTX_TRIMETHOPRIM']['management'].lower()
    assert 'reduce lithium dose empirically' not in PAIRS['DDI_LITHIUM_THIAZIDE']['management'].lower()
    assert normalize_severity(PAIRS['DDI_MAOI_MEPERIDINE']['severity']) == 'contraindicated'


def test_contrast_copy_uses_label_risk_factors_and_clinician_directed_restart():
    text = PAIRS['DDI_METFORMIN_IVCONTRAST']['management'].lower()
    assert 'any procedure' not in text
    assert all(term in text for term in ('30', '60', 'liver', 'alcohol', 'heart failure', 'intra-arterial', '48', 'clinician'))


def test_warfarin_acetaminophen_copy_does_not_invent_a_safe_two_gram_boundary():
    pair = PAIRS['DDI_ANTICOAG_ACETAMINOPHEN']
    assert pair['agent1_id'] == '11289'
    text = (pair['mechanism'] + ' ' + pair['management']).lower()
    assert '2 g/day' in text and 'day 3' in text
    assert '≤2 g/day' not in text and '>2 g/day' not in text
    assert pair['materiality'] == 'presence'


def test_oral_bisphosphonate_timing_is_formulation_specific():
    text = PAIRS['DSI_MAGNESIUM_BISPHOSPHONATE']['management'].lower()
    assert 'delayed-release' in text and 'after breakfast' in text
    assert 'oral' in PAIRS['DSI_MAGNESIUM_BISPHOSPHONATE']['mechanism'].lower()
    assert 'different time' in text


def test_preclinical_kava_risk_is_not_reported_as_established_human_pair_risk():
    pair = PAIRS['SSI_KAVA_ACETAMINOPHEN']
    assert pair['evidence_basis'] == 'preclinical'
    assert pair['clinical_confidence'] == 'low'
    assert '21397479' in pair['source_pmids']
    assert 'human' in pair['mechanism'].lower()
    assert 'substantially increases risk' not in pair['mechanism'].lower()


def test_ghost_sources_are_not_kept_as_pair_support():
    assert not any('001508' in s for s in PAIRS['DSI_MAOI_TYRAMINE']['source_urls'])
    assert not any('000813' in s for s in PAIRS['DDI_BENZO_OPIOID']['source_urls'])
    assert '10801966' not in PAIRS['SSI_ZINC_COPPER'].get('source_pmids', [])
    assert '40198642' not in PAIRS['DSI_WAR_GINKGO'].get('source_pmids', [])
    assert '26958257' in PAIRS['DSI_WAR_GINKGO'].get('source_pmids', [])


def test_niacin_floor_has_actual_regulatory_provenance_and_no_coq10_speculation():
    pair = PAIRS['DSI_STATINS_NIACIN']
    assert pair['dose_threshold']['value'] == 1000
    assert 'dailymed.nlm.nih.gov' in pair['dose_threshold']['source']
    assert 'coq10' not in pair['mechanism'].lower()
    assert not any('CoQ10-HealthProfessional' in s for s in pair['source_urls'])


def test_disclosed_old_screening_gates_cannot_override_the_accepted_source_boundary_rule():
    for rule_id in ('SSI_ZINC_COPPER', 'DSI_DM_CHROMIUM'):
        pair = PAIRS[rule_id]
        assert pair['dose_threshold'] is None
        assert pair['materiality'] == 'presence'
        assert 'do not establish' in pair['management'].lower()


def test_label_contraindication_and_known_serious_controls_survive():
    assert normalize_severity(PAIRS['DDI_SIMVASTATIN_ERYTHROMYCIN']['severity']) == 'contraindicated'
    for rid in ('DDI_MAOI_SSRI', 'DDI_ERGOTAMINE_ERYTHROMYCIN', 'DSI_IMMUNO_SJW'):
        assert normalize_severity(PAIRS[rid]['severity']) == 'contraindicated'
        assert PAIRS[rid]['materiality'] == 'presence'


def test_approved_epo_retirement_removes_the_unsupported_pair():
    # PMID17764919 disputes the original seizure attribution; Sean approved
    # retirement on2026-10-12. Preserve this negative guard and serious controls.
    assert 'DSI_ANTICONV_EPO' not in PAIRS
