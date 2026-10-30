"""Source assessments reach product context without inventing product hazards."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_build_final_db import make_enriched, make_scored
from build_final_db import build_detail_blob
from enrich_supplements_v3 import SupplementEnricherV3

@pytest.fixture(scope='module')
def enricher():
    return SupplementEnricherV3()

def test_detected_claims_survive_export_as_documented_list():
    e=make_enriched();e['evidence_data']={'clinical_matches':[], 'match_count':0,'unsubstantiated_claims':{'found':True,'claims':[{'type':'false FDA approval claim','severity':'critical'}]}}
    blob=build_detail_blob(e,make_scored())
    assert blob['evidence_data']['unsubstantiated_claims']==[{'type':'false FDA approval claim','severity':'critical'}]
    warnings=[w for w in blob['warnings'] if w['source']=='evidence_data']
    assert len(warnings)==1
    assert warnings[0]['display_mode_default']=='informational'
    assert 'label' in warnings[0]['detail'].lower()

def test_category_context_is_visible_but_not_a_product_contamination_finding():
    e=make_enriched();e['certification_data']={'category_contamination_risk':{'has_elevated_risk':True,'category':'weight_loss','severity_level':'high','concerns':['adulterants'],'note':'FDA has found hidden drugs in weight loss supplements'}}
    blob=build_detail_blob(e,make_scored())
    row=next(w for w in blob['warnings'] if w['source']=='category_contamination_risk')
    assert row['severity']=='informational'
    assert row['display_mode_default']=='informational'
    assert 'not a finding' in row['detail'].lower()
    assert row['source_urls']

def test_manufacturer_history_preserves_date_scope_and_source(enricher,monkeypatch):
    monkeypatch.setitem(enricher.databases,'manufacturer_violations',{'manufacturer_violations':[{'id':'VTEST','manufacturer':'Test Company','violation_type':'Warning Letter','date':'2024-01-01','is_resolved':True,'brand_trust_summary':'Historical manufacturing issue.','fda_source_url':'https://www.fda.gov/test-history','product':'Other product'}]})
    assessment=enricher._check_violations('Test Company','Test Company')
    e=make_enriched();e['manufacturer_data']={'violations':assessment}
    blob=build_detail_blob(e,make_scored());row=next(w for w in blob['warnings'] if w['source']=='manufacturer_violations')
    assert row['severity']=='informational'
    assert '2024-01-01' in row['detail']
    assert 'Other product' in row['detail']
    assert 'resolved' in row['detail'].lower()
    assert 'does not clear recalled units' in row['detail'].lower()
    assert 'product or lot' in row['detail'].lower()
    assert 'product-specific check' in row['detail'].lower()
    assert row['source_urls']==['https://www.fda.gov/test-history']

@pytest.mark.parametrize('text',['Not intended to treat cancer.','This product is not FDA approved.','Manufactured in an FDA approved facility.','No miracle claims are made.'])
def test_denied_or_facility_claims_do_not_become_disease_claims(enricher,text):
    assert enricher._check_unsubstantiated_claims(text)['found'] is False

@pytest.mark.parametrize('text',['Treats cancer.','FDA approved supplement.','Guaranteed results.','FDA approved supplement. Our facility is modern.','Not only treats cancer but also guarantees results.','No sugar and FDA approved supplement.'])
def test_positive_claims_are_detected(enricher,text):
    assert enricher._check_unsubstantiated_claims(text)['found'] is True

def test_metabolism_word_alone_is_not_a_weight_loss_category(enricher):
    assert not enricher._assess_category_contamination_risk({'product_name':'B12 for normal energy metabolism'})['has_elevated_risk']

@pytest.mark.parametrize('text', [
    'This product has not been FDA approved.',
    'Does not claim to treat cancer.',
    'This product is not, and has never been, FDA approved.',
    'This supplement is not intended to diagnose, treat, cure or prevent cancer.',
])
def test_standard_disclaimers_do_not_become_claims(enricher, text):
    assert not enricher._check_unsubstantiated_claims(text)['found']

def test_disclaimer_does_not_hide_separate_affirmative_claim(enricher):
    assert enricher._check_unsubstantiated_claims('Not intended to diagnose, treat, cure or prevent cancer. Treats diabetes.')['found']

def test_distinct_context_events_survive_full_export():
    e = make_enriched()
    e['manufacturer_data'] = {'violations': {'violations': [
        {'matched_manufacturer': 'Company', 'date': '2024-01-01', 'product': 'Product A', 'reason': 'Event A', 'fda_source_url': 'https://example.org/a'},
        {'matched_manufacturer': 'Company', 'date': '2025-01-01', 'product': 'Product B', 'reason': 'Event B', 'fda_source_url': 'https://example.org/b'},
    ]}}
    e['evidence_data'] = {'unsubstantiated_claims': {'found': True, 'claims': [
        {'type': 'disease treatment claim'}, {'type': 'false FDA approval claim'},
    ]}}
    rows = build_detail_blob(e, make_scored())['warnings']
    history = [r for r in rows if r['type'] == 'manufacturer_violation']
    claims = [r for r in rows if r['type'] == 'marketing_claim']
    assert len(history) == 2
    assert {u for r in history for u in r['source_urls']} == {'https://example.org/a', 'https://example.org/b'}
    assert len(claims) == 2

@pytest.mark.parametrize('recall_id', ['F-27XX', 'F-2XXX', 'F-XXXX'])
def test_placeholder_recall_identifiers_cannot_drive_history_or_penalties(enricher, monkeypatch, recall_id):
    monkeypatch.setitem(enricher.databases, 'manufacturer_violations', {'manufacturer_violations': [
        {'id': 'INVALID', 'manufacturer': 'Test Company', 'fda_recall_id': recall_id, 'reason': 'Unverified recall', 'total_deduction_applied': -10},
        {'id': 'VALID', 'manufacturer': 'Test Company', 'fda_recall_id': 'F-1234-2024', 'reason': 'Synthetic valid-format control', 'total_deduction_applied': -2},
    ]})
    assessment = enricher._check_violations('Test Company', 'Test Company')
    assert [r['violation_id'] for r in assessment['violations']] == ['VALID']
    assert assessment['total_deduction_applied'] == -2

def test_one_recall_event_is_not_charged_twice(enricher, monkeypatch):
    row = {'manufacturer': 'Test Company', 'fda_recall_id': 'H-0647-2026', 'reason': 'Synthetic duplicate-event control', 'total_deduction_applied': -3}
    monkeypatch.setitem(enricher.databases, 'manufacturer_violations', {'manufacturer_violations': [dict(row, id='FIRST'), dict(row, id='SECOND')]})
    result = enricher._check_violations('Test Company', 'Test Company')
    assert len(result['violations']) == 1
    assert result['total_deduction_applied'] == -3

def test_source_supported_recall_without_enforcement_number_is_retained(enricher, monkeypatch):
    monkeypatch.setitem(enricher.databases, 'manufacturer_violations', {'manufacturer_violations': [
        {'id': 'V037', 'manufacturer': 'Natural Dior LLC', 'fda_recall_id': None, 'fda_source_url': 'https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/natural-dior-llc-issues-voluntary-nationwide-recall-vitafer-l-gold-liquid-due-presence-undeclared', 'reason': 'Undeclared tadalafil', 'total_deduction_applied': -9},
    ]})
    result = enricher._check_violations('Natural Dior LLC', 'Natural Dior LLC')
    assert result['violations'][0]['violation_id'] == 'V037'
    assert result['total_deduction_applied'] == -9

def test_real_siluetaya_event_keeps_lot_scope_without_duplicate_deduction(enricher):
    event_rows = [row for row in enricher.databases['manufacturer_violations']['manufacturer_violations']
                  if row.get('fda_recall_id') == 'H-0647-2026']
    assert len(event_rows) == 2  # curated and openFDA records of the same event
    assert len({row['total_deduction_applied'] for row in event_rows}) == 1
    assessment = enricher._check_violations('SiluetaYa', 'Siluetaya, LLC')
    assert len(assessment['violations']) == 1
    assert assessment['total_deduction_applied'] == event_rows[0]['total_deduction_applied']
    assert 'US1220' in assessment['violations'][0]['product']
    assert '7500464462411' in assessment['violations'][0]['product']
    assert '06/2027' in assessment['violations'][0]['product']

@pytest.mark.parametrize('recall_id', [None, 'N/A', 'F-2856'])
def test_uncitable_history_cannot_drive_assessment(enricher, monkeypatch, recall_id):
    monkeypatch.setitem(enricher.databases, 'manufacturer_violations', {'manufacturer_violations': [
        {'id': 'UNSOURCED', 'manufacturer': 'Test Company', 'fda_recall_id': recall_id, 'reason': 'Uncorroborated history', 'total_deduction_applied': -10},
        {'id': 'SOURCED', 'manufacturer': 'Test Company', 'fda_recall_id': None, 'fda_source_url': 'https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/test-fixture', 'reason': 'Synthetic source-link control', 'total_deduction_applied': -2},
    ]})
    result = enricher._check_violations('Test Company', 'Test Company')
    assert [v['violation_id'] for v in result['violations']] == ['SOURCED']
    assert result['total_deduction_applied'] == -2


def test_source_corrected_manufacturer_history_does_not_repeat_disproved_claims(enricher):
    rows = {r['id']: r for r in enricher.databases['manufacturer_violations']['manufacturer_violations']}
    assert rows['V051']['deaths_reported'] == 0
    assert '2 deaths' not in str(rows['V051']).lower()
    assert rows['V066']['violation_type'] == 'Class II Recall'
    assert rows['V011']['violation_type'] == 'Class II Recall'
    assert rows['V015']['violation_type'] == 'Class II Recall'
    assert rows['V026']['is_resolved'] is True
    assert rows['V062']['date'] == '2025-06-25'
    assert rows['V039']['fda_recall_id'] == 'D-0397-2026'
    assert rows['V042']['fda_recall_id'] == 'H-0302-2026'


def test_resolution_and_scope_are_not_inferred_from_old_event(enricher):
    rows = {r['id']: r for r in enricher.databases['manufacturer_violations']['manufacturer_violations']}
    assert rows['V027']['is_resolved'] is False
    assert 'as supplements' not in rows['V055']['product'].lower()
    assert rows['V048']['cdc_outbreak_investigation'] is False
    assert rows['V053']['cdc_outbreak_investigation'] is False
