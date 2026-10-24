"""Machine source verification cannot promote animal/cell evidence to human trials."""
import json

import pytest

from api_audit import verify_literature_records as verifier


@pytest.mark.parametrize('abstract, mesh, expected', [
    ('Animals received supplementation for 28 days.', ['Animals', 'Mice'], False),
    ('Treatment improved experimental outcomes in rats.', ['animals'], False),
    ('Human blood-derived cells and human chondrosarcoma cells were tested in vitro.', ['Humans', 'Animals', 'Cells, Cultured'], False),
    ('This may benefit patients; experiments used rats.', ['Animals', 'Rats'], False),
    ('Thirty participants were enrolled in a randomized trial.', ['Humans'], True),
    ('Participants received supplementation.', ['Humans'], True),
    ('A randomized trial in adults.', [], False),
])
def test_verifier_requires_indexed_human_population(tmp_path, monkeypatch, abstract, mesh, expected):
    path = tmp_path / 'literature.json'
    title = 'Effects of melon extract'
    path.write_text(json.dumps({'_metadata': {}, 'literature_evidence_records': [{
        'canonical_id': 'melon', 'qualifying_human_studies': [{'pmid': '1', 'title': title}],
    }]}))
    monkeypatch.setattr(verifier, 'LITERATURE_RECORDS_PATH', path)
    monkeypatch.setattr(verifier, 'fetch_articles', lambda ids, **kwargs: {'1': {
        'title': title, 'abstract': abstract, 'mesh_terms': mesh,
    }})
    verifier.verify_literature_file(apply_fixes=True)
    record, = json.loads(path.read_text())['literature_evidence_records']
    study, = record['qualifying_human_studies']
    assert study['verification_provenance']['human_subjects_verified'] is expected
    if not expected:
        assert record['verification_result'] == 'verification_failure_unresolved'


@pytest.mark.parametrize('cid, pmid', [('boswellia_serrata_resin', '32565872'), ('superoxide_dismutase', '15742357')])
def test_retained_animal_citations_do_not_claim_human_verification(cid, pmid):
    payload = json.loads(verifier.LITERATURE_RECORDS_PATH.read_text())
    record = next(r for r in payload['literature_evidence_records'] if r['canonical_id'] == cid)
    study = next(s for s in record['qualifying_human_studies'] if s['pmid'] == pmid)
    assert study['verification_provenance']['human_subjects_verified'] is False
    assert study['scoring_eligible'] is False
    assert record['verification_result'] == 'verification_failure_unresolved'


def test_graviola_lab_source_remains_a_negative_safety_finding():
    payload = json.loads(verifier.LITERATURE_RECORDS_PATH.read_text())
    record = next(r for r in payload['literature_evidence_records'] if r['canonical_id'] == 'graviola')
    study, = record['qualifying_human_studies']
    assert study['verification_provenance']['human_subjects_verified'] is False
    assert record['effect_direction'] == 'negative'
    assert record['applicability_status'] == 'reviewed_null_evidence'
    assert 'toxic to cultured dopaminergic neurons' in record['applicability_decision']


def test_verifier_preserves_reviewed_nonhuman_negative_evidence(tmp_path, monkeypatch):
    payload = json.loads(verifier.LITERATURE_RECORDS_PATH.read_text())
    record = next(r for r in payload['literature_evidence_records'] if r['canonical_id'] == 'graviola')
    path = tmp_path / 'literature.json'
    path.write_text(json.dumps({'_metadata': {}, 'literature_evidence_records': [record]}))
    monkeypatch.setattr(verifier, 'LITERATURE_RECORDS_PATH', path)
    monkeypatch.setattr(verifier, 'fetch_articles', lambda ids, **kwargs: {'14521988': {
        'title': record['qualifying_human_studies'][0]['title'],
        'abstract': 'Annonacin killed cultured mesencephalic neurons.',
        'mesh_terms': ['Animals', 'Cells, Cultured'],
    }})
    verifier.verify_literature_file(apply_fixes=True)
    verified, = json.loads(path.read_text())['literature_evidence_records']
    assert verified['qualifying_human_studies'][0]['verification_provenance']['human_subjects_verified'] is False
    assert verified['verification_result'] == record['verification_result']
    assert verified['applicability_status'] == record['applicability_status']
    assert verified['effect_direction'] == record['effect_direction']


@pytest.fixture
def audit_source(tmp_path, monkeypatch):
    path = tmp_path / 'literature.json'
    path.write_text(json.dumps({'_metadata': {}, 'literature_evidence_records': [
        {'canonical_id': cid, 'qualifying_human_studies': [{'pmid': pmid, 'title': f'{cid} clinical outcomes'}]}
        for cid, pmid in [('melon', '1'), ('cherry', '2')]
    ]}))
    monkeypatch.setattr(verifier, 'LITERATURE_RECORDS_PATH', path)
    monkeypatch.setattr(verifier, 'fetch_articles', lambda ids, **kwargs: {
        p: {'title': f'{dict([( "1", "melon"), ("2", "cherry")])[p]} clinical outcomes',
            'abstract': 'Participants received treatment.', 'mesh_terms': ['Humans']}
        for p in ids
    })
    return path


def test_default_audit_never_changes_source(audit_source):
    before = audit_source.read_bytes()
    report = verifier.verify_literature_file()
    assert audit_source.read_bytes() == before
    assert report['mode'] == 'read_only'


def test_selected_records_and_unknown_ids_fail_closed(audit_source):
    report = verifier.verify_literature_file(record_ids={'melon'})
    assert report['records_checked'] == 1
    assert report['studies_checked'] == 1
    assert [r['canonical_id'] for r in report['records']] == ['melon']
    with pytest.raises(ValueError, match='Unknown'):
        verifier.verify_literature_file(record_ids={'typo'})


def test_cli_default_read_only_report_and_selection(audit_source, tmp_path):
    before = audit_source.read_bytes()
    report = tmp_path / 'report.json'
    assert verifier.main(['--record-id', 'melon', '--report', str(report)]) == 0
    assert audit_source.read_bytes() == before
    result = json.loads(report.read_text())
    assert result['records_checked'] == 1
    assert result['clinical_applicability_verified'] is False


def test_retracted_publication_type_blocks_verification(audit_source, monkeypatch):
    monkeypatch.setattr(verifier, 'fetch_articles', lambda ids, **kw: {
        '1': {'title': 'melon clinical outcomes', 'abstract': 'Melon effects.',
              'mesh_terms': ['Humans'], 'publication_types': ['Retracted Publication']}})
    report = verifier.verify_literature_file(record_ids={'melon'})
    assert report['retractions_count'] == 1


def test_unresolved_title_search_is_not_applied(audit_source, monkeypatch):
    before = audit_source.read_bytes()
    monkeypatch.setattr(verifier, 'fetch_articles', lambda ids, **kw: {})
    # No speculative title-search replacement is permitted.
    report = verifier.verify_literature_file(record_ids={'melon'})
    assert report['verification_failures_count'] > 0
    assert audit_source.read_bytes() == before


def test_empty_studies_are_not_verified(audit_source):
    data = json.loads(audit_source.read_text())
    data['literature_evidence_records'][0]['qualifying_human_studies'] = []
    audit_source.write_text(json.dumps(data))
    report = verifier.verify_literature_file(record_ids={'melon'})
    assert report['verification_failures_count'] == 1
    assert report['records'][0]['verification_result'] == 'verification_failure_unresolved'


def test_cli_missing_source_fails_and_protects_data(audit_source, monkeypatch):
    monkeypatch.setattr(verifier, 'fetch_articles', lambda *a, **kw: {})
    assert verifier.main(['--record-id', 'melon']) == 1
    before = audit_source.read_bytes()
    with pytest.raises(SystemExit):
        verifier.main(['--report', str(audit_source)])
    assert audit_source.read_bytes() == before


@pytest.mark.parametrize('flag', ['expression_of_concern', 'has_erratum'])
def test_source_notices_require_review(audit_source, monkeypatch, flag):
    monkeypatch.setattr(verifier, 'fetch_articles', lambda *a, **kw: {
        '1': {'title': 'melon clinical outcomes', 'abstract': 'Melon trial',
              'mesh_terms': ['Humans'], flag: True}})
    report = verifier.verify_literature_file(record_ids={'melon'})
    assert any(f['error'] == flag + '_requires_review' for f in report['failures'])
